// Function to handle loading state
function setLoadingState(isLoading) {
    const metricValues = document.querySelectorAll('.metric-value');
    metricValues.forEach(value => {
        value.style.opacity = isLoading ? '0.5' : '1';
    });
}

// Function to update metrics display
function updateMetrics(data) {
    // Add debug logging
    console.log('Raw data received:', data);

    // Update each metric individually with specific selectors
    const metrics = {
        'Total Volume': data.total_volume,
        'Total Users': data.total_users,
        'Total Trades': data.trade_count,
        'Average Trades Per User': data.average_trades,
        'Users With Multiple Trades': data.perc_above,
        'Previous Day Volume': data.last_day_v
    };

    // Update each metric box by finding its heading text
    document.querySelectorAll('.metric-box').forEach(box => {
        const heading = box.querySelector('h3').textContent;
        const valueElement = box.querySelector('.metric-value');
        
        if (heading in metrics) {
            const value = metrics[heading];
            if (heading === 'Total Volume' || heading === 'Previous Day Volume') {
                valueElement.textContent = `$${formatNumber(value)}`;
            } else if (heading === 'Users With Multiple Trades') {
                valueElement.textContent = `${value}%`;
            } else if (heading === 'Average Trades Per User') {
                valueElement.textContent = Math.round(value).toString();
            } else if (heading === 'Total Users' || heading === 'Total Trades') {
                valueElement.textContent = Math.round(value).toLocaleString();
            } else {
                valueElement.textContent = formatNumber(value);
            }
        }
    });
}

// Remove all existing window.onclick handlers and replace with this single one
window.onclick = function(event) {
    // Handle dropdown button clicks
    if (!event.target.matches('.dropbtn')) {
        var dropdowns = document.getElementsByClassName("dropdown-content");
        for (var i = 0; i < dropdowns.length; i++) {
            var openDropdown = dropdowns[i];
            if (openDropdown.classList.contains('show')) {
                openDropdown.classList.remove('show');
            }
        }
    }
};

// Update the toggle functions to just toggle their specific dropdowns
window.toggleDropdown = function() {
    document.getElementById("timeRangeDropdown").classList.toggle("show");
};

window.togglePieChartDropdown = function() {
    document.getElementById("pieChartDropdown").classList.toggle("show");
};

window.toggleSankeyDropdown = function() {
    document.getElementById("sankeyDropdown").classList.toggle("show");
};

window.toggleUserAnalysisDropdown = function() {
    document.getElementById("userAnalysisDropdown").classList.toggle("show");
};

window.toggleVolumeDistributionDropdown = function() {
    document.getElementById("volumeDistributionDropdown").classList.toggle("show");
};

window.toggleLongTermDropdown = function() {
    document.getElementById("longTermDropdown").classList.toggle("show");
};

window.toggleShortTermDropdown = function() {
    document.getElementById("shortTermDropdown").classList.toggle("show");
};

window.toggleAssetDropdown = function() {
    document.getElementById("assetDropdown").classList.toggle("show");
};

window.toggleMachVolumeDropdown = function() {
    document.getElementById("machVolumeDropdown").classList.toggle("show");
};

window.toggleMachTradesDropdown = function() {
    document.getElementById("machTradesDropdown").classList.toggle("show");
};

window.toggleFillTimeDropdown = function() {
    document.getElementById("fillTimeDropdown").classList.toggle("show");
};

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
    // Get selected assets from the selected-asset-tags instead of select element
    const selectedAssets = Array.from(document.querySelectorAll('.selected-asset-tag'))
        .map(tag => tag.textContent.replace('×', '').trim());

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

// Add these functions
let selectedAssets = [];

function updateSelectedAssetsList() {
    const container = document.querySelector('.selected-assets-list');
    container.innerHTML = '';
    
    selectedAssets.forEach(asset => {
        const tag = document.createElement('div');
        tag.className = 'selected-asset-tag';
        tag.innerHTML = `
            ${asset}
            <button onclick="removeAsset('${asset}')">&times;</button>
        `;
        container.appendChild(tag);
    });
}

let currentTimeRange = 'all';

// Update the toggleAsset function
function toggleAsset(asset) {
    console.log('Toggling asset:', asset);  // Debug log
    
    const index = selectedAssets.indexOf(asset);
    if (index === -1) {
        // Add asset
        selectedAssets.push(asset);
        
        // Create and add the visual tag
        const tag = document.createElement('div');
        tag.className = 'selected-asset-tag';
        tag.innerHTML = `
            ${asset}
            <button onclick="removeAsset('${asset}')">&times;</button>
        `;
        document.querySelector('.selected-assets-list').appendChild(tag);
    }
    
    // Update dropdown options
    populateAssetSelector();
    
    // Update charts with current time range
    updateLineCharts(currentTimeRange);
}

function removeAsset(asset) {
    console.log('Removing asset:', asset);  // Debug log
    
    const index = selectedAssets.indexOf(asset);
    if (index !== -1) {
        // Remove from array
        selectedAssets.splice(index, 1);
        
        // Remove visual tag
        const tags = document.querySelectorAll('.selected-asset-tag');
        tags.forEach(tag => {
            if (tag.textContent.replace('×', '').trim() === asset) {
                tag.remove();
            }
        });
        
        // Update dropdown options
        populateAssetSelector();
        
        // Update charts
        updateLineCharts(currentTimeRange);
    }
}

// Replace the populateAssetSelector function
function populateAssetSelector() {
    fetch('/get_assets')
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(data => {
            const assets = data.assets;
            const dropdown = document.getElementById('assetDropdown');
            dropdown.innerHTML = '';
            
            assets.forEach(asset => {
                if (!selectedAssets.includes(asset)) {
                    const link = document.createElement('a');
                    link.href = '#';
                    link.setAttribute('data-asset', asset);
                    link.textContent = asset;
                    
                    // Add click handler directly to the link
                    link.addEventListener('click', (e) => {
                        e.preventDefault();  // Prevent page jump
                        toggleAsset(asset);
                        toggleAssetDropdown();  // Close dropdown after selection
                    });
                    
                    dropdown.appendChild(link);
                }
            });
        })
        .catch(error => {
            console.error('Error loading assets:', error);
        });
}

// Add these functions for the long-term dropdown
function createVolumeLineChart(data, elementId, title, dateRange, isCumulative) {
    console.log('Creating volume line chart with data:', {
        dataStructure: data[0],
        isCumulative: isCumulative,
        elementId: elementId
    });

    const traces = [];
    const assets = [...new Set(data.map(d => d.asset))];
    
    assets.forEach(asset => {
        let assetData = data.filter(d => d.asset === asset);
        
        // Only process weekly average data for non-cumulative charts
        if (!isCumulative) {
    // Calculate cutoff date if dateRange is specified
    const cutoffDate = dateRange && dateRange !== 'all' 
        ? new Date(new Date().setDate(new Date().getDate() - parseInt(dateRange)))
        : null;
        
        // Filter data by date range if specified
        if (cutoffDate) {
            assetData = assetData.filter(d => new Date(d.day) >= cutoffDate);
        }

        // Sort data by date
        assetData.sort((a, b) => new Date(a.day) - new Date(b.day));
        }

        const trace = {
            name: asset,
            x: assetData.map(d => new Date(d.day)),
            y: assetData.map(d => {
                return isCumulative ? d.cumulative_volume : d.total_weekly_avg_volume || d.total_daily_volume;
            }),
            type: 'scatter',
            mode: 'lines',
            hovertemplate: '%{x}<br>' +
                          'Volume: $%{y:,.2f}<br>' +
                          'Asset: ' + asset +
                          '<extra></extra>'
        };
        traces.push(trace);
    });

    const layout = {
        title: title,
        showlegend: true,
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#ffffff' },
        xaxis: {
            title: 'Time',
            gridcolor: '#333',
            color: '#ffffff',
            tickangle: -45,
            tickformat: '%b %d\n%Y',
            nticks: 10
        },
        yaxis: {
            title: isCumulative ? 'Cumulative Volume (USD)' : 'Weekly Average Volume (USD)',
            gridcolor: '#333',
            color: '#ffffff',
            type: isCumulative ? 'log' : 'linear',  // Log scale for cumulative volume
            tickformat: isCumulative ? '.2e' : '',   // Scientific notation for log scale
        },
        hovermode: 'closest',
        legend: {
            orientation: 'h',  // horizontal legend
            y: -0.4,          // move legend down
            x: 0.5,           // center legend
            xanchor: 'center'
        },
        margin: { 
            t: 40,            // top margin
            b: 180,           // increased bottom margin for legend
            l: 80,            // left margin
            r: 20             // right margin
        },
        height: 600,          // Reduced height
        autosize: true
    };

    Plotly.newPlot(elementId, traces, layout, {responsive: true});
}

function updateLineCharts(dateRange) {
    console.log('Updating charts with date range:', dateRange);

    currentTimeRange = dateRange || 'all';
    
    const selectedAssets = Array.from(document.querySelectorAll('.selected-asset-tag'))
        .map(tag => tag.textContent.replace('×', '').trim());
    console.log('Selected assets:', selectedAssets);

    // Add loading state
    document.getElementById('totalVolumeLineChart').innerHTML = '';
    document.getElementById('weeklyAverageLineChart').innerHTML = '';

    // Use the cumulative_data endpoint for total volume chart
    fetch(`/cumulative_data/${dateRange}`)
                .then(r => {
                    if (!r.ok) throw new Error('Network response was not ok');
                    return r.json();
                })
        .then(data => {
            console.log('Cumulative data:', data);
            // Filter data to only include selected assets
            const filteredData = data.filter(d => selectedAssets.includes(d.asset));
            console.log('Filtered cumulative data:', filteredData);
        createVolumeLineChart(
                filteredData,
            'totalVolumeLineChart', 
            '', 
            dateRange,
                true
        );
        })
        .catch(error => {
            console.error('Error loading cumulative data:', error);
        document.getElementById('totalVolumeLineChart').innerHTML = 'Error loading data';
    });

    // Keep the weekly average chart as is
    Promise.all(
        selectedAssets.map(asset => 
            fetch(`/get_weekly_average_by_asset/${asset}`)
                .then(r => {
                    if (!r.ok) throw new Error('Network response was not ok');
                    return r.json();
                })
        )
    ).then(weeklyData => {
        const combinedData = weeklyData.flat();
        createVolumeLineChart(
            combinedData, 
            'weeklyAverageLineChart', 
            '',
            dateRange,
            false
        );
    }).catch(error => {
        console.error('Error loading weekly data:', error);
        document.getElementById('weeklyAverageLineChart').innerHTML = 'Error loading data';
    });
}

// Modify the main DOMContentLoaded event listener
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOMContentLoaded event fired');
    console.log('Document loaded, initializing short term charts');
    // Initial load of short term charts with 7 days of data
    updateShortTermCharts(7);

    // Add event listeners for short term dropdown
    document.querySelectorAll('#shortTermDropdown a').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const timeRange = this.getAttribute('data-value');
            // Update the button text to match selected option
            const buttonText = this.textContent;
            // Find the specific button within the shortTermDropdown
            document.querySelector('#shortTermDropdown').previousElementSibling.textContent = buttonText;
            
            // Existing functionality
            updateShortTermCharts(timeRange);
            toggleShortTermDropdown();
        });
    });

    // Initialize time range selector
    const dropdownLinks = document.querySelectorAll('.dropdown-content a');
    dropdownLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const timeRange = this.getAttribute('data-value');
            // Find the specific button within the metrics section
            this.closest('.dropdown').querySelector('.dropbtn').textContent = this.textContent;
            
            // Update metrics with new time range
            fetch(`/update_metrics?range=${timeRange}`)
                .then(response => response.json())
                .then(data => {
                    updateMetrics(data);
                    // Close the specific dropdown that was clicked
                    this.closest('.dropdown-content').classList.remove('show');
                })
                .catch(error => {
                    console.error('Error:', error);
                });
        });
    });

    updateLineCharts('all');

    const longTermDropdownLinks = document.querySelectorAll('#longTermDropdown a');
    longTermDropdownLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const timeRange = this.getAttribute('data-value');
            const buttonText = this.textContent;
            
            // Update button text
            const button = document.querySelector('.long-term-charts-section .dropbtn');
            if (button) {
                button.textContent = buttonText;
            }
            
            updateLineCharts(timeRange);
            toggleLongTermDropdown();
        });
    });

    // Initial load of line charts
    updateLineCharts();

    // Load initial metrics
    setLoadingState(false);

    // Initialize asset selector
    //populateAssetSelector();  // Just call this directly

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

    // Initialize with first 4 assets and 'all' time range
    fetch('/get_assets')
        .then(response => response.json())
        .then(data => {
            // Add check for data structure
            const assets = Array.isArray(data) ? data : (data.assets || []);
            const defaultAssets = assets.slice(0, 4);
            selectedAssets = defaultAssets;  // Set initial selected assets
            
            // Add default assets to selected list
            defaultAssets.forEach(asset => {
                const tag = document.createElement('div');
                tag.className = 'selected-asset-tag';
                tag.innerHTML = `
                    ${asset}
                    <button onclick="removeAsset('${asset}')">&times;</button>
                `;
                document.querySelector('.selected-assets-list').appendChild(tag);
            });

            // Update asset dropdown to exclude selected assets
            populateAssetSelector();

            // Initialize charts with default assets and 'all' time range
            updateLineCharts('all');
        })
        .catch(error => {
            console.error('Error initializing charts:', error);
        });

    // Load and create volume histograms
    // fetch('/histogram_data/7d')  // DELETE THIS

    // Initialize volume distribution charts
    initVolumeDistribution();

    // Add event listeners for volume distribution dropdown
    document.querySelectorAll('#volumeDistributionDropdown a').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const timeRange = this.getAttribute('data-value');
            const buttonText = this.textContent;
            document.querySelector('.volume-distribution-section .dropbtn').textContent = buttonText;
            updateVolumeDistribution(timeRange);
            toggleVolumeDistributionDropdown();
        });
    });

    updateSankeyDiagrams('all');

    // Add event listeners for pie chart time range selector
    const pieChartLinks = document.querySelectorAll('#pieChartDropdown a');
    pieChartLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const timeRange = this.getAttribute('data-value');
            const buttonText = this.textContent;
            
            // Update button text
            const button = document.querySelector('.pie-charts-row').previousElementSibling.querySelector('.dropbtn');
            if (button) {
                button.textContent = buttonText;
            }
            
            updatePieCharts(timeRange);
            togglePieChartDropdown();
        });
    });

    // Add event listeners for Sankey time range selector
    const sankeyLinks = document.querySelectorAll('#sankeyDropdown a');
    sankeyLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const timeRange = this.getAttribute('data-value');
            const buttonText = this.textContent;
            
            // Update button text
            const button = document.querySelector('.sankey-section .dropbtn');
            if (button) {
                button.textContent = buttonText;
            }
            
            updateSankeyDiagrams(timeRange);
            toggleSankeyDropdown();
        });
    });

    // Preload all charts for different time ranges
    const timeRanges = ['all', '15', '30', '90', '180'];
    
    // Create promises for all data fetching
    const promises = timeRanges.map(range => {
        return Promise.all([
            fetch(`/histogram_data/${range}`).then(r => r.json()),
            fetch(`/sankey_data/${range}`).then(r => r.json())
        ]);
    });

    // Store preloaded data
    const chartData = {};

    // Load all data and create charts
    Promise.all(promises)
        .then(results => {
            timeRanges.forEach((range, index) => {
                const [histogramData, sankeyData] = results[index];
                chartData[range] = {
                    histogram: histogramData,
                    sankey: sankeyData
                };
            });

            // Create initial charts with 'all' time range
            createVolumeHistograms(chartData['all'].histogram);
            createPieCharts(chartData['all'].histogram);
            createSankeyDiagrams(chartData['all'].sankey);

            // Update event listeners to use preloaded data
            document.querySelectorAll('#volumeDistributionDropdown a').forEach(link => {
                link.addEventListener('click', function(e) {
                    e.preventDefault();
                    const timeRange = this.getAttribute('data-value');
                    const buttonText = this.textContent;
                    document.querySelector('.volume-distribution-section .dropbtn').textContent = buttonText;
                    createVolumeHistograms(chartData[timeRange].histogram);
                });
            });

            document.querySelectorAll('#pieChartDropdown a').forEach(link => {
                link.addEventListener('click', function(e) {
                    e.preventDefault();
                    const timeRange = this.getAttribute('data-value');
                    const buttonText = this.textContent;
                    document.querySelector('.pie-charts-row').previousElementSibling.querySelector('.dropbtn').textContent = buttonText;
                    createPieCharts(chartData[timeRange].histogram);
                });
            });

            document.querySelectorAll('#sankeyDropdown a').forEach(link => {
                link.addEventListener('click', function(e) {
                    e.preventDefault();
                    const timeRange = this.getAttribute('data-value');
                    const buttonText = this.textContent;
                    document.querySelector('.sankey-section .dropbtn').textContent = buttonText;
                    createSankeyDiagrams(chartData[timeRange].sankey);
                });
            });
        })
        .catch(error => {
            console.error('Error preloading chart data:', error);
        });

    // Initialize user analysis charts
    updateUserAnalysis('all');

    // Add event listeners for user analysis dropdown
    document.querySelectorAll('#userAnalysisDropdown a').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const timeRange = this.getAttribute('data-value');
            const buttonText = this.textContent;
            document.querySelector('.user-analysis-section .dropbtn').textContent = buttonText;
            updateUserAnalysis(timeRange);
            toggleUserAnalysisDropdown();
        });
    });

    // Load initial data with 'all' time range
    updatePieCharts('all');

    // Add this to your document.addEventListener('DOMContentLoaded', function() {...})
    fetch('/get_mach_trades/7')  // Default to 7 days
        .then(response => response.json())
        .then(data => createMachTradesChart(data));

    fetch('/get_mach_chain_volume/7')
        .then(response => response.json())
        .then(data => createMachChainVolumeChart(data));

    fetch('/get_mach_asset_volume/7')
        .then(response => response.json())
        .then(data => createMachAssetVolumeChart(data));

    // Add event listeners for mach trades dropdown
    document.querySelectorAll('#machTradesDropdown a').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const days = this.getAttribute('data-value');
            const buttonText = this.textContent;
            document.querySelector('.mach-trades-time-selector .dropbtn').textContent = buttonText;
            
            // Update trades chart
            fetch(`/get_mach_trades/${days}`)
                .then(response => response.json())
                .then(data => createMachTradesChart(data));
            
            toggleMachTradesDropdown();
        });
    });

    // Initial load with 30 days
    fetch('/get_fill_time_data/30')
        .then(response => response.json())
        .then(data => createFillTimeVisualizations(data));

    // Add event listeners for fill time dropdown
    document.querySelectorAll('#fillTimeDropdown a').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const days = this.getAttribute('data-value');
            const buttonText = this.textContent;
            document.querySelector('.fill-time-section .dropbtn').textContent = buttonText;
            
            fetch(`/get_fill_time_data/${days}`)
                .then(response => response.json())
                .then(data => createFillTimeVisualizations(data));
            
            toggleFillTimeDropdown();
        });
    });

    // Add event listeners for long term dropdown
    document.querySelectorAll('#longTermDropdown a').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const timeRange = this.getAttribute('data-value');
            const buttonText = this.textContent;
            document.querySelector('.long-term-section .dropbtn').textContent = buttonText;
            
            updateLongTermCharts(timeRange);  // This is the function we want to debug
            toggleLongTermDropdown();
        });
    });
});

function initVolumeDistribution() {
    console.log('Initializing volume distribution charts');
    // Your initialization code for volume distribution
}

function updateVolumeDistribution(timeRange) {
    console.log('Fetching data for timeRange:', timeRange);
    
    fetch(`/histogram_data/${timeRange}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Received histogram data:', data);
            
            if (data.error) {
                console.error('Error from server:', data.error);
                return;
            }

            if (!data.chains || !data.volumes || !data.assets) {
                console.error('Invalid data structure:', data);
                return;
            }

            createVolumeHistograms(data);
        })
        .catch(error => {
            console.error('Error in updateVolumeDistribution:', error);
        });
}

function createVolumeHistograms(data) {
    console.log('Creating histograms with data:', data);

    // Ensure "Other" is always last and grey
    const otherIndex = data.assets.indexOf('Other');
    if (otherIndex !== -1) {
        data.assets.splice(otherIndex, 1);
        data.volumes.forEach(chainVolumes => {
            const otherVolume = chainVolumes.splice(otherIndex, 1)[0];
            chainVolumes.push(otherVolume);
        });
        data.assets.push('Other');
    }

    // Create color scale with more distinct colors
    const colors = [
        '#1f77b4',  // blue
        '#ff7f0e',  // orange
        '#2ca02c',  // green
        '#d62728',  // red
        '#9467bd',  // purple
        '#8c564b',  // brown
        '#e377c2',  // pink
        '#17becf',  // cyan
        '#bcbd22',  // yellow-green
        '#7b4173',  // dark purple
        '#e6550d',  // dark orange
        '#31a354',  // darker green
        '#756bb1',  // indigo
        '#636363'   // dark grey
    ];
    colors.push('#7f7f7f');  // grey for "Other"

    const traces = data.assets.map((asset, i) => ({
        name: asset,
        type: 'bar',
        x: data.chains,
        y: data.volumes.map(chainVolumes => chainVolumes[i] || 0),
        marker: { color: colors[i] },
        hovertemplate: `${asset}<br>$%{y:,.2f}<extra></extra>`,  // Simple hover showing just asset name and value
        showlegend: true
    }));

    const layout = {
        title: '',
        barmode: 'stack',
        showlegend: true,
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#ffffff' },
        xaxis: {
            title: 'Chain',
            gridcolor: '#333',
            color: '#ffffff',
            tickangle: -45
        },
        yaxis: {
            title: 'Volume (USD)',
            gridcolor: '#333',
            color: '#ffffff',
            type: 'log'
        },
        legend: {
            orientation: 'h',
            y: -0.2,
            yanchor: 'top',
            xanchor: 'center',
            x: 0.5,
            bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#ffffff' }
        },
        margin: { 
            t: 40,
            b: 150,
            l: 80,
            r: 20
        },
        height: 700,
        hovermode: 'closest'  // Changed to 'closest' to only show nearest point
    };

    const config = {
        responsive: true,
        displayModeBar: false
    };

    // Create the plots
    Plotly.newPlot('sourceVolumeHistogram', traces, layout, config);
    Plotly.newPlot('destVolumeHistogram', traces, layout, config);
    Plotly.newPlot('totalVolumeHistogram', traces, layout, config);
}

function createPieCharts(data) {
    // Define a larger set of distinct colors
    const distinctColors = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEEAD',
        '#D4A5A5', '#9B59B6', '#3498DB', '#E67E22', '#2ECC71',
        '#F1C40F', '#E74C3C', '#1ABC9C', '#34495E', '#8E44AD',
        '#F39C12', '#16A085', '#2980B9', '#C0392B', '#27AE60'
    ];

    // Function to process data and ensure "Other" is last with grey color
    function processChartData(labels, values) {
        const otherIndex = labels.indexOf('Other');
        if (otherIndex !== -1) {
            // Remove "Other" from current position
            labels.splice(otherIndex, 1);
            const otherValue = values.splice(otherIndex, 1)[0];
            // Add "Other" to the end
            labels.push('Other');
            values.push(otherValue);
        }
        
        // Create colors array with grey for "Other"
        const colors = labels.map((label, index) => 
            label === 'Other' ? '#808080' : distinctColors[index]
        );
        
        return { labels, values, colors };
    }

    // Chain Volume Pie Chart
    const chainData = processChartData([...data.chains], [...data.chain_volumes]);
    const chainTrace = {
        type: 'pie',
        hole: 0.4,
        textinfo: 'none',
        marker: { colors: chainData.colors },
        values: chainData.values,
        labels: chainData.labels,
        name: 'Chain Distribution',
        hovertemplate: '%{label}<br>Volume: $%{value:,.2f}<br>Percentage: %{percent:.1%}<extra></extra>'
    };

    // Asset Volume Pie Chart
    const assetData = processChartData([...data.assets], [...data.asset_volumes]);
    const assetTrace = {
        type: 'pie',
        hole: 0.4,
        textinfo: 'none',
        marker: { colors: assetData.colors },
        values: assetData.values,
        labels: assetData.labels,
        name: 'Asset Distribution',
        hovertemplate: '%{label}<br>Volume: $%{value:,.2f}<br>Percentage: %{percent:.1%}<extra></extra>'
    };

    const commonLayout = {
        showlegend: true,
        legend: {
            orientation: 'v',
            yanchor: 'bottom',
            y: -0.8,
            xanchor: 'center',
            x: 0.5
        },
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#ffffff' },
        height: 800,
        width: 600
    };

    // Create the plots with hover event handlers
    Plotly.newPlot('chainPie', [chainTrace], {...commonLayout, title: ''})
        .then(function(gd) {
            gd.on('plotly_hover', function(data) {
                const pt = data.points[0];
                console.log('Chain Hover Data:', {
                    label: pt.label,
                    value: pt.value,
                    percent: pt.percent,
                    curveNumber: pt.curveNumber,
                    pointNumber: pt.pointNumber,
                    text: pt.text
                });
            });
        });

    Plotly.newPlot('assetPie', [assetTrace], {...commonLayout, title: ''})
        .then(function(gd) {
            gd.on('plotly_hover', function(data) {
                const pt = data.points[0];
                console.log('Asset Hover Data:', {
                    label: pt.label,
                    value: pt.value,
                    percent: pt.percent,
                    curveNumber: pt.curveNumber,
                    pointNumber: pt.pointNumber,
                    text: pt.text
                });
            });
        });
}

function updatePieCharts(timeRange) {
    fetch(`/pie_data/${timeRange}`)
        .then(response => response.json())
        .then(data => {
            if (!data.chains || !data.chain_volumes || !data.assets || !data.asset_volumes) {
                console.error('Invalid pie data structure:', data);
                return;
            }
            createPieCharts(data);
        })
        .catch(error => {
            console.error('Error loading pie data:', error);
        });
}

function createSankeyDiagrams(data) {
    const commonLayout = {
        font: { 
            color: '#ffffff', 
            size: 14
        },
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        height: 500,
        margin: { t: 30, b: 30, l: 30, r: 30 }
    };

    // Helper function to get unique nodes
    function getUniqueNodes(data, sourceKey, targetKey) {
        const sourceNodes = [...new Set(data.map(d => d[sourceKey]))];
        const targetNodes = [...new Set(data.map(d => d[targetKey]))];
        return { sourceNodes, targetNodes };
    }

    // Asset Flow Sankey
    const assetNodes = getUniqueNodes(data.top_asset_data, 'source_id', 'dest_id');
    const assetSankey = {
        type: "sankey",
        orientation: "h",
        valueformat: "$,.0f",
        valuesuffix: " USD",
        arrangement: "snap",
        node: {
            pad: 15,
            thickness: 30,
            line: { color: "black", width: 0.5 },
            label: [...assetNodes.sourceNodes, ...assetNodes.targetNodes],
            color: '#1f77b4',
            x: [...Array(assetNodes.sourceNodes.length).fill(0), 
            ...Array(assetNodes.targetNodes.length).fill(1)],
            font: { color: '#ffffff', size: 14 }  // Set node label color to white
        },
        link: {
            source: data.top_asset_data.map(d => assetNodes.sourceNodes.indexOf(d.source_id)),
            target: data.top_asset_data.map(d => assetNodes.targetNodes.indexOf(d.dest_id) + assetNodes.sourceNodes.length),
            value: data.top_asset_data.map(d => d.avg_volume),
            color: data.top_asset_data.map(d => `rgba(31, 119, 180, 0.4)`)
        }
    };

    // Chain Flow Sankey
    const chainNodes = getUniqueNodes(data.top_chain_data, 'source_chain', 'dest_chain');
    const chainSankey = {
        type: "sankey",
        orientation: "h",
        valueformat: "$,.0f",
        valuesuffix: " USD",
        arrangement: "snap",
        node: {
            pad: 15,
            thickness: 30,
            line: { color: "black", width: 0.5 },
            label: [...chainNodes.sourceNodes, ...chainNodes.targetNodes],
            color: '#1f77b4',
            x: [...Array(chainNodes.sourceNodes.length).fill(0), 
                ...Array(chainNodes.targetNodes.length).fill(1)],
            font: { color: '#ffffff', size: 14 }  // Set node label color to white
        },
        link: {
            source: data.top_chain_data.map(d => chainNodes.sourceNodes.indexOf(d.source_chain)),
            target: data.top_chain_data.map(d => chainNodes.targetNodes.indexOf(d.dest_chain) + chainNodes.sourceNodes.length),
            value: data.top_chain_data.map(d => d.avg_volume),
            color: data.top_chain_data.map(d => `rgba(31, 119, 180, 0.4)`)
        }
    };

    // Asset-Chain Pair Flow Sankey
    const pairNodes = getUniqueNodes(data.top_pair_data, 'source_pair', 'dest_pair');
    const pairSankey = {
        type: "sankey",
        orientation: "h",
        valueformat: "$,.0f",
        valuesuffix: " USD",
        arrangement: "snap",
        node: {
            pad: 15,
            thickness: 30,
            line: { color: "black", width: 0.5 },
            label: [...pairNodes.sourceNodes, ...pairNodes.targetNodes],
            color: '#1f77b4',
            x: [...Array(pairNodes.sourceNodes.length).fill(0), 
                ...Array(pairNodes.targetNodes.length).fill(1)],
            font: { color: '#ffffff', size: 14 }  // Set node label color to white
        },
        link: {
            source: data.top_pair_data.map(d => pairNodes.sourceNodes.indexOf(d.source_pair)),
            target: data.top_pair_data.map(d => pairNodes.targetNodes.indexOf(d.dest_pair) + pairNodes.sourceNodes.length),
            value: data.top_pair_data.map(d => d.avg_volume),
            color: data.top_pair_data.map(d => `rgba(31, 119, 180, 0.4)`)
        }
    };

    Plotly.newPlot('assetSankey', [assetSankey], commonLayout);
    Plotly.newPlot('chainSankey', [chainSankey], commonLayout);
    Plotly.newPlot('pairSankey', [pairSankey], commonLayout);
}

function updateSankeyDiagrams(timeRange) {
    const validTimeRange = timeRange === 'all' ? 'all' : timeRange.toString();
    
    fetch(`/sankey_data/${validTimeRange}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            createSankeyDiagrams(data);
        })
        .catch(error => {
            console.error('Error loading Sankey data:', error);
        });
}

function getChainColors(chains) {
    const colorMap = {
        'ethereum': '#627EEA',
        'arbitrum': '#28A0F0',
        'optimism': '#FF0420',
        'polygon': '#8247E5',
        'base': '#0052FF',
        'bsc': '#F3BA2F',
        'solana': '#14F195',
        'avalanche': '#E84142',
        'celo': '#35D07F',
        'mantle': '#000000',
        'scroll': '#FDF2F8',
        'opbnb': '#F0B90B'
    };
    
    return chains.map(chain => colorMap[chain.toLowerCase()] || '#808080');
}

function updatePieCharts(timeRange) {
    fetch(`/pie_data/${timeRange}`)
        .then(response => response.json())
        .then(data => {
            console.log('Received pie data:', data);
            createPieCharts(data);
        })
        .catch(error => {
            console.error('Error loading pie data:', error);
        });
}

// Make sure updateCharts is defined and includes pie charts
function updateCharts(timeRange) {
    updateHistograms(timeRange);
    updatePieCharts(timeRange);
    updateSankey(timeRange);
}

function createUserAnalysisCharts(data) {
    // Create trade distribution chart
    const tradeTrace = {
        x: data.trade_rank.map(d => d.n),
        y: data.trade_rank.map(d => d.percentage_of_total_trades),
        type: 'bar',
        name: 'Trade Distribution',
        text: data.trade_rank.map(d => d.percentage_of_total_trades.toFixed(1) + '%'),
        textposition: 'outside',
        marker: {
            color: '#1f77b4'
        }
    };

    const tradeLayout = {
        title: '',
        xaxis: {
            title: 'Top N Users',
            gridcolor: '#333',
            color: '#ffffff'
        },
        yaxis: {
            title: 'Percentage of Total Trades',
            gridcolor: '#333',
            color: '#ffffff'
        },
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#ffffff' },
        margin: { t: 30, b: 80, l: 80, r: 30 }
    };

    // Create volume distribution chart
    const volumeTrace = {
        x: data.volume_rank.map(d => d.top_n),
        y: data.volume_rank.map(d => d.percentage_of_total_volume),
        type: 'bar',
        name: 'Volume Distribution',
        text: data.volume_rank.map(d => d.percentage_of_total_volume.toFixed(1) + '%'),
        textposition: 'outside',
        marker: {
            color: '#1f77b4'
        }
    };

    const volumeLayout = {
        title: '',
        xaxis: {
            title: 'Top N Users',
            gridcolor: '#333',
            color: '#ffffff'
        },
        yaxis: {
            title: 'Percentage of Total Volume',
            gridcolor: '#333',
            color: '#ffffff'
        },
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#ffffff' },
        margin: { t: 30, b: 80, l: 80, r: 30 }
    };

    // Filter out blank addresses and create tables with truncated addresses
    const tradeTable = `
        <table>
            <thead>
                <tr>
                    <th style="width: 10%">Rank</th>
                    <th style="width: 60%">User ID</th>
                    <th style="width: 30%">Number of Trades</th>
                </tr>
            </thead>
            <tbody>
                ${data.trade_address
                    .filter(row => row.address && row.address.trim() !== '')
                    .map((row, i) => `
                        <tr>
                            <td>${i + 1}</td>
                            <td>
                                <span class="truncate-address" 
                                      title="Click to view full address"
                                      onclick="showFullAddress('${row.address}')"
                                      style="cursor: pointer">
                                    ${truncateAddress(row.address)}
                                </span>
                            </td>
                            <td>${row.trade_count}</td>
                        </tr>
                    `).join('')}
            </tbody>
        </table>
    `;

    const volumeTable = `
        <table>
            <thead>
                <tr>
                    <th style="width: 10%">Rank</th>
                    <th style="width: 60%">User ID</th>
                    <th style="width: 30%">Total Volume</th>
                </tr>
            </thead>
            <tbody>
                ${data.volume_address
                    .filter(row => row.address && row.address.trim() !== '')
                    .map((row, i) => `
                        <tr>
                            <td>${i + 1}</td>
                            <td>
                                <span class="truncate-address" 
                                      title="Click to view full address"
                                      onclick="showFullAddress('${row.address}')"
                                      style="cursor: pointer">
                                    ${truncateAddress(row.address)}
                                </span>
                            </td>
                            <td>$${row.total_user_volume.toLocaleString('en-US', {maximumFractionDigits: 2})}</td>
                        </tr>
                    `).join('')}
            </tbody>
        </table>
    `;

    // Plot charts and update tables
    Plotly.newPlot('tradeDistributionChart', [tradeTrace], tradeLayout);
    Plotly.newPlot('volumeDistributionChart', [volumeTrace], volumeLayout);
    document.getElementById('tradeTable').innerHTML = tradeTable;
    document.getElementById('volumeTable').innerHTML = volumeTable;
}

function updateUserAnalysis(timeRange) {
    const validTimeRange = timeRange === 'all' ? 'all' : timeRange.toString();
    
    fetch(`/user_analysis/${validTimeRange}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            createUserAnalysisCharts(data);
        })
        .catch(error => {
            console.error('Error loading user analysis data:', error);
        });
}

// Add these new helper functions
function truncateAddress(address) {
    if (address.length > 20) {
        return address.substring(0, 10) + '...' + address.substring(address.length - 10);
    }
    return address;
}

function showFullAddress(address) {
    // Create modal if it doesn't exist
    let modal = document.getElementById('addressModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'addressModal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <span class="close">&times;</span>
                <h3>Full Address</h3>
                <p id="fullAddress"></p>
            </div>
        `;
        document.body.appendChild(modal);

        // Add close button functionality
        modal.querySelector('.close').onclick = function() {
            modal.style.display = 'none';
        };

        // Close modal when clicking outside
        window.onclick = function(event) {
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        };
    }

    // Update and show modal
    document.getElementById('fullAddress').textContent = address;
    modal.style.display = 'block';
}

function updateShortTermCharts(days) {
    console.log('Starting updateShortTermCharts with days:', days);
    
    // Update button text
    const button = document.querySelector('.daily-charts-section .dropbtn');
    if (button) {
        button.textContent = `Last ${days} ${days === '1' ? 'Day' : 'Days'}`;
    }

    fetch(`/short_term_data/${days}`)
        .then(response => {
            console.log('Response received:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Data received:', data);
            if (!data || !data.result) {
                console.error('No data received from server');
                return;
            }
            createCumulativeCharts(data.result);
        })
        .catch(error => {
            console.error('Error in updateShortTermCharts:', error);
        });
}

function createCumulativeCharts(data) {
    console.log("Initial data for cumulative charts:", data);

    // Common layout settings
    const commonLayout = {
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#ffffff' },
        xaxis: {
            gridcolor: '#333',
            color: '#ffffff',
            title: 'Time',
            type: 'date',
            tickformat: '%H:%M\n%b %d'
        },
        yaxis: {
            gridcolor: '#333',
            color: '#ffffff'
        },
        height: 400,
        margin: { t: 30, b: 50, l: 60, r: 20 }
    };

    // Calculate cumulative values
    let cumulativeVolume = 0;
    let cumulativeTrades = 0;
    const uniqueUsers = new Set();

    const processedData = data.map(d => {
        cumulativeVolume += Number(d.volume_total) || 0;
        cumulativeTrades += Number(d.trades_count) || 0;
        
        // Safely handle wallets array
        try {
            const walletsArray = d.wallets || [];
            if (Array.isArray(walletsArray)) {
                walletsArray.forEach(user => uniqueUsers.add(user));
            } else if (typeof walletsArray === 'string') {
                const parsedWallets = JSON.parse(walletsArray);
                if (Array.isArray(parsedWallets)) {
                    parsedWallets.forEach(user => uniqueUsers.add(user));
                }
            }
        } catch (e) {
            console.warn('Error processing wallets:', e);
        }

        return {
            hour: new Date(d.hour),
            cumVolume: cumulativeVolume,
            cumTrades: cumulativeTrades,
            cumUsers: uniqueUsers.size
        };
    }).sort((a, b) => a.hour - b.hour);

    console.log("Processed data for cumulative charts:", processedData);

    // Create volume chart
    const volumeTrace = {
        x: processedData.map(d => d.hour),
        y: processedData.map(d => d.cumVolume),
        type: 'scatter',
        mode: 'lines',
        name: 'Cumulative Volume',
        line: { color: '#1f77b4' }
    };

    console.log("Volume trace data:", volumeTrace);

    Plotly.newPlot('cumulativeVolumeChart', [volumeTrace], {
        ...commonLayout,
        yaxis: { ...commonLayout.yaxis, title: 'Cumulative Volume (USD)' }
    }).then(function(gd) {
        gd.on('plotly_legendclick', function(data) {
            console.log("Legend click event:", data);
            setTimeout(() => {
                const visibleTraces = gd.data
                    .filter(trace => trace.visible !== 'legendonly')
                    .map(trace => ({
                        name: trace.name,
                        points: trace.x.map((x, i) => ({
                            date: x,
                            value: trace.y[i]
                        }))
                    }));
                console.log("Currently visible traces after legend click:", visibleTraces);
                console.log("Full trace data:", gd.data);
            }, 100);
        });
    });

    // Create trades chart
    const tradesTrace = {
        x: processedData.map(d => d.hour),
        y: processedData.map(d => d.cumTrades),
        type: 'scatter',
        mode: 'lines',
        name: 'Cumulative Trades',
        line: { color: '#2ca02c' }
    };
    
    Plotly.newPlot('cumulativeTradesChart', [tradesTrace], {
        ...commonLayout,
        yaxis: { ...commonLayout.yaxis, title: 'Cumulative Number of Trades' }
    });

    // Create users chart
    const usersTrace = {
        x: processedData.map(d => d.hour),
        y: processedData.map(d => d.cumUsers),
        type: 'scatter',
        mode: 'lines',
        name: 'Cumulative Users',
        line: { color: '#ff7f0e' }
    };
    
    Plotly.newPlot('cumulativeUsersChart', [usersTrace], {
        ...commonLayout,
        yaxis: { ...commonLayout.yaxis, title: 'Cumulative Number of Users' }
    });
}

function createMachTradesChart(data) {
    // Get unique chains for color assignment
    const uniqueChains = [...new Set(data.map(d => d.chain))];
    
    // Create color scale for chains
    const colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#17becf', '#bcbd22', '#7b4173'
    ];
    const chainColors = Object.fromEntries(
        uniqueChains.map((chain, i) => [chain, colors[i % colors.length]])
    );

    // Create a trace for each chain
    const traces = uniqueChains.map(chain => {
        const chainData = data.filter(d => d.chain === chain);
        return {
            name: chain,
            x: chainData.map(d => d.block_timestamp),
            y: chainData.map(d => d.cumulative_volume),
            mode: 'markers',
            type: 'scatter',
            marker: {
                // Slightly larger circles
                size: chainData.map(d => Math.max(4, Math.min(15, Math.log10(d.volume) * 4))),
                color: chainColors[chain],
                opacity: 0.7,
                // Set a consistent size in the legend
                line: { width: 0 },
                symbol: 'circle'
            },
            hovertemplate: 
                '<b>Chain:</b> %{customdata[0]}<br>' +
                '<b>Volume:</b> $%{customdata[1]:,.2f}<br>' +
                '<b>Sender:</b> %{customdata[2]}<br>' +
                '<b>Time:</b> %{x}<br>' +
                '<b>Tx Hash:</b> %{customdata[3]}<br>' +
                '<b>Cumulative Volume:</b> $%{y:,.2f}' +
                '<extra></extra>',
            customdata: chainData.map(d => [
                d.chain,
                d.volume,
                d.wallet,
                d.transaction_hash
            ]),
            visible: 'true',
            showlegend: true,
            legendgroup: chain
        };
    });

    // Add a line trace for cumulative volume
    const lineTrace = {
        name: 'Cumulative Volume',
        x: data.map(d => d.block_timestamp),
        y: data.map(d => d.cumulative_volume),
        mode: 'lines',
        type: 'scatter',
        line: {
            color: '#ffffff',
            width: 1,
            dash: 'dot'
        },
        hoverinfo: 'skip',
        showlegend: false
    };

    traces.push(lineTrace);

    const layout = {
        title: '',
        showlegend: true,
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#ffffff' },
        xaxis: {
            title: 'Time',
            gridcolor: '#333',
            color: '#ffffff',
            tickangle: -45
        },
        yaxis: {
            title: 'Cumulative Volume (USD)',
            gridcolor: '#333',
            color: '#ffffff',
            // Removed log scale
            type: 'linear',
            showgrid: true,
            gridwidth: 1,
            gridcolor: '#333'
        },
        margin: { 
            t: 30,
            b: 150,
            l: 80,
            r: 20
        },
        legend: {
            bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#ffffff' },
            yanchor: "top",
            y: 0.99,
            xanchor: "left",
            x: 1.05,
            itemsizing: 'constant'  // Makes legend symbols consistent size
        },
        hovermode: 'closest',
        grid: {
            rows: 1,
            columns: 1,
            pattern: 'independent'
        }
    };

    const config = {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['lasso2d', 'select2d']
    };

    Plotly.newPlot('machTradesChart', traces, layout, config);
}

function createMachChainVolumeChart(data) {
    // Group data by day and chain, filter out empty chain names
    const days = [...new Set(data.map(d => d.day))];
    const chains = [...new Set(data.map(d => d.chain))].filter(chain => chain !== "");
    
    const traces = chains.map(chain => ({
        name: chain,
        x: days,
        y: days.map(day => {
            const match = data.find(d => d.day === day && d.chain === chain);
            return match ? match.total_volume : 0;
        }),
        type: 'bar',
        stack: 'one',
        hovertemplate: `${chain}<br>$%{y:,.2f}<extra></extra>`,
        hoverlabel: { bgcolor: '#333' }
    }));

    const layout = {
        title: '',
        barmode: 'stack',
        showlegend: true,
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#ffffff' },
        xaxis: {
            title: 'Day',
            gridcolor: '#333',
            color: '#ffffff',
            tickangle: -45
        },
        yaxis: {
            title: 'Volume (USD)',
            gridcolor: '#333',
            color: '#ffffff'
        },
        margin: { 
            t: 30,
            b: 150,
            l: 80,
            r: 20
        },
        legend: {
            bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#ffffff' }
        },
        hovermode: 'closest'
    };

    Plotly.newPlot('machChainVolumeChart', traces, layout, {responsive: true});
}

function createMachAssetVolumeChart(data) {
    const days = [...new Set(data.map(d => d.day))];
    const assets = [...new Set(data.map(d => d.asset))];
    
    // Define a diverse color palette
    const colors = [
        '#1f77b4',  // blue
        '#ff7f0e',  // orange
        '#2ca02c',  // green
        '#d62728',  // red
        '#9467bd',  // purple
        '#8c564b',  // brown
        '#e377c2',  // pink
        '#17becf',  // cyan
        '#bcbd22',  // yellow-green
        '#7b4173',  // dark purple
        '#e6550d',  // dark orange
        '#31a354',  // darker green
        '#756bb1',  // indigo
        '#636363'   // dark grey
    ];
    
    // Calculate total volume for each asset
    const assetVolumes = assets.map(asset => ({
        name: asset,
        totalVolume: data
            .filter(d => d.asset === asset)
            .reduce((sum, d) => sum + d.total_volume, 0)
    }));
    
    // Sort assets by volume and take top 14
    const sortedAssets = assetVolumes.sort((a, b) => b.totalVolume - a.totalVolume);
    const topAssets = sortedAssets.slice(0, 14);
    const otherAssets = sortedAssets.slice(14);
    
    // Create traces for top assets
    const traces = topAssets.map(({name}, index) => {
        const displayName = name.length > 8 ? name.slice(0, 8) + '...' : name;
        return {
            name: displayName,
            fullName: name,
            x: days,
            y: days.map(day => {
                const match = data.find(d => d.day === day && d.asset === name);
                return match ? match.total_volume : 0;
            }),
            type: 'bar',
            stack: 'one',
            marker: { color: colors[index] },  // Assign color from palette
            hovertemplate: `${name}<br>$%{y:,.2f}<extra></extra>`,
            hoverlabel: { bgcolor: '#333' }
        };
    });
    
    // Create trace for "Other" assets
    if (otherAssets.length > 0) {
        const otherTrace = {
            name: 'Other',
            x: days,
            y: days.map(day => {
                const sum = otherAssets.reduce((total, {name}) => {
                    const match = data.find(d => d.day === day && d.asset === name);
                    return total + (match ? match.total_volume : 0);
                }, 0);
                return sum;
            }),
            type: 'bar',
            stack: 'one',
            marker: { color: '#7f7f7f' },
            hovertemplate: 'Other<br>$%{y:,.2f}<extra></extra>',
            hoverlabel: { bgcolor: '#333' }
        };
        traces.push(otherTrace);
    }

    const layout = {
        title: '',
        barmode: 'stack',
        showlegend: true,
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#ffffff' },
        xaxis: {
            title: 'Day',
            gridcolor: '#333',
            color: '#ffffff',
            tickangle: -45
        },
        yaxis: {
            title: 'Volume (USD)',
            gridcolor: '#333',
            color: '#ffffff'
        },
        margin: { 
            t: 30,
            b: 150,
            l: 80,
            r: 20
        },
        legend: {
            bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#ffffff' },
            title: { text: 'Hover for full names' }
        },
        hovermode: 'closest'
    };

    const config = {
        responsive: true,
        displayModeBar: false
    };

    // Create the plot and add legend hover events
    Plotly.newPlot('machAssetVolumeChart', traces, layout, config)
        .then(function(gd) {
            const legendItems = document.querySelectorAll('#machAssetVolumeChart .legend .traces text');
            
            let tooltip = document.getElementById('asset-tooltip');
            if (!tooltip) {
                tooltip = document.createElement('div');
                tooltip.id = 'asset-tooltip';
                tooltip.style.position = 'fixed';
                tooltip.style.display = 'none';
                tooltip.style.backgroundColor = '#333';
                tooltip.style.color = '#fff';
                tooltip.style.padding = '5px 10px';
                tooltip.style.borderRadius = '4px';
                tooltip.style.fontSize = '12px';
                tooltip.style.zIndex = '9999';
                document.body.appendChild(tooltip);
            }

            legendItems.forEach((item) => {
                // Find matching trace by displayed name
                const displayedName = item.textContent.trim();
                const trace = traces.find(t => t.name === displayedName);
                
                if (trace && trace.fullName && trace.name !== trace.fullName) {
                    const legendGroup = item.closest('.traces');
                    if (legendGroup) {
                        legendGroup.addEventListener('mouseenter', (e) => {
                            tooltip.textContent = trace.fullName;
                            tooltip.style.display = 'block';
                            const rect = item.getBoundingClientRect();
                            tooltip.style.left = `${rect.left}px`;
                            tooltip.style.top = `${rect.top - 25}px`;
                        });

                        legendGroup.addEventListener('mouseleave', () => {
                            tooltip.style.display = 'none';
                        });
                    }
                }
            });
        });
}

function createFillTimeVisualizations(data) {
    // Chain Pair Chart
    const chainPairTrace = {
        x: data.chain_pairs.filter((_, i) => data.median_fill_times[i] > 0),
        y: data.median_fill_times.filter(time => time > 0),
        type: 'bar',
        marker: {
            color: data.median_fill_times.filter(time => time > 0),
            colorscale: 'Viridis'
        }
    };

    const chainPairLayout = {
        title: '',
        showlegend: false,
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#ffffff' },
        xaxis: {
            title: 'Chain Pair',
            gridcolor: '#333',
            color: '#ffffff',
            tickangle: -45
        },
        yaxis: {
            title: 'Median Fill Time (seconds)',
            gridcolor: '#333',
            color: '#ffffff'
        },
        margin: { t: 30, b: 150, l: 80, r: 20 }
    };

    Plotly.newPlot('fillTimeChainPairChart', [chainPairTrace], chainPairLayout, {responsive: true});

    // Date Chart
    const validDateIndices = data.daily_medians.map((val, idx) => val > 0 ? idx : -1).filter(idx => idx !== -1);
    const dateTrace = {
        x: validDateIndices.map(i => data.dates[i]),
        y: validDateIndices.map(i => data.daily_medians[i]),
        type: 'scatter',
        mode: 'lines',
        line: { color: '#1f77b4' }
    };

    const dateLayout = {
        ...chainPairLayout,
        xaxis: {
            ...chainPairLayout.xaxis,
            title: 'Date',
            nticks: 10,  // Reduce number of ticks shown on x-axis
            tickangle: -45
        }
    };

    Plotly.newPlot('fillTimeDateChart', [dateTrace], dateLayout, {responsive: true});

    // Create tables
    createFillTimeTable('sourceChainFillTimeTable', data.source_chain_data);
    createFillTimeTable('destChainFillTimeTable', data.dest_chain_data);
    createFillTimeExtremesTable('lowestFillTimesTable', data.lowest_fill_times);
    createFillTimeExtremesTable('highestFillTimesTable', data.highest_fill_times);
}

function createFillTimeTable(tableId, data) {
    const table = document.getElementById(tableId);
    if (!table) return;

    // Sort data by fill time in ascending order
    const sortedData = [...data].sort((a, b) => a.fill_time - b.fill_time);

    table.innerHTML = `
        <div class="fill-time-table-container">
            <table>
                <thead>
                    <tr>
                        <th style="width: 15%">Rank</th>
                        <th style="width: 55%">Chain</th>
                        <th style="width: 30%">Time(s)</th>
                    </tr>
                </thead>
                <tbody>
                    ${sortedData.map((row, index) => `
                        <tr>
                            <td>${index + 1}</td>
                            <td>${row.chain}</td>
                            <td>${row.fill_time.toFixed(2)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function createFillTimeExtremesTable(tableId, data) {
    const table = document.getElementById(tableId);
    if (!table || !data || data.length === 0) {
        if (table) {
            table.innerHTML = '<p>No data available</p>';
        }
        return;
    }

    // Sort data if needed (lowest/highest)
    const sortedData = [...data].sort((a, b) => 
        tableId === 'lowestFillTimesTable' ? a.fill_time - b.fill_time : b.fill_time - a.fill_time
    );

    table.innerHTML = `
        <div class="fill-time-table-container">
            <table>
                <thead>
                    <tr>
                        <th style="width: 15%">Rank</th>
                        <th style="width: 55%">Order ID</th>
                        <th style="width: 30%">Time(s)</th>
                    </tr>
                </thead>
                <tbody>
                    ${sortedData.map((row, index) => `
                        <tr>
                            <td>${index + 1}</td>
                            <td>
                                <span class="truncate-address" 
                                      title="Click to view full address"
                                      onclick="showFullAddress('${row.address}')"
                                      style="cursor: pointer">
                                    ${truncateAddress(row.address)}
                                </span>
                            </td>
                            <td>${row.fill_time.toFixed(2)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function updateLongTermCharts(timeRange) {
    fetch(`/cumulative_data/${timeRange}`)
        .then(response => response.json())
        .then(data => {
            // Debug: Log raw data from server
            console.log('Raw data from server:', data);
            
            // Get all unique dates and sort them first
            const allDates = [...new Set(data.map(item => item.day))]
                .map(d => new Date(d))
                .sort((a, b) => a - b);
            
            // Debug: Log sorted dates
            console.log('Sorted unique dates:', allDates);
            
            // Group data by asset
            const assetData = {};
            data.forEach(item => {
                if (!assetData[item.asset]) {
                    assetData[item.asset] = [];
                }
                assetData[item.asset].push({
                    x: new Date(item.day),
                    y: item.cumulative_volume
                });
            });

            // Debug: Log data for a specific asset
            console.log('Asset data:', assetData);
            
            const traces = Object.keys(assetData).map(asset => {
                const trace = {
                    name: asset,
                    x: assetData[asset].map(d => d.x),
                    y: assetData[asset].map(d => d.y),
                    type: 'scatter',
                    mode: 'lines',
                    connectgaps: true,
                    transforms: [{
                        type: 'sort',
                        target: 'x',
                        order: 'ascending'
                    }]
                };
                return trace;
            });

            const layout = {
                title: '',
                xaxis: {
                    title: 'Time',
                    gridcolor: '#333',
                    color: '#ffffff',
                    tickangle: -45,
                    type: 'date',
                    range: [allDates[0], allDates[allDates.length - 1]],
                    autorange: false,
                    fixedrange: true,
                    constrain: 'domain'
                },
                yaxis: {
                    title: 'Cumulative Volume (USD)',
                    gridcolor: '#333',
                    color: '#ffffff'
                },
                plot_bgcolor: 'rgba(0,0,0,0)',
                paper_bgcolor: 'rgba(0,0,0,0)',
                font: { color: '#ffffff' },
                showlegend: true,
                hovermode: 'closest'
            };

            Plotly.newPlot('totalVolumeLineChart', traces, layout, {
                responsive: true,
                displayModeBar: false
            }).then(gd => {
                console.log('Plot data:', gd.data.map(trace => ({
                    name: trace.name,
                    points: trace.x.length,
                    hasGaps: trace.x.some((x, i) => 
                        i > 0 && (new Date(x) - new Date(trace.x[i-1])) > 86400000
                    )
                })));
            });
        })
        .catch(error => {
            console.error('Error updating long term charts:', error);
        });
}

document.addEventListener('DOMContentLoaded', function() {
    // Add event listeners for long term dropdown
    document.querySelectorAll('#longTermDropdown a').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const timeRange = this.getAttribute('data-value');
            const buttonText = this.textContent;
            document.querySelector('.long-term-section .dropbtn').textContent = buttonText;
            
            updateLongTermCharts(timeRange);  // This is the function we want to debug
            toggleLongTermDropdown();
        });
    });

    // Look for other initialization code that might be handling these updates
    console.log('Checking for existing event listeners on longTermDropdown');
    const dropdownLinks = document.querySelectorAll('#longTermDropdown a');
    dropdownLinks.forEach(link => {
        const events = getEventListeners(link);
        console.log('Events on dropdown link:', events);
    });
});

// Add logging to help find where the chart is being updated
const originalUpdateLineCharts = window.updateLineCharts;
window.updateLineCharts = function(...args) {
    console.log('updateLineCharts called with:', args);
    console.log('Call stack:', new Error().stack);
    return originalUpdateLineCharts.apply(this, args);
};

const originalUpdateMetrics = window.updateMetrics;
window.updateMetrics = function(...args) {
    console.log('updateMetrics called with:', args);
    console.log('Call stack:', new Error().stack);
    return originalUpdateMetrics.apply(this, args);
};

