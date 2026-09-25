function _buildComparativeLineChart(canvasId, titleAtual, titleAnterior, hist, colors) {

    const el = document.getElementById(canvasId);

    if (!el || !el.getContext) return null;



    const labels = hist.labels || [];

    const atual = hist.atual || [];

    const anterior = hist.anterior || [];

    if (!labels.length) return null;



    const ctx = el.getContext('2d');

    return new Chart(ctx, {

        type: 'line',

        data: {

            labels: labels,

            datasets: [

                {

                    label: titleAtual,

                    data: atual,

                    borderColor: colors.atual,

                    backgroundColor: colors.fill,

                    fill: true,

                    tension: 0.3

                },

                {

                    label: titleAnterior,

                    data: anterior,

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



function initInstagramCharts(instagramData) {

    if (!instagramData) return;

    window.charts = window.charts || {};



    if (!window.charts['chartIgVisitas']) {

        try {

            const chart = _buildComparativeLineChart(

                'chartIgVisitas',

                'Visitas (período atual)',

                'Visitas (período anterior)',

                instagramData.visitas_historico || {},

                {

                    atual: '#E1306C',

                    fill: 'rgba(225, 48, 108, 0.1)',

                    anterior: '#A67C52'

                }

            );

            if (chart) window.charts['chartIgVisitas'] = chart;

        } catch (err) {

            console.error('Erro no gráfico de visitas Instagram:', err);

        }

    }



    if (!window.charts['chartIgSeguidores']) {

        try {

            const chart = _buildComparativeLineChart(

                'chartIgSeguidores',

                'Seguidores (período atual)',

                'Seguidores (período anterior)',

                instagramData.seguidores_historico || {},

                {

                    atual: '#833AB4',

                    fill: 'rgba(131, 58, 180, 0.1)',

                    anterior: '#A67C52'

                }

            );

            if (chart) window.charts['chartIgSeguidores'] = chart;

        } catch (err) {

            console.error('Erro no gráfico de seguidores Instagram:', err);

        }

    }

}



function onInstagramTabShown() {

    const data = (window.dashboardData || {}).instagram;

    if (!data) return;

    if (!window.charts || !window.charts['chartIgVisitas'] || !window.charts['chartIgSeguidores']) {

        initInstagramCharts(data);

    } else {

        window.charts['chartIgVisitas'].resize();

        window.charts['chartIgSeguidores'].resize();

    }

}



function setupInstagramCliquesCard() {

    const wrap = document.getElementById('card-ig-cliques-wrap');

    if (wrap && wrap.dataset.disponivel === 'true') {

        wrap.style.display = '';

    }

}


