/**
 * Recalcula métricas da Visão Geral (site + redes sociais) conforme filtro de datas.
 */
(function () {
    function parseIsoDate(value) {
        if (!value) return null;
        const d = new Date(String(value).slice(0, 10) + 'T12:00:00');
        return isNaN(d.getTime()) ? null : d;
    }

    function parseLabelDate(label, fallbackYear) {
        if (!label) return null;
        const parts = String(label).split('/');
        if (parts.length === 3) {
            return new Date(parts[2], parts[1] - 1, parts[0], 12, 0, 0);
        }
        if (parts.length === 2 && fallbackYear) {
            return new Date(fallbackYear, parts[1] - 1, parts[0], 12, 0, 0);
        }
        return null;
    }

    function dateInRange(d, dStart, dEnd) {
        if (!d) return false;
        if (dStart && d < dStart) return false;
        if (dEnd && d > dEnd) return false;
        return true;
    }

    function rangeOverlaps(startIso, endIso, dStart, dEnd) {
        const start = parseIsoDate(startIso);
        const end = parseIsoDate(endIso || startIso);
        if (!start || !end) return false;
        if (dStart && end < dStart) return false;
        if (dEnd && start > dEnd) return false;
        return true;
    }

    function resolveHistoricoDate(hist, idx, dStart, dEnd) {
        if (!hist) return null;
        const dates = hist.dates_iso || [];
        const starts = hist.date_start_iso || [];
        if (dates[idx]) {
            const end = parseIsoDate(dates[idx]);
            const start = starts[idx] ? parseIsoDate(starts[idx]) : end;
            if (start && end && (dStart || dEnd)) {
                return rangeOverlaps(starts[idx] || dates[idx], dates[idx], dStart, dEnd) ? end : null;
            }
            return end;
        }
        const fallbackYear = dEnd ? dEnd.getFullYear() : (dStart ? dStart.getFullYear() : new Date().getFullYear());
        return parseLabelDate((hist.labels || [])[idx], fallbackYear);
    }

    function sumSeriesInRange(hist, dStart, dEnd) {
        if (!hist || !hist.atual) return 0;
        let sum = 0;
        hist.atual.forEach((val, idx) => {
            const d = resolveHistoricoDate(hist, idx, dStart, dEnd);
            if (dateInRange(d, dStart, dEnd) || (hist.date_start_iso && hist.date_start_iso[idx] &&
                rangeOverlaps(hist.date_start_iso[idx], hist.dates_iso[idx], dStart, dEnd))) {
                sum += parseInt(val) || 0;
            }
        });
        return sum;
    }

    function filterHistoricoIndices(hist, dStart, dEnd) {
        const indices = [];
        if (!hist) return indices;
        const dates = hist.dates_iso || [];
        const len = dates.length || (hist.usuarios || hist.vistas || hist.labels || []).length;
        for (let idx = 0; idx < len; idx++) {
            const d = resolveHistoricoDate(hist, idx, dStart, dEnd);
            if (hist.date_start_iso && hist.date_start_iso[idx]) {
                if (rangeOverlaps(hist.date_start_iso[idx], hist.dates_iso[idx], dStart, dEnd)) {
                    indices.push(idx);
                }
            } else if (dateInRange(d, dStart, dEnd)) {
                indices.push(idx);
            }
        }
        return indices;
    }

    function averageFromHist(hist, field, dStart, dEnd) {
        const indices = filterHistoricoIndices(hist, dStart, dEnd);
        if (!indices.length) return null;
        const values = indices.map(i => parseFloat((hist[field] || [])[i])).filter(v => !isNaN(v));
        if (!values.length) return null;
        return values.reduce((a, b) => a + b, 0) / values.length;
    }

    function sumFromHist(hist, field, dStart, dEnd) {
        const indices = filterHistoricoIndices(hist, dStart, dEnd);
        if (!indices.length) return 0;
        return indices.reduce((acc, i) => acc + (parseInt((hist[field] || [])[i]) || 0), 0);
    }

    function formatDuration(seconds) {
        const sec = Math.max(0, Math.round(parseFloat(seconds) || 0));
        if (sec < 60) return sec + 's';
        return Math.floor(sec / 60) + 'm ' + (sec % 60) + 's';
    }

    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    function aggregatePaginasByPeriod(site, dStart, dEnd, limit) {
        const maxRows = limit || 10;
        const defaultPages = site.paginas_mais_visitadas || [];
        if (!dStart && !dEnd) return defaultPages.slice(0, maxRows);

        const diario = site.paginas_diario || [];
        if (!diario.length) return defaultPages.slice(0, maxRows);

        const totals = {};
        const titles = {};
        diario.forEach(row => {
            const d = parseIsoDate(row.date);
            if (!dateInRange(d, dStart, dEnd)) return;
            const url = row.url || row.titulo || '';
            const vistas = parseInt(row.vistas) || 0;
            totals[url] = (totals[url] || 0) + vistas;
            if (!titles[url] || vistas > (titles[url].score || 0)) {
                titles[url] = { titulo: row.titulo || url, score: vistas };
            }
        });

        return Object.keys(totals)
            .map(url => ({
                titulo: (titles[url] && titles[url].titulo) || url,
                url: url,
                vistas: totals[url]
            }))
            .sort((a, b) => b.vistas - a.vistas)
            .slice(0, maxRows);
    }

    function renderPaginasTable(tbodyId, pages, compact) {
        const tbody = document.getElementById(tbodyId);
        if (!tbody) return;
        if (!pages.length) {
            tbody.innerHTML = '<tr><td colspan="2" style="text-align:center; color:#999;">Sem dados de páginas</td></tr>';
            return;
        }
        tbody.innerHTML = pages.map(pg => {
            if (compact) {
                return '<tr><td>' + escapeHtml(pg.titulo) + '</td><td>' + pg.vistas + '</td></tr>';
            }
            return '<tr><td><strong>' + escapeHtml(pg.titulo) + '</strong><br>' +
                '<small style="color: #999;">' + escapeHtml(pg.url) + '</small></td><td>' + pg.vistas + '</td></tr>';
        }).join('');
    }

    window.aggregatePaginasByPeriod = aggregatePaginasByPeriod;
    window.renderPaginasTable = renderPaginasTable;

    window.updatePaginasTable = function (site, tbodyId, dStart, dEnd, compact, limit) {
        renderPaginasTable(tbodyId, aggregatePaginasByPeriod(site || {}, dStart, dEnd, limit), compact);
    };

    function updateSiteOverviewCards(site, cardPrefix, dStart, dEnd) {
        if (!site) return;
        const hist = site.historico_7d || {};
        const defaults = (site.metricas_principais || {});

        if (!dStart && !dEnd) {
            setText('card-' + cardPrefix + '-usuarios-ativos', defaults.usuarios_ativos || '0');
            setText('card-' + cardPrefix + '-novos-usuarios', defaults.novos_usuarios || '0');
            setText('card-' + cardPrefix + '-taxa-rejeicao', defaults.taxa_rejeicao || '0%');
            setText('card-' + cardPrefix + '-taxa-engajamento', defaults.taxa_engajamento || '0%');
            setText('card-' + cardPrefix + '-tempo-engajamento', defaults.tempo_engajamento || '0s');
            setText('card-' + cardPrefix + '-vistas-por-usuario', defaults.vistas_por_usuario || '0');
            if (typeof window.updatePaginasTable === 'function') {
                window.updatePaginasTable(site, 'overview-' + cardPrefix + '-paginas', null, null, true);
            }
            return;
        }

        const totalUsuarios = sumFromHist(hist, 'usuarios', dStart, dEnd);
        const totalVistas = sumFromHist(hist, 'vistas', dStart, dEnd);
        const totalNovos = sumFromHist(hist, 'novos_usuarios', dStart, dEnd);
        const avgBounce = averageFromHist(hist, 'taxa_rejeicao', dStart, dEnd);
        const avgEng = averageFromHist(hist, 'taxa_engajamento', dStart, dEnd);
        const avgDuration = averageFromHist(hist, 'duracao_sessao', dStart, dEnd);
        const vistasPorUsuario = totalUsuarios > 0 ? (totalVistas / totalUsuarios).toFixed(2) : '0';

        setText('card-' + cardPrefix + '-usuarios-ativos', totalUsuarios);
        setText('card-' + cardPrefix + '-novos-usuarios', totalNovos);
        setText('card-' + cardPrefix + '-taxa-rejeicao', avgBounce != null ? avgBounce.toFixed(1).replace('.', ',') + '%' : defaults.taxa_rejeicao || '0%');
        setText('card-' + cardPrefix + '-taxa-engajamento', avgEng != null ? avgEng.toFixed(1).replace('.', ',') + '%' : defaults.taxa_engajamento || '0%');
        setText('card-' + cardPrefix + '-tempo-engajamento', avgDuration != null ? formatDuration(avgDuration) : defaults.tempo_engajamento || '0s');
        setText('card-' + cardPrefix + '-vistas-por-usuario', vistasPorUsuario.replace('.', ','));
        if (typeof window.updatePaginasTable === 'function') {
            window.updatePaginasTable(site, 'overview-' + cardPrefix + '-paginas', dStart, dEnd, true);
        }
    }

    function parseLinkedInDate(item) {
        const raw = item.Data || item.data || item.data_publicacao || '';
        if (!raw) return null;
        const parts = String(raw).split('/');
        if (parts.length === 3) {
            return new Date(parts[2], parts[1] - 1, parts[0], 12, 0, 0);
        }
        const d = new Date(raw);
        return isNaN(d.getTime()) ? null : d;
    }

    function filterLinkedInManual(items, dStart, dEnd) {
        return (items || []).filter(item => {
            const d = parseLinkedInDate(item);
            return d && dateInRange(d, dStart, dEnd);
        });
    }

    function sumLinkedInField(items, field) {
        return items.reduce((acc, item) => acc + (parseInt(item[field]) || 0), 0);
    }

    function updateSocialTableMetrics(data, dStart, dEnd, filterByDateFn) {
        const fb = data.facebook || {};
        const ig = data.instagram || {};
        const li = data.linkedin_abiarb || {};

        if (!dStart && !dEnd) {
            setText('table-fb-alcance', fb.alcance || '0');
            setText('table-fb-seguidores', fb.seguidores_periodo != null ? fb.seguidores_periodo : (fb.followers || '0'));
            setText('table-fb-visitas', fb.visitas || '0');
            setText('table-ig-alcance', ig.alcance || '0');
            setText('table-ig-seguidores', ig.seguidores_periodo != null ? ig.seguidores_periodo : (ig.followers || '0'));
            setText('table-ig-visitas', ig.visitas || '0');
            setText('table-li-impressoes', li.total_impressoes || '0');
            setText('table-li-seguidores', li.followers || '0');
            setText('table-li-visitas', li.visitas || li.total_cliques || '0');
            return;
        }

        setText('table-fb-alcance', sumSeriesInRange(fb.visualizadores_historico, dStart, dEnd) || 0);
        setText('table-fb-visitas', sumSeriesInRange(fb.visitas_historico, dStart, dEnd) || 0);
        setText('table-fb-seguidores', sumSeriesInRange(fb.seguidores_historico, dStart, dEnd) || 0);

        const igAlcanceHist = ig.alcance_historico || ig.visitas_historico;
        setText('table-ig-alcance', sumSeriesInRange(igAlcanceHist, dStart, dEnd) || 0);
        setText('table-ig-visitas', sumSeriesInRange(ig.visitas_historico, dStart, dEnd) || 0);
        setText('table-ig-seguidores', sumSeriesInRange(ig.seguidores_historico, dStart, dEnd) || 0);

        const liFiltered = filterLinkedInManual(li.detailed_data_manual || li.detailed_data || [], dStart, dEnd);
        setText('table-li-impressoes', sumLinkedInField(liFiltered, 'impressoes_total'));
        setText('table-li-visitas', sumLinkedInField(liFiltered, 'cliques_total'));
        setText('table-li-seguidores', li.followers || '0');
        setText('table-li-interacoes',
            sumLinkedInField(liFiltered, 'reacoes_total') +
            sumLinkedInField(liFiltered, 'comentarios_total') +
            sumLinkedInField(liFiltered, 'compartilhamentos_total')
        );
    }

    function aggregateCanaisByPeriod(canaisDiario, dStart, dEnd) {
        const agg = {};
        (canaisDiario || []).forEach(row => {
            const d = parseIsoDate(row.date);
            if (!d) return;
            if (dStart && d < dStart) return;
            if (dEnd && d > dEnd) return;
            agg[row.canal] = (agg[row.canal] || 0) + (parseInt(row.usuarios) || 0);
        });
        return agg;
    }

    function aggregateGscByPeriod(gscDiario, dStart, dEnd) {
        if (!gscDiario || !gscDiario.length || (!dStart && !dEnd)) return null;
        let impressoes = 0;
        let cliques = 0;
        let posSum = 0;
        let posCount = 0;
        gscDiario.forEach(row => {
            const d = parseIsoDate(row.date);
            if (!dateInRange(d, dStart, dEnd)) return;
            impressoes += parseInt(row.impressoes) || 0;
            cliques += parseInt(row.cliques) || 0;
            const pos = parseFloat(row.posicao);
            if (!isNaN(pos)) {
                posSum += pos;
                posCount += 1;
            }
        });
        const ctr = impressoes > 0 ? (cliques / impressoes * 100).toFixed(1).replace('.', ',') + '%' : '0%';
        const posicao = posCount > 0 ? (posSum / posCount).toFixed(1).replace('.', ',') : '0';
        return {
            visualizacoes: String(impressoes),
            cliques: String(cliques),
            ctr: ctr,
            posicao: posicao
        };
    }

    function updateGscOverviewCards(site, idPrefix, dStart, dEnd) {
        if (!site) return;
        const defaults = site.google_search || {};
        const filtered = aggregateGscByPeriod(site.gsc_diario, dStart, dEnd);
        const searchData = filtered || defaults;

        setText('card-' + idPrefix + '-visualizacoes', searchData.visualizacoes || '0');
        setText('card-' + idPrefix + '-cliques', searchData.cliques || '0');
        setText('card-' + idPrefix + '-ctr', searchData.ctr || '0%');
        setText('card-' + idPrefix + '-posicao', searchData.posicao || '0');

        const gscSection = document.querySelector('.metrics-mini-grid[data-gsc-prefix="' + idPrefix + '"]');
        if (!gscSection) return;
        const oldNote = gscSection.querySelector('.filter-note');
        if (oldNote) oldNote.remove();
        if ((dStart || dEnd) && (!site.gsc_diario || !site.gsc_diario.length)) {
            const note = document.createElement('div');
            note.className = 'filter-note';
            note.style.cssText = 'font-size: 0.8rem; color: #666; margin-top: 8px; font-style: italic;';
            note.textContent = site.seo_fonte === 'ga4_organico'
                ? 'Dados orgânicos GA4 (sem histórico diário para filtro)'
                : 'Histórico GSC indisponível — exibindo resumo dos últimos 30 dias';
            gscSection.appendChild(note);
        }
    }

    window.updateGscOverviewCards = updateGscOverviewCards;

    function updateOrigemChart(site, chartId, dStart, dEnd) {
        const chart = window.charts[chartId];
        if (!chart || !site) return;
        let source;
        if (!dStart && !dEnd) {
            source = site.origem_trafego || {};
        } else if (site.canais_diario && site.canais_diario.length) {
            source = aggregateCanaisByPeriod(site.canais_diario, dStart, dEnd);
        } else {
            source = site.origem_trafego || {};
        }
        chart.data.labels = Object.keys(source);
        chart.data.datasets[0].data = Object.values(source);
        chart.update('none');
    }

    window.parseDashboardFilterDates = function (start, end) {
        return {
            dStart: start ? new Date(start + 'T00:00:00') : null,
            dEnd: end ? new Date(end + 'T23:59:59') : null
        };
    };

    window.updateSiteAndSocialOverview = function (data, dStart, dEnd, filterByDateFn) {
        updateSiteOverviewCards(data.sites, 'site', dStart, dEnd);
        updateSiteOverviewCards(data.site_conecta, 'conecta', dStart, dEnd);
        updateGscOverviewCards(data.sites, 'gsc', dStart, dEnd);
        updateGscOverviewCards(data.site_conecta, 'conecta-gsc', dStart, dEnd);
        updateSocialTableMetrics(data, dStart, dEnd, filterByDateFn);
        updateOrigemChart(data.sites, 'chartOrigemGeral', dStart, dEnd);
        updateOrigemChart(data.site_conecta, 'chartOrigemConecta', dStart, dEnd);
    };

    window.refreshAllChartsLayout = function () {
        Object.values(window.charts || {}).forEach(chart => {
            if (chart && typeof chart.resize === 'function') {
                chart.resize();
                chart.update('none');
            }
        });
    };
})();
