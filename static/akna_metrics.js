/**
 * Métricas AKNA unificadas — mesma fonte e fórmulas na Visão Geral e na aba Manual.
 */
(function () {
    function toNum(v) {
        if (v == null || v === '') return 0;
        var n = parseFloat(String(v).replace(/\./g, '').replace(',', '.').replace(/[^\d.\-]/g, ''));
        return isNaN(n) ? 0 : n;
    }

    function pct(num, den) {
        return den > 0 ? (num / den) * 100 : 0;
    }

    function varStr(curr, prev) {
        if (prev === 0) return curr === 0 ? '0,0%' : '+∞%';
        var v = ((curr - prev) / prev) * 100;
        return (v >= 0 ? '+' : '') + v.toFixed(1).replace('.', ',') + '%';
    }

    function varColor(str) {
        if (!str || str.indexOf('+') === 0) return '#28a745';
        if (str.indexOf('-') === 0) return '#dc3545';
        return '#666';
    }

    function parseAknaDate(item) {
        var raw = item.data_envio || item.data || item.Data || '';
        if (!raw) return null;
        var s = String(raw).trim();
        var br = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
        if (br) return new Date(br[3] + '-' + br[2].padStart(2, '0') + '-' + br[1].padStart(2, '0') + 'T12:00:00');
        var iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (iso) return new Date(iso[1] + '-' + iso[2] + '-' + iso[3] + 'T12:00:00');
        return null;
    }

    function getDefaultKpis() {
        var kpi = (((window.dashboardData || {}).akna_manual || {}).analytics || {}).kpis || {};
        return {
            total_campanhas: toNum(kpi.total_campanhas),
            total_enviados: toNum(kpi.total_enviados),
            total_entregues: toNum(kpi.total_entregues),
            total_aberturas: toNum(kpi.total_aberturas),
            total_cliques: toNum(kpi.total_cliques),
            taxa_entrega: parseFloat(kpi.taxa_entrega || 0),
            taxa_abertura: parseFloat(kpi.taxa_abertura || 0),
            taxa_clique: parseFloat(kpi.taxa_clique || 0),
            ctor: parseFloat(kpi.ctor || 0)
        };
    }

    window.getAknaAllData = function () {
        var D = window.dashboardData || {};
        if (D.akna_manual && D.akna_manual.analytics && D.akna_manual.analytics.all_data && D.akna_manual.analytics.all_data.length) {
            return D.akna_manual.analytics.all_data;
        }
        if (window.aknaOptimizer && window.aknaOptimizer.allData && window.aknaOptimizer.allData.length) {
            return window.aknaOptimizer.allData;
        }
        try {
            var el = document.getElementById('akna_all_data_json');
            if (el && el.textContent) {
                var parsed = JSON.parse(el.textContent);
                if (Array.isArray(parsed) && parsed.length) return parsed;
            }
        } catch (e) { /* ignore */ }
        if (D.akna_manual && D.akna_manual.detailed_data && D.akna_manual.detailed_data.length) {
            return D.akna_manual.detailed_data;
        }
        return [];
    };

    function filterByDateRange(allData, dStart, dEnd) {
        return (allData || []).filter(function (item) {
            var d = parseAknaDate(item);
            if (!d) return false;
            if (dStart && d < dStart) return false;
            if (dEnd && d > dEnd) return false;
            return true;
        });
    }

    function filterByTabFields(items) {
        var tipo = ((document.getElementById('akna_filter_tipo') || {}).value || '').toLowerCase();
        var assunto = ((document.getElementById('akna_filter_assunto') || {}).value || '').toLowerCase();
        var horario = ((document.getElementById('akna_filter_horario') || {}).value || '').toLowerCase();
        var acao = ((document.getElementById('akna_filter_acao') || {}).value || '').toLowerCase();
        if (!tipo && !assunto && !horario && !acao) return items;

        return items.filter(function (item) {
            if (tipo && String(item.tipo || item.campanhas || '').toLowerCase().indexOf(tipo) === -1) return false;
            if (assunto && String(item.assunto || '').toLowerCase().indexOf(assunto) === -1) return false;
            if (horario && String(item.horario || '').toLowerCase().indexOf(horario) === -1) return false;
            if (acao && String(item.acao || item.acoes || '').toLowerCase().indexOf(acao) === -1) return false;
            return true;
        });
    }

    window.calcAknaKpis = function (items) {
        items = items || [];
        var totEnv = items.reduce(function (a, i) { return a + toNum(i.enviados); }, 0);
        var totEnt = items.reduce(function (a, i) { return a + toNum(i.entregues); }, 0);
        var totAb = items.reduce(function (a, i) {
            return a + toNum(i.aberturas_unicas != null ? i.aberturas_unicas : i.aberturas);
        }, 0);
        var totCl = items.reduce(function (a, i) { return a + toNum(i.cliques); }, 0);

        return {
            total_campanhas: items.length,
            total_enviados: totEnv,
            total_entregues: totEnt,
            total_aberturas: totAb,
            total_cliques: totCl,
            taxa_entrega: pct(totEnt, totEnv),
            taxa_abertura: pct(totAb, totEnt),
            taxa_clique: pct(totCl, totEnt),
            ctor: pct(totCl, totAb)
        };
    };

    function prevRange(dStart, dEnd) {
        var dur = dEnd.getTime() - dStart.getTime();
        var prevEnd = new Date(dStart.getTime() - 1);
        var prevStart = new Date(prevEnd.getTime() - dur);
        return { prevStart: prevStart, prevEnd: prevEnd };
    }

    function setText(id, value) {
        var el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    function fmtPct(n) {
        return n.toFixed(1).replace('.', ',') + '%';
    }

    function setComp(id, curr, prev, suffix) {
        var el = document.getElementById(id);
        if (!el) return;
        var str = varStr(curr, prev);
        el.innerHTML = '<span style="color:' + varColor(str) + '">Período anterior: ' +
            (typeof prev === 'number' && suffix.indexOf('%') === -1 ? Math.round(prev).toLocaleString('pt-BR') : fmtPct(prev)) +
            suffix + ' | Variação: ' + str + '</span>';
        el.style.display = 'block';
    }

    function hideComps(ids) {
        ids.forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.style.display = 'none';
        });
    }

    function renderOverview(kpis, hasFilter) {
        setText('card-akna-taxa', fmtPct(kpis.taxa_abertura));
        setText('card-akna-small',
            kpis.total_campanhas.toLocaleString('pt-BR') + ' campanhas • ' +
            Math.round(kpis.total_enviados).toLocaleString('pt-BR') + ' enviados');

        var compEl = document.getElementById('card-akna-comparativo');
        if (!hasFilter) {
            if (compEl) compEl.style.display = 'none';
            return;
        }
    }

    function renderTab(kpis) {
        setText('akna_kpi_total_campanhas', kpis.total_campanhas);
        setText('akna_kpi_total_enviados', Math.round(kpis.total_enviados).toLocaleString('pt-BR'));
        setText('akna_kpi_taxa_entrega', fmtPct(kpis.taxa_entrega));
        setText('akna_kpi_taxa_abertura', fmtPct(kpis.taxa_abertura));
        setText('akna_kpi_taxa_clique', fmtPct(kpis.taxa_clique));
        setText('akna_kpi_ctor', fmtPct(kpis.ctor));
        setText('akna_small_entregues', Math.round(kpis.total_entregues).toLocaleString('pt-BR') + ' entregues');
        setText('akna_small_aberturas', Math.round(kpis.total_aberturas).toLocaleString('pt-BR') + ' aberturas');
        setText('akna_small_cliques', Math.round(kpis.total_cliques).toLocaleString('pt-BR') + ' cliques');
        setText('akna_total_registros_label', kpis.total_campanhas);
    }

    function renderComparatives(allData, filtered, kpis, dStart, dEnd) {
        var r = prevRange(dStart, dEnd);
        var prevItems = filterByDateRange(allData, r.prevStart, r.prevEnd);
        prevItems = filterByTabFields(prevItems);
        var prevKpis = window.calcAknaKpis(prevItems);

        setComp('akna_campanhas_comparativo', kpis.total_campanhas, prevKpis.total_campanhas, ' campanhas');
        setComp('akna_enviados_comparativo', kpis.total_enviados, prevKpis.total_enviados, ' enviados');
        setComp('akna_entrega_comparativo', kpis.taxa_entrega, prevKpis.taxa_entrega, '%');
        setComp('akna_abertura_comparativo', kpis.taxa_abertura, prevKpis.taxa_abertura, '%');
        setComp('akna_clique_comparativo', kpis.taxa_clique, prevKpis.taxa_clique, '%');
        setComp('akna_ctor_comparativo', kpis.ctor, prevKpis.ctor, '%');

        var compEl = document.getElementById('card-akna-comparativo');
        if (compEl) {
            var str = varStr(kpis.taxa_abertura, prevKpis.taxa_abertura);
            compEl.innerHTML = '<span style="color:' + varColor(str) + '">Período anterior: ' +
                fmtPct(prevKpis.taxa_abertura) + ' | Variação: ' + str + '</span>';
            compEl.style.display = 'block';
        }
    }

    /**
     * Sincroniza Visão Geral + aba Akna a partir do intervalo de datas.
     * @param {Date|null} dStart
     * @param {Date|null} dEnd
     * @param {Array|null} prefiltered - dados já filtrados (ex.: aknaOptimizer)
     */
    window.syncAknaMetrics = function (dStart, dEnd, prefiltered) {
        var compIds = [
            'akna_campanhas_comparativo', 'akna_enviados_comparativo', 'akna_entrega_comparativo',
            'akna_abertura_comparativo', 'akna_clique_comparativo', 'akna_ctor_comparativo'
        ];
        var hasFilter = !!(dStart || dEnd);
        var allData = window.getAknaAllData();

        if (!hasFilter || (!allData.length && !prefiltered)) {
            var defaults = getDefaultKpis();
            renderOverview(defaults, false);
            renderTab(defaults);
            hideComps(compIds);
            return defaults;
        }

        var filtered = prefiltered || filterByDateRange(allData, dStart, dEnd);
        if (!prefiltered) filtered = filterByTabFields(filtered);

        var kpis = window.calcAknaKpis(filtered);
        renderOverview(kpis, true);
        renderTab(kpis);

        if (dStart && dEnd && allData.length) {
            renderComparatives(allData, filtered, kpis, dStart, dEnd);
        } else {
            hideComps(compIds);
            var compEl = document.getElementById('card-akna-comparativo');
            if (compEl) compEl.style.display = 'none';
        }

        return kpis;
    };
})();
