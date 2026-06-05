// Store chart instances globally so we can destroy and recreate them
let trendChartInstance = null;
let probChartInstance = null;
let featureChartInstance = null;
let currentPredictionResult = null;
let selectedTimeframe = 60;

// Setup Chart.js global defaults for dark theme
Chart.defaults.color = '#94a3b8';
Chart.defaults.font.family = "'Plus Jakarta Sans', sans-serif";
Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(15, 23, 42, 0.9)';
Chart.defaults.plugins.tooltip.titleColor = '#fff';
Chart.defaults.scale.grid.color = 'rgba(255, 255, 255, 0.05)';

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('prediction-form');
    const btn = document.getElementById('predict-btn');
    const fetchBtn = document.getElementById('fetch-data-btn');
    const welcomeState = document.getElementById('welcome-state');
    const resultsDashboard = document.getElementById('results-dashboard');

    fetchBtn.addEventListener('click', async () => {
        const originalText = fetchBtn.innerText;
        fetchBtn.innerText = 'Mengambil Data...';
        fetchBtn.disabled = true;

        try {
            const response = await fetch('/fetch_data');
            const result = await response.json();
            
            if (result.success) {
                if(result.data.USDIDR) document.getElementById('USDIDR').value = result.data.USDIDR;
                if(result.data.DXY) document.getElementById('DXY').value = result.data.DXY;
                if(result.data.VIX) document.getElementById('VIX').value = result.data.VIX;
                if(result.data.IHSG) document.getElementById('IHSG').value = result.data.IHSG;
            } else {
                alert('Gagal mengambil data: ' + result.error);
            }
        } catch (error) {
            console.error('Error fetching data:', error);
            alert('Gagal terhubung ke server untuk mengambil data aktual.');
        } finally {
            fetchBtn.innerText = originalText;
            fetchBtn.disabled = false;
        }
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Visual feedback
        const originalText = btn.innerText;
        btn.innerText = 'Memproses Data...';
        btn.style.opacity = '0.8';
        btn.disabled = true;

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch('/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                welcomeState.style.display = 'none';
                resultsDashboard.classList.remove('hidden');
                updateDashboard(result);
            } else {
                alert('Error memproses prediksi: ' + result.error);
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Gagal terhubung ke server prediksi.');
        } finally {
            btn.innerText = originalText;
            btn.style.opacity = '1';
            btn.disabled = false;
        }
    });

    // Timeframe selector buttons
    document.querySelectorAll('.tf-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedTimeframe = parseInt(btn.getAttribute('data-days'));
            if (currentPredictionResult) {
                renderTrendChart(currentPredictionResult);
            }
        });
    });
});

function updateDashboard(res) {
    currentPredictionResult = res;

    // 1. Update Summary Card
    const labelText = document.getElementById('label-text');
    const statusBadge = document.getElementById('status-badge');
    const valReturn = document.getElementById('val-return');
    const valPrice = document.getElementById('val-price');

    labelText.innerText = res.predicted_label;
    statusBadge.className = 'status-badge'; // reset
    if (res.predicted_class === 0) statusBadge.classList.add('menguat');
    else if (res.predicted_class === 2) statusBadge.classList.add('melemah');
    else statusBadge.classList.add('stabil');

    valReturn.innerText = (res.predicted_return_30d > 0 ? '+' : '') + res.predicted_return_30d.toFixed(2) + '%';
    
    const formatter = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', minimumFractionDigits: 0 });
    valPrice.innerText = formatter.format(res.predicted_price_30d);

    // 2. Update Context / Sentiment Card
    const riskBadge = document.getElementById('risk-level-badge');
    riskBadge.innerText = res.risk_level;
    riskBadge.style.color = res.risk_color;

    document.getElementById('sentiment-text').innerText = res.market_sentiment;
    document.getElementById('ai-insight-text').innerHTML = `<strong>Insight:</strong> ${res.ai_insight}`;

    // 3. Render Trend Chart (Historical + Future)
    renderTrendChart(res);

    // 4. Render Probability Donut
    renderProbabilityChart(res.probabilities);

    // 5. Render Feature Importance
    renderFeatureChart(res.feature_importance);
}

function renderTrendChart(res) {
    const ctx = document.getElementById('trendChart').getContext('2d');
    
    if (trendChartInstance) { trendChartInstance.destroy(); }

    let histDates = res.historical_dates;
    let histPrices = res.historical_prices;
    
    if (histDates.length > selectedTimeframe) {
        histDates = histDates.slice(-selectedTimeframe);
        histPrices = histPrices.slice(-selectedTimeframe);
    }

    const projectionDays = 30;
    let projLabels = [];
    let projData = [];
    
    const startPrice = histPrices[histPrices.length - 1] || res.latest_price;
    const endPrice = res.predicted_price_30d;
    const step = (endPrice - startPrice) / projectionDays;
    
    for (let i = 1; i <= projectionDays; i++) {
        projLabels.push(`H+${i}`);
        projData.push(startPrice + (step * i));
    }

    const labels = [...histDates, ...projLabels];
    const histData = [...histPrices, ...new Array(projectionDays).fill(null)];
    
    const predData = new Array(histPrices.length - 1).fill(null);
    predData.push(startPrice);
    predData.push(...projData);

    trendChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Historis Aktual',
                    data: histData,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: true,
                    tension: 0.1
                },
                {
                    label: 'Proyeksi Mendatang',
                    data: predData,
                    borderColor: res.predicted_class === 0 ? '#10b981' : (res.predicted_class === 2 ? '#ef4444' : '#f59e0b'),
                    backgroundColor: res.predicted_class === 0 ? 'rgba(16, 185, 129, 0.2)' : (res.predicted_class === 2 ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)'),
                    borderWidth: 4,
                    borderDash: [6, 4],
                    pointRadius: function(context) {
                        return context.dataIndex === labels.length - 1 ? 7 : 0;
                    },
                    pointBackgroundColor: '#fff',
                    pointBorderColor: res.predicted_class === 0 ? '#10b981' : (res.predicted_class === 2 ? '#ef4444' : '#f59e0b'),
                    pointBorderWidth: 3,
                    fill: true,
                    tension: 0 // Straight line for interpolation
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                x: {
                    display: false // hide dense dates
                },
                y: {
                    ticks: {
                        callback: function(value) { return 'Rp ' + value; }
                    }
                }
            },
            plugins: {
                legend: { position: 'top', align: 'end' }
            }
        }
    });
}

function renderProbabilityChart(probs) {
    const ctx = document.getElementById('probChart').getContext('2d');
    
    if (probChartInstance) { probChartInstance.destroy(); }

    probChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Menguat', 'Stabil', 'Melemah'],
            datasets: [{
                data: [probs.menguat, probs.stabil, probs.melemah],
                backgroundColor: ['#10b981', '#f59e0b', '#ef4444'],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { padding: 20 }
                }
            }
        }
    });
}

function renderFeatureChart(features) {
    const ctx = document.getElementById('featureChart').getContext('2d');
    
    if (featureChartInstance) { featureChartInstance.destroy(); }

    const labels = features.map(f => f.feature);
    const data = features.map(f => f.importance);

    featureChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Tingkat Pengaruh %',
                data: data,
                backgroundColor: 'rgba(139, 92, 246, 0.6)',
                borderColor: '#8b5cf6',
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: { display: false }
            }
        }
    });
}
