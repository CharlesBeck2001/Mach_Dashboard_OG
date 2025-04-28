from flask import Flask, render_template, jsonify, request
import pandas as pd
import requests
from datetime import datetime, timedelta
from functools import lru_cache
import numpy as np
import traceback
import os

app = Flask(__name__)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response


# Constants
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://fzkeftdzgseugijplhsh.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'your_default_key')

# Time ranges
TIME_RANGES = {
    "all": None,
    "15": 15,  # Last Week
    "30": 30,  # Last Month
    "90": 90,  # Last 3 Months
    "180": 180 # Last 6 Months
}

# Cache for metrics
metrics_cache = {}

def execute_sql(query):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    rpc_endpoint = f"{SUPABASE_URL}/rest/v1/rpc/execute_sql"
    payload = {"query": query}
    
    response = requests.post(rpc_endpoint, headers=headers, json=payload)
    
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data)
        return df
    else:
        print("Error executing query:", response.status_code, response.json())
        return None

@lru_cache(maxsize=1)
def get_oldest_time():
    time_query = """
    SELECT MIN(op.block_timestamp) AS oldest_time
    FROM order_placed op
    INNER JOIN match_executed me
    ON op.order_uuid = me.order_uuid
    """
    time_point = execute_sql(time_query)
    time_point = pd.json_normalize(time_point['result'])
    return time_point['oldest_time'][0]

def get_metrics(start_date):
    query = f"""
    WITH user_stats AS (
        SELECT 
            user_address,
            COUNT(*) as trade_count
        FROM (
            SELECT sender_address as user_address
            FROM main_volume_table
            WHERE block_timestamp >= '{start_date}'
            UNION ALL
            SELECT maker_address as user_address
            FROM main_volume_table
            WHERE block_timestamp >= '{start_date}'
        ) all_users
        GROUP BY user_address
    ),
    volume_stats AS (
        SELECT 
            SUM(total_volume) as total_volume,
            COUNT(DISTINCT order_uuid) as trade_count,
            COUNT(DISTINCT CASE 
                WHEN block_timestamp >= NOW() - INTERVAL '24 hours' 
                THEN order_uuid 
            END) as last_day_trades,
            SUM(CASE 
                WHEN block_timestamp >= NOW() - INTERVAL '24 hours' 
                THEN total_volume 
                ELSE 0 
            END) as last_day_volume
        FROM main_volume_table
        WHERE block_timestamp >= '{start_date}'
    )
    SELECT 
        v.total_volume,
        COUNT(DISTINCT u.user_address) as total_users,
        v.trade_count,
        v.trade_count::float / COUNT(DISTINCT u.user_address) as average_trades,
        (SELECT COUNT(*) * 100.0 / NULLIF(COUNT(DISTINCT user_address), 0)
         FROM user_stats
         WHERE trade_count > 1) as perc_above,
        v.last_day_volume
    FROM volume_stats v
    CROSS JOIN user_stats u
    GROUP BY v.total_volume, v.trade_count, v.last_day_volume
    """
    
    result = execute_sql(query)
    if result is not None and 'result' in result and len(result['result']) > 0:
        metrics = result['result'][0]
        return {
            'total_volume': float(metrics['total_volume'] or 0),
            'total_users': int(metrics['total_users'] or 0),
            'trade_count': int(metrics['trade_count'] or 0),
            'average_trades': round(metrics['average_trades'] or 0),
            'perc_above': float(metrics['perc_above'] or 0),
            'last_day_v': float(metrics['last_day_volume'] or 0)
        }
    return create_default_metrics()

def get_assets():
    asset_query = """
    WITH source_volume_table AS (
        SELECT DISTINCT
            op.*, 
            ti.decimals AS source_decimal,
            cal.id AS source_id,
            cal.chain AS source_chain,
            cmd.current_price::FLOAT AS source_price,
            (cmd.current_price::FLOAT * op.source_quantity) / POWER(10, ti.decimals) AS source_volume
        FROM order_placed op
        INNER JOIN match_executed me
            ON op.order_uuid = me.order_uuid
        INNER JOIN token_info ti
            ON op.source_asset = ti.address
        INNER JOIN coingecko_assets_list cal
            ON op.source_asset = cal.address
        INNER JOIN coingecko_market_data cmd 
            ON cal.id = cmd.id
    ),
    dest_volume_table AS (
        SELECT DISTINCT
            op.*, 
            ti.decimals AS dest_decimal,
            cal.id AS dest_id,
            cal.chain AS dest_chain,
            cmd.current_price::FLOAT AS dest_price,
            (cmd.current_price::FLOAT * op.dest_quantity) / POWER(10, ti.decimals) AS dest_volume
        FROM order_placed op
        INNER JOIN match_executed me
            ON op.order_uuid = me.order_uuid
        INNER JOIN token_info ti
            ON op.dest_asset = ti.address
        INNER JOIN coingecko_assets_list cal
            ON op.dest_asset = cal.address
        INNER JOIN coingecko_market_data cmd 
            ON cal.id = cmd.id
    ),
    overall_volume_table_2 AS (
        SELECT DISTINCT
            svt.*,
            dvt.dest_id AS dest_id,
            dvt.dest_chain AS dest_chain,
            dvt.dest_decimal AS dest_decimal,
            dvt.dest_price AS dest_price,
            dvt.dest_volume AS dest_volume,
            (dvt.dest_volume + svt.source_volume) AS total_volume
        FROM source_volume_table svt
        INNER JOIN dest_volume_table dvt
            ON svt.order_uuid = dvt.order_uuid
    ),
    consolidated_volumes AS (
        SELECT
            id,
            SUM(volume) AS total_volume
        FROM (
            SELECT
                source_id AS id,
                SUM(source_volume) AS volume
            FROM overall_volume_table_2
            GROUP BY source_id
            UNION ALL
            SELECT
                dest_id AS id,
                SUM(dest_volume) AS volume
            FROM overall_volume_table_2
            GROUP BY dest_id
        ) combined
        GROUP BY id
    )
    SELECT id
    FROM consolidated_volumes
    ORDER BY total_volume DESC
    """
    
    asset_list = execute_sql(asset_query)
    return pd.json_normalize(asset_list['result'])['id'].tolist()

def get_assets_day():

    query = """
    WITH latest_date AS (
            SELECT DATE_TRUNC('day', MAX(block_timestamp)) AS max_date
            FROM main_volume_table
    ),
    consolidated_volumes AS (
        SELECT
            id,
            SUM(volume) AS total_volume
        FROM (
            SELECT
                source_id AS id,
                SUM(source_volume) AS volume
            FROM main_volume_table
            WHERE block_timestamp >= (
                SELECT max_date - INTERVAL '1 day' 
                FROM latest_date
            )
            AND block_timestamp < (
                SELECT max_date 
                FROM latest_date
            )     
            GROUP BY source_id
            UNION ALL
            SELECT
                dest_id AS id,
                SUM(dest_volume) AS volume
            FROM main_volume_table
            WHERE block_timestamp >= (
                SELECT max_date - INTERVAL '1 day' 
                FROM latest_date
            )
            AND block_timestamp < (
                SELECT max_date 
                FROM latest_date
            )     
            GROUP BY dest_id
        ) combined
        GROUP BY id
    )
    SELECT id
    FROM consolidated_volumes
    ORDER BY total_volume DESC
    """
    asset_list = execute_sql(query)
    asset_list = pd.json_normalize(asset_list['result'])['id'].tolist()
    asset_list = [asset for asset in asset_list if asset != ""]
    return asset_list


def get_weekly_volume(asset_id, start_date=None):
    if not start_date:
        start_date = get_oldest_time()
    
    query = f"""
    WITH RECURSIVE date_series AS (
        SELECT DATE_TRUNC('day', '{start_date}'::timestamp) AS day
        UNION ALL
        SELECT day + INTERVAL '1 day'
        FROM date_series
        WHERE day < CURRENT_DATE
    ),
    daily_volume_table AS (
        SELECT 
            DATE_TRUNC('day', block_timestamp) AS day,
            SUM(total_volume) AS daily_volume
        FROM main_volume_table
        WHERE block_timestamp >= '{start_date}'
        GROUP BY DATE_TRUNC('day', block_timestamp)
    ),
    filled_daily_volume_table AS (
        SELECT 
            ds.day,
            COALESCE(dv.daily_volume, 0) AS daily_volume,
            '{asset_id}' AS asset
        FROM date_series ds
        LEFT JOIN daily_volume_table dv
        ON ds.day = dv.day
    ),
    weekly_averaged_volume_table AS (
        SELECT 
            day,
            asset,
            AVG(daily_volume) OVER (
                ORDER BY day ROWS BETWEEN 3 PRECEDING AND 3 FOLLOWING
            ) AS weekly_avg_volume
        FROM filled_daily_volume_table
    )
    SELECT 
        TO_CHAR(day, 'FMMonth FMDD, YYYY') AS day,
        weekly_avg_volume AS total_weekly_avg_volume,
        asset
    FROM weekly_averaged_volume_table
    ORDER BY day
    """
    
    return pd.json_normalize(execute_sql(query)['result'])

def preload_metrics():
    """Preload metrics and chart data for all time ranges"""
    print("Preloading metrics...")
    
    try:
        # Initialize metrics cache
        metrics_cache = {}
        
        # Get oldest time for 'all' time range
        oldest_time = get_oldest_time()
        if oldest_time:
            metrics_cache['all'] = get_metrics(oldest_time)
        else:
            metrics_cache['all'] = create_default_metrics()

        # Get metrics for each specific time range
        current_time = datetime.now()
        time_ranges = ['15', '30', '90', '180']
        
        for days in time_ranges:
            try:
                days_int = int(days)
                start_date = (current_time - timedelta(days=days_int)).strftime('%Y-%m-%dT%H:%M:%S')
                metrics_cache[days] = get_metrics(start_date)
            except Exception as e:
                print(f"Error loading metrics for {days} days: {str(e)}")
                metrics_cache[days] = create_default_metrics()
        
        # Store in application context
        app.config['metrics_cache'] = metrics_cache
        print("Metrics preloaded successfully!")

    except Exception as e:
        print(f"Error in preload_metrics: {str(e)}")
        # Set default values if preloading fails
        app.config['metrics_cache'] = {
            'all': create_default_metrics(),
            '15': create_default_metrics(),
            '30': create_default_metrics(),
            '90': create_default_metrics(),
            '180': create_default_metrics()
        }

def create_default_metrics():
    """Create default metrics when data loading fails"""
    return {
        'total_volume': 0,
        'total_users': 0,
        'trade_count': 0,
        'average_trades': 0,
        'perc_above': 0,
        'last_day_v': 0
    }

def create_default_histogram():
    """Create default histogram data when loading fails"""
    return jsonify({
        'chains': [],
        'volumes': [],
        'assets': []
    }).get_json()

def create_default_sankey():
    """Create default sankey data when loading fails"""
    return jsonify({
        "top_asset_data": [],
        "top_chain_data": [],
        "top_pair_data": []
    }).get_json()

@app.route('/get_assets_day')
def get_assets_day():

    query = """
    WITH latest_date AS (
            SELECT DATE_TRUNC('day', MAX(block_timestamp)) AS max_date
            FROM main_volume_table
    ),
    consolidated_volumes AS (
        SELECT
            id,
            SUM(volume) AS total_volume
        FROM (
            SELECT
                source_id AS id,
                SUM(source_volume) AS volume
            FROM main_volume_table
            WHERE block_timestamp >= (
                SELECT max_date - INTERVAL '1 day' 
                FROM latest_date
            )
            AND block_timestamp < (
                SELECT max_date 
                FROM latest_date
            )     
            GROUP BY source_id
            UNION ALL
            SELECT
                dest_id AS id,
                SUM(dest_volume) AS volume
            FROM main_volume_table
            WHERE block_timestamp >= (
                SELECT max_date - INTERVAL '1 day' 
                FROM latest_date
            )
            AND block_timestamp < (
                SELECT max_date 
                FROM latest_date
            )     
            GROUP BY dest_id
        ) combined
        GROUP BY id
    )
    SELECT id
    FROM consolidated_volumes
    ORDER BY total_volume DESC
    """
    df = execute_sql(query)
    if df is not None and 'result' in df:
        asset_list = pd.json_normalize(df['result'])['id'].tolist()
        return jsonify({"assets": asset_list})  # Return a dictionary instead of a list
    return jsonify({"assets": []})  # Return empty list in a dictionary if no results


@app.route('/')
@app.route('/dashboard')
def dashboard():
    # Get metrics from cache or use defaults
    metrics_cache = app.config.get('metrics_cache', {})
    if 'all' not in metrics_cache:
        metrics_cache['all'] = create_default_metrics()
    
    return render_template('dashboard.html', metrics=metrics_cache['all'])

@app.route('/update_metrics')
def update_metrics():
    time_range = request.args.get('range', 'all')
    
    try:
        if time_range == 'all':
            start_date = get_oldest_time()
        else:
            days = int(time_range)
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
        
        # Get new metrics directly
        metrics = get_metrics(start_date)
        return jsonify(metrics)
        
    except Exception as e:
        print(f"Error in update_metrics: {str(e)}")
        return jsonify(create_default_metrics())

@app.route('/get_hourly_volume')
def get_hourly_volume():
    query = """
    WITH latest_date AS (
            SELECT DATE_TRUNC('day', MAX(created_at)) AS max_date
            FROM mm_order_placed
        ),
        source_volume_table AS (
            SELECT DISTINCT
                op.*, 
                ti.decimals AS source_decimal,
                cal.id AS source_id,
                cal.chain AS source_chain,
                cmd.current_price::FLOAT AS source_price,
                (cmd.current_price::FLOAT * op.src_amount) / POWER(10, ti.decimals) AS source_volume
            FROM mm_order_placed op
            INNER JOIN mm_match_executed me
                ON op.order_uuid = me.order_uuid
            INNER JOIN token_info ti
                ON op.src_asset_address = ti.address
            INNER JOIN coingecko_assets_list cal
                ON op.src_asset_address = cal.address
            INNER JOIN coingecko_market_data cmd 
                ON cal.id = cmd.id
            WHERE op.created_at >= (
                    SELECT max_date - INTERVAL '1 day' 
                    FROM latest_date
                )
              AND op.created_at < (
                    SELECT max_date 
                    FROM latest_date
                )
        ),
        overall_volume_table_2 AS (
            SELECT DISTINCT
                svt.*,
                2*svt.source_volume AS total_volume
            FROM source_volume_table svt
        )
        SELECT 
            TO_CHAR(DATE_TRUNC('hour', svt.created_at), 'HH12 AM') AS hour,
            COALESCE(SUM(svt.total_volume), 0) AS total_hourly_volume,
            'Total' AS asset
        FROM overall_volume_table_2 svt
        GROUP BY DATE_TRUNC('hour', svt.created_at)
        ORDER BY DATE_TRUNC('hour', svt.created_at)
        """

    query_2 = """
    WITH latest_date AS (
        SELECT DATE_TRUNC('day', MAX(block_timestamp)) AS max_date
        FROM main_volume_table
    )
    SELECT 
        TO_CHAR(DATE_TRUNC('hour', svt.block_timestamp), 'HH12 AM') AS hour,
        COALESCE(SUM(svt.total_volume), 0) AS total_hourly_volume,
        'Total' AS asset
    FROM main_volume_table svt
    WHERE svt.block_timestamp >= (
        SELECT max_date - INTERVAL '1 day' 
        FROM latest_date
    )
    AND svt.block_timestamp < (
        SELECT max_date 
        FROM latest_date
    )
    GROUP BY DATE_TRUNC('hour', svt.block_timestamp)
    ORDER BY DATE_TRUNC('hour', svt.block_timestamp)
    """

    query_3 = f"""
    SELECT 
        TO_CHAR(DATE_TRUNC('hour', svt.block_timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'America/New_York'), 'HH12 AM') AS hour,
        COALESCE(SUM(svt.total_volume), 0) AS total_hourly_volume,
        'Total' AS asset
    FROM main_volume_table svt
    WHERE svt.block_timestamp >= (
            NOW() AT TIME ZONE 'UTC' AT TIME ZONE 'America/New_York' - INTERVAL '24 hours'
        )
    AND svt.block_timestamp < (NOW() AT TIME ZONE 'UTC' AT TIME ZONE 'America/New_York')
    GROUP BY DATE_TRUNC('hour', svt.block_timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'America/New_York')
    ORDER BY DATE_TRUNC('hour', svt.block_timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'America/New_York')
    """
    
    df = execute_sql(query_3)
    if df is not None and 'result' in df:
        return jsonify(pd.json_normalize(df['result']).to_dict(orient='records'))
    return jsonify([])  # Return empty array if no data

@app.route('/get_weekly_volume')
def get_weekly_volume():
    today = datetime.now()
    date = today - timedelta(days=7)
    date = date.strftime('%Y-%m-%dT%H:%M:%S')
    
    query = f"""
        WITH source_volume_table AS (
            SELECT DISTINCT
                op.*, 
                ti.decimals AS source_decimal,
                cal.id AS source_id,
                cal.chain AS source_chain,
                cmd.current_price::FLOAT AS source_price,
                (cmd.current_price::FLOAT * op.source_quantity) / POWER(10, ti.decimals) AS source_volume
            FROM order_placed op
            INNER JOIN match_executed me
                ON op.order_uuid = me.order_uuid
            INNER JOIN token_info ti
                ON op.source_asset = ti.address
            INNER JOIN coingecko_assets_list cal
                ON op.source_asset = cal.address
            INNER JOIN coingecko_market_data cmd 
                ON cal.id = cmd.id
        ),
        dest_volume_table AS (
            SELECT DISTINCT
                op.*, 
                ti.decimals AS dest_decimal,
                cal.id AS dest_id,
                cal.chain AS dest_chain,
                cmd.current_price::FLOAT AS dest_price,
                (cmd.current_price::FLOAT * op.dest_quantity) / POWER(10, ti.decimals) AS dest_volume
            FROM order_placed op
            INNER JOIN match_executed me
                ON op.order_uuid = me.order_uuid
            INNER JOIN token_info ti
                ON op.dest_asset = ti.address
            INNER JOIN coingecko_assets_list cal
                ON op.dest_asset = cal.address
            INNER JOIN coingecko_market_data cmd 
                ON cal.id = cmd.id
        ),
        overall_volume_table_2 AS (
            SELECT DISTINCT
                svt.order_uuid AS order_id,
                (dvt.dest_volume + svt.source_volume) AS total_volume,
                svt.block_timestamp AS date,
                svt.source_id AS source_asset,
                dvt.dest_id AS dest_asset
            FROM source_volume_table svt
            INNER JOIN dest_volume_table dvt
                ON svt.order_uuid = dvt.order_uuid
        ),
        source_volume_table_3 AS (
            SELECT DISTINCT
                op.*, 
                ti.decimals AS source_decimal,
                cal.id AS source_id,
                cal.chain AS source_chain,
                cmd.current_price::FLOAT AS source_price,
                (cmd.current_price::FLOAT * op.src_amount) / POWER(10, ti.decimals) AS source_volume
            FROM mm_order_placed op
            INNER JOIN mm_match_executed me
                ON op.order_uuid = me.order_uuid
            INNER JOIN token_info ti
                ON op.src_asset_address = ti.address
            INNER JOIN coingecko_assets_list cal
                ON op.src_asset_address = cal.address
            INNER JOIN coingecko_market_data cmd 
                ON cal.id = cmd.id
        ),
        overall_volume_table_3 AS (
            SELECT DISTINCT
                svt.order_uuid AS order_id,
                2*svt.source_volume AS total_volume,
                svt.created_at AS date,
                svt.source_id AS source_asset,
                '' AS dest_asset
            FROM source_volume_table_3 svt
        ),
        combined_volume_table AS (
            SELECT DISTINCT
                * 
            FROM overall_volume_table_2
            UNION
            SELECT DISTINCT
                * 
            FROM overall_volume_table_3
        )
        SELECT 
            TO_CHAR(DATE_TRUNC('day', svt.date), 'FMMonth FMDD, YYYY') AS day,
            COALESCE(SUM(svt.total_volume), 0) AS total_daily_volume,
            'Total' AS asset
        FROM combined_volume_table svt
        GROUP BY DATE_TRUNC('day', svt.date)
        ORDER BY DATE_TRUNC('day', svt.date)
        """
    
    query_2 = f"""
        SELECT 
            TO_CHAR(DATE_TRUNC('day', svt.block_timestamp), 'FMMonth FMDD, YYYY') AS day,
            COALESCE(SUM(svt.total_volume), 0) AS total_daily_volume,
            'Total' AS asset
        FROM main_volume_table svt
        GROUP BY DATE_TRUNC('day', svt.block_timestamp)
        ORDER BY DATE_TRUNC('day', svt.block_timestamp)
        """
    
    print("Executing weekly volume query")  # Debug print
    df = execute_sql(query_2)
    if df is not None and 'result' in df:
        df = pd.json_normalize(df['result'])
        #print("Before date filter:", df)  # Debug print
        df = df[pd.to_datetime(df['day']) > pd.to_datetime(date)]
        #print("After date filter:", df)  # Debug print
        return jsonify(df.to_dict(orient='records'))
    return jsonify([])


#@app.route('/get_weekly_volume_by_asset/<asset_id>')
#def get_weekly_volume_by_asset(asset_id):
    # New function for individual asset volumes
    today = datetime.now()
    date = today - timedelta(days=7)
    date = date.strftime('%Y-%m-%dT%H:%M:%S')
    
    query = f"""
    WITH source_volume_table AS (
        SELECT DISTINCT
            op.*, 
            ti.decimals AS source_decimal,
            cal.id AS source_id,
            cal.chain AS source_chain,
            cmd.current_price::FLOAT AS source_price,
            (cmd.current_price::FLOAT * op.source_quantity) / POWER(10, ti.decimals) AS source_volume
        FROM order_placed op
        INNER JOIN match_executed me
            ON op.order_uuid = me.order_uuid
        INNER JOIN token_info ti
            ON op.source_asset = ti.address
        INNER JOIN coingecko_assets_list cal
            ON op.source_asset = cal.address
        INNER JOIN coingecko_market_data cmd 
            ON cal.id = cmd.id
        WHERE cal.id = '{asset_id}'
    ),
    dest_volume_table AS (
        SELECT DISTINCT
            op.*, 
            ti.decimals AS dest_decimal,
            cal.id AS dest_id,
            cal.chain AS dest_chain,
            cmd.current_price::FLOAT AS dest_price,
            (cmd.current_price::FLOAT * op.dest_quantity) / POWER(10, ti.decimals) AS dest_volume
        FROM order_placed op
        INNER JOIN match_executed me
            ON op.order_uuid = me.order_uuid
        INNER JOIN token_info ti
            ON op.dest_asset = ti.address
        INNER JOIN coingecko_assets_list cal
            ON op.dest_asset = cal.address
        INNER JOIN coingecko_market_data cmd 
            ON cal.id = cmd.id
        WHERE cal.id = '{asset_id}'
    ),
    overall_volume_table_2 AS (
        SELECT DISTINCT
            svt.*,
            dvt.dest_id AS dest_id,
            dvt.dest_chain AS dest_chain,
            dvt.dest_decimal AS dest_decimal,
            dvt.dest_price AS dest_price,
            dvt.dest_volume AS dest_volume,
            (dvt.dest_volume + svt.source_volume) AS total_volume
        FROM source_volume_table svt
        INNER JOIN dest_volume_table dvt
            ON svt.order_uuid = dvt.order_uuid
    ),
    daily_volume_table AS (
        SELECT 
            DATE_TRUNC('day', block_timestamp) AS day,
            SUM(total_volume) AS total_daily_volume,
            '{asset_id}' as asset
        FROM overall_volume_table_2
        GROUP BY DATE_TRUNC('day', block_timestamp)
    ),
    date_series AS (
        SELECT generate_series(
            DATE_TRUNC('day', '{date}'::timestamp),
            DATE_TRUNC('day', CURRENT_DATE),
            '1 day'::interval
        ) AS day
    ),
    filled_daily_volume_table AS (
        SELECT 
            ds.day,
            COALESCE(dv.total_daily_volume, 0) AS total_daily_volume,
            '{asset_id}' AS asset
        FROM date_series ds
        LEFT JOIN daily_volume_table dv
        ON DATE_TRUNC('day', ds.day) = dv.day
    )
    SELECT 
        TO_CHAR(day, 'FMMonth FMDD, YYYY') AS day,
        total_daily_volume,
        asset
    FROM filled_daily_volume_table
    ORDER BY day
    """

    query_2 = """
        SELECT 
            TO_CHAR(DATE_TRUNC('day', svt.block_timestamp), 'FMMonth FMDD, YYYY') AS day,
            COALESCE(SUM(svt.total_volume), 0) AS total_daily_volume,
            '{asset_id}' AS asset
        FROM main_volume_table svt
        WHERE svt.source_id = '{asset_id}' OR svt.dest_id = '{asset_id}'
        GROUP BY DATE_TRUNC('day', svt.block_timestamp)
        ORDER BY DATE_TRUNC('day', svt.block_timestamp)
        """
    
    df = execute_sql(query_2)
    if df is not None and 'result' in df:
        df = pd.json_normalize(df['result'])
        df = df[pd.to_datetime(df['day']) > pd.to_datetime(date)]
        return jsonify(df.to_dict(orient='records'))
    return jsonify([])

@app.route('/get_hourly_volume_by_asset/<asset_id>')
def get_hourly_volume_by_asset(asset_id):

    # New function for individual asset volumes
    today = datetime.now()
    date = today - timedelta(days=7)
    date = date.strftime('%Y-%m-%dT%H:%M:%S')

    query = f"""
    WITH latest_date AS (
        SELECT DATE_TRUNC('day', MAX(block_timestamp)) AS max_date
        FROM main_volume_table
    )
    SELECT 
        TO_CHAR(DATE_TRUNC('hour', svt.block_timestamp), 'HH12 AM') AS hour,
        COALESCE(SUM(svt.total_volume), 0) AS total_hourly_volume,
        '{asset_id}' AS asset
    FROM main_volume_table svt
    WHERE svt.block_timestamp >= (
        SELECT max_date - INTERVAL '1 day' 
        FROM latest_date
    )
    AND svt.block_timestamp < (
        SELECT max_date 
        FROM latest_date
    )
    AND svt.source_id = '{asset_id}' OR svt.dest_id = '{asset_id}'
    GROUP BY DATE_TRUNC('hour', svt.block_timestamp)
    ORDER BY DATE_TRUNC('hour', svt.block_timestamp)
    """

    df = execute_sql(query)
    if df is not None and 'result' in df:
        df = pd.json_normalize(df['result'])
        return jsonify(df.to_dict(orient='records'))
    return jsonify([])


@app.route('/get_assets')
def get_assets_route():
    query = """
    WITH consolidated_volumes AS (
        SELECT
            id,
            SUM(volume) AS total_volume
        FROM (
            SELECT
                source_id AS id,
                SUM(source_volume) AS volume
            FROM main_volume_table
            WHERE source_id != 'usualx'
            GROUP BY source_id
            UNION ALL
            SELECT
                dest_id AS id,
                SUM(dest_volume) AS volume
            FROM main_volume_table
            WHERE dest_id != 'usualx'
            GROUP BY dest_id
        ) combined
        GROUP BY id
    )
    SELECT id
    FROM consolidated_volumes
    WHERE id != 'usualx'
    ORDER BY total_volume DESC
    LIMIT 15
    """
    
    df = execute_sql(query)
    if df is not None and 'result' in df:
        asset_list = pd.json_normalize(df['result'])['id'].tolist()
        #print("\nAvailable assets:")
        #print(f"Total number of assets: {len(asset_list)}")
        #print("Asset list:", asset_list)
        return jsonify({"assets": asset_list})
    return jsonify({"assets": []})

@app.route('/get_weekly_volume/<time_range>')
def weekly_volume(time_range):
    try:
        if time_range == 'all':
            start_date = get_oldest_time()
        else:
            try:
                days = int(time_range)
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
            except ValueError:
                return jsonify({"error": "Invalid time range"}), 400

        sql_query = f"""
        WITH filtered_data AS (
            SELECT 
                block_timestamp,
                source_volume as volume,
                source_id as asset
            FROM main_volume_table
            WHERE block_timestamp >= '{start_date}'
            AND source_id NOT IN ('usualx', '0', 'O', '')
            UNION ALL
            SELECT 
                block_timestamp,
                dest_volume as volume,
                dest_id as asset
            FROM main_volume_table
            WHERE block_timestamp >= '{start_date}'
            AND dest_id NOT IN ('usualx', '0', 'O', '')
        ),
        date_series AS (
            SELECT generate_series(
                DATE_TRUNC('day', MIN(block_timestamp)),
                DATE_TRUNC('day', MAX(block_timestamp)),
                '1 day'::interval
            )::date as day
            FROM filtered_data
        ),
        top_assets AS (
            SELECT asset
            FROM filtered_data
            GROUP BY asset
            ORDER BY SUM(volume) DESC
            LIMIT 14
        ),
        daily_volumes AS (
            SELECT 
                DATE_TRUNC('day', block_timestamp) as day,
                asset,
                SUM(volume) as daily_volume
            FROM filtered_data
            WHERE asset IN (SELECT asset FROM top_assets)
            GROUP BY DATE_TRUNC('day', block_timestamp), asset
        ),
        all_combinations AS (
            SELECT 
                d.day,
                a.asset
            FROM date_series d
            CROSS JOIN top_assets a
        ),
        filled_daily_volumes AS (
            SELECT 
                ac.day,
                ac.asset,
                COALESCE(dv.daily_volume, 0) as daily_volume
            FROM all_combinations ac
            LEFT JOIN daily_volumes dv
                ON ac.day = dv.day
                AND ac.asset = dv.asset
            ORDER BY ac.day, ac.asset
        ),
        cumulative_volumes AS (
            SELECT 
                day,
                asset,
                daily_volume,
                SUM(daily_volume) OVER (
                    PARTITION BY asset 
                    ORDER BY day
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) as cumulative_volume
            FROM filled_daily_volumes
        )
        SELECT 
            day,
            asset,
            daily_volume,
            cumulative_volume
        FROM cumulative_volumes
        ORDER BY 
            day,
            asset
        """

        result = execute_sql(sql_query)
        if result is None or 'result' not in result:
            return jsonify({"error": "No data available"}), 500

        df = pd.json_normalize(result['result'])
        if len(df) == 0:
            return jsonify({"error": "No data available"}), 500

        return jsonify(df.to_dict(orient='records'))

    except Exception as e:
        print(f"Error in weekly_volume: {str(e)}")
        print(f"Traceback:\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_weekly_volume_by_asset/<asset>')
def get_weekly_volume_by_asset(asset):
    
    if asset != 'Total':
        query_2 = f"""
            SELECT 
                TO_CHAR(DATE_TRUNC('day', svt.block_timestamp), 'FMMonth FMDD, YYYY') AS day,
                COALESCE(SUM(svt.total_volume), 0) AS total_daily_volume,
                '{asset}' AS asset
            FROM main_volume_table svt
            WHERE svt.source_id = '{asset}' OR svt.dest_id = '{asset}'
            GROUP BY DATE_TRUNC('day', svt.block_timestamp)
            ORDER BY DATE_TRUNC('day', svt.block_timestamp)
            """
    else:
        query_2 = f"""
            SELECT 
                TO_CHAR(DATE_TRUNC('day', svt.block_timestamp), 'FMMonth FMDD, YYYY') AS day,
                COALESCE(SUM(svt.total_volume), 0) AS total_daily_volume,
                'Total' AS asset
            FROM main_volume_table svt
            GROUP BY DATE_TRUNC('day', svt.block_timestamp)
            ORDER BY DATE_TRUNC('day', svt.block_timestamp)
            """

    df = execute_sql(query_2)
    if df is not None and 'result' in df:
        return jsonify(pd.json_normalize(df['result']).to_dict(orient='records'))
    return jsonify([])

@app.route('/get_weekly_average_by_asset/<asset>')
def get_weekly_average_by_asset(asset):
    if asset != 'Total':
        query = f"""
        WITH date_series AS (
            -- Generate a series of dates from the minimum to the maximum block timestamp
            SELECT 
                generate_series(
                    (SELECT MIN(DATE_TRUNC('day', block_timestamp)) FROM order_placed), 
                    (SELECT MAX(DATE_TRUNC('day', block_timestamp)) FROM order_placed), 
                    '1 day'::interval
                )::date AS day
        ),
        daily_volume_table AS (
            SELECT 
                DATE_TRUNC('day', svt.block_timestamp) AS day,
                SUM(svt.total_volume) AS daily_volume,
                '{asset}' AS asset
                FROM main_volume_table svt
                WHERE svt.source_id = '{asset}' OR svt.dest_id = '{asset}'
                GROUP BY DATE_TRUNC('day', svt.block_timestamp)
        ),
        filled_daily_volume_table AS (
            SELECT 
                ds.day,
                COALESCE(dv.daily_volume, 0) AS daily_volume,
                '{asset}' AS asset
            FROM date_series ds
            LEFT JOIN daily_volume_table dv
            ON ds.day = dv.day
        ),
        weekly_averaged_volume_table AS (
            SELECT 
                day,
                asset,
                -- Calculate the 7-day centered moving average
                AVG(daily_volume) OVER (
                    ORDER BY day ROWS BETWEEN 3 PRECEDING AND 3 FOLLOWING
                ) AS weekly_avg_volume
            FROM filled_daily_volume_table
        )
        SELECT 
            TO_CHAR(day, 'FMMonth FMDD, YYYY') AS day,
            weekly_avg_volume AS total_weekly_avg_volume,
            asset
        FROM weekly_averaged_volume_table
        ORDER BY day
        """
    else:
        query = f"""
        WITH date_series AS (
            -- Generate a series of dates from the minimum to the maximum block timestamp
            SELECT 
                generate_series(
                    (SELECT MIN(DATE_TRUNC('day', block_timestamp)) FROM order_placed), 
                    (SELECT MAX(DATE_TRUNC('day', block_timestamp)) FROM order_placed), 
                    '1 day'::interval
                )::date AS day
        ),
        daily_volume_table AS (
            SELECT 
                DATE_TRUNC('day', svt.block_timestamp) AS day,
                SUM(svt.total_volume) AS daily_volume,
                'Total' AS asset
                FROM main_volume_table svt
                GROUP BY DATE_TRUNC('day', svt.block_timestamp)
        ),
        filled_daily_volume_table AS (
            SELECT 
                ds.day,
                COALESCE(dv.daily_volume, 0) AS daily_volume,
                'Total' AS asset
            FROM date_series ds
            LEFT JOIN daily_volume_table dv
            ON ds.day = dv.day
        ),
        weekly_averaged_volume_table AS (
            SELECT 
                day,
                asset,
                -- Calculate the 7-day centered moving average
                AVG(daily_volume) OVER (
                    ORDER BY day ROWS BETWEEN 3 PRECEDING AND 3 FOLLOWING
                ) AS weekly_avg_volume
            FROM filled_daily_volume_table
        )
        SELECT 
            TO_CHAR(day, 'FMMonth FMDD, YYYY') AS day,
            weekly_avg_volume AS total_weekly_avg_volume,
            asset
        FROM weekly_averaged_volume_table
        ORDER BY day
        """

    df = execute_sql(query)
    if df is not None and 'result' in df:
        return jsonify(pd.json_normalize(df['result']).to_dict(orient='records'))
    return jsonify([])

def get_start_date(time_range):
    """Convert time_range to start_date"""
    try:
        if time_range == 'all':
            return get_oldest_time()
        else:
            days = int(time_range)
            return (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
    except ValueError:
        print(f"Invalid time range: {time_range}")
        return None

@app.route('/histogram_data/<time_range>')
def get_histogram_data(time_range):
    try:
        if time_range == 'all':
            start_date = get_oldest_time()
        else:
            try:
                days = int(time_range)
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
            except ValueError:
                return jsonify({"error": "Invalid time range"}), 400

        query = f"""
        WITH volume_data AS (
            SELECT 
                chain,
                id,
                SUM(volume) as total_volume
            FROM (
                SELECT 
                    source_chain as chain,
                    source_id as id,
                    source_volume as volume
                FROM main_volume_table
                WHERE block_timestamp >= '{start_date}'
                UNION ALL
                SELECT 
                    dest_chain as chain,
                    dest_id as id,
                    dest_volume as volume
                FROM main_volume_table
                WHERE block_timestamp >= '{start_date}'
            ) combined
            GROUP BY chain, id
        ),
        period_top_assets AS (
            SELECT id
            FROM volume_data
            GROUP BY id
            ORDER BY SUM(total_volume) DESC
            LIMIT 14
        )
        SELECT json_build_object(
            'chain', v.chain,
            'asset', CASE 
                WHEN v.id IN (SELECT id FROM period_top_assets) THEN v.id 
                ELSE 'Other'
            END,
            'volume', SUM(v.total_volume)
        ) as result
        FROM volume_data v
        GROUP BY 
            v.chain, 
            CASE 
                WHEN v.id IN (SELECT id FROM period_top_assets) THEN v.id 
                ELSE 'Other'
            END
        ORDER BY SUM(v.total_volume) DESC
        """

        result = execute_sql(query)
        if result is None:
            return jsonify({"error": "No data available"}), 500

        # Parse the JSON objects in the result column
        df = pd.json_normalize([r['result'] for r in result['result']])

        if len(df) == 0:
            return jsonify({"error": "No data available"}), 500

        # Process data as before
        chains = df['chain'].unique().tolist()
        assets = df['asset'].unique().tolist()
        if 'Other' in assets:
            assets.remove('Other')
            assets.sort()
            assets.append('Other')

        volume_matrix = []
        for chain in chains:
            chain_volumes = []
            for asset in assets:
                volume = df[(df['chain'] == chain) & (df['asset'] == asset)]['volume'].sum()
                chain_volumes.append(float(volume))
            volume_matrix.append(chain_volumes)

        return jsonify({
            'chains': chains,
            'assets': assets,
            'volumes': volume_matrix
        })

    except Exception as e:
        print(f"Error in get_histogram_data: {str(e)}")
        print(f"Full error: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/sankey_data/<time_range>')
def sankey_data(time_range):
    # Check if data is in cache
    sankey_cache = app.config.get('sankey_cache', {})
    if time_range in sankey_cache:
        return sankey_cache[time_range]
    
    # If not in cache, generate data (existing code)
    try:
        # Convert time_range to start_date
        if time_range == 'all':
            start_date = get_oldest_time()
        else:
            try:
                days = int(time_range)
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
            except ValueError:
                return jsonify({"error": "Invalid time range"}), 400

        sql_query = f"""
        SELECT 
            source_chain,
            source_id,
            dest_chain,
            dest_id,
            SUM(source_volume) AS total_source_volume,
            SUM(dest_volume) AS total_dest_volume
        FROM 
            main_volume_table
        WHERE
            block_timestamp >= '{start_date}'
        GROUP BY 
            source_chain, source_id, dest_chain, dest_id
        ORDER BY 
            total_source_volume DESC
        """

        # Execute query and get results
        result = execute_sql(sql_query)
        data = pd.json_normalize(result['result'])

        # Label sources and destinations
        data["source_chain"] = data["source_chain"] + " (S)"
        data["dest_chain"] = data["dest_chain"] + " (D)"
        data["source_id"] = data["source_id"] + " (S)"
        data["dest_id"] = data["dest_id"] + " (D)"

        # Create asset-chain pairs
        data["source_pair"] = data["source_id"] + " | " + data["source_chain"]
        data["dest_pair"] = data["dest_id"] + " | " + data["dest_chain"]

        # Process data for different Sankey diagrams
        # 1. Asset Flow
        asset_data = data.groupby(["source_id", "dest_id"], as_index=False).agg({
            "total_source_volume": "sum",
            "total_dest_volume": "sum"
        })
        asset_data["avg_volume"] = (asset_data["total_source_volume"] + asset_data["total_dest_volume"]) / 2
        top_asset_data = asset_data.nlargest(10, "avg_volume")

        # 2. Chain Flow
        chain_data = data.groupby(["source_chain", "dest_chain"], as_index=False).agg({
            "total_source_volume": "sum",
            "total_dest_volume": "sum"
        })
        chain_data["avg_volume"] = (chain_data["total_source_volume"] + chain_data["total_dest_volume"]) / 2
        top_chain_data = chain_data.nlargest(10, "avg_volume")

        # 3. Asset-Chain Pair Flow
        pair_data = data.groupby(["source_pair", "dest_pair"], as_index=False).agg({
            "total_source_volume": "sum",
            "total_dest_volume": "sum"
        })
        pair_data["avg_volume"] = (pair_data["total_source_volume"] + pair_data["total_dest_volume"]) / 2
        top_pair_data = pair_data.nlargest(10, "avg_volume")

        return jsonify({
            "top_asset_data": top_asset_data.to_dict(orient='records'),
            "top_chain_data": top_chain_data.to_dict(orient='records'),
            "top_pair_data": top_pair_data.to_dict(orient='records')
        })

    except Exception as e:
        print(f"Error in sankey_data: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/user_analysis/<time_range>')
def user_analysis(time_range):
    # Check if data is in cache
    user_cache = app.config.get('user_cache', {})
    if time_range in user_cache:
        return user_cache[time_range]
    
    try:
        # Convert time_range to start_date
        if time_range == 'all':
            start_date = get_oldest_time()
        else:
            try:
                days = int(time_range)
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
            except ValueError:
                return jsonify({"error": "Invalid time range"}), 400

        # Trade rank query
        sql_query12 = f""" 
        WITH RankedTrades AS (
        SELECT
            ROW_NUMBER() OVER (ORDER BY COUNT(order_id) DESC) AS rank,
            address,
            COUNT(order_id) AS trade_count
        FROM (
            SELECT sender_address AS address, order_uuid AS order_id
            FROM main_volume_table
            WHERE block_timestamp >= '{start_date}'
            UNION ALL
            SELECT maker_address AS address, order_uuid AS order_id
            FROM main_volume_table
            WHERE block_timestamp >= '{start_date}'
        ) AS all_trades
        GROUP BY address
        ),
        CumulativeTrades AS (
        SELECT
            rank AS N,
            SUM(trade_count) OVER (ORDER BY rank) AS cumulative_trade_count,
            (SELECT SUM(trade_count) FROM RankedTrades) AS total_trades
        FROM RankedTrades
        WHERE rank <= 200
        )
        SELECT
            N,
            CAST(cumulative_trade_count * 100.0 / total_trades AS FLOAT) AS percentage_of_total_trades
        FROM CumulativeTrades
        ORDER BY N
        """

        # Volume rank query
        sql_query13 = f"""
        WITH total_volume_table AS (
            SELECT 
                address,
                COALESCE(SUM(total_volume), 0) AS total_user_volume
            FROM (
                SELECT sender_address AS address, total_volume
                FROM main_volume_table
                WHERE block_timestamp >= '{start_date}'
                UNION ALL
                SELECT maker_address AS address, total_volume
                FROM main_volume_table
                WHERE block_timestamp >= '{start_date}'
            ) AS combined_addresses
            GROUP BY address
        ),
        ranked_volume_table AS (
            SELECT 
                address,
                total_user_volume,
                RANK() OVER (ORDER BY total_user_volume DESC) AS rank
            FROM total_volume_table
        ),
        cumulative_volume_table AS (
            SELECT 
                rank,
                SUM(total_user_volume) OVER (ORDER BY rank) AS cumulative_volume,
                (SUM(total_user_volume) OVER (ORDER BY rank) * 100.0) / (SUM(total_user_volume) OVER ()) AS percentage_of_total_volume
            FROM ranked_volume_table
        )
        SELECT 
            rank AS top_n,
            percentage_of_total_volume
        FROM cumulative_volume_table
        WHERE rank <= 300
        """

        # Top traders query
        trade_add_query = f"""
        SELECT
            address,
            COUNT(order_id) AS trade_count
        FROM (
            SELECT sender_address AS address, order_uuid AS order_id
            FROM main_volume_table
            WHERE block_timestamp >= '{start_date}'
            UNION ALL
            SELECT maker_address AS address, order_uuid AS order_id
            FROM main_volume_table
            WHERE block_timestamp >= '{start_date}'
        ) AS all_trades
        GROUP BY address
        ORDER BY trade_count DESC
        LIMIT 200
        """

        # Top volume query
        volume_add_query = f"""
        SELECT 
            address,
            COALESCE(SUM(total_volume), 0) AS total_user_volume
        FROM (
            SELECT sender_address AS address, total_volume
            FROM main_volume_table
            WHERE block_timestamp >= '{start_date}'
            UNION ALL
            SELECT maker_address AS address, total_volume
            FROM main_volume_table
            WHERE block_timestamp >= '{start_date}'
        ) AS combined_addresses
        GROUP BY address
        ORDER BY total_user_volume DESC
        LIMIT 200
        """

        # Execute queries and process results
        df_trade_rank = pd.json_normalize(execute_sql(sql_query12)['result'].head(10))
        df_volume_rank = pd.json_normalize(execute_sql(sql_query13)['result'].head(10))
        df_trade_address = pd.json_normalize(execute_sql(trade_add_query)['result'])
        df_volume_address = pd.json_normalize(execute_sql(volume_add_query)['result'])

        # Round percentages
        df_trade_rank['percentage_of_total_trades'] = df_trade_rank['percentage_of_total_trades'].round(1)
        df_volume_rank['percentage_of_total_volume'] = df_volume_rank['percentage_of_total_volume'].round(1)

        # Add indices
        df_trade_address.index = df_trade_address.index + 1
        df_volume_address.index = df_volume_address.index + 1

        return jsonify({
            "trade_rank": df_trade_rank.to_dict(orient='records'),
            "volume_rank": df_volume_rank.to_dict(orient='records'),
            "trade_address": df_trade_address.to_dict(orient='records'),
            "volume_address": df_volume_address.to_dict(orient='records')
        })

    except Exception as e:
        print(f"Error in user_analysis: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/pie_data/<time_range>')
def pie_data(time_range):
    try:
        print(f"\n=== Starting pie data request for time_range: {time_range} ===")
        # Convert time_range to start_date
        if time_range == 'all':
            start_date = get_oldest_time()
        else:
            try:
                days = int(time_range)
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
            except ValueError:
                print(f"Invalid time range value: {time_range}")
                return jsonify({"error": "Invalid time range"}), 400
        
        print(f"Using start_date: {start_date}")

        # Query for pie charts
        sql_query = f"""
        WITH volume_data AS (
            SELECT 
                source_chain as chain,
                source_id as asset,
                source_volume as volume
            FROM main_volume_table
            WHERE block_timestamp >= '{start_date}'
            AND source_chain NOT IN ('0', 'O', '')
            AND source_id NOT IN ('0', 'O', '')
            UNION ALL
            SELECT 
                dest_chain as chain,
                dest_id as asset,
                dest_volume as volume
            FROM main_volume_table
            WHERE block_timestamp >= '{start_date}'
            AND dest_chain NOT IN ('0', 'O', '')
            AND dest_id NOT IN ('0', 'O', '')
        ),
        asset_totals AS (
            SELECT 
                asset,
                SUM(volume) as total_volume
            FROM volume_data
            GROUP BY asset
            ORDER BY total_volume DESC
        ),
        top_assets AS (
            SELECT asset
            FROM asset_totals
            LIMIT 14
        )
        SELECT 
            chain,
            CASE 
                WHEN asset IN (SELECT asset FROM top_assets) THEN asset
                ELSE 'Other'
            END as asset,
            SUM(volume) as total_volume
        FROM volume_data
        GROUP BY 
            chain,
            CASE 
                WHEN asset IN (SELECT asset FROM top_assets) THEN asset
                ELSE 'Other'
            END
        ORDER BY total_volume DESC
        """

        #print("Executing SQL query...")
        result = execute_sql(sql_query)
        #print(f"SQL Result type: {type(result)}")
        #if result is not None:
         #   print(f"SQL Result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
         #   print(f"First few rows of result:\n{result.head() if isinstance(result, pd.DataFrame) else result}")

        if result is None or 'result' not in result:
            print("No results from query")
            return jsonify({"error": "No data available"}), 500

        df = pd.json_normalize(result['result'])
        #print("\nDataFrame after normalization:")
        #print(f"Columns: {df.columns.tolist()}")
        #print(f"Shape: {df.shape}")
        #print(f"First few rows:\n{df.head()}")

        if len(df) == 0:
            print("DataFrame is empty")
            return jsonify({"error": "No data available"}), 500

        # Process data for pie charts
        chain_volumes = df.groupby('chain')['total_volume'].sum().reset_index()
        asset_volumes = df.groupby('asset')['total_volume'].sum().reset_index()

       # print("\nProcessed data:")
       # print("Chain volumes:\n", chain_volumes.head())
       # print("Asset volumes:\n", asset_volumes.head())

        response = {
            'chains': chain_volumes['chain'].tolist(),
            'chain_volumes': chain_volumes['total_volume'].tolist(),
            'assets': asset_volumes['asset'].tolist(),
            'asset_volumes': asset_volumes['total_volume'].tolist()
        }

        #print("\nFinal response structure:")
        #print(f"Number of chains: {len(response['chains'])}")
        #print(f"Number of assets: {len(response['assets'])}")

        return jsonify(response)

    except Exception as e:
        print(f"\nError in pie_data:")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        print(f"Traceback:\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/short_term_data/<days>')
def short_term_data(days):
    try:
        days = int(days)
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
        print(f"Fetching data from {start_date}")

        query = f"""
        WITH pre AS (
            SELECT 
                source_chain AS chain,
                source_id AS asset,
                source_volume AS volume,
                block_timestamp,
                transaction_hash,
                sender_address AS wallet
            FROM public.main_volume_table
            UNION ALL
            SELECT 
                dest_chain AS chain,
                dest_id AS asset,
                dest_volume AS volume,
                block_timestamp,
                transaction_hash,
                sender_address AS wallet
            FROM public.main_volume_table
        )
        SELECT 
            date_trunc('hour', block_timestamp)::timestamp AS hour,
            COUNT(DISTINCT transaction_hash) AS trades_count,
            COALESCE(SUM(volume), 0) AS volume_total,
            array_agg(DISTINCT wallet) AS wallets
        FROM pre
        WHERE block_timestamp >= '{start_date}'::timestamp
          AND volume > 0
        GROUP BY date_trunc('hour', block_timestamp)
        ORDER BY hour ASC
        """
        
        result = execute_sql(query)
        result = pd.json_normalize(result['result'])
        #print("Raw DataFrame:")
        #print(result)
        #print("\nDataFrame Info:")
        #print(result.info())
        #print("\nDataFrame Columns:", result.columns.tolist())
        
        # Convert DataFrame to JSON records
        records = result.to_dict(orient='records')
        return jsonify({'result': records})
        
    except Exception as e:
        print(f"Error in short_term_data: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify([])

@app.route('/get_mach_trades/<days>')
def get_mach_trades(days):
    days = float(days)
    interval = f"{days * 24} hours" if days < 1 else f"{days} days"
    
    print(f"Fetching Mach trades for interval: {interval}")
    
    query = f"""
    WITH pre AS (
        SELECT DISTINCT
            source_chain AS chain,
            source_volume AS volume,
            block_timestamp,
            transaction_hash,
            sender_address AS wallet
        FROM public.main_volume_table
        WHERE block_timestamp >= CURRENT_TIMESTAMP - INTERVAL '{interval}'
          AND source_volume > 0
        UNION ALL
        SELECT DISTINCT
            dest_chain AS chain,
            dest_volume AS volume,
            block_timestamp,
            transaction_hash,
            sender_address AS wallet
        FROM public.main_volume_table
        WHERE block_timestamp >= CURRENT_TIMESTAMP - INTERVAL '{interval}'
          AND dest_volume > 0
    ),
    top_trades AS (
        SELECT 
            chain,
            volume,
            block_timestamp,
            transaction_hash,
            wallet
        FROM (
            SELECT DISTINCT ON (transaction_hash)
                chain,
                volume,
                block_timestamp,
                transaction_hash,
                wallet
            FROM pre
            ORDER BY transaction_hash, volume DESC
        ) unique_trades
        ORDER BY volume DESC
        LIMIT 1000
    ),
    debug_counts AS (
        SELECT COUNT(*) as total_trades FROM top_trades
    ),
    ordered_trades AS (
        SELECT 
            chain,
            volume,
            block_timestamp,
            transaction_hash,
            wallet,
            SUM(volume) OVER (ORDER BY block_timestamp) as cumulative_volume
        FROM top_trades
        ORDER BY block_timestamp ASC
    )
    SELECT 
        (SELECT total_trades FROM debug_counts) as total_trades_count,
        chain,
        volume,
        block_timestamp,
        transaction_hash,
        wallet,
        cumulative_volume
    FROM ordered_trades
    ORDER BY block_timestamp ASC
    """
    
    df = execute_sql(query)
    if df is not None and 'result' in df:
        result = pd.json_normalize(df['result']).to_dict(orient='records')
        print(f"Total trades in query: {result[0]['total_trades_count'] if result else 0}")
        print(f"Number of trades returned: {len(result)}")
        print(f"Time range: from {min(r['block_timestamp'] for r in result)} to {max(r['block_timestamp'] for r in result)}")
        return jsonify(result)
    return jsonify([])

@app.route('/get_mach_chain_volume/<days>')
def get_mach_chain_volume(days):
    # Handle 'all' case
    if days == 'all':
        where_clause = ""
    else:
        where_clause = f"WHERE block_timestamp >= CURRENT_TIMESTAMP - INTERVAL '{days} days'"
    
    query = f"""
    WITH pre AS (
        SELECT 
            source_chain as chain,
            source_id as asset,
            source_volume as volume,
            block_timestamp
        FROM public.main_volume_table
        WHERE source_chain != '0'
        UNION ALL
        SELECT 
            dest_chain as chain,
            dest_id as asset,
            dest_volume as volume,
            block_timestamp
        FROM public.main_volume_table
        WHERE dest_chain != '0'
    )
    SELECT 
        chain,
        date_trunc('day', block_timestamp) as day,
        sum(volume) as total_volume
    FROM pre
    {where_clause + (' AND ' if where_clause else 'WHERE ') + "chain != '0'"}
    GROUP BY chain, date_trunc('day', block_timestamp)
    ORDER BY date_trunc('day', block_timestamp) ASC
    """
    
    df = execute_sql(query)
    if df is not None and 'result' in df:
        return jsonify(pd.json_normalize(df['result']).to_dict(orient='records'))
    return jsonify([])

@app.route('/get_mach_asset_volume/<days>')
def get_mach_asset_volume(days):
    # Handle 'all' case
    if days == 'all':
        where_clause = ""
    else:
        where_clause = f"WHERE block_timestamp >= CURRENT_TIMESTAMP - INTERVAL '{days} days'"
    
    query = f"""
    WITH pre AS (
        SELECT 
            source_chain as chain,
            source_id as asset,
            source_volume as volume,
            block_timestamp
        FROM public.main_volume_table
        WHERE source_id != 'usualx' AND source_id != '0'
        UNION ALL
        SELECT 
            dest_chain as chain,
            dest_id as asset,
            dest_volume as volume,
            block_timestamp
        FROM public.main_volume_table
        WHERE dest_id != 'usualx' AND dest_id != '0'
    )
    SELECT 
        asset,
        date_trunc('day', block_timestamp) as day,
        sum(volume) as total_volume
    FROM pre
    {where_clause + (' AND ' if where_clause else 'WHERE ') + "asset != 'usualx' AND asset != '0'"}
    GROUP BY asset, date_trunc('day', block_timestamp)
    ORDER BY date_trunc('day', block_timestamp) ASC, SUM(volume) DESC
    """
    
    df = execute_sql(query)
    if df is not None and 'result' in df:
        return jsonify(pd.json_normalize(df['result']).to_dict(orient='records'))
    return jsonify([])

@app.route('/get_fill_time_data/<days>')
def get_fill_time_data(days):
    # Handle 'all' case and convert days parameter
    if days == 'all':
        interval = "ALL"
        where_clause = ""
    else:
        days = float(days)
        interval = f"{days * 24} hours" if days < 1 else f"{days} days"
        where_clause = f"WHERE op.block_timestamp >= CURRENT_TIMESTAMP - INTERVAL '{interval}'"
      
    # Query for chain pair data
    chain_pair_query = f"""
    WITH deduplicated AS (
        SELECT 
            op.order_uuid,
            cal.chain as source_chain,
            cal2.chain as dest_chain,
            op.block_timestamp as time_order_made,
            EXTRACT(EPOCH FROM (me.block_timestamp - op.block_timestamp))::FLOAT AS fill_time,
            ROW_NUMBER() OVER (PARTITION BY op.order_uuid ORDER BY me.block_timestamp) AS rn
        FROM order_placed op
        INNER JOIN match_executed me
          ON op.order_uuid = me.order_uuid
        INNER JOIN coingecko_assets_list cal
          ON op.source_asset = cal.address
        INNER JOIN coingecko_assets_list cal2
          ON op.dest_asset = cal2.address
        {where_clause}
    ),
    fill_table AS (
      SELECT order_uuid, source_chain, dest_chain, time_order_made, fill_time
      FROM deduplicated
      WHERE rn = 1
    ),
    chain_pair_stats AS (
        SELECT
            source_chain || ' to ' || dest_chain as chain_pair,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fill_time) AS median_fill_time
        FROM fill_table
        WHERE fill_time > 0
        GROUP BY source_chain, dest_chain
        ORDER BY median_fill_time DESC
    )
    SELECT * 
    FROM chain_pair_stats
    WHERE median_fill_time > 0
    """
    
    # Query for daily median fill times
    daily_query = f"""
    WITH deduplicated AS (
        SELECT 
            op.order_uuid,
            op.block_timestamp as time_order_made,
            EXTRACT(EPOCH FROM (me.block_timestamp - op.block_timestamp))::FLOAT AS fill_time,
            ROW_NUMBER() OVER (PARTITION BY op.order_uuid ORDER BY me.block_timestamp) AS rn
        FROM order_placed op
        INNER JOIN match_executed me
          ON op.order_uuid = me.order_uuid
        {where_clause}
    ),
    fill_table AS (
      SELECT order_uuid, time_order_made, fill_time
      FROM deduplicated
      WHERE rn = 1
    ),
    daily_stats AS (
        SELECT
            DATE(time_order_made) as date,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fill_time) AS median_fill_time
        FROM fill_table
        WHERE fill_time > 0
        GROUP BY DATE(time_order_made)
        ORDER BY date
    )
    SELECT * FROM daily_stats
    WHERE median_fill_time > 0
    """
    
    # Query for source chain median fill times
    source_chain_query = f"""
    WITH deduplicated AS (
        SELECT 
            op.order_uuid,
            cal.chain as chain,
            EXTRACT(EPOCH FROM (me.block_timestamp - op.block_timestamp))::FLOAT AS fill_time,
            ROW_NUMBER() OVER (PARTITION BY op.order_uuid ORDER BY me.block_timestamp) AS rn
        FROM order_placed op
        INNER JOIN match_executed me
          ON op.order_uuid = me.order_uuid
        INNER JOIN coingecko_assets_list cal
          ON op.source_asset = cal.address
        {where_clause}
    ),
    fill_table AS (
      SELECT order_uuid, chain, fill_time
      FROM deduplicated
      WHERE rn = 1 AND fill_time > 0
    )
    SELECT 
        chain,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fill_time) AS fill_time
    FROM fill_table
    GROUP BY chain
    ORDER BY fill_time DESC
    """
    
    # Query for destination chain median fill times
    dest_chain_query = f"""
    WITH deduplicated AS (
        SELECT 
            op.order_uuid,
            cal.chain as chain,
            EXTRACT(EPOCH FROM (me.block_timestamp - op.block_timestamp))::FLOAT AS fill_time,
            ROW_NUMBER() OVER (PARTITION BY op.order_uuid ORDER BY me.block_timestamp) AS rn
        FROM order_placed op
        INNER JOIN match_executed me
          ON op.order_uuid = me.order_uuid
        INNER JOIN coingecko_assets_list cal
          ON op.dest_asset = cal.address
        {where_clause}
    ),
    fill_table AS (
      SELECT order_uuid, chain, fill_time
      FROM deduplicated
      WHERE rn = 1 AND fill_time > 0
    )
    SELECT 
        chain,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fill_time) AS fill_time
    FROM fill_table
    GROUP BY chain
    ORDER BY fill_time DESC
    """
    
    # Query for lowest fill times
    lowest_fill_times_query = f"""
    WITH deduplicated AS (
        SELECT 
            op.order_uuid,
            op.sender_address as address,
            op.source_asset,
            op.dest_asset,
            EXTRACT(EPOCH FROM (me.block_timestamp - op.block_timestamp))::FLOAT AS fill_time,
            ROW_NUMBER() OVER (PARTITION BY op.order_uuid ORDER BY me.block_timestamp) AS rn
        FROM order_placed op
        INNER JOIN match_executed me
          ON op.order_uuid = me.order_uuid
        {where_clause}
    )
    SELECT 
        order_uuid,
        address,
        fill_time
    FROM deduplicated
    WHERE rn = 1 AND fill_time > 0
    ORDER BY fill_time ASC
    LIMIT 10
    """
    
    # Query for highest fill times
    highest_fill_times_query = f"""
    WITH deduplicated AS (
        SELECT 
            op.order_uuid,
            op.sender_address as address,
            op.source_asset,
            op.dest_asset,
            EXTRACT(EPOCH FROM (me.block_timestamp - op.block_timestamp))::FLOAT AS fill_time,
            ROW_NUMBER() OVER (PARTITION BY op.order_uuid ORDER BY me.block_timestamp) AS rn
        FROM order_placed op
        INNER JOIN match_executed me
          ON op.order_uuid = me.order_uuid
        {where_clause}
    )
    SELECT 
        order_uuid,
        address,
        fill_time
    FROM deduplicated
    WHERE rn = 1 AND fill_time > 0
    ORDER BY fill_time DESC
    LIMIT 10
    """
    
    chain_pair_data = execute_sql(chain_pair_query)
    chain_pair_df = pd.json_normalize(chain_pair_data['result'])
    
    daily_data = execute_sql(daily_query)
    daily_df = pd.json_normalize(daily_data['result'])
    
    source_chain_data = execute_sql(source_chain_query)
    source_chain_df = pd.json_normalize(source_chain_data['result'])
    
    dest_chain_data = execute_sql(dest_chain_query)
    dest_chain_df = pd.json_normalize(dest_chain_data['result'])
    
    lowest_fill_times_data = execute_sql(lowest_fill_times_query)
    lowest_fill_times_df = pd.json_normalize(lowest_fill_times_data['result'])
    
    highest_fill_times_data = execute_sql(highest_fill_times_query)
    highest_fill_times_df = pd.json_normalize(highest_fill_times_data['result'])
    
    response_data = {
        'chain_pairs': chain_pair_df['chain_pair'].tolist(),
        'median_fill_times': chain_pair_df['median_fill_time'].tolist(),
        'dates': daily_df['date'].tolist(),
        'daily_medians': daily_df['median_fill_time'].tolist(),
        'source_chain_data': source_chain_df.to_dict('records'),
        'dest_chain_data': dest_chain_df.to_dict('records'),
        'lowest_fill_times': lowest_fill_times_df.to_dict('records'),
        'highest_fill_times': highest_fill_times_df.to_dict('records')
    }
    
    return jsonify(response_data)

@app.route('/cumulative_data/<time_range>')
def cumulative_data(time_range):
    try:
        if time_range == 'all':
            start_date = get_oldest_time()
        else:
            try:
                days = int(time_range)
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
            except ValueError:
                return jsonify({"error": "Invalid time range"}), 400

        sql_query = f"""
        WITH all_asset_volumes AS (
            -- Get total volume for each asset to find top assets
            SELECT 
                asset_id,
                SUM(volume) as total_volume
            FROM (
                SELECT source_id as asset_id, source_volume as volume
                FROM main_volume_table
                WHERE source_id NOT IN ('usualx', '0', 'O', '')
                UNION ALL
                SELECT dest_id as asset_id, dest_volume as volume
                FROM main_volume_table
                WHERE dest_id NOT IN ('usualx', '0', 'O', '')
            ) all_volumes
            GROUP BY asset_id
        ),
        top_assets AS (
            -- Select top 14 assets by total volume
            SELECT asset_id
            FROM all_asset_volumes
            ORDER BY total_volume DESC
            LIMIT 14
        ),
        filtered_data AS (
            SELECT 
                block_timestamp,
                source_volume as volume,
                source_id as asset
            FROM main_volume_table
            WHERE block_timestamp >= '{start_date}'
                AND source_id IN (SELECT asset_id FROM top_assets)
            UNION ALL
            SELECT 
                block_timestamp,
                dest_volume as volume,
                dest_id as asset
            FROM main_volume_table
            WHERE block_timestamp >= '{start_date}'
                AND dest_id IN (SELECT asset_id FROM top_assets)
        ),
        date_series AS (
            SELECT generate_series(
                DATE_TRUNC('day', MIN(block_timestamp)),
                DATE_TRUNC('day', MAX(block_timestamp)),
                '1 day'::interval
            )::date as day
            FROM main_volume_table
            WHERE block_timestamp >= '{start_date}'
        ),
        daily_volumes AS (
            SELECT 
                DATE_TRUNC('day', block_timestamp)::date as day,
                asset,
                SUM(volume) as daily_volume
            FROM filtered_data
            GROUP BY 
                DATE_TRUNC('day', block_timestamp)::date,
                asset
        ),
        all_combinations AS (
            SELECT 
                d.day,
                a.asset_id as asset
            FROM date_series d
            CROSS JOIN top_assets a
        ),
        filled_daily_volumes AS (
            SELECT 
                ac.day,
                ac.asset,
                COALESCE(dv.daily_volume, 0) as daily_volume
            FROM all_combinations ac
            LEFT JOIN daily_volumes dv
                ON ac.day = dv.day
                AND ac.asset = dv.asset
            ORDER BY ac.day, ac.asset
        ),
        cumulative_volumes AS (
            SELECT 
                day,
                asset,
                SUM(daily_volume) OVER (
                    PARTITION BY asset 
                    ORDER BY day
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) as cumulative_volume
            FROM filled_daily_volumes
        )
        SELECT 
            day,
            asset,
            cumulative_volume
        FROM cumulative_volumes
        ORDER BY day, asset
        """

        result = execute_sql(sql_query)
        if result is None or 'result' not in result:
            return jsonify({"error": "No data available"}), 500

        df = pd.json_normalize(result['result'])
        #print(df)
        if len(df) == 0:
            return jsonify({"error": "No data available"}), 500

        return jsonify(df.to_dict(orient='records'))

    except Exception as e:
        print(f"Error in cumulative_data: {str(e)}")
        print(f"Traceback:\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

def create_app():
    app.config['metrics_cache'] = {}
    
    with app.app_context():
        try:
            # Initialize metrics cache with default values
            time_ranges = ['all', '15', '30', '90', '180']
            for time_range in time_ranges:
                app.config['metrics_cache'][time_range] = create_default_metrics()
            
            # Try to preload metrics
            preload_metrics()
        except Exception as e:
            print(f"Error during app initialization: {str(e)}")
    
    return app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)