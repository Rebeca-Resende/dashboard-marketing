window.charts = window.charts || {};
window.siteTrendOriginals = window.siteTrendOriginals || {};
window.siteTabDefaults = window.siteTabDefaults || {};
window.siteEngajamentoOriginals = window.siteEngajamentoOriginals || {};

function parseSiteFilterDates(prefix) {
    const startEl = document.getElementById(prefix + 'Start');
    const endEl = document.getElementById(prefix + 'End');
    const start = startEl ? startEl.value : '';
    const end = endEl ? endEl.value : '';
    const dStart = start ? new Date(start + 'T00:00:00') : null;
    const dEnd = end ? new Date(end + 'T23:59:59') : null;
    return { dStart, dEnd };
}

function historicoIndicesInRange(hist, dStart, dEnd) {
    const indices = [];
    if (!hist) return indices;
    const dates = hist.dates_iso || [];
    dates.forEach((dateIso, idx) => {
        const d = new Date(dateIso + 'T12:00:00');
        if (isNaN(d.getTime())) return;
        if (dStart && d < dStart) return;
        if (dEnd && d > dEnd) return;
        indices.push(idx);
    });
    return indices;
}

function sumHistField(hist, field, indices) {
    return indices.reduce((acc, i) => acc + (parseInt((hist[field] || [])[i]) || 0), 0);
}

function avgHistField(hist, field, indices) {
    const values = indices
        .map(i => parseFloat((hist[field] || [])[i]))
        .filter(v => !isNaN(v));
    if (!values.length) return null;
    return values.reduce((a, b) => a + b, 0) / values.length;
}

function formatDurationSeconds(seconds) {
    const sec = Math.max(0, Math.round(parseFloat(seconds) || 0));
    if (sec < 60) return sec + 's';
    return Math.floor(sec / 60) + 'm ' + (sec % 60) + 's';
}

function setMetricText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function aggregateCanaisByPeriod(canaisDiario, dStart, dEnd) {
    const agg = {};
    (canaisDiario || []).forEach(row => {
        const d = new Date((row.date || '') + 'T12:00:00');
        if (isNaN(d.getTime())) return;
        if (dStart && d < dStart) return;
        if (dEnd && d > dEnd) return;
        agg[row.canal] = (agg[row.canal] || 0) + (parseInt(row.usuarios) || 0);
    });
    return agg;
}

function updateSiteTabMetrics(prefix, dStart, dEnd) {
    const site = (window.dashboardSiteData || {})[prefix];
    if (!site) return;
    const defaults = window.siteTabDefaults[prefix] || {
        metricas: site.metricas_principais || {},
        atividade: site.atividade || {},
        origem_trafego: site.origem_trafego || {}
    };

    const hist = site.historico_7d || {};
    const m = defaults.metricas || {};
    const a = defaults.atividade || {};

    if (!dStart && !dEnd) {
        setMetricText('metric-' + prefix + '-usuarios', m.usuarios_ativos || '0');
        setMetricText('metric-' + prefix + '-sessoes', m.sessoes || '0');
        setMetricText('metric-' + prefix + '-visualizacoes', m.visualizacoes || '0');
        setMetricText('metric-' + prefix + '-novos-usuarios', m.novos_usuarios || '0');
        setMetricText('metric-' + prefix + '-tempo-engajamento', m.tempo_engajamento || '0s');
        setMetricText('metric-' + prefix + '-taxa-rejeicao', m.taxa_rejeicao || '0%');
        setMetricText('metric-' + prefix + '-atividade-sessoes', a.sessoes || '0');
        setMetricText('metric-' + prefix + '-atividade-visualizacoes', a.visualizacoes || '0');
        setMetricText('metric-' + prefix + '-atividade-eventos', a.eventos || '0');
        return;
    }

    const indices = historicoIndicesInRange(hist, dStart, dEnd);
    const totalUsuarios = sumHistField(hist, 'usuarios', indices);
    const totalSessoes = sumHistField(hist, 'sessoes', indices);
    const totalVistas = sumHistField(hist, 'vistas', indices);
    const totalNovos = sumHistField(hist, 'novos_usuarios', indices);
    const avgBounce = avgHistField(hist, 'taxa_rejeicao', indices);
    const avgDuration = avgHistField(hist, 'duracao_sessao', indices);

    setMetricText('metric-' + prefix + '-usuarios', totalUsuarios);
    setMetricText('metric-' + prefix + '-sessoes', totalSessoes);
    setMetricText('metric-' + prefix + '-visualizacoes', totalVistas);
    setMetricText('metric-' + prefix + '-novos-usuarios', totalNovos);
    setMetricText('metric-' + prefix + '-tempo-engajamento', avgDuration != null ? formatDurationSeconds(avgDuration) : (m.tempo_engajamento || '0s'));
    setMetricText('metric-' + prefix + '-taxa-rejeicao', avgBounce != null ? avgBounce.toFixed(1).replace('.', ',') + '%' : (m.taxa_rejeicao || '0%'));
    setMetricText('metric-' + prefix + '-atividade-sessoes', totalSessoes);
    setMetricText('metric-' + prefix + '-atividade-visualizacoes', totalVistas);
    setMetricText('metric-' + prefix + '-atividade-eventos', a.eventos || '0');
}

function updateSiteChannelsChart(prefix, dStart, dEnd) {
    const site = (window.dashboardSiteData || {})[prefix];
    const defaults = window.siteTabDefaults[prefix];
    const chart = window.charts['chart-bar-channels-' + prefix];
    if (!chart || !site) return;

    let source;
    if (!dStart && !dEnd) {
        source = defaults ? (defaults.origem_trafego || {}) : (site.origem_trafego || {});
    } else if (site.canais_diario && site.canais_diario.length) {
        source = aggregateCanaisByPeriod(site.canais_diario, dStart, dEnd);
    } else {
        source = defaults ? (defaults.origem_trafego || {}) : (site.origem_trafego || {});
    }

    chart.data.labels = Object.keys(source);
    chart.data.datasets[0].data = Object.values(source);
    chart.update();
}

function updateSiteEngajamentoChart(prefix, dStart, dEnd) {
    const original = window.siteEngajamentoOriginals[prefix];
    const chart = window.charts['chart-' + prefix + '-engajamento'];
    if (!chart || !original) return;

    if (!dStart && !dEnd) {
        chart.data.labels = original.labels.slice();
        chart.data.datasets[0].data = original.taxa.slice();
        chart.update();
        return;
    }

    const newLabels = [];
    const newTaxa = [];
    (original.dates_iso || []).forEach((dateIso, idx) => {
        const d = new Date(dateIso + 'T12:00:00');
        if (isNaN(d.getTime())) return;
        if (dStart && d < dStart) return;
        if (dEnd && d > dEnd) return;
        newLabels.push(original.labels[idx]);
        newTaxa.push(original.taxa[idx]);
    });
    chart.data.labels = newLabels;
    chart.data.datasets[0].data = newTaxa;
    chart.update();
}

function filterSiteByDate(prefix) {
    prefix = prefix || 'site';
    const site = (window.dashboardSiteData || {})[prefix];
    if (site && !window.siteChartsInitialized[prefix]) {
        initSiteTabCharts(prefix, site);
    }

    const { dStart, dEnd } = parseSiteFilterDates(prefix);

    const chart = window.charts['chart-line-' + prefix];
    const original = window.siteTrendOriginals[prefix];
    if (chart && original) {
        const newLabels = [];
        const newUsuarios = [];
        const newVistas = [];
        const nowYear = (new Date()).getFullYear();

        original.labels.forEach((label, idx) => {
            let parsed = null;
            if (original.dates_iso && original.dates_iso[idx]) {
                parsed = new Date(original.dates_iso[idx] + 'T12:00:00');
            } else if (typeof label === 'string') {
                if (label.includes('/')) {
                    const parts = label.split('/');
                    if (parts.length === 3) {
                        parsed = new Date(parts[2], parts[1] - 1, parts[0]);
                    } else if (parts.length === 2) {
                        parsed = new Date(nowYear, parts[1] - 1, parts[0]);
                    }
                } else if (label.includes('-')) {
                    parsed = new Date(label);
                } else {
                    parsed = new Date(label);
                }
            } else {
                parsed = new Date(label);
            }

            if (parsed && !isNaN(parsed)) {
                if (dStart && parsed < dStart) return;
                if (dEnd && parsed > dEnd) return;
            }

            newLabels.push(original.labels[idx]);
            newUsuarios.push(original.usuarios[idx]);
            newVistas.push(original.vistas[idx]);
        });

        chart.data.labels = newLabels;
        chart.data.datasets[0].data = newUsuarios;
        chart.data.datasets[1].data = newVistas;
        chart.update();
    }

    updateSiteTabMetrics(prefix, dStart, dEnd);
    updateSiteChannelsChart(prefix, dStart, dEnd);
    updateSiteEngajamentoChart(prefix, dStart, dEnd);
    if (typeof window.updatePaginasTable === 'function') {
        window.updatePaginasTable(site, 'tab-' + prefix + '-paginas', dStart, dEnd, false);
    }
}

function clearFilterSite(prefix) {
    prefix = prefix || 'site';
    const s = document.getElementById(prefix + 'Start');
    const e = document.getElementById(prefix + 'End');
    if (s) s.value = '';
    if (e) e.value = '';

    const chart = window.charts['chart-line-' + prefix];
    const original = window.siteTrendOriginals[prefix];
    if (chart && original) {
        chart.data.labels = original.labels.slice();
        chart.data.datasets[0].data = original.usuarios.slice();
        chart.data.datasets[1].data = original.vistas.slice();
        chart.update();
    }

    updateSiteTabMetrics(prefix, null, null);
    updateSiteChannelsChart(prefix, null, null);
    updateSiteEngajamentoChart(prefix, null, null);
    const site = (window.dashboardSiteData || {})[prefix];
    if (typeof window.updatePaginasTable === 'function') {
        window.updatePaginasTable(site, 'tab-' + prefix + '-paginas', null, null, false);
    }
}

function resizeSiteCharts(prefix) {
    const keys = Object.keys(window.charts || {}).filter(k => k.includes(prefix));
    keys.forEach(key => {
        const chart = window.charts[key];
        if (chart && typeof chart.resize === 'function') {
            chart.resize();
        }
    });
}

function initSitePerformanceCharts(prefix, site) {
    if (!site) return;
    const isGa4Organic = site.seo_fonte === 'ga4_organico';

    window.siteTabDefaults[prefix] = {
        metricas: Object.assign({}, site.metricas_principais || {}),
        atividade: Object.assign({}, site.atividade || {}),
        origem_trafego: Object.assign({}, site.origem_trafego || {})
    };

    const elLine = document.getElementById('chart-line-' + prefix);
    if (elLine && elLine.getContext) {
        try {
            const ctxLine = elLine.getContext('2d');
            const originalLabels = (site.historico_7d && site.historico_7d.labels) ? site.historico_7d.labels : [];
            const originalUsuarios = (site.historico_7d && site.historico_7d.usuarios) ? site.historico_7d.usuarios : [];
            const originalVistas = (site.historico_7d && site.historico_7d.vistas) ? site.historico_7d.vistas : [];
            window.siteTrendOriginals[prefix] = {
                labels: originalLabels.slice(),
                dates_iso: (site.historico_7d && site.historico_7d.dates_iso) ? site.historico_7d.dates_iso.slice() : [],
                usuarios: originalUsuarios.slice(),
                vistas: originalVistas.slice()
            };
            window.charts['chart-line-' + prefix] = new Chart(ctxLine, {
                type: 'line',
                data: {
                    labels: originalLabels,
                    datasets: [
                        {
                            label: 'Usuários',
                            data: originalUsuarios,
                            borderColor: '#EA621C',
                            backgroundColor: 'rgba(234, 98, 28, 0.1)',
                            fill: true,
                            yAxisID: 'y'
                        },
                        {
                            label: 'Visualizações',
                            data: originalVistas,
                            borderColor: '#A67C52',
                            borderDash: [5, 5],
                            fill: false,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'Usuários' } },
                        y1: { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Visualizações' } }
                    }
                }
            });
        } catch (err) { console.error('Erro no gráfico de linha (' + prefix + '):', err); }
    }

    const elPie = document.getElementById('chart-pie-device-' + prefix);
    if (elPie && elPie.getContext) {
        try {
            const ctxPie = elPie.getContext('2d');
            window.charts['chart-pie-device-' + prefix] = new Chart(ctxPie, {
                type: 'doughnut',
                data: {
                    labels: Object.keys(site.dispositivos || {}),
                    datasets: [{
                        data: Object.values(site.dispositivos || {}),
                        backgroundColor: ['#EA621C', '#A67C52', '#D4C4B8']
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
            });
        } catch (err) { console.error('Erro no gráfico de pizza (' + prefix + '):', err); }
    }

    const elBar = document.getElementById('chart-bar-channels-' + prefix);
    if (elBar && elBar.getContext) {
        try {
            const ctxBar = elBar.getContext('2d');
            window.charts['chart-bar-channels-' + prefix] = new Chart(ctxBar, {
                type: 'bar',
                data: {
                    labels: Object.keys(site.origem_trafego || {}),
                    datasets: [{
                        label: 'Usuários por Canal',
                        data: Object.values(site.origem_trafego || {}),
                        backgroundColor: '#EA621C',
                        borderRadius: 5
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } }
                }
            });
        } catch (err) { console.error('Erro no gráfico de barras (' + prefix + '):', err); }
    }

    const elHora = document.getElementById('chart-' + prefix + '-atividade-hora');
    if (elHora && elHora.getContext && site.atividade) {
        try {
            const ctxHora = elHora.getContext('2d');
            window.charts['chart-' + prefix + '-atividade-hora'] = new Chart(ctxHora, {
                type: 'bar',
                data: {
                    labels: (site.atividade.por_hora && site.atividade.por_hora.labels) || [],
                    datasets: [{
                        label: 'Usuários',
                        data: (site.atividade.por_hora && site.atividade.por_hora.usuarios) || [],
                        backgroundColor: 'rgba(234, 98, 28, 0.7)',
                        borderRadius: 3
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
            });
        } catch (err) { console.error('Erro no gráfico atividade hora (' + prefix + '):', err); }
    }

    const elDia = document.getElementById('chart-' + prefix + '-atividade-dia');
    if (elDia && elDia.getContext && site.atividade) {
        try {
            const ctxDia = elDia.getContext('2d');
            window.charts['chart-' + prefix + '-atividade-dia'] = new Chart(ctxDia, {
                type: 'bar',
                data: {
                    labels: (site.atividade.por_dia_semana && site.atividade.por_dia_semana.labels) || [],
                    datasets: [{
                        label: 'Usuários',
                        data: (site.atividade.por_dia_semana && site.atividade.por_dia_semana.usuarios) || [],
                        backgroundColor: '#A67C52',
                        borderRadius: 5
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
            });
        } catch (err) { console.error('Erro no gráfico atividade dia (' + prefix + '):', err); }
    }

    const elEng = document.getElementById('chart-' + prefix + '-engajamento');
    if (elEng && elEng.getContext && site.atividade) {
        try {
            const engData = site.atividade.engajamento_diario || {};
            window.siteEngajamentoOriginals[prefix] = {
                labels: (engData.labels || []).slice(),
                dates_iso: (engData.dates_iso || []).slice(),
                taxa: (engData.taxa || []).slice()
            };
            const ctxEng = elEng.getContext('2d');
            window.charts['chart-' + prefix + '-engajamento'] = new Chart(ctxEng, {
                type: 'line',
                data: {
                    labels: (site.atividade.engajamento_diario && site.atividade.engajamento_diario.labels) || [],
                    datasets: [{
                        label: 'Taxa de Engajamento (%)',
                        data: (site.atividade.engajamento_diario && site.atividade.engajamento_diario.taxa) || [],
                        borderColor: '#4A90D9',
                        backgroundColor: 'rgba(74, 144, 217, 0.1)',
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, max: 100 } } }
            });
        } catch (err) { console.error('Erro no gráfico engajamento (' + prefix + '):', err); }
    }

    const elSeoQ = document.getElementById('chart-' + prefix + '-seo-queries');
    if (elSeoQ && elSeoQ.getContext && site.seo_ranking) {
        try {
            const queries = (site.seo_ranking.top_queries || []).slice(0, 10);
            const pages = (site.seo_ranking.top_pages || [])
                .filter(p => p.page && p.page !== '(not set)')
                .slice(0, 10);
            const usePages = isGa4Organic && queries.length === 0 && pages.length > 0;
            const items = usePages ? pages : queries;
            const shortLabel = (text) => {
                if (!text) return '—';
                const clean = String(text).replace(/^https?:\/\/[^/]+/, '') || '/';
                return clean.length > 30 ? clean.substring(0, 27) + '...' : clean;
            };
            const ctxSeoQ = elSeoQ.getContext('2d');
            window.charts['chart-' + prefix + '-seo-queries'] = new Chart(ctxSeoQ, {
                type: 'bar',
                data: {
                    labels: usePages
                        ? items.map(p => shortLabel(p.page))
                        : items.map(q => (q.query && q.query.length > 30) ? q.query.substring(0, 27) + '...' : (q.query || '—')),
                    datasets: [{
                        label: usePages ? 'Sessões orgânicas' : 'Cliques',
                        data: items.map(item => item.cliques),
                        backgroundColor: '#2ecc71',
                        borderRadius: 4
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        title: usePages ? {
                            display: true,
                            text: 'Páginas orgânicas (GA4)',
                            color: '#888',
                            font: { size: 11 }
                        } : { display: false }
                    },
                    scales: { x: { beginAtZero: true } }
                }
            });
        } catch (err) { console.error('Erro no gráfico SEO queries (' + prefix + '):', err); }
    }

    const elSeoEv = document.getElementById('chart-' + prefix + '-seo-evolucao');
    if (elSeoEv && elSeoEv.getContext && site.seo_ranking) {
        try {
            const evo = site.seo_ranking.evolucao || {};
            const hasEvo = (evo.labels || []).length > 0;
            const labelCliques = isGa4Organic ? 'Sessões orgânicas' : 'Cliques';
            const labelImpressoes = isGa4Organic ? 'Visualizações' : 'Impressões';
            const ctxSeoEv = elSeoEv.getContext('2d');
            window.charts['chart-' + prefix + '-seo-evolucao'] = new Chart(ctxSeoEv, {
                type: 'line',
                data: {
                    labels: evo.labels || [],
                    datasets: [
                        { label: labelCliques, data: evo.cliques || [], borderColor: '#2ecc71', fill: false, yAxisID: 'y' },
                        { label: labelImpressoes, data: evo.impressoes || [], borderColor: '#3498db', fill: false, yAxisID: 'y1' }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: hasEvo },
                        title: (!hasEvo && isGa4Organic) ? {
                            display: true,
                            text: 'Sem tráfego orgânico no período',
                            color: '#888',
                            font: { size: 12 }
                        } : { display: false }
                    },
                    scales: {
                        y: { type: 'linear', position: 'left', beginAtZero: true, title: { display: true, text: labelCliques } },
                        y1: { type: 'linear', position: 'right', beginAtZero: true, grid: { drawOnChartArea: false }, title: { display: true, text: labelImpressoes } }
                    }
                }
            });
        } catch (err) { console.error('Erro no gráfico SEO evolução (' + prefix + '):', err); }
    }

    const elEstados = document.getElementById('chart-' + prefix + '-estados');
    if (elEstados && elEstados.getContext && site.localidades) {
        try {
            const estados = (site.localidades.estados || []).slice(0, 10);
            const ctxEstados = elEstados.getContext('2d');
            window.charts['chart-' + prefix + '-estados'] = new Chart(ctxEstados, {
                type: 'bar',
                data: {
                    labels: estados.map(e => e.estado),
                    datasets: [{
                        label: 'Usuários',
                        data: estados.map(e => e.usuarios),
                        backgroundColor: estados.map(e =>
                            e.estado && e.estado.toLowerCase().includes('santa catarina') ? '#EA621C' : '#A67C52'
                        ),
                        borderRadius: 4
                    }]
                },
                options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true } } }
            });
        } catch (err) { console.error('Erro no gráfico estados (' + prefix + '):', err); }
    }
}

window.siteChartsInitialized = window.siteChartsInitialized || {};

function initSiteTabCharts(prefix, site) {
    if (!site || window.siteChartsInitialized[prefix]) return;
    initSitePerformanceCharts(prefix, site);
    window.siteChartsInitialized[prefix] = true;
}

function initAllSitePerformanceCharts(dashboardData) {
    window.dashboardSiteData = window.dashboardSiteData || {};
    if (dashboardData.sites) {
        window.dashboardSiteData.site = dashboardData.sites;
    }
    if (dashboardData.site_conecta) {
        window.dashboardSiteData.conecta = dashboardData.site_conecta;
    }
}

function onSiteTabShown(tabId) {
    const map = { sites: 'site', 'site-conecta': 'conecta' };
    const prefix = map[tabId];
    if (!prefix) return;
    const site = (window.dashboardSiteData || {})[prefix];
    if (!site) return;
    if (!window.siteChartsInitialized[prefix]) {
        initSiteTabCharts(prefix, site);
    }
    setTimeout(() => resizeSiteCharts(prefix), 120);
}
