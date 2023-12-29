document.addEventListener("DOMContentLoaded", function() {
    function updateGainsLosses(tab) {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", "/get_data?tab=" + tab, true);
        xhr.onreadystatechange = function() {
            if (xhr.readyState == 4 && xhr.status == 200) {
                var data = JSON.parse(xhr.responseText);

                // Get the canvas element
                var canvas = document.getElementById(tab + "-chart");

                // Extract the chart data and total gains/losses
                var chartData = data[tab].data;
                var totalGainsLosses = data[tab].total_gains_losses;

                // Create the line chart
                new Chart(canvas, {
                    type: 'line',
                    data: {
                        datasets: [{
                            label: tab,
                            data: chartData,
                            borderColor: 'blue',
                            fill: false
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            x: {
                                type: 'linear',
                                position: 'bottom',
                                title: {
                                    display: true,
                                    text: 'Time'
                                }
                            },
                            y: {
                                type: 'linear',
                                position: 'left',
                                title: {
                                    display: true,
                                    text: 'Price'
                                }
                            }
                        },
                        plugins: {
                            title: {
                                display: true,
                                text: 'Total Gains/Losses: ' + totalGainsLosses
                            }
                        }
                    }
                });
            }
        };
        xhr.send();
    }

    // Event listener for tab clicks
    var tabs = document.querySelectorAll("#timeScaleTabs a");
    tabs.forEach(function(tab) {
        tab.addEventListener("click", function() {
            var tabId = this.id;
            updateGainsLosses(tabId);
        });
    });

    // Initial load (for the default active tab)
    var defaultTab = document.querySelector("#timeScaleTabs .active").id;
    updateGainsLosses(defaultTab);
});