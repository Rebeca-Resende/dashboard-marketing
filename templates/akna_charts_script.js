// Script para renderização dos gráficos AKNA Manual com suporte a filtros dinâmicos
// Este script deve ser incluído no final do template HTML

// Variáveis globais para armazenar as instâncias dos gráficos
let aknaCharts = {
    funil: null,
    evolucao: null,
    distribuicao: null,
    tipos: null,
    horarios: null
};

// Dados originais (carregados do JSON / dashboardData — fonte completa)
let originalAknaData = [];

function loadOriginalAknaData() {
    if (typeof window.getAknaAllData === 'function') {
        const data = window.getAknaAllData();
        if (data && data.length) {
            originalAknaData = data.map(function (item) { return Object.assign({}, item); });
            return true;
        }
    }
    return false;
}

// ✅ NOVO: Referência para sincronismo entre tabela e dados
let tableRowsReference = [];

function initAknaCharts() {
    if (loadOriginalAknaData()) {
        console.log(`✅ AKNA: ${originalAknaData.length} registros carregados do JSON`);
        updateAknaDashboard(originalAknaData);
        return;
    }

    // Fallback: ler da tabela HTML (legado)
    // Pegar os dados brutos da tabela para garantir que temos todos os dados para filtrar
    const table = document.getElementById('tableAknaManual');
    if (!table) {
        console.error('❌ Tabela AKNA não encontrada');
        return;
    }

    // ✅ ROBUSTO: Proteger contra tbody ausente
    const tbody = table.querySelector('tbody') || table.getElementsByTagName('tbody')[0];
    if (!tbody) {
        console.error('❌ tbody não encontrado na tabela AKNA');
        return;
    }

    const rows = tbody.getElementsByTagName('tr');
    console.log(`📊 Iniciando leitura da tabela: ${rows.length} linhas encontradas`);
    
    originalAknaData = [];
    tableRowsReference = [];

    let validRowCount = 0;
    for (let i = 0; i < rows.length; i++) {
        const cells = rows[i].getElementsByTagName('td');
        
        // ✅ VALIDAÇÃO: Exigir 13 colunas (não 10)
        if (cells.length < 13) {
            console.warn(`⚠️ Linha ${i} pulada: ${cells.length} colunas (esperado 13)`);
            continue;
        }

        // Extrair dados das células
        const aknaData = {
            tipo: cells[0].textContent.trim(),
            data: cells[1].textContent.trim(),
            horario: cells[2].textContent.trim(),
            acao: cells[3].textContent.trim(),
            assunto: cells[4].textContent.trim(),
            enviados: parseInt(cells[5].textContent.replace(/\D/g, '')) || 0,
            entregues: parseInt(cells[6].textContent.replace(/\D/g, '')) || 0,
            aberturas: parseInt(cells[7].textContent.replace(/\D/g, '')) || 0,
            cliques: parseInt(cells[8].textContent.replace(/\D/g, '')) || 0,
            taxa_entrega: parseFloat(cells[9].textContent.replace(',', '.')) || 0,
            taxa_abertura: parseFloat(cells[10].textContent.replace(',', '.')) || 0,
            taxa_clique: parseFloat(cells[11].textContent.replace(',', '.')) || 0,
            ctor: parseFloat(cells[12].textContent.replace(',', '.')) || 0
        };

        // 🔥 CRÍTICO: VINCULAR o elemento DOM AO DADO
        aknaData._row = rows[i];
        
        originalAknaData.push(aknaData);
        tableRowsReference.push(rows[i]);
        validRowCount++;
    }

    console.log(`✅ Inicialização concluída: ${validRowCount}/${rows.length} registros carregados`);
    console.log(`📦 originalAknaData.length = ${originalAknaData.length}`);
    
    // Log do primeiro registro para validar formato
    if (originalAknaData.length > 0) {
        console.log('🔍 Primeiro registro:', {
            tipo: originalAknaData[0].tipo,
            data: originalAknaData[0].data,
            horario: originalAknaData[0].horario,
            assunto: originalAknaData[0].assunto
        });
    }

    // Inicializar os gráficos com todos os dados
    updateAknaDashboard(originalAknaData);
}

function updateAknaDashboard(filteredData) {
    console.log(`🎨 updateAknaDashboard acionado com ${filteredData.length} registros`);
    
    // 1. Calcular KPIs
    const totalCampanhas = filteredData.length;
    const totalEnviados = filteredData.reduce((sum, item) => sum + item.enviados, 0);
    const totalEntregues = filteredData.reduce((sum, item) => sum + item.entregues, 0);
    const totalAberturas = filteredData.reduce((sum, item) => sum + (item.aberturas_unicas ?? item.aberturas ?? 0), 0);
    const totalCliques = filteredData.reduce((sum, item) => sum + item.cliques, 0);

    const taxaEntrega = totalEnviados > 0 ? (totalEntregues / totalEnviados * 100).toFixed(2) : "0.00";
    const taxaAbertura = totalEntregues > 0 ? (totalAberturas / totalEntregues * 100).toFixed(2) : "0.00";
    const taxaClique = totalEntregues > 0 ? (totalCliques / totalEntregues * 100).toFixed(2) : "0.00";
    const ctor = totalAberturas > 0 ? (totalCliques / totalAberturas * 100).toFixed(2) : "0.00";

    console.log('📊 KPIs calculados:', {
        campanhas: totalCampanhas,
        enviados: totalEnviados,
        entregues: totalEntregues,
        aberturas: totalAberturas,
        cliques: totalCliques,
        taxas: { entrega: taxaEntrega, abertura: taxaAbertura, clique: taxaClique, ctor }
    });

    // Atualizar elementos do DOM (Cards)
    if(document.getElementById('akna_kpi_total_campanhas')) {
        document.getElementById('akna_kpi_total_campanhas').innerText = totalCampanhas;
        console.log('✅ Card atualizado: total_campanhas');
    }
    if(document.getElementById('akna_kpi_total_enviados')) {
        document.getElementById('akna_kpi_total_enviados').innerText = totalEnviados.toLocaleString('pt-BR');
        console.log('✅ Card atualizado: total_enviados');
    }
    if(document.getElementById('akna_kpi_taxa_entrega')) {
        document.getElementById('akna_kpi_taxa_entrega').innerText = `${taxaEntrega}%`;
        console.log('✅ Card atualizado: taxa_entrega');
    }
    if(document.getElementById('akna_small_entregues')) document.getElementById('akna_small_entregues').innerText = `${totalEntregues.toLocaleString('pt-BR')} entregues`;
    if(document.getElementById('akna_kpi_taxa_abertura')) document.getElementById('akna_kpi_taxa_abertura').innerText = `${taxaAbertura}%`;
    if(document.getElementById('akna_small_aberturas')) document.getElementById('akna_small_aberturas').innerText = `${totalAberturas.toLocaleString('pt-BR')} aberturas`;
    if(document.getElementById('akna_kpi_taxa_clique')) document.getElementById('akna_kpi_taxa_clique').innerText = `${taxaClique}%`;
    if(document.getElementById('akna_small_cliques')) document.getElementById('akna_small_cliques').innerText = `${totalCliques.toLocaleString('pt-BR')} cliques`;
    if(document.getElementById('akna_kpi_ctor')) document.getElementById('akna_kpi_ctor').innerText = `${ctor}%`;
    
    // Adicionar comparativos com período anterior
    const startDate = document.getElementById('akna_filter_start')?.value;
    const endDate = document.getElementById('akna_filter_end')?.value;
    
    if (startDate && endDate) {
        const duration = new Date(endDate + 'T23:59:59') - new Date(startDate + 'T00:00:00');
        const prevStart = new Date(new Date(startDate + 'T00:00:00').getTime() - duration);
        const prevEnd = new Date(new Date(startDate + 'T00:00:00').getTime() - 1);
        
        // Calcular dados do período anterior
        const prevFilteredData = originalAknaData.filter(item => {
            const parts = (item.data || item.data_envio || '').split('/');
            if (parts.length === 3) {
                const itemDate = `${parts[2]}-${parts[1]}-${parts[0]}`;
                return itemDate >= prevStart.toISOString().split('T')[0] && itemDate <= prevEnd.toISOString().split('T')[0];
            }
            return false;
        });
        
        const prevTotalCampanhas = prevFilteredData.length;
        const prevTotalEnviados = prevFilteredData.reduce((sum, item) => sum + item.enviados, 0);
        const prevTotalEntregues = prevFilteredData.reduce((sum, item) => sum + item.entregues, 0);
        const prevTotalAberturas = prevFilteredData.reduce((sum, item) => sum + item.aberturas, 0);
        const prevTotalCliques = prevFilteredData.reduce((sum, item) => sum + item.cliques, 0);
        
        const prevTaxaEntrega = prevTotalEnviados > 0 ? (prevTotalEntregues / prevTotalEnviados * 100).toFixed(2) : "0.00";
        const prevTaxaAbertura = prevTotalEntregues > 0 ? (prevTotalAberturas / prevTotalEntregues * 100).toFixed(2) : "0.00";
        const prevTaxaClique = prevTotalEntregues > 0 ? (prevTotalCliques / prevTotalEntregues * 100).toFixed(2) : "0.00";
        const prevCTOR = prevTotalAberturas > 0 ? (prevTotalCliques / prevTotalAberturas * 100).toFixed(2) : "0.00";
        
        // Função auxiliar para calcular variação
        const calculateVariation = (current, previous) => {
            if (previous == 0) return current == 0 ? '0,0%' : '+∞%';
            const variation = ((current - previous) / previous * 100);
            const sign = variation >= 0 ? '+' : '';
            return `${sign}${variation.toFixed(1)}%`;
        };
        
        // Atualizar comparativos
        const campanhasCompEl = document.getElementById('akna_campanhas_comparativo');
        if (campanhasCompEl) {
            const variation = calculateVariation(totalCampanhas, prevTotalCampanhas);
            campanhasCompEl.innerHTML = `<span style="color: ${variation.includes('+') ? '#28a745' : '#dc3545'}">Período anterior: ${prevTotalCampanhas} | Variação: ${variation}</span>`;
            campanhasCompEl.style.display = 'block';
        }
        
        const enviadosCompEl = document.getElementById('akna_enviados_comparativo');
        if (enviadosCompEl) {
            const variation = calculateVariation(totalEnviados, prevTotalEnviados);
            enviadosCompEl.innerHTML = `<span style="color: ${variation.includes('+') ? '#28a745' : '#dc3545'}">Período anterior: ${prevTotalEnviados.toLocaleString('pt-BR')} | Variação: ${variation}</span>`;
            enviadosCompEl.style.display = 'block';
        }
        
        const entregaCompEl = document.getElementById('akna_entrega_comparativo');
        if (entregaCompEl) {
            const variation = calculateVariation(parseFloat(taxaEntrega), parseFloat(prevTaxaEntrega));
            entregaCompEl.innerHTML = `<span style="color: ${variation.includes('+') ? '#28a745' : '#dc3545'}">Período anterior: ${prevTaxaEntrega}% | Variação: ${variation}</span>`;
            entregaCompEl.style.display = 'block';
        }
        
        const aberturaCompEl = document.getElementById('akna_abertura_comparativo');
        if (aberturaCompEl) {
            const variation = calculateVariation(parseFloat(taxaAbertura), parseFloat(prevTaxaAbertura));
            aberturaCompEl.innerHTML = `<span style="color: ${variation.includes('+') ? '#28a745' : '#dc3545'}">Período anterior: ${prevTaxaAbertura}% | Variação: ${variation}</span>`;
            aberturaCompEl.style.display = 'block';
        }
        
        const cliqueCompEl = document.getElementById('akna_clique_comparativo');
        if (cliqueCompEl) {
            const variation = calculateVariation(parseFloat(taxaClique), parseFloat(prevTaxaClique));
            cliqueCompEl.innerHTML = `<span style="color: ${variation.includes('+') ? '#28a745' : '#dc3545'}">Período anterior: ${prevTaxaClique}% | Variação: ${variation}</span>`;
            cliqueCompEl.style.display = 'block';
        }
        
        const ctorCompEl = document.getElementById('akna_ctor_comparativo');
        if (ctorCompEl) {
            const variation = calculateVariation(parseFloat(ctor), parseFloat(prevCTOR));
            ctorCompEl.innerHTML = `<span style="color: ${variation.includes('+') ? '#28a745' : '#dc3545'}">Período anterior: ${prevCTOR}% | Variação: ${variation}</span>`;
            ctorCompEl.style.display = 'block';
        }
    } else {
        // Esconder comparativos quando não há filtro de data
        ['akna_campanhas_comparativo', 'akna_enviados_comparativo', 'akna_entrega_comparativo', 'akna_abertura_comparativo', 'akna_clique_comparativo', 'akna_ctor_comparativo'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        });
    }
    
    // Atualizar label de total de registros
    if(document.getElementById('akna_total_registros_label')) document.getElementById('akna_total_registros_label').innerText = totalCampanhas;

    // 2. Atualizar Tabela de Top Campanhas
    updateTopCampanhasTable(filteredData);

    // 3. Preparar dados para os gráficos
    console.log('🔄 Recriando gráficos...');
    renderFunilChart(totalEnviados, totalEntregues, totalAberturas, totalCliques);
    renderEvolucaoChart(filteredData);
    renderDistribuicaoChart(filteredData);
    renderTiposChart(filteredData);
    renderHorariosChart(filteredData);
    console.log('✅ Todos os gráficos atualizados');
}

function updateTopCampanhasTable(data) {
    const tbody = document.getElementById('akna_top_campanhas_body');
    if (!tbody) return;

    // Ordenar por taxa de abertura e pegar top 20
    const sortedData = [...data].sort((a, b) => b.taxa_abertura - a.taxa_abertura).slice(0, 20);
    
    if (sortedData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="12" style="text-align: center; padding: 40px; color: #999;">Nenhum dado disponível para os filtros selecionados</td></tr>';
        return;
    }

    tbody.innerHTML = sortedData.map((item, index) => `
        <tr>
            <td>${index + 1}</td>
            <td style="max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${item.assunto}">
                ${item.assunto}
            </td>
            <td>${item.tipo}</td>
            <td>${item.data}</td>
            <td>${item.enviados.toLocaleString('pt-BR')}</td>
            <td>${item.entregues.toLocaleString('pt-BR')}</td>
            <td>${item.aberturas.toLocaleString('pt-BR')}</td>
            <td>${item.cliques.toLocaleString('pt-BR')}</td>
            <td>${item.taxa_entrega.toFixed(2)}%</td>
            <td><strong style="color: #4CAF50;">${item.taxa_abertura.toFixed(2)}%</strong></td>
            <td>${item.taxa_clique.toFixed(2)}%</td>
            <td>${item.ctor.toFixed(2)}%</td>
        </tr>
    `).join('');
}

function renderFunilChart(enviados, entregues, abertos, cliques) {
    const ctx = document.getElementById('chartAknaFunil');
    if (!ctx) return;

    const data = [enviados, entregues, abertos, cliques];
    const labels = ["Enviados", "Entregues", "Abertos", "Cliques"];
    const percentages = [100, enviados > 0 ? (entregues/enviados*100) : 0, enviados > 0 ? (abertos/enviados*100) : 0, enviados > 0 ? (cliques/enviados*100) : 0];

    if (aknaCharts.funil) aknaCharts.funil.destroy();

    aknaCharts.funil = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Quantidade',
                data: data,
                backgroundColor: ['#2196F3', '#4CAF50', '#FF9800', '#E91E63'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const val = context.parsed.x.toLocaleString('pt-BR');
                            const perc = percentages[context.dataIndex].toFixed(2);
                            return `${val} (${perc}% do total)`;
                        }
                    }
                }
            }
        }
    });
}

function renderEvolucaoChart(data) {
    const ctx = document.getElementById('chartAknaEvolucao');
    if (!ctx) return;

    // Agrupar por Mês/Ano ou por Data se o período for curto
    const evolution = {};
    data.forEach(item => {
        const parts = item.data.split('/');
        if (parts.length === 3) {
            const key = `${parts[1]}/${parts[2]}`; // MM/YYYY
            if (!evolution[key]) {
                evolution[key] = { enviados: 0, aberturas: 0, cliques: 0 };
            }
            evolution[key].enviados += item.enviados;
            evolution[key].aberturas += item.aberturas;
            evolution[key].cliques += item.cliques;
        }
    });

    const labels = Object.keys(evolution).sort((a, b) => {
        const [mA, yA] = a.split('/').map(Number);
        const [mB, yB] = b.split('/').map(Number);
        return yA !== yB ? yA - yB : mA - mB;
    });

    if (aknaCharts.evolucao) aknaCharts.evolucao.destroy();

    aknaCharts.evolucao = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                { label: 'Enviados', data: labels.map(l => evolution[l].enviados), borderColor: '#2196F3', tension: 0.3, fill: false },
                { label: 'Aberturas', data: labels.map(l => evolution[l].aberturas), borderColor: '#4CAF50', tension: 0.3, fill: false },
                { label: 'Cliques', data: labels.map(l => evolution[l].cliques), borderColor: '#E91E63', tension: 0.3, fill: false }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'top' } }
        }
    });
}

function renderDistribuicaoChart(data) {
    const ctx = document.getElementById('chartAknaDistribuicao');
    if (!ctx) return;

    const counts = {};
    data.forEach(item => {
        counts[item.tipo] = (counts[item.tipo] || 0) + item.enviados;
    });

    const sortedLabels = Object.keys(counts).sort((a, b) => counts[b] - counts[a]);
    const topLabels = sortedLabels.slice(0, 8);
    const otherValue = sortedLabels.slice(8).reduce((sum, l) => sum + counts[l], 0);
    
    const finalLabels = [...topLabels];
    const finalValues = topLabels.map(l => counts[l]);
    if (otherValue > 0) {
        finalLabels.push("Outros");
        finalValues.push(otherValue);
    }

    if (aknaCharts.distribuicao) aknaCharts.distribuicao.destroy();

    aknaCharts.distribuicao = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: finalLabels,
            datasets: [{
                data: finalValues,
                backgroundColor: ['#2196F3', '#4CAF50', '#FF9800', '#E91E63', '#9C27B0', '#00BCD4', '#FFEB3B', '#795548', '#607D8B']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'right' } }
        }
    });
}

function renderTiposChart(data) {
    const ctx = document.getElementById('chartAknaTipos');
    if (!ctx) return;

    const stats = {};
    data.forEach(item => {
        if (!stats[item.tipo]) stats[item.tipo] = { enviados: 0, aberturas: 0 };
        stats[item.tipo].enviados += item.enviados;
        stats[item.tipo].aberturas += item.aberturas;
    });

    const sorted = Object.keys(stats).sort((a, b) => stats[b].enviados - stats[a].enviados).slice(0, 10);

    if (aknaCharts.tipos) aknaCharts.tipos.destroy();

    aknaCharts.tipos = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sorted,
            datasets: [
                { label: 'Enviados', data: sorted.map(l => stats[l].enviados), backgroundColor: '#2196F3' },
                { label: 'Aberturas', data: sorted.map(l => stats[l].aberturas), backgroundColor: '#4CAF50' }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'top' } }
        }
    });
}

function renderHorariosChart(data) {
    const ctx = document.getElementById('chartAknaHorarios');
    if (!ctx) return;

    const hourly = Array(24).fill(0);
    data.forEach(item => {
        const hour = parseInt(item.horario.split(':')[0]);
        if (!isNaN(hour)) hourly[hour] += item.aberturas;
    });

    if (aknaCharts.horarios) aknaCharts.horarios.destroy();

    aknaCharts.horarios = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: hourly.map((_, i) => `${i}h`),
            datasets: [{
                label: 'Aberturas',
                data: hourly,
                backgroundColor: '#FF9800'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } }
        }
    });
}

// 🔥 VERSÃO PROFISSIONAL: Filtros SEM dependência de índice
window.applyAknaFilters = function() {
    console.log('🎯 FILTRO EXECUTADO');
    
    const startDate = document.getElementById('akna_filter_start')?.value;
    const endDate = document.getElementById('akna_filter_end')?.value;
    const tipo = document.getElementById('akna_filter_tipo')?.value.toLowerCase();
    const assunto = document.getElementById('akna_filter_assunto')?.value.toLowerCase();
    const horario = document.getElementById('akna_filter_horario')?.value.toLowerCase();
    const acao = document.getElementById('akna_filter_acao')?.value.toLowerCase();
    
    console.log('📋 Parâmetros de filtro:', {
        startDate: startDate || 'vazio',
        endDate: endDate || 'vazio',
        tipo: tipo || 'vazio',
        assunto: assunto || 'vazio',
        horario: horario || 'vazio',
        acao: acao || 'vazio'
    });
    
    if (originalAknaData.length === 0) {
        loadOriginalAknaData();
    }
    if (originalAknaData.length === 0) {
        console.error('❌ Nenhum dado carregado. originalAknaData.length = 0');
        initAknaCharts();
        return;
    }

    console.log(`📦 Iniciando filtro sobre ${originalAknaData.length} registros`);

    const filteredData = [];
    
    for (let i = 0; i < originalAknaData.length; i++) {
        const item = originalAknaData[i];
        let show = true;
        
        if (tipo && String(item.tipo || item.campanhas || '').toLowerCase().indexOf(tipo) === -1) show = false;
        if (show && assunto && String(item.assunto || '').toLowerCase().indexOf(assunto) === -1) show = false;
        if (show && horario && String(item.horario || '').toLowerCase().indexOf(horario) === -1) show = false;
        if (show && acao && String(item.acao || item.acoes || '').toLowerCase().indexOf(acao) === -1) show = false;
        
        if (show && (startDate || endDate)) {
            const parts = (item.data || item.data_envio || '').split('/');
            if (parts.length === 3) {
                const rowDate = `${parts[2]}-${parts[1].padStart(2,'0')}-${parts[0].padStart(2,'0')}`;
                if (startDate && rowDate < startDate) show = false;
                if (endDate && rowDate > endDate) show = false;
            } else {
                show = false;
            }
        }

        if (item._row) item._row.style.display = show ? '' : 'none';
        if (show) filteredData.push(item);
    }

    console.log(`✅ Filtros aplicados: ${filteredData.length}/${originalAknaData.length} registros`);

    updateAknaDashboard(filteredData);

    if (typeof window.syncAknaMetrics === 'function') {
        const dS = startDate ? new Date(startDate + 'T00:00:00') : null;
        const dE = endDate ? new Date(endDate + 'T23:59:59') : null;
        window.syncAknaMetrics(dS, dE, filteredData);
    }
}

// 🔥 VERSÃO PROFISSIONAL: Reset sem dependência de índice
function resetAknaFilters() {
    try {
        // Limpar os inputs de filtro
        const filterStart = document.getElementById('akna_filter_start');
        const filterEnd = document.getElementById('akna_filter_end');
        const filterTipo = document.getElementById('akna_filter_tipo');
        const filterAssunto = document.getElementById('akna_filter_assunto');
        const filterHorario = document.getElementById('akna_filter_horario');
        const filterAcao = document.getElementById('akna_filter_acao');

        if (filterStart?.value !== undefined) filterStart.value = '';
        if (filterEnd?.value !== undefined) filterEnd.value = '';
        if (filterTipo?.value !== undefined) filterTipo.value = '';
        if (filterAssunto?.value !== undefined) filterAssunto.value = '';
        if (filterHorario?.value !== undefined) filterHorario.value = '';
        if (filterAcao?.value !== undefined) filterAcao.value = '';

        // 🔥 CRÍTICO: Mostrar todas as linhas usando vínculo direto (SEM dependência de índice)
        for (let i = 0; i < originalAknaData.length; i++) {
            const item = originalAknaData[i];
            if (item._row) {
                item._row.style.display = '';
            }
        }

        console.log('✅ Filtros resetados. Todos os registros visíveis.');

        // Resetar gráficos e KPIs para o original
        updateAknaDashboard(originalAknaData);
    } catch (error) {
        console.error('❌ Erro ao resetar filtros:', error);
    }
}

// 🔥 VERSÃO PROFISSIONAL: Inicializar quando o documento estiver pronto ou a aba for ativada
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 DOMContentLoaded disparado');
    
    const aknaTab = document.getElementById('akna_manual');
    
    if (!aknaTab) {
        console.warn('⚠️ Aba AKNA (#akna_manual) não encontrada.');
        console.log('Tentando inicializar de forma genérica em 500ms...');
        setTimeout(() => { 
            if (originalAknaData.length === 0) {
                console.log('Iniciando por timeout...');
                initAknaCharts();
            }
        }, 500);
        return;
    }

    console.log('✅ Aba AKNA encontrada');

    // ✅ NOVO: A função para inicializar
    function tryInitializeAkna() {
        const isVisible = aknaTab.style.display !== 'none' && aknaTab.offsetHeight > 0;
        console.log(`👁️  Verificando visibilidade: display=${aknaTab.style.display}, offsetHeight=${aknaTab.offsetHeight}, visible=${isVisible}`);
        
        if (isVisible && originalAknaData.length === 0) {
            console.log('🟢 Aba visível e dados vazios. Inicializando agora...');
            initAknaCharts();
        } else if (originalAknaData.length > 0) {
            console.log(`✅ Dados já carregados: ${originalAknaData.length} registros`);
        }
    }

    // ✅ NOVO: Observer para detectar quando a aba fica visível
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            console.log(`🔔 Mutação detectada: atributo=${mutation.attributeName}`);
            if ((mutation.attributeName === 'style' || mutation.attributeName === 'class') && 
                originalAknaData.length === 0) {
                console.log('⏱️  Agendando inicialização em 100ms...');
                setTimeout(tryInitializeAkna, 100);
            }
        });
    });
    
    observer.observe(aknaTab, { attributes: true, attributeFilter: ['style', 'class'] });
    console.log('✅ MutationObserver configurado');

    // ✅ NOVO: Tentar inicializar no DOMContentLoaded também (em 300ms)
    console.log('⏱️  Agendando tryInitializeAkna em 300ms...');
    setTimeout(tryInitializeAkna, 300);

    // ✅ NOVO: Adicionar event listeners aos filtros
    const filterStart = document.getElementById('akna_filter_start');
    const filterEnd = document.getElementById('akna_filter_end');
    const filterTipo = document.getElementById('akna_filter_tipo');
    const filterAssunto = document.getElementById('akna_filter_assunto');
    const filterHorario = document.getElementById('akna_filter_horario');
    const filterAcao = document.getElementById('akna_filter_acao');
    const resetButton = document.getElementById('akna_filter_reset');

    if (filterStart) {
        filterStart.addEventListener('change', applyAknaFilters);
        console.log('✅ Listener adicionado: akna_filter_start');
    } else {
        console.warn('⚠️ Elemento #akna_filter_start não encontrado');
    }
    
    if (filterEnd) {
        filterEnd.addEventListener('change', applyAknaFilters);
        console.log('✅ Listener adicionado: akna_filter_end');
    } else {
        console.warn('⚠️ Elemento #akna_filter_end não encontrado');
    }
    
    if (filterTipo) {
        filterTipo.addEventListener('change', applyAknaFilters);
        console.log('✅ Listener adicionado: akna_filter_tipo');
    } else {
        console.warn('⚠️ Elemento #akna_filter_tipo não encontrado');
    }
    
    if (filterAssunto) {
        filterAssunto.addEventListener('input', applyAknaFilters);
        console.log('✅ Listener adicionado: akna_filter_assunto');
    } else {
        console.warn('⚠️ Elemento #akna_filter_assunto não encontrado');
    }

    if (filterHorario) {
        filterHorario.addEventListener('change', applyAknaFilters);
        console.log('✅ Listener adicionado: akna_filter_horario');
    } else {
        console.warn('⚠️ Elemento #akna_filter_horario não encontrado');
    }

    if (filterAcao) {
        filterAcao.addEventListener('input', applyAknaFilters);
        console.log('✅ Listener adicionado: akna_filter_acao');
    } else {
        console.warn('⚠️ Elemento #akna_filter_acao não encontrado');
    }
    
    if (resetButton) {
        resetButton.addEventListener('click', resetAknaFilters);
        console.log('✅ Listener adicionado: akna_filter_reset');
    } else {
        console.warn('⚠️ Elemento #akna_filter_reset não encontrado');
    }

    console.log('✅✅✅ Inicialização AKNA concluída');
});
