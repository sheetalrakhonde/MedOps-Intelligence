// Global variable so the refresh button can access the anomaly data
window.currentAnomaly = null;

document.addEventListener("DOMContentLoaded", function() {
    fetch('/api/data')
        .then(response => response.json())
        .then(data => {
            
            // Populate KPIs
            document.getElementById('pred-wait-time').innerText = data.prediction.expected_wait_time + " min";

            const commonLayout = {
                font: { family: 'Inter, sans-serif' },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: { t: 50, l: 40, r: 40, b: 40 }
            };

            // Chart 1: Admissions vs Wait Time (Bar + Line)
            const trace1 = { x: data.dates, y: data.admissions, name: 'Admissions', type: 'bar', marker: { color: '#e2e8f0', borderRadius: 4 } };
            const trace2 = { x: data.dates, y: data.wait_times, name: 'Wait (min)', type: 'scatter', mode: 'lines+markers', yaxis: 'y2', line: { color: '#f43f5e', width: 3 } };
            const layout1 = { ...commonLayout, title: { text: 'Admissions vs ER Wait Time', font: { size: 16 } }, yaxis2: { overlaying: 'y', side: 'right' }, legend: { orientation: 'h', y: -0.2 } };
            Plotly.newPlot('chart-admissions-wait', [trace1, trace2], layout1);

            // Chart 2: Ward Distribution (Donut)
            const traceDonut = { labels: data.ward_labels, values: data.ward_values, type: 'pie', hole: 0.6, marker: { colors: ['#3b82f6', '#10b981', '#f59e0b'] } };
            const layoutDonut = { ...commonLayout, title: { text: 'Admissions by Ward', font: { size: 16 } }, showlegend: true, legend: { orientation: 'h', y: -0.2 } };
            Plotly.newPlot('chart-ward-donut', [traceDonut], layoutDonut);

            // Chart 3: Occupancy Rate (Area)
            const traceOcc = { x: data.dates, y: data.occupancy, type: 'scatter', fill: 'tozeroy', line: { color: '#10b981', width: 3 }, fillcolor: 'rgba(16, 185, 129, 0.1)' };
            const layoutOcc = { ...commonLayout, title: { text: 'Daily Bed Occupancy (%)', font: { size: 16 } }, yaxis: { range: [0, 100] } };
            Plotly.newPlot('chart-occupancy', [traceOcc], layoutOcc);

            // Chart 4: Patient to Staff Ratio (Line)
            const traceStaff = { x: data.dates, y: data.staff_ratio, type: 'scatter', mode: 'lines+markers', line: { color: '#8b5cf6', width: 3 } };
            const layoutStaff = { ...commonLayout, title: { text: 'Patient-to-Staff Ratio (Stress Indicator)', font: { size: 16 } } };
            Plotly.newPlot('chart-staff-ratio', [traceStaff], layoutStaff);

            // Handle Anomalies
            if (data.latest_anomaly) {
                window.currentAnomaly = data.latest_anomaly; 
                const anom = data.latest_anomaly;
                
                document.getElementById('anomaly-title').innerText = `CRITICAL: ${anom.Anomaly_Type}`;
                document.getElementById('anomaly-desc').innerText = `Ward: ${anom.Ward} | Wait: ${anom.ER_Wait_Time} min | Details: ${anom.Anomaly_Context}`;
                
                // NEW: Check if we have a saved AI plan in local storage from a previous button click
                const savedPlan = localStorage.getItem('medops_ai_plan');
                if (savedPlan) {
                    document.getElementById('ai-recommendation-panel').innerHTML = savedPlan;
                } else {
                    document.getElementById('ai-recommendation-panel').innerHTML = '<p class="text-muted mb-0"><i class="fa-solid fa-circle-info me-2"></i> Awaiting manual refresh to generate plan...</p>';
                }
                
            } else {
                window.currentAnomaly = null;
                localStorage.removeItem('medops_ai_plan'); // Clear saved plan if things are nominal
                document.getElementById('anomaly-title').innerText = "All Systems Nominal";
                document.getElementById('anomaly-title').className = "text-success fw-bold mb-1";
                document.getElementById('anomaly-desc').innerText = "No critical alerts in the current timeframe.";
                document.getElementById('ai-recommendation-panel').innerHTML = "<p class='text-success mb-0 fw-bold'><i class='fa-solid fa-check-circle me-2'></i>No action required. Operations are stable.</p>";
            }
        });
});