function _buildComparativeLineChart(canvasId, titleAtual, titleAnterior, hist, colors) {
    const el = document.getElementById(canvasId);
    if (!el || !el.getContext) return null;

    const labels = hist.labels || [];
    if (!labels.length) return null;

    const ctx = el.getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: titleAtual,
                    data: hist.atual || [],
                    borderColor: colors.atual,
                    backgroundColor: colors.fill,
                    fill: true,
                    tension: 0.3
                },
                {
                    label: titleAnterior,
                    data: hist.anterior || [],
                    borderColor: colors.anterior,
                    borderDash: [6, 4],
                    fill: false,
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }
            },
            scales: { y: { beginAtZero: true } }
        }
    });
}

const FB_CHARTS = [
    {
        id: 'chartFbVisitas',
        atual: 'Visitas (período atual)',
        anterior: 'Visitas (período anterior)',
        key: 'visitas_historico',
        colors: { atual: '#1877F2', fill: 'rgba(24, 119, 242, 0.1)', anterior: '#A67C52' }
    },
    {
        id: 'chartFbSeguidores',
        atual: 'Seguidores (período atual)',
        anterior: 'Seguidores (período anterior)',
        key: 'seguidores_historico',
        colors: { atual: '#4267B2', fill: 'rgba(66, 103, 178, 0.1)', anterior: '#A67C52' }
    },
    {
        id: 'chartFbVisualizadores',
        atual: 'Visualizadores (período atual)',
        anterior: 'Visualizadores (período anterior)',
        key: 'visualizadores_historico',
        colors: { atual: '#5B8DEF', fill: 'rgba(91, 141, 239, 0.1)', anterior: '#A67C52' }
    }
];

function initFacebookCharts(facebookData) {
    if (!facebookData) return;
    window.charts = window.charts || {};

    FB_CHARTS.forEach((cfg) => {
        if (window.charts[cfg.id]) return;
        try {
            const chart = _buildComparativeLineChart(
                cfg.id,
                cfg.atual,
                cfg.anterior,
                facebookData[cfg.key] || {},
                cfg.colors
            );
            if (chart) window.charts[cfg.id] = chart;
        } catch (err) {
            console.error(`Erro no gráfico ${cfg.id}:`, err);
        }
    });
}

function onFacebookTabShown() {
    const data = (window.dashboardData || {}).facebook;
    if (!data) return;

    const allReady = FB_CHARTS.every((cfg) => window.charts && window.charts[cfg.id]);
    if (!allReady) {
        initFacebookCharts(data);
    } else {
        FB_CHARTS.forEach((cfg) => window.charts[cfg.id].resize());
    }
}
