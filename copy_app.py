from flask import Flask, render_template, jsonify, request
import pandas as pd
import requests
from datetime import datetime, timedelta
from functools import lru_cache

app = Flask(__name__)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response


# Constants
SUPABASE_URL = "https://fzkeftdzgseugijplhsh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ6a2VmdGR6Z3NldWdpanBsaHNoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczMjcxMzk3NCwiZXhwIjoyMDQ4Mjg5OTc0fQ.Og46ddAeoybqUavWBAUbUoj8HJiZrfAQZi-6gRP46i4"

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
    # Query for total volume
    sql_query_volume = f"""
        SELECT 
            SUM(total_volume)
        FROM main_volume_table
        WHERE block_timestamp >= '{start_date}'
        """

    # Query for total users
    sql_query_users = f"""
    WITH user_list AS (
        SELECT DISTINCT address AS unique_address_count
        FROM (
            SELECT sender_address AS address
            FROM main_volume_table
            WHERE main_volume_table.block_timestamp >= '{start_date}'
            UNION
            SELECT maker_address AS address
            FROM main_volume_table
            WHERE main_volume_table.block_timestamp >= '{start_date}'
        ) AS unique_addresses
    )
    SELECT * FROM user_list
    """

    # Query for total trades
    sql_query_trades = f"""
        SELECT COUNT(order_uuid)
        FROM main_volume_table
        WHERE block_timestamp >= '{start_date}'
        """

    # Query for average trades per user
    sql_query_avg_trades = f"""
    WITH combined_address_trades AS (
      SELECT 
        sender_address AS address,
        COUNT(*) AS trades
      FROM main_volume_table
      WHERE block_timestamp >= '{start_date}'
      GROUP BY sender_address
    
      UNION ALL
    
      SELECT 
        maker_address AS address,
        COUNT(*) AS trades
      FROM main_volume_table
      WHERE block_timestamp >= '{start_date}'
      GROUP BY maker_address
    ),
    user_trade_count AS (
    SELECT 
      address,
      CAST(SUM(trades) AS INT) AS total_trades
    FROM combined_address_trades
    GROUP BY address
    ORDER BY total_trades DESC
    )
    SELECT CAST(AVG(total_trades) AS INT) AS average_trades_per_user FROM user_trade_count
    """

    # Query for percentage of users with more than one trade
    sql_query_perc_above = f"""
    WITH user_trade_counts AS (
        SELECT
            sender_address AS address,
            COUNT(order_uuid) AS trade_count
        FROM main_volume_table
        WHERE block_timestamp >= '{start_date}'
        GROUP BY sender_address

        UNION ALL

        SELECT
            maker_address AS address,
            COUNT(order_uuid) AS trade_count
        FROM main_volume_table
        WHERE block_timestamp >= '{start_date}'
        GROUP BY maker_address
    )   
    SELECT
        CAST(
            (COUNT(CASE WHEN trade_count > 1 THEN 1 END) * 100.0) / COUNT(*) AS INT
        ) AS percent_users_with_more_than_one_trade
    FROM user_trade_counts
    """

    # Query for last day volume
    sql_query_last_day = """
    WITH latest_date AS (
        SELECT DATE_TRUNC('day', MAX(block_timestamp)) AS max_date
        FROM main_volume_table
    )
    SELECT 
        SUM(total_volume) AS volume
    FROM main_volume_table
    WHERE block_timestamp >= (
        SELECT max_date - INTERVAL '1 day' 
        FROM latest_date
    )
    AND block_timestamp < (
        SELECT max_date 
        FROM latest_date
    )
    """

    # Execute queries
    df_volume = execute_sql(sql_query_volume)
    #df_volume = pd.json_normalize(df_volume['result'])

    df_users = execute_sql(sql_query_users)
    df_trades = execute_sql(sql_query_trades)
    df_avg_trades = execute_sql(sql_query_avg_trades)
    df_perc_above = execute_sql(sql_query_perc_above)
    df_last_day = execute_sql(sql_query_last_day)


    # Process results
    total_volume = float(pd.json_normalize(df_volume['result'])['sum'].iloc[0])
    total_users = len(pd.json_normalize(df_users['result']))
    trade_count = int(pd.json_normalize(df_trades['result'])['count'].iloc[0])
    average_trades = int(pd.json_normalize(df_avg_trades['result'])['average_trades_per_user'].iloc[0])
    perc_above = int(pd.json_normalize(df_perc_above['result'])['percent_users_with_more_than_one_trade'].iloc[0])
    last_day_v = float(pd.json_normalize(df_last_day['result'])['volume'].iloc[0])

    return {
        "total_volume": total_volume,
        "total_users": total_users,
        "trade_count": trade_count,
        "average_trades": average_trades,
        "perc_above": perc_above,
        "last_day_v": last_day_v
    }

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
    """Preload metrics for all time ranges"""
    print("Preloading metrics...")
    
    # Get oldest time for 'all' time range
    oldest_time = get_oldest_time()
    metrics_cache['all'] = get_metrics(oldest_time)
    
    # Get metrics for each specific time range
    current_time = datetime.now()
    for days in [15, 30, 90, 180]:
        start_date = (current_time - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
        metrics_cache[str(days)] = get_metrics(start_date)
    
    print("Metrics preloaded successfully!")

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
def dashboard():
    # Use cached metrics for initial load
    return render_template('dashboard.html', metrics=metrics_cache['all'])

@app.route('/update_metrics')
def update_metrics():
    time_range = request.args.get('range', 'all')
    print("Metrics Cache Contents:", metrics_cache)

    # Return cached metrics
    return jsonify(metrics_cache[time_range])

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
    
    df = execute_sql(query_2)
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
        print("Before date filter:", df)  # Debug print
        df = df[pd.to_datetime(df['day']) > pd.to_datetime(date)]
        print("After date filter:", df)  # Debug print
        return jsonify(df.to_dict(orient='records'))
    return jsonify([])


@app.route('/get_weekly_volume_by_asset/<asset_id>')
def get_weekly_volume_by_asset(asset_id):
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

    query_2 = f"""
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
    assets = get_assets()
    return jsonify(assets)

@app.route('/get_weekly_volume/<asset_id>')
def get_weekly_volume_route(asset_id):
    start_date = request.args.get('start_date', None)
    data = get_weekly_volume(asset_id, start_date)
    return jsonify(data.to_dict(orient='records'))

def create_app():
    # Preload metrics when the app starts
    preload_metrics()
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)