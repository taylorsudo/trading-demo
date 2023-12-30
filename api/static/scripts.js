document.addEventListener("DOMContentLoaded", function() {
    function updateTab(tab) {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", "/timescale?tab=" + tab, true);
        xhr.onreadystatechange = function() {
            if (xhr.readyState == 4 && xhr.status == 200) {
                var data = JSON.parse(xhr.responseText);

                // Extract the total gains/losses and chart data
                // var gainsLosses = data[tab].gain_loss;
                var gainsLosses = data[tab].gain_loss;
                var chartData = data[tab].chart_data;

                document.querySelector('#gains-losses').innerHTML = gainsLosses;

                // Update the gains/losses text colour
                if (gainsLosses < 0) {
                    document.getElementById("gains-losses").className = "text-danger";
                } else {
                    document.getElementById("gains-losses").className = "text-success";
                }

                // Get the canvas element
                var canvas = document.getElementById(tab + "-chart");
                var ctx = canvas.getContext("2d");

                // Clear previous chart if exists
                if (window.myLineChart) {
                    window.myLineChart.destroy();
                }

                // Create arrays for labels (dates) and data points (balances)
                var labels = Object.keys(chartData);
                var dataPoints = Object.values(chartData);

                // Create the line chart
                window.myLineChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Balance',
                            data: dataPoints,
                            borderColor: 'blue',
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true
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
            updateTab(tabId);
        });
    });

    // Initial load (for the default active tab)
    var defaultTab = document.querySelector("#timeScaleTabs .active").id;
    updateTab(defaultTab);
});