(function () {
    let iobAllRecords = [];
    let chartBar = null;
    let chartPie = null;

    function parseIso(iso) {
        if (!iso) return null;
        const d = new Date(iso);
        return Number.isNaN(d.getTime()) ? null : d;
    }

    function loadRecords() {
        const el = document.getElementById('iob-analytics-json');
        if (!el) return [];
        try {
            const data = JSON.parse(el.textContent || '{}');
            return Array.isArray(data.all_data) ? data.all_data : [];
        } catch (e) {
            console.warn('IOB: JSON inválido', e);
            return [];
        }
    }

    function populateGrupoFilter(records) {
        const sel = document.getElementById('iob_filter_grupo');
        if (!sel) return;
        const current = sel.value;
        const groups = [...new Set(records.map((r) => r.grupo_ferramenta).filter(Boolean))].sort();
        sel.innerHTML = '<option value="">Todos</option>';
        groups.forEach((g) => {
            const opt = document.createElement('option');
            opt.value = g;
            opt.textContent = g;
            sel.appendChild(opt);
        });
        if (groups.includes(current)) sel.value = current;
    }

    function filterRecords() {
        const start = document.getElementById('iob_filter_start')?.value;
        const end = document.getElementById('iob_filter_end')?.value;
        const grupo = document.getElementById('iob_filter_grupo')?.value || '';
        const startD = start ? new Date(start + 'T00:00:00') : null;
        const endD = end ? new Date(end + 'T23:59:59') : null;

        return iobAllRecords.filter((row) => {
            const dt = parseIso(row.data_hora_iso);
            if (startD && dt && dt < startD) return false;
            if (endD && dt && dt > endD) return false;
            if (grupo && row.grupo_ferramenta !== grupo) return false;
            return true;
        });
    }

    function aggregateTools(records) {
        const toolRows = records.filter((r) => r.tipo_evento === 'Acesso a ferramenta');
        const counter = {};
        toolRows.forEach((r) => {
            const g = r.grupo_ferramenta || 'Outros / Não identificado';
            counter[g] = (counter[g] || 0) + 1;
        });
        const labels = Object.keys(counter);
        const values = labels.map((k) => counter[k]);
        return { labels, values, toolRows };
    }

    function updateKpis(records) {
        const set = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };
        set('iob_kpi_total', records.length);
        set('iob_kpi_logins', records.filter((r) => r.tipo_evento === 'Login').length);
        set('iob_kpi_logouts', records.filter((r) => r.tipo_evento === 'Logout').length);
        set('iob_kpi_ferramentas', records.filter((r) => r.tipo_evento === 'Acesso a ferramenta').length);
        const countEl = document.getElementById('iob_table_count');
        if (countEl) countEl.textContent = records.length;
    }

    function renderTable(records) {
        const tbody = document.getElementById('iob_table_body');
        if (!tbody) return;
        if (!records.length) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:40px;color:#999;">Nenhum registro no filtro selecionado.</td></tr>';
            return;
        }
        tbody.innerHTML = records.map((r) => `
            <tr data-iso="${r.data_hora_iso || ''}" data-grupo="${r.grupo_ferramenta || ''}">
                <td>${r.data_hora || ''}</td>
                <td>${r.tipo_evento || ''}</td>
                <td>${r.grupo_ferramenta || ''}</td>
                <td>${r.acao_1 || ''}</td>
                <td>${r.acao_3 || ''}</td>
                <td title="${(r.acao_4 || '').replace(/"/g, '&quot;')}">${r.acao_4 || ''}</td>
            </tr>
        `).join('');
    }

    function renderCharts(records) {
        const { labels, values } = aggregateTools(records);
        const barCtx = document.getElementById('chartIobGruposBar');
        const pieCtx = document.getElementById('chartIobGruposPie');
        if (!barCtx || !pieCtx || typeof Chart === 'undefined') return;

        if (chartBar) chartBar.destroy();
        if (chartPie) chartPie.destroy();

        chartBar = new Chart(barCtx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Acessos',
                    data: values,
                    backgroundColor: '#1565C0',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
            },
        });

        chartPie = new Chart(pieCtx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data: values,
                    backgroundColor: ['#1565C0', '#42A5F5', '#0D47A1', '#FF9800', '#9E9E9E', '#4CAF50'],
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
            },
        });
    }

    function refreshIobDashboard() {
        const filtered = filterRecords();
        updateKpis(filtered);
        renderTable(filtered);
        renderCharts(filtered);
    }

    window.applyIobFilters = function () {
        refreshIobDashboard();
    };

    window.resetIobFilters = function () {
        const ids = ['iob_filter_start', 'iob_filter_end', 'iob_filter_grupo'];
        ids.forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        refreshIobDashboard();
    };

    window.initIobDashboard = function () {
        iobAllRecords = loadRecords();
        populateGrupoFilter(iobAllRecords);
        refreshIobDashboard();
    };

    document.addEventListener('DOMContentLoaded', function () {
        if (document.getElementById('iob')) {
            window.initIobDashboard();
        }
    });

    const origShowTab = window.showTab;
    if (typeof origShowTab === 'function') {
        window.showTab = function (tabId, element) {
            origShowTab(tabId, element);
            if (tabId === 'iob') {
                setTimeout(() => {
                    if (!iobAllRecords.length) iobAllRecords = loadRecords();
                    populateGrupoFilter(iobAllRecords);
                    refreshIobDashboard();
                }, 100);
            }
        };
    }
})();
