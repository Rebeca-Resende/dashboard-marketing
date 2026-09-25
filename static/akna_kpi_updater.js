/**
 * ATUALIZADOR DE KPIs PARA FILTROS AKNA
 * 
 * Atualiza os cards de KPI quando filtros são aplicados
 * Considera TODOS os dados filtrados, não apenas os 50 da tela
 */

class AknaKPIUpdater {
    constructor() {
        this.originalKPIs = null;
        this.currentFilteredData = [];
    }

    /**
     * Inicializa o atualizador com os KPIs originais
     */
    init(allData) {
        this.allData = allData;
        this.storeOriginalKPIs();
        console.log('✅ Atualizador de KPI inicializado');
    }

    /**
     * Armazena os KPIs originais (com todos os dados)
     */
    storeOriginalKPIs() {
        this.originalKPIs = {
            total_campanhas: document.getElementById('akna_kpi_total_campanhas')?.textContent || '0',
            total_enviados: document.getElementById('akna_kpi_total_enviados')?.textContent || '0',
            total_entregues: document.getElementById('akna_kpi_total_entregues')?.textContent || '0',
            total_aberturas: document.getElementById('akna_kpi_total_aberturas')?.textContent || '0',
            total_cliques: document.getElementById('akna_kpi_total_cliques')?.textContent || '0',
            taxa_entrega: document.getElementById('akna_kpi_taxa_entrega')?.textContent || '0%',
            taxa_abertura: document.getElementById('akna_kpi_taxa_abertura')?.textContent || '0%',
            taxa_clique: document.getElementById('akna_kpi_taxa_clique')?.textContent || '0%',
            ctor: document.getElementById('akna_kpi_ctor')?.textContent || '0%'
        };
    }

    /**
     * Calcula KPIs a partir dos dados filtrados
     */
    calculateKPIs(filteredData) {
        if (!filteredData || filteredData.length === 0) {
            return {
                total_campanhas: 0,
                total_enviados: 0,
                total_entregues: 0,
                total_aberturas: 0,
                total_cliques: 0,
                taxa_entrega: 0,
                taxa_abertura: 0,
                taxa_clique: 0,
                ctor: 0
            };
        }

        const total_campanhas = filteredData.length;
        const total_enviados = filteredData.reduce((sum, item) => sum + (item.enviados || 0), 0);
        const total_entregues = filteredData.reduce((sum, item) => sum + (item.entregues || 0), 0);
        const total_aberturas = filteredData.reduce((sum, item) => sum + (item.aberturas || 0), 0);
        const total_cliques = filteredData.reduce((sum, item) => sum + (item.cliques || 0), 0);

        const taxa_entrega = total_enviados > 0 ? (total_entregues / total_enviados * 100) : 0;
        const taxa_abertura = total_entregues > 0 ? (total_aberturas / total_entregues * 100) : 0;
        const taxa_clique = total_entregues > 0 ? (total_cliques / total_entregues * 100) : 0;
        const ctor = total_aberturas > 0 ? (total_cliques / total_aberturas * 100) : 0;

        return {
            total_campanhas,
            total_enviados,
            total_entregues,
            total_aberturas,
            total_cliques,
            taxa_entrega: taxa_entrega.toFixed(2),
            taxa_abertura: taxa_abertura.toFixed(2),
            taxa_clique: taxa_clique.toFixed(2),
            ctor: ctor.toFixed(2)
        };
    }

    /**
     * Atualiza os KPIs na tela
     */
    updateKPIs(filteredData) {
        const kpis = this.calculateKPIs(filteredData);

        // Atualizar elementos na tela
        this.updateElement('akna_kpi_total_campanhas', kpis.total_campanhas);
        this.updateElement('akna_kpi_total_enviados', this.formatNumber(kpis.total_enviados));
        this.updateElement('akna_kpi_total_entregues', this.formatNumber(kpis.total_entregues));
        this.updateElement('akna_kpi_total_aberturas', this.formatNumber(kpis.total_aberturas));
        this.updateElement('akna_kpi_total_cliques', this.formatNumber(kpis.total_cliques));
        this.updateElement('akna_kpi_taxa_entrega', kpis.taxa_entrega + '%');
        this.updateElement('akna_kpi_taxa_abertura', kpis.taxa_abertura + '%');
        this.updateElement('akna_kpi_taxa_clique', kpis.taxa_clique + '%');
        this.updateElement('akna_kpi_ctor', kpis.ctor + '%');

        console.log(`📊 KPIs atualizados: ${kpis.total_campanhas} campanhas, ${this.formatNumber(kpis.total_enviados)} enviados`);
    }

    /**
     * Atualiza um elemento HTML
     */
    updateElement(elementId, value) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = value;
        }
    }

    /**
     * Formata número com separador de milhares
     */
    formatNumber(num) {
        if (typeof num === 'string') num = parseInt(num.replace(/,/g, ''));
        return num.toLocaleString('pt-BR');
    }

    /**
     * Reseta KPIs para os valores originais
     */
    resetKPIs() {
        if (this.originalKPIs) {
            this.updateElement('akna_kpi_total_campanhas', this.originalKPIs.total_campanhas);
            this.updateElement('akna_kpi_total_enviados', this.originalKPIs.total_enviados);
            this.updateElement('akna_kpi_total_entregues', this.originalKPIs.total_entregues);
            this.updateElement('akna_kpi_total_aberturas', this.originalKPIs.total_aberturas);
            this.updateElement('akna_kpi_total_cliques', this.originalKPIs.total_cliques);
            this.updateElement('akna_kpi_taxa_entrega', this.originalKPIs.taxa_entrega);
            this.updateElement('akna_kpi_taxa_abertura', this.originalKPIs.taxa_abertura);
            this.updateElement('akna_kpi_taxa_clique', this.originalKPIs.taxa_clique);
            this.updateElement('akna_kpi_ctor', this.originalKPIs.ctor);

            console.log('🔄 KPIs resetados para valores originais');
        }
    }
}

// Instância global
const aknaKPIUpdater = new AknaKPIUpdater();
