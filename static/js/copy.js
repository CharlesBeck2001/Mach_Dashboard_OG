// Function to handle loading state
function setLoadingState(isLoading) {
    const metricValues = document.querySelectorAll('.metric-value');
    metricValues.forEach(value => {
        value.style.opacity = isLoading ? '0.5' : '1';
    });
}

// Function to update metrics display
function updateMetrics(data) {
    console.log('Updating metrics with data:', data);  // Debug log
    
    try {
        // Update total volume
        const totalVolumeElement = document.querySelector('.metric-box:nth-child(1) .metric-value');
        totalVolumeElement.textContent = `$${formatNumber(data.total_volume)}`;
        
        // Update total users
        const totalUsersElement = document.querySelector('.metric-box:nth-child(2) .metric-value');
        totalUsersElement.textContent = formatNumber(data.total_users);
        
        // Update trade count
        const tradeCountElement = document.querySelector('.metric-box:nth-child(3) .metric-value');
        tradeCountElement.textContent = formatNumber(data.trade_count);
        
        // Update average trades
        const averageTradesElement = document.querySelector('.metric-box:nth-child(4) .metric-value');
        averageTradesElement.textContent = data.average_trades;
        
        // Update percentage above
        const percentageElement = document.querySelector('.metric-box:nth-child(5) .metric-value');
        percentageElement.textContent = `${data.perc_above}%`;
        
        // Update last day volume
        const lastDayElement = document.querySelector('.metric-box:last-child .metric-value');
        lastDayElement.textContent = `$${formatNumber(data.last_day_v)}`;
    } catch (error) {
        console.error('Error updating metrics:', error);
    }
}

function toggleDropdown() {
    document.getElementById("timeRangeDropdown").classList.toggle("show");
}

window.onclick = function(event) {
    if (!event.target.matches('.dropbtn')) {
        var dropdowns = document.getElementsByClassName("dropdown-content");
        for (var i = 0; i < dropdowns.length; i++) {
            var openDropdown = dropdowns[i];
            if (openDropdown.classList.contains('show')) {
                openDropdown.classList.remove('show');
            }
        }
    }
}


// Helper function to format numbers
function formatNumber(number) {
    return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(number);
}

// Chart creation functions
function createHourlyVolumeChart(data) {
    if (!data || data.length === 0) {
        console.log('No hourly volume data available');
        document.getElementById('hourlyVolumeChart').innerHTML = 'No data available for the selected period';
        return;
    }

    const trace = {
        x: data.map(d => d.hour),
        y: data.map(d => d.total_hourly_volume),
        type: 'bar',
        name: 'Total Volume',
        marker: {
            color: '#1f77b4'
        }
    };

    const layout = {
        title: '',
        xaxis: {
            title: 'Hour',
            tickangle: -45,
            gridcolor: '#333',
            color: '#ffffff'
        },
        yaxis: {
            title: 'Volume',
            gridcolor: '#333',
            color: '#ffffff'
        },
        margin: { 
            t: 40,    // top margin
            b: 150,   // increased bottom margin for date labels
            l: 80,    // left margin
            r: 20     // right margin
        },
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: {
            color: '#ffffff'
        },
        showlegend: false
    };

    Plotly.newPlot('hourlyVolumeChart', [trace], layout, {responsive: true});
}

function createWeeklyVolumeChart(data) {
    if (!data || data.length === 0) {
        console.log('No weekly volume data available');
        document.getElementById('weeklyVolumeChart').innerHTML = 'No data available for the selected period';
        return;
    }

    const trace = {
        x: data.map(d => d.day),
        y: data.map(d => d.total_daily_volume),
        type: 'bar',
        name: 'Total Volume',
        marker: {
            color: '#1f77b4'
        }
    };

    const layout = {
        title: '',
        xaxis: {
            title: 'Date',
            tickangle: -45,
            gridcolor: '#333',
            color: '#ffffff'
        },
        yaxis: {
            title: 'Volume',
            gridcolor: '#333',
            color: '#ffffff'
        },
        margin: { 
            t: 40,    // top margin
            b: 150,   // increased bottom margin for date labels
            l: 80,    // left margin
            r: 20     // right margin
        },
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: {
            color: '#ffffff'
        },
        showlegend: false
    };

    Plotly.newPlot('weeklyVolumeChart', [trace], layout, {responsive: true});
}

// Function to update breakdown charts
function updateBreakdownCharts() {
    const selectedAssets = Array.from(document.getElementById('assetSelect').selectedOptions)
        .map(option => option.value);

    // Clear existing charts
    document.getElementById('hourlyVolumeBreakdownChart').innerHTML = '';
    document.getElementById('weeklyVolumeBreakdownChart').innerHTML = '';

    // Fetch and combine data for all selected assets
    Promise.all([
        ...selectedAssets.map(asset => 
            fetch(`/get_hourly_volume_by_asset/${asset}`).then(r => r.json())
        )
    ]).then(hourlyData => {
        const combinedHourlyData = hourlyData.flat();
        createHourlyVolumeBreakdownChart(combinedHourlyData);
    });

    Promise.all([
        ...selectedAssets.map(asset => 
            fetch(`/get_weekly_volume_by_asset/${asset}`).then(r => r.json())
        )
    ]).then(weeklyData => {
        const combinedWeeklyData = weeklyData.flat();
        createWeeklyVolumeBreakdownChart(combinedWeeklyData);
    });
}

function createHourlyVolumeBreakdownChart(data) {
    const traces = [];
    const assets = [...new Set(data.map(d => d.asset))];
    
    assets.forEach(asset => {
        const assetData = data.filter(d => d.asset === asset);
        traces.push({
            x: assetData.map(d => d.hour),
            y: assetData.map(d => d.total_hourly_volume),
            type: 'bar',
            name: asset
        });
    });

    const layout = {
        title: 'Volume By Hour Breakdown',
        xaxis: {
            title: 'Hour',
            tickangle: -45,
            gridcolor: '#333',
            color: '#ffffff'
        },
        yaxis: {
            title: 'Volume',
            gridcolor: '#333',
            color: '#ffffff'
        },
        barmode: 'group',
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#ffffff' },
        showlegend: true,
        margin: { t: 40, b: 150, l: 80, r: 20 }
    };

    Plotly.newPlot('hourlyVolumeBreakdownChart', traces, layout, {responsive: true});
}

function createWeeklyVolumeBreakdownChart(data) {
    const traces = [];
    const assets = [...new Set(data.map(d => d.asset))];
    
    assets.forEach(asset => {
        const assetData = data.filter(d => d.asset === asset);
        traces.push({
            x: assetData.map(d => d.day),
            y: assetData.map(d => d.total_daily_volume),
            type: 'bar',
            name: asset
        });
    });

    const layout = {
        title: 'Volume In The Last Week By Asset',
        xaxis: {
            title: 'Date',
            tickangle: -45,
            gridcolor: '#333',
            color: '#ffffff'
        },
        yaxis: {
            title: 'Volume',
            gridcolor: '#333',
            color: '#ffffff'
        },
        barmode: 'group',
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#ffffff' },
        showlegend: true,
        margin: { t: 40, b: 150, l: 80, r: 20 }
    };

    Plotly.newPlot('weeklyVolumeBreakdownChart', traces, layout, {responsive: true});
}

// Function to populate asset selector
function populateAssetSelector() {
    fetch('/get_assets_day')
    .then(response => {
        if (!response.ok) throw new Error('Network response was not ok');
        return response.json();
    })
    .then(data => {
        const assets = data.assets;  // Get the assets array from the response
        const select = document.getElementById('assetSelect');
        
        // Clear existing options
        select.innerHTML = '';
        
        // Add first 4 assets as selected by default
        assets.slice(0, 4).forEach(asset => {
            const option = document.createElement('option');
            option.value = asset;
            option.text = asset;
            option.selected = true;
            select.appendChild(option);
        });
        
        // Add remaining assets
        assets.slice(4).forEach(asset => {
            const option = document.createElement('option');
            option.value = asset;
            option.text = asset;
            select.appendChild(option);
        });

        // Initial load of breakdown charts
        updateBreakdownCharts();
    })
    .catch(error => {
        console.error('Error loading assets:', error);
    });
}




document.addEventListener('DOMContentLoaded', function() {
    // Initialize time range selector
    const dropdownLinks = document.querySelectorAll('.dropdown-content a');
    dropdownLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const timeRange = this.getAttribute('data-value');
            document.querySelector('.dropbtn').textContent = this.textContent;
            
            // Update metrics with new time range
            fetch(`/update_metrics?range=${timeRange}`)
                .then(response => response.json())
                .then(data => {
                    updateMetrics(data);
                    toggleDropdown(); // Close dropdown after selection
                })
                .catch(error => {
                    console.error('Error:', error);
                });
        });
    });

    // Initialize asset selector
    const assetSelect = document.getElementById('assetSelect');
    if (assetSelect) {
        assetSelect.addEventListener('change', updateBreakdownCharts);
        // Fetch assets and populate selector
        fetch('/get_assets_day')
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(data => {
                const assets = data.assets;  // Get the assets array from the response
                const select = document.getElementById('assetSelect');
                
                // Clear existing options
                select.innerHTML = '';
                
                // Add first 4 assets as selected by default
                assets.slice(0, 4).forEach(asset => {
                    const option = document.createElement('option');
                    option.value = asset;
                    option.text = asset;
                    option.selected = true;
                    select.appendChild(option);
                });
                
                // Add remaining assets
                assets.slice(4).forEach(asset => {
                    const option = document.createElement('option');
                    option.value = asset;
                    option.text = asset;
                    select.appendChild(option);
                });

                // Initial load of breakdown charts
                updateBreakdownCharts();
            })
            .catch(error => {
                console.error('Error loading assets:', error);
            });
    } else {
        console.error('Could not find assetSelect element');
    }

    // Load initial metrics
    setLoadingState(false);

    // Load and create the total hourly volume chart
    fetch('/get_hourly_volume')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log('Total hourly volume data:', data);
            createHourlyVolumeChart(data);
        })
        .catch(error => {
            console.error('Error loading hourly volume:', error);
            document.getElementById('hourlyVolumeChart').innerHTML = 'Error loading data: ' + error.message;
        });

    // Load and create the total weekly volume chart
    fetch('/get_weekly_volume')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log('Total weekly volume data:', data);
            createWeeklyVolumeChart(data);
        })
        .catch(error => {
            console.error('Error loading weekly volume:', error);
            document.getElementById('weeklyVolumeChart').innerHTML = 'Error loading data: ' + error.message;
        });
});