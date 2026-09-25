function toggleYtRanking(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel) return;

    const block = panel.closest('.yt-ranking-block');
    const isOpen = panel.classList.contains('open');

    document.querySelectorAll('.yt-ranking-panel.open').forEach((el) => {
        el.classList.remove('open');
        el.closest('.yt-ranking-block')?.classList.remove('active');
    });

    if (!isOpen) {
        panel.classList.add('open');
        if (block) block.classList.add('active');
    }
}

function _formatYtHorasLabel(valor) {
    const num = Number(valor || 0);
    if (num <= 0) return '0h';
    if (num < 1) return `${Math.round(num * 60)}min`;
    if (num < 10) return `${num.toFixed(1)}h`;
    return `${Math.round(num)}h`;
}

function initYoutubeCharts(youtubeData) {
    if (!youtubeData) return;
    window.charts = window.charts || {};

    const grafico = youtubeData.grafico_tempo_inscritos || {};
    if (!grafico.disponivel || window.charts.chartYtTempoInscritos) return;

    const canvas = document.getElementById('chartYtTempoInscritos');
    if (!canvas || !canvas.getContext) return;

    const labels = grafico.labels || ['Inscritos', 'Não inscritos'];
    const horas = grafico.horas || [0, 0];
    if (!horas.some((v) => Number(v) > 0)) return;

    try {
        const ctx = canvas.getContext('2d');
        window.charts.chartYtTempoInscritos = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Tempo de exibição (horas)',
                    data: horas,
                    backgroundColor: ['#FF0000', '#8B0000'],
                    borderRadius: 6,
                    maxBarThickness: 72
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label(context) {
                                const valor = context.parsed.y || 0;
                                return ` ${_formatYtHorasLabel(valor)}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Horas',
                            font: { size: 11 }
                        },
                        ticks: {
                            callback(value) {
                                return _formatYtHorasLabel(value);
                            }
                        }
                    }
                }
            }
        });
    } catch (err) {
        console.error('Erro no gráfico de tempo de inscritos YouTube:', err);
    }
}

function onYoutubeTabShown() {
    const data = (window.dashboardData || {}).youtube;
    if (!data) return;

    if (!window.charts || !window.charts.chartYtTempoInscritos) {
        initYoutubeCharts(data);
    } else {
        window.charts.chartYtTempoInscritos.resize();
    }

    if (typeof window.refreshInfoTooltips === 'function') {
        window.refreshInfoTooltips();
    }
}
