document.addEventListener("DOMContentLoaded", function () {
    function showLoader(tab) {
        var chartContainer = document.getElementById(tab + "-chart-container");
        if (!chartContainer.querySelector(".loader")) {
            var loader = document.createElement("div");
            loader.className = "loader";
            chartContainer.appendChild(loader);
        }
    }

    function hideLoader(tab) {
        var chartContainer = document.getElementById(tab + "-chart-container");
        var loader = chartContainer.querySelector(".loader");
        if (loader) {
            chartContainer.removeChild(loader);
        }
    }
    function updateTab(tab) {
        showLoader(tab);
        var xhr = new XMLHttpRequest();
        xhr.open("GET", "/timescale?tab=" + tab, true);
        xhr.onreadystatechange = function () {
            if (xhr.readyState == 4 && xhr.status == 200) {
                hideLoader(tab);
                var data = JSON.parse(xhr.responseText);

                // Extract the total gains/losses and chart data
                var gainLoss = data[tab].gain_loss.toFixed(2);
                var percentChange = data[tab].percent_change.toFixed(2);
                var chartData = data[tab].chart_data;

                // Set timescale text
                var timeScale;
                if (tab === "1D") {
                    timeScale = "today";
                } else if (tab === "5D") {
                    timeScale = "past 5 days";
                } else if (tab === "1M") {
                    timeScale = "past month";
                } else if (tab === "6M") {
                    timeScale = "past 6 months";
                } else if (tab === "YTD") {
                    timeScale = "year to date";
                } else if (tab === "1Y") {
                    timeScale = "past year";
                } else {
                    timeScale = "past 5 years";
                }

                // Create a unique identifier for elements based on the tab
                var portfolioStatusElement = document.querySelector("#portfolio-status-" + tab);
                var gainsLossesElement = document.querySelector("#gains-losses-" + tab);
                var percentChangeElement = document.querySelector("#percent-change-" + tab);
                var timeScaleElement = document.querySelector("#timescale-" + tab);


                // Update the gains/losses text content
                gainsLossesElement.innerHTML = gainLoss;
                timeScaleElement.innerHTML = timeScale;

                // Update the gains/losses text color
                if (gainLoss < 0) {
                    portfolioStatusElement.className = "text-danger";
                    percentChangeElement.innerHTML = " (" + percentChange + "%) &darr;";
                    borderColour = "red";
                    backgroundColour = "rgba(255, 0, 0, 0.1)";
                } else {
                    portfolioStatusElement.className = "text-success";
                    percentChangeElement.innerHTML = " (" + percentChange + "%) &uarr;";
                    borderColour = "green";
                    backgroundColour = "rgba(0, 255, 0, 0.1)";
                }

                // Get the canvas element
                var canvas = document.getElementById(tab + "-chart");
                var ctx = canvas.getContext("2d");

                // Clear previous chart if exists
                if (window.lineChart) {
                    window.lineChart.destroy();
                }

                // Create arrays for labels (dates) and data points (balances)
                var labels = Object.keys(chartData);
                var dataPoints = Object.values(chartData);

                // Create the line chart
                window.lineChart = new Chart(ctx, {
                    type: "line",
                    data: {
                        labels: labels,
                        datasets: [{
                            label: "Portfolio Value",
                            data: dataPoints,
                            borderColor: borderColour,
                            fill: true,
                            backgroundColor: backgroundColour
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false
                    }
                });
            }
        };
        xhr.send();
    }

    // Event listener for tab clicks
    var tabs = document.querySelectorAll("#timescale-tabs a");
    tabs.forEach(function (tab) {
        tab.addEventListener("click", function () {
            var tabId = this.id;
            updateTab(tabId);
        });
    });

    // Initial load (for the default active tab)
    var defaultTab = document.querySelector("#timescale-tabs .active").id;
    updateTab(defaultTab);
});
