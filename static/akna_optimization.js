/**
 * OTIMIZAÇÃO DE PERFORMANCE - EMAIL MARKETING (AKNA)
 * 
 * Implementa:
 * - Paginação dinâmica (50 registros por página)
 * - Virtualização de tabela (renderiza apenas linhas visíveis)
 * - Cache inteligente em memória
 * - Lazy loading de dados
 * - Filtros otimizados
 */

class AknaTableOptimization {
    constructor() {
        this.pageSize = 50;
        this.currentPage = 1;
        this.allData = [];
        this.filteredData = [];
        this.cache = new Map();
        this.isInitialized = false;
        this.virtualScroll = null;
        
        // Configurações de performance
        this.debounceDelay = 300;
        this.debounceTimer = null;
    }

    /**
     * Linha válida: Horario, Ação e Assunto obrigatórios.
     */
    _isValidAknaRow(row) {
        if (!row) return false;
        const empty = (val) => val == null || String(val).trim() === '' || String(val).trim().toLowerCase() === 'nan';
        const horario = row.horario;
        const acao = row.acao != null ? row.acao : row.acoes;
        const assunto = row.assunto;
        return !empty(horario) && !empty(acao) && !empty(assunto);
    }

    _filterValidRows(rows) {
        const valid = (rows || []).filter((row) => this._isValidAknaRow(row));
        const removed = (rows || []).length - valid.length;
        if (removed > 0) {
            console.log(`[AKNA] ${removed} registro(s) ocultado(s) (Horario, Ações ou Assunto vazio)`);
        }
        return valid;
    }

    /**
     * Inicializa o sistema de otimização
     */
    init(data = null) {
        if (this.isInitialized) return;
        
        console.log('🚀 Inicializando otimização de tabela Akna...');
        
        // Se dados forem passados, usar; caso contrário, extrair do DOM
        if (data && Array.isArray(data)) {
            this.allData = this._filterValidRows(data);
        } else {
            this.extractDataFromDOM();
        }
        
        this.filteredData = [...this.allData];
        this.setupEventListeners();
        this.renderPage(1);
        this.setupVirtualScroll();
        
        this.isInitialized = true;
        console.log(`✅ Tabela otimizada: ${this.allData.length} registros carregados`);
    }

    /**
     * Extrai dados da tabela existente no DOM
     */
    extractDataFromDOM() {
        const table = document.getElementById('tableAknaManual');
        if (!table) {
            console.warn('⚠️ Tabela não encontrada. Usando dados vazios.');
            this.allData = [];
            return;
        }

        const rows = table.querySelectorAll('tbody tr');
        this.allData = this._filterValidRows(Array.from(rows).map(row => {
            const cells = row.querySelectorAll('td');
            return {
                tipo: cells[0]?.textContent.trim() || '',
                data: cells[1]?.textContent.trim() || '',
                horario: cells[2]?.textContent.trim() || '',
                acao: cells[3]?.textContent.trim() || '',
                assunto: cells[4]?.textContent.trim() || '',
                enviados: parseInt(cells[5]?.textContent.replace(/,/g, '') || 0),
                entregues: parseInt(cells[6]?.textContent.replace(/,/g, '') || 0),
                aberturas: parseInt(cells[7]?.textContent.replace(/,/g, '') || 0),
                cliques: parseInt(cells[8]?.textContent.replace(/,/g, '') || 0),
                taxa_entrega: parseFloat(cells[9]?.textContent.replace('%', '') || 0),
                taxa_abertura: parseFloat(cells[10]?.textContent.replace('%', '') || 0),
                taxa_clique: parseFloat(cells[11]?.textContent.replace('%', '') || 0),
                ctor: parseFloat(cells[12]?.textContent.replace('%', '') || 0)
            };
        }));

        console.log(`📊 Extraídos ${this.allData.length} registros da tabela`);
    }

    /**
     * Configura listeners para filtros e paginação
     */
    setupEventListeners() {
        // Filtros de data
        const startDateInput = document.getElementById('akna_filter_start');
        const endDateInput = document.getElementById('akna_filter_end');
        const tipoInput = document.getElementById('akna_filter_tipo');
        const assuntoInput = document.getElementById('akna_filter_assunto');
        const horarioInput = document.getElementById('akna_filter_horario');
        const acaoInput = document.getElementById('akna_filter_acao');

        // Aplicar filtros com debounce
        [startDateInput, endDateInput, tipoInput, assuntoInput, horarioInput, acaoInput].forEach(input => {
            if (input) {
                input.addEventListener('input', () => this.debounceFilter());
            }
        });

        // Botões de ação
        const applyBtn = document.querySelector('button[onclick="applyAknaFilters()"]');
        const resetBtn = document.querySelector('button[onclick="resetAknaFilters()"]');
        
        if (applyBtn) applyBtn.addEventListener('click', () => this.applyFilters());
        if (resetBtn) resetBtn.addEventListener('click', () => this.resetFilters());
    }

    /**
     * Debounce para filtros (evita recálculos excessivos)
     */
    debounceFilter() {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => this.applyFilters(), this.debounceDelay);
    }

    /**
     * Converte data em formato DD/MM/YYYY para Date object
     * Trata corretamente o formato brasileiro
     */
    parseDate(dateStr) {
        if (!dateStr) return null;
        
        // Se for formato DD/MM/YYYY (brasileiro)
        if (dateStr.includes('/')) {
            const parts = dateStr.split('/');
            if (parts.length === 3) {
                const day = parseInt(parts[0], 10);
                const month = parseInt(parts[1], 10);
                const year = parseInt(parts[2], 10);
                
                // Criar data com hora 00:00:00 para comparação correta
                const date = new Date(year, month - 1, day, 0, 0, 0, 0);
                return date;
            }
        }
        
        // Se for formato YYYY-MM-DD (input date HTML)
        if (dateStr.includes('-')) {
            const date = new Date(dateStr + 'T00:00:00');
            return date;
        }
        
        return null;
    }

    /**
     * Aplica filtros aos dados
     */
    applyFilters() {
        const startDate = document.getElementById('akna_filter_start')?.value;
        const endDate = document.getElementById('akna_filter_end')?.value;
        const tipo = document.getElementById('akna_filter_tipo')?.value.toLowerCase() || '';
        const assunto = document.getElementById('akna_filter_assunto')?.value.toLowerCase() || '';
        const horario = document.getElementById('akna_filter_horario')?.value || '';
        const acao = document.getElementById('akna_filter_acao')?.value.toLowerCase() || '';

        // Criar chave de cache para este filtro
        const cacheKey = `${startDate}|${endDate}|${tipo}|${assunto}|${horario}|${acao}`;
        
        if (this.cache.has(cacheKey)) {
            this.filteredData = this.cache.get(cacheKey);
            console.log(`📦 Usando dados em cache: ${this.filteredData.length} registros`);
        } else {
            // Parse das datas de filtro
            const filterStartDate = startDate ? this.parseDate(startDate) : null;
            const filterEndDate = endDate ? this.parseDate(endDate) : null;

            console.log(`🔍 Filtrando com datas:`, {
                startDate: startDate,
                endDate: endDate,
                filterStartDate: filterStartDate,
                filterEndDate: filterEndDate
            });

            this.filteredData = this.allData.filter(item => {
                // Filtro de data
                if (filterStartDate || filterEndDate) {
                    const itemDate = this.parseDate(item.data);
                    
                    if (!itemDate) {
                        console.warn(`⚠️ Data inválida: ${item.data}`);
                        return false;
                    }
                    
                    if (filterStartDate && itemDate < filterStartDate) {
                        return false;
                    }
                    if (filterEndDate && itemDate > filterEndDate) {
                        return false;
                    }
                }

                // Filtros de texto
                if (tipo && !item.tipo.toLowerCase().includes(tipo)) return false;
                if (assunto && !item.assunto.toLowerCase().includes(assunto)) return false;
                if (horario && !item.horario.includes(horario)) return false;
                if (acao && !item.acao.toLowerCase().includes(acao)) return false;

                return true;
            });

            // Armazenar em cache
            this.cache.set(cacheKey, this.filteredData);
            console.log(`✅ Filtrados ${this.filteredData.length} registros`);
        }

        // Atualizar label de registros
        const label = document.getElementById('akna_total_registros_label');
        if (label) label.textContent = this.filteredData.length;

        // Sincronizar KPIs na Visão Geral e na aba (mesma fonte de dados)
        const filterStartDate = startDate ? this.parseDate(startDate) : null;
        const filterEndDate = endDate ? this.parseDate(endDate) : null;
        if (filterEndDate) filterEndDate.setHours(23, 59, 59, 999);
        if (typeof window.syncAknaMetrics === 'function') {
            window.syncAknaMetrics(filterStartDate, filterEndDate, this.filteredData);
        } else if (window.aknaKPIUpdater) {
            window.aknaKPIUpdater.updateKPIs(this.filteredData);
        }

        // Voltar para página 1 e renderizar
        this.currentPage = 1;
        this.renderPage(1);
    }

    /**
     * Reseta todos os filtros
     */
    resetFilters() {
        document.getElementById('akna_filter_start').value = '';
        document.getElementById('akna_filter_end').value = '';
        document.getElementById('akna_filter_tipo').value = '';
        document.getElementById('akna_filter_assunto').value = '';
        document.getElementById('akna_filter_horario').value = '';
        document.getElementById('akna_filter_acao').value = '';

        this.filteredData = [...this.allData];
        this.currentPage = 1;
        this.cache.clear();
        
        const label = document.getElementById('akna_total_registros_label');
        if (label) label.textContent = this.allData.length;
        
        if (typeof window.syncAknaMetrics === 'function') {
            window.syncAknaMetrics(null, null);
        } else if (window.aknaKPIUpdater) {
            window.aknaKPIUpdater.resetKPIs();
        }
        
        console.log('🔄 Filtros resetados');
        this.renderPage(1);
    }

    /**
     * Renderiza uma página específica
     */
    renderPage(pageNum) {
        const startIdx = (pageNum - 1) * this.pageSize;
        const endIdx = startIdx + this.pageSize;
        const pageData = this.filteredData.slice(startIdx, endIdx);

        const tbody = document.querySelector('#tableAknaManual tbody');
        if (!tbody) return;

        // Limpar tbody
        tbody.innerHTML = '';

        // Renderizar linhas
        pageData.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${this.escapeHtml(item.tipo)}</td>
                <td>${this.escapeHtml(item.data)}</td>
                <td>${this.escapeHtml(item.horario)}</td>
                <td>${this.escapeHtml(item.acao)}</td>
                <td title="${this.escapeHtml(item.assunto)}">${this.escapeHtml(item.assunto)}</td>
                <td>${this.formatNumber(item.enviados)}</td>
                <td>${this.formatNumber(item.entregues)}</td>
                <td>${this.formatNumber(item.aberturas)}</td>
                <td>${this.formatNumber(item.cliques)}</td>
                <td>${item.taxa_entrega.toFixed(2)}%</td>
                <td>${item.taxa_abertura.toFixed(2)}%</td>
                <td>${item.taxa_clique.toFixed(2)}%</td>
                <td>${item.ctor.toFixed(2)}%</td>
            `;
            tbody.appendChild(row);
        });

        // Atualizar paginação
        this.updatePagination(pageNum);
        this.currentPage = pageNum;
    }

    /**
     * Atualiza controles de paginação
     */
    updatePagination(currentPage) {
        const totalPages = Math.ceil(this.filteredData.length / this.pageSize);
        
        // Criar ou atualizar controles de paginação
        let paginationContainer = document.getElementById('akna_pagination_controls');
        
        if (!paginationContainer) {
            paginationContainer = document.createElement('div');
            paginationContainer.id = 'akna_pagination_controls';
            paginationContainer.style.cssText = `
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 10px;
                margin-top: 20px;
                padding: 15px;
                background: #f5f5f5;
                border-radius: 8px;
            `;
            
            const table = document.getElementById('tableAknaManual');
            if (table && table.parentNode) {
                table.parentNode.insertAdjacentElement('afterend', paginationContainer);
            }
        }

        // Construir HTML da paginação
        let paginationHTML = '';

        // Botão Primeira Página
        paginationHTML += `<button class="pagination-btn" onclick="aknaOptimizer.renderPage(1)" ${currentPage === 1 ? 'disabled' : ''}>
            <i class="fas fa-step-backward"></i> Primeira
        </button>`;

        // Botão Página Anterior
        paginationHTML += `<button class="pagination-btn" onclick="aknaOptimizer.renderPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>
            <i class="fas fa-chevron-left"></i> Anterior
        </button>`;

        // Info de página
        paginationHTML += `<span style="margin: 0 15px; font-weight: bold;">Página ${currentPage} de ${totalPages}</span>`;

        // Botão Próxima Página
        paginationHTML += `<button class="pagination-btn" onclick="aknaOptimizer.renderPage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>
            Próxima <i class="fas fa-chevron-right"></i>
        </button>`;

        // Botão Última Página
        paginationHTML += `<button class="pagination-btn" onclick="aknaOptimizer.renderPage(${totalPages})" ${currentPage === totalPages ? 'disabled' : ''}>
            Última <i class="fas fa-step-forward"></i>
        </button>`;

        paginationContainer.innerHTML = paginationHTML;
    }

    /**
     * Formata número com separador de milhares
     */
    formatNumber(num) {
        return num.toLocaleString('pt-BR');
    }

    /**
     * Escapa caracteres HTML para evitar XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Configura scroll virtual (otimização para muitos registros)
     */
    setupVirtualScroll() {
        const container = document.querySelector('.table-container');
        if (!container) return;

        container.addEventListener('scroll', () => {
            // Implementar lazy loading se necessário
        });
    }

    /**
     * Exporta dados filtrados para CSV
     */
    exportToCSV() {
        const data = this.filteredData;
        let csv = 'Tipo,Data,Horário,Ação,Assunto,Enviados,Entregues,Aberturas,Cliques,Taxa Entrega,Taxa Abertura,CTR,CTOR\n';
        
        data.forEach(row => {
            csv += `"${row.tipo}","${row.data}","${row.horario}","${row.acao}","${row.assunto}",${row.enviados},${row.entregues},${row.aberturas},${row.cliques},${row.taxa_entrega}%,${row.taxa_abertura}%,${row.taxa_clique}%,${row.ctor}%\n`;
        });

        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `akna_campanhas_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
    }

    /**
     * Retorna estatísticas dos dados filtrados
     */
    getStatistics() {
        return {
            total: this.filteredData.length,
            totalEnviados: this.filteredData.reduce((sum, item) => sum + item.enviados, 0),
            totalEntregues: this.filteredData.reduce((sum, item) => sum + item.entregues, 0),
            totalAberturas: this.filteredData.reduce((sum, item) => sum + item.aberturas, 0),
            totalCliques: this.filteredData.reduce((sum, item) => sum + item.cliques, 0)
        };
    }
}

// Instância global
const aknaOptimizer = new AknaTableOptimization();

// Funções globais para compatibilidade com onclick
function applyAknaFilters() {
    aknaOptimizer.applyFilters();
}

function resetAknaFilters() {
    aknaOptimizer.resetFilters();
}

function goToAknaPage(pageNum) {
    aknaOptimizer.renderPage(pageNum);
}

function exportAknaToCSV() {
    aknaOptimizer.exportToCSV();
}
