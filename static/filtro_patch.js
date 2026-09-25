/**
 * ============================================================
 * PATCH — Correção de filtro de data (Visão Geral + Akna)
 * ============================================================
 * Como usar:
 *   Adicione no index.html, logo ANTES do </body>,
 *   depois dos outros scripts:
 *
 *     <script src="static/filtro_patch.js"></script>
 *
 * O patch sobrescreve apenas as funções com bug, sem quebrar
 * nenhuma outra lógica existente.
 * ============================================================
 */

// ─── 1. UTILITÁRIOS DE DATA ──────────────────────────────────────────────────

/**
 * Converte qualquer string de data para Date às 12h (evita problema de fuso).
 * Suporta: yyyy-mm-dd | dd/mm/yyyy | mm/dd/yyyy
 */
function _parseAnyDate(s) {
    if (!s) return null;
    s = String(s).trim();

    // ISO: yyyy-mm-dd (vindo de <input type="date">)
    var iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (iso) return new Date(iso[1] + '-' + iso[2] + '-' + iso[3] + 'T12:00:00');

    // Com barra: testa dd/mm/yyyy (padrão BR)
    var slash = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    if (slash) {
        var p0 = parseInt(slash[1], 10);
        var p1 = parseInt(slash[2], 10);
        var yr = slash[3];
        var dd, mm;
        // Se primeiro campo > 12, com certeza é dd/mm/yyyy
        if (p0 > 12) {
            dd = String(p0).padStart(2,'0');
            mm = String(p1).padStart(2,'0');
        } else {
            // Assume padrão BR: dd/mm/yyyy
            dd = String(p0).padStart(2,'0');
            mm = String(p1).padStart(2,'0');
        }
        return new Date(yr + '-' + mm + '-' + dd + 'T12:00:00');
    }

    // Último recurso: construção nativa
    var d = new Date(s);
    return isNaN(d) ? null : d;
}

/**
 * Converte valor de <input type="date"> (sempre yyyy-mm-dd) para Date local.
 * endOfDay=true → 23:59:59  |  false → 00:00:00
 */
function _inputToDate(val, endOfDay) {
    if (!val) return null;
    return new Date(val + (endOfDay ? 'T23:59:59' : 'T00:00:00'));
}

// ─── 2. HELPERS NUMÉRICOS ────────────────────────────────────────────────────

function _toNum(v) {
    if (v == null || v === '') return 0;
    var n = parseFloat(
        String(v).replace(/\./g, '').replace(',', '.').replace(/[^\d.\-]/g, '')
    );
    return isNaN(n) ? 0 : n;
}

function _pct(num, den) {
    return den > 0 ? (num / den) * 100 : 0;
}

function _varStr(curr, prev) {
    if (prev === 0) return curr === 0 ? '0,0%' : '+∞%';
    var v = ((curr - prev) / prev) * 100;
    return (v >= 0 ? '+' : '') + v.toFixed(1).replace('.', ',') + '%';
}

function _varColor(str) {
    return str.startsWith('+') ? '#28a745' : '#dc3545';
}

// ─── 3. HELPERS DE DOM ───────────────────────────────────────────────────────

function _setCard(id, value) {
    console.log('🎯 _setCard chamado:', id, value);
    var el = document.getElementById(id);
    console.log('🔍 Elemento encontrado?', !!el, el);
    if (!el) return;
    
    // Formatar número com separador brasileiro
    if (typeof value === 'number') {
        el.textContent = value.toLocaleString('pt-BR');
    } else {
        el.textContent = value;
    }
    console.log('✅ Card atualizado:', el.textContent);
}

function _setComp(id, curr, prev, suffix) {
    suffix = suffix || '';
    var el = document.getElementById(id);
    if (!el) return;
    var str = _varStr(curr, prev);
    var prevFmt = (typeof prev === 'number') ? prev.toLocaleString('pt-BR') : prev;
    el.innerHTML = '<span style="color:' + _varColor(str) + '">' +
        'Período anterior: ' + prevFmt + suffix + ' | Variação: ' + str + '</span>';
    el.style.display = 'block';
}

function _hideComp(id) {
    var el = document.getElementById(id);
    if (el) el.style.display = 'none';
}

// ─── 4. SOMA DE CAMPO COM FILTRO DE DATA ─────────────────────────────────────

function _sumField(arr, dateField, numField, dStart, dEnd) {
    if (!arr || !arr.length) return 0;
    return arr.reduce(function(acc, item) {
        var d = _parseAnyDate(item[dateField]);
        if (!d) return acc;
        if (dStart && d < dStart) return acc;
        if (dEnd   && d > dEnd)   return acc;
        return acc + _toNum(item[numField]);
    }, 0);
}

/** Período anterior de mesmo tamanho, imediatamente antes de dStart */
function _prevRange(dStart, dEnd) {
    var dur = dEnd.getTime() - dStart.getTime();
    var prevEnd   = new Date(dStart.getTime() - 1);
    var prevStart = new Date(prevEnd.getTime() - dur);
    return { prevStart: prevStart, prevEnd: prevEnd };
}

// ─── 5. CARDS DA VISÃO GERAL (Instagram, Facebook, YouTube, Akna) ────────────

function _updateOverviewCards(dStart, dEnd) {
    console.log('🎯 _updateOverviewCards chamado com:', dStart, dEnd);
    var D = window.dashboardData || {};
    console.log('📊 dashboardData disponível:', !!D);
    console.log('📊 Estrutura completa dos dados:', D);
    
    // Verificar estrutura específica dos dados
    console.log('📱 Dados Instagram:', D.instagram);
    console.log('📘 Dados Facebook:', D.facebook);
    console.log('📺 Dados YouTube:', D.youtube);
    
    var hasFilter = !!(dStart && dEnd);
    console.log('🔍 Tem filtro?', hasFilter);

    // ── Instagram ──
    var igAll  = (D.instagram && D.instagram.detailed_data) || [];
    console.log('📱 Dados Instagram detailed_data:', igAll.length, 'itens');
    console.log('📱 Exemplo de item Instagram:', igAll[0]);
    
    var igCurr = hasFilter
        ? _sumField(igAll, 'data_publicacao', 'interacao', dStart, dEnd)
        : _toNum(D.instagram && D.instagram.total_interactions);
    console.log('💙 Valor Instagram calculado:', igCurr);
    
    console.log('🎯 Atualizando card-ig-interacoes...');
    _setCard('card-ig-interacoes', igCurr);
    
    if (hasFilter) {
        var igR = _prevRange(dStart, dEnd);
        _setComp('card-ig-comparativo', igCurr,
            _sumField(igAll, 'data_publicacao', 'interacao', igR.prevStart, igR.prevEnd),
            ' interações');
    } else { _hideComp('card-ig-comparativo'); }

    // ── Facebook ──
    var fbAll  = (D.facebook && D.facebook.detailed_data) || [];
    console.log('📘 Dados Facebook detailed_data:', fbAll.length, 'itens');
    console.log('📘 Exemplo de item Facebook:', fbAll[0]);
    
    var fbCurr = hasFilter
        ? _sumField(fbAll, 'data_publicacao', 'interacao', dStart, dEnd)
        : _toNum(D.facebook && D.facebook.total_interactions);
    console.log('💚 Valor Facebook calculado:', fbCurr);
    
    console.log('🎯 Atualizando card-fb-interacoes...');
    _setCard('card-fb-interacoes', fbCurr);
    
    if (hasFilter) {
        var fbR = _prevRange(dStart, dEnd);
        _setComp('card-fb-comparativo', fbCurr,
            _sumField(fbAll, 'data_publicacao', 'interacao', fbR.prevStart, fbR.prevEnd),
            ' interações');
    } else { _hideComp('card-fb-comparativo'); }

    // ── YouTube ──
    var ytAll  = (D.youtube && D.youtube.detailed_data) || [];
    console.log('📺 Dados YouTube detailed_data:', ytAll.length, 'itens');
    console.log('📺 Exemplo de item YouTube:', ytAll[0]);
    
    var ytCurr = hasFilter
        ? _sumField(ytAll, 'data_publicacao', 'visualizacoes', dStart, dEnd)
        : _toNum(D.youtube && D.youtube.total_views);
    console.log('💛 Valor YouTube calculado:', ytCurr);
    
    console.log('🎯 Atualizando card-yt-views...');
    _setCard('card-yt-views', ytCurr);
    
    if (hasFilter) {
        var ytR = _prevRange(dStart, dEnd);
        _setComp('card-yt-comparativo', ytCurr,
            _sumField(ytAll, 'data_publicacao', 'visualizacoes', ytR.prevStart, ytR.prevEnd),
            ' visualizações');
    } else { _hideComp('card-yt-comparativo'); }

    // ── YouTube: vídeo mais assistido ──
    var ytTopTitleEl = document.getElementById('card-yt-top-title');
    var ytTopViewsEl = document.getElementById('card-yt-top-views');
    var ytTopWatchEl = document.getElementById('card-yt-top-watch');

    if (ytTopTitleEl && ytTopViewsEl && ytTopWatchEl) {
        var ytVideos = ytAll;
        if (hasFilter) {
            ytVideos = ytAll.filter(function(item) {
                var d = _parseAnyDate(item.data_publicacao);
                return d && d >= dStart && d <= dEnd;
            });
        }

        if (!ytVideos.length) {
            ytTopTitleEl.textContent = 'N/A';
            ytTopViewsEl.textContent = '0';
            ytTopWatchEl.textContent = '0h';
        } else {
            var topVideo = ytVideos.reduce(function(best, item) {
                if (!best) return item;
                return _toNum(item.visualizacoes) > _toNum(best.visualizacoes) ? item : best;
            }, null);

            ytTopTitleEl.textContent = topVideo.titulo_descricao || topVideo.titulo || 'N/A';
            ytTopViewsEl.textContent = Math.round(_toNum(topVideo.visualizacoes)).toLocaleString('pt-BR');
            ytTopWatchEl.textContent = topVideo.watch_time || topVideo.duracao || '0h';
        }
    }

    // ── Akna (Visão Geral + aba Manual) ──
    if (typeof window.syncAknaMetrics === 'function') {
        window.syncAknaMetrics(dStart, dEnd);
    }

    // ── Acessos ao Site (Borracha + ABIARB CONECTA) e origem dos visitantes ──
    if (typeof window.updateSiteAndSocialOverview === 'function') {
        window.updateSiteAndSocialOverview(D, dStart, dEnd);
    }
}

// ─── 6. AKNA — delegado para static/akna_metrics.js ─────────────────────────

window._updateAknaTabCards = function (dStart, dEnd) {
    if (typeof window.syncAknaMetrics === 'function') {
        window.syncAknaMetrics(dStart, dEnd);
    }
};

// ─── 8. SOBRESCREVE filterAllTables / resetAllTables ─────────────────────────

window.filterAllTables = function(start, end) {
    var dStart = _inputToDate(start, false);
    var dEnd   = _inputToDate(end,   true);
    _updateOverviewCards(dStart, dEnd);
    if (typeof updateAllCharts === 'function') updateAllCharts(start, end);
    if (typeof window.updateSiteAndSocialOverview === 'function') {
        window.updateSiteAndSocialOverview(window.dashboardData || {}, dStart, dEnd);
    }
};

window.resetAllTables = function() {
    _updateOverviewCards(null, null);
    window._updateAknaTabCards(null, null);
};

// ─── 9. SOBRESCREVE applyGlobalFilter ────────────────────────────────────────

window.applyGlobalFilter = function() {
    console.log('🚀 applyGlobalFilter chamado!');
    var start = (document.getElementById('global-start-date') || {}).value || '';
    var end   = (document.getElementById('global-end-date')   || {}).value || '';
    console.log('📅 Datas do filtro:', start, end);
    var dStart = _inputToDate(start, false);
    var dEnd   = _inputToDate(end,   true);
    console.log('📆 Datas convertidas:', dStart, dEnd);

    // Sincroniza inputs individuais dos gráficos
    document.querySelectorAll('.individual-start').forEach(function(el) { el.value = start; });
    document.querySelectorAll('.individual-end').forEach(function(el)   { el.value = end;   });

    // Tabelas individuais
    ['ytStart','fbStart','igStart'].forEach(function(id) {
        var el = document.getElementById(id); if (el) el.value = start;
    });
    ['ytEnd','fbEnd','igEnd'].forEach(function(id) {
        var el = document.getElementById(id); if (el) el.value = end;
    });
    if (typeof filterTableYT === 'function') filterTableYT();
    if (typeof filterTableFB === 'function') filterTableFB();
    if (typeof filterTableIG === 'function') filterTableIG();

    // Site (aba individual + cards na Visão Geral)
    var ss = document.getElementById('siteStart'); if (ss) ss.value = start;
    var se = document.getElementById('siteEnd');   if (se) se.value = end;
    var cs = document.getElementById('conectaStart'); if (cs) cs.value = start;
    var ce = document.getElementById('conectaEnd');   if (ce) ce.value = end;
    if (typeof filterSiteByDate === 'function') {
        filterSiteByDate('site');
        filterSiteByDate('conecta');
    }

    // Akna
    var as = document.getElementById('akna_filter_start'); if (as) as.value = start;
    var ae = document.getElementById('akna_filter_end');   if (ae) ae.value = end;
    if (typeof window.applyAknaFilters === 'function') window.applyAknaFilters();

    // LinkedIn ABIARB
    var ls = document.getElementById('liAbiarbStart'); if (ls) ls.value = start;
    var le = document.getElementById('liAbiarbEnd');   if (le) le.value = end;
    if (typeof window.filterTableLinkedinAbiarb === 'function') window.filterTableLinkedinAbiarb();

    // Cards da Visão Geral
    console.log('🔄 Chamando _updateOverviewCards...');
    _updateOverviewCards(dStart, dEnd);

    // Gráficos (origem do site é recalculada depois, pois updateAllCharts não filtra esses charts)
    if (typeof updateAllCharts === 'function') updateAllCharts(start, end);
    if (typeof window.updateSiteAndSocialOverview === 'function') {
        window.updateSiteAndSocialOverview(window.dashboardData || {}, dStart, dEnd);
    }

    // YoY
    if (typeof updateYearOverYearComparison === 'function') updateYearOverYearComparison(start, end);
};

// ─── 10. SOBRESCREVE resetGlobalFilter ───────────────────────────────────────

window.resetGlobalFilter = function() {
    var ids = [
        'global-start-date','global-end-date',
        'ytStart','ytEnd','fbStart','fbEnd','igStart','igEnd',
        'siteStart','siteEnd','conectaStart','conectaEnd',
        'akna_filter_start','akna_filter_end',
        'akna_filter_tipo','akna_filter_assunto','akna_filter_horario','akna_filter_acao',
        'liAbiarbStart','liAbiarbEnd','liAbiarbSearchName',
        'ytSearchName','fbSearchName','igSearchName'
    ];
    ids.forEach(function(id) { var el = document.getElementById(id); if (el) el.value = ''; });
    document.querySelectorAll('.individual-start,.individual-end').forEach(function(el) { el.value = ''; });

    if (typeof clearFilterYT  === 'function') clearFilterYT();
    if (typeof clearFilterFB  === 'function') clearFilterFB();
    if (typeof clearFilterIG  === 'function') clearFilterIG();
    if (typeof clearFilterSite === 'function') {
        clearFilterSite('site');
        clearFilterSite('conecta');
    }
    if (typeof window.resetAknaFilters === 'function') window.resetAknaFilters();
    if (typeof window.clearFilterLinkedinAbiarb === 'function') window.clearFilterLinkedinAbiarb();

    _updateOverviewCards(null, null);
    window._updateAknaTabCards(null, null);
    if (typeof window.updateSiteAndSocialOverview === 'function') {
        window.updateSiteAndSocialOverview(window.dashboardData || {}, null, null);
    }

    if (typeof updateAllCharts === 'function') updateAllCharts(null, null);
    if (typeof updateYearOverYearComparison === 'function') updateYearOverYearComparison(null, null);
};

// ─── 11. HOOK NO applyAknaFilters DO SCRIPT EXTERNO ──────────────────────────
// Garante que os cards da aba Akna são atualizados quando o filtro interno
// da aba for acionado (botão "Aplicar Filtro" na própria aba Akna).

document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        // Wrap em applyAknaFilters (definida no akna_charts_script.js externo)
        var origApply = window.applyAknaFilters;
        if (typeof origApply === 'function') {
            window.applyAknaFilters = function() {
                origApply.apply(this, arguments);
            };
        }

        // Wrap em resetAknaFilters
        var origReset = window.resetAknaFilters;
        if (typeof origReset === 'function') {
            window.resetAknaFilters = function() {
                origReset.apply(this, arguments);
                if (typeof window.syncAknaMetrics === 'function') {
                    window.syncAknaMetrics(null, null);
                } else {
                    window._updateAknaTabCards(null, null);
                }
            };
        }
    }, 600);
});
