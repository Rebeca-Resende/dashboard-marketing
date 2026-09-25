"""
Módulo de Análise de Dados AKNA
Processa dados do Excel e gera métricas, gráficos e indicadores para o dashboard
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

from modules.akna_validation import filter_akna_dataframe

def parse_time_to_hour(time_str):
    """
    Extrai a hora de um horário em formato flexível (HH:MM ou HH:MM:SS).
    Evita warnings do pandas ao trabalhar com horários em formato inconsistente.
    
    Args:
        time_str: String contendo o horário
    
    Returns:
        int: Hora (0-23), ou None se inválido
    """
    if pd.isna(time_str) or time_str == '' or time_str is None:
        return None
    
    time_str = str(time_str).strip()
    
    # Tenta formato HH:MM:SS
    try:
        dt = pd.to_datetime(time_str, format='%H:%M:%S', errors='raise')
        return dt.hour
    except (ValueError, TypeError):
        pass
    
    # Tenta formato HH:MM
    try:
        dt = pd.to_datetime(time_str, format='%H:%M', errors='raise')
        return dt.hour
    except (ValueError, TypeError):
        pass
    
    # Tenta conversão flexível (última tentativa)
    try:
        dt = pd.to_datetime(time_str, errors='coerce')
        if pd.notna(dt):
            return dt.hour
    except:
        pass
    
    return None

class AknaAnalytics:
    """Classe para análise de dados de campanhas AKNA"""
    
    def __init__(self, df):
        """
        Inicializa o analisador com um DataFrame pandas
        
        Args:
            df: DataFrame com os dados do Excel AKNA
        """
        self.df = df.copy()
        self._prepare_data()
    
    # Mapeamento: coluna normalizada (Parquet/snake_case) → nome original (Excel)
    _COL_MAP = {
        'campanhas':        'Campanhas',
        'assunto':          'Assunto',
        'data_envio':       'Data de envio',
        'horario':          'Horario',
        'acoes':            'Ações',
        'enviados':         'Enviados',
        'entregues':        'Entregues',
        'aberturas_unicas': 'Aberturas Únicas',
        'aberturas_totais': 'Aberturas Totais',
        'cliques_unicos':   'Cliques únicos',
        'cliques_totais':   'Cliques totais',
        'nao_entregues':    'N.Entreg.',
        'remocoes':         'Remoções',
        'spam':             'Spam',
    }

    def _normalize_columns(self):
        """Renomeia colunas snake_case do Parquet para os nomes originais do Excel."""
        rename = {k: v for k, v in self._COL_MAP.items()
                  if k in self.df.columns and v not in self.df.columns}
        if rename:
            self.df.rename(columns=rename, inplace=True)

    def _prepare_data(self):
        """Prepara e limpa os dados para análise"""
        # Normalizar nomes: Parquet snake_case → nomes originais do Excel
        self._normalize_columns()

        # Ignorar linhas sem Horario, Ações ou Assunto
        self.df = filter_akna_dataframe(self.df, log_prefix="[AKNA Analytics]")

        # ✅ MODIFICAÇÃO: Remover validação de duplicatas para Email Marketing
        # Agora aceita dados iguais conforme solicitado
        # try:
        #     subset_cols = [c for c in ['Campanhas', 'Assunto', 'Data de envio', 'Enviados', 'Entregues']
        #                    if c in self.df.columns]
        #     self.df = self.df.drop_duplicates(subset=subset_cols) if subset_cols else self.df.drop_duplicates()
        # except Exception:
        #     self.df = self.df.drop_duplicates()

        # Garantir colunas numéricas obrigatórias com fallback zero
        for col in ['Enviados', 'Entregues', 'Aberturas Únicas', 'Cliques únicos', 'N.Entreg.', 'Remoções', 'Spam']:
            if col not in self.df.columns:
                self.df[col] = 0
            self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0)
        
        # ✅ MODIFICAÇÃO: Não remover duplicatas - permite dados iguais
        # Comentado para aceitar dados duplicados conforme solicitado

        # Garantir que Data de envio seja datetime
        if 'Data de envio' in self.df.columns:
            self.df['Data de envio'] = pd.to_datetime(self.df['Data de envio'], dayfirst=True, errors='coerce')
        else:
            self.df['Data de envio'] = pd.NaT
        
        # ✅ MODIFICAÇÃO: Sem validação de duplicatas - aceita dados iguais

        # Extrair mês e ano
        self.df['Mes'] = self.df['Data de envio'].dt.to_period('M')
        self.df['Ano'] = self.df['Data de envio'].dt.year
        self.df['Mes_Nome'] = self.df['Data de envio'].dt.strftime('%b/%Y')

        # Extrair hora do horário
        if 'Horario' in self.df.columns:
            self.df['Hora'] = self.df['Horario'].apply(parse_time_to_hour)
        else:
            self.df['Hora'] = None

        # Calcular taxas (sem divisão por zero)
        self.df['Taxa_Entrega']  = np.where(self.df['Enviados'] > 0,
            self.df['Entregues'] / self.df['Enviados'] * 100, 0)
        self.df['Taxa_Abertura'] = np.where(self.df['Entregues'] > 0,
            self.df['Aberturas Únicas'] / self.df['Entregues'] * 100, 0)
        self.df['Taxa_Clique']   = np.where(self.df['Entregues'] > 0,
            self.df['Cliques únicos'] / self.df['Entregues'] * 100, 0)
        self.df['CTOR_Calc']     = np.where(self.df['Aberturas Únicas'] > 0,
            self.df['Cliques únicos'] / self.df['Aberturas Únicas'] * 100, 0)
    
    def get_kpis(self):
        """
        Retorna os KPIs principais
        
        Returns:
            dict: Dicionário com os KPIs principais
        """
        total_enviados = int(self.df['Enviados'].sum())
        total_entregues = int(self.df['Entregues'].sum())
        total_aberturas = int(self.df['Aberturas Únicas'].sum())
        total_cliques = int(self.df['Cliques únicos'].sum())
        total_nao_entregues = int(self.df['N.Entreg.'].sum())
        total_remocoes = int(self.df['Remoções'].sum())
        total_spam = int(self.df['Spam'].sum())
        
        taxa_entrega = (total_entregues / total_enviados * 100) if total_enviados > 0 else 0
        taxa_abertura = (total_aberturas / total_entregues * 100) if total_entregues > 0 else 0
        taxa_clique = (total_cliques / total_entregues * 100) if total_entregues > 0 else 0
        ctor = (total_cliques / total_aberturas * 100) if total_aberturas > 0 else 0
        
        return {
            'total_campanhas': len(self.df),
            'total_enviados': total_enviados,
            'total_entregues': total_entregues,
            'total_aberturas': total_aberturas,
            'total_cliques': total_cliques,
            'total_nao_entregues': total_nao_entregues,
            'total_remocoes': total_remocoes,
            'total_spam': total_spam,
            'taxa_entrega': round(taxa_entrega, 2),
            'taxa_abertura': round(taxa_abertura, 2),
            'taxa_clique': round(taxa_clique, 2),
            'ctor': round(ctor, 2)
        }
    
    def get_funil_conversao(self):
        """
        Retorna dados para o gráfico de funil de conversão
        
        Returns:
            dict: Dados do funil com valores e percentuais
        """
        kpis = self.get_kpis()
        
        return {
            'labels': ['Enviados', 'Entregues', 'Abertos', 'Cliques'],
            'values': [
                kpis['total_enviados'],
                kpis['total_entregues'],
                kpis['total_aberturas'],
                kpis['total_cliques']
            ],
            'percentages': [
                100.0,
                kpis['taxa_entrega'],
                kpis['taxa_abertura'],
                kpis['taxa_clique']
            ]
        }
    
    def get_evolucao_temporal(self, ultimos_meses=6):
        """
        Retorna dados para o gráfico de evolução temporal
        
        Args:
            ultimos_meses: Número de meses a considerar (padrão: 6) - IGNORADO, usa TODOS os dados
        
        Returns:
            dict: Dados temporais com labels e séries
        """
        # ✅ CORRIGIDO: Usar TODOS os dados, não apenas últimos 6 meses
        # Antes: data_corte = datetime.now() - timedelta(days=ultimos_meses*30)
        # Antes: df_filtrado = self.df[self.df['Data de envio'] >= data_corte].copy()
        df_filtrado = self.df.copy()
        
        # Agrupar por mês usando período real (ordenação cronológica correta)
        temporal = df_filtrado.groupby('Mes').agg({
            'Enviados': 'sum',
            'Aberturas Únicas': 'sum',
            'Cliques únicos': 'sum'
        }).reset_index()
        
        temporal = temporal.sort_values('Mes')
        temporal['Mes_Nome'] = temporal['Mes'].dt.strftime('%b/%Y')
        
        return {
            'labels': temporal['Mes_Nome'].tolist(),
            'enviados': temporal['Enviados'].tolist(),
            'aberturas': temporal['Aberturas Únicas'].tolist(),
            'cliques': temporal['Cliques únicos'].tolist()
        }
    
    def get_campanhas_por_tipo(self, top_n=10):
        """
        Retorna dados para o gráfico de campanhas por tipo
        
        Args:
            top_n: Número de tipos a retornar (padrão: 10)
        
        Returns:
            dict: Dados de campanhas por tipo
        """
        por_tipo = self.df.groupby('Campanhas').agg({
            'Enviados': 'sum',
            'Aberturas Únicas': 'sum',
            'Cliques únicos': 'sum'
        }).sort_values('Enviados', ascending=False).head(top_n)
        
        return {
            'labels': por_tipo.index.tolist(),
            'enviados': por_tipo['Enviados'].tolist(),
            'aberturas': por_tipo['Aberturas Únicas'].tolist(),
            'cliques': por_tipo['Cliques únicos'].tolist()
        }
    
    def get_distribuicao_tipos(self):
        """
        Retorna dados para o gráfico de pizza de distribuição de tipos
        
        Returns:
            dict: Dados de distribuição percentual por tipo
        """
        distribuicao = self.df.groupby('Campanhas')['Enviados'].sum().sort_values(ascending=False)
        total = distribuicao.sum()
        
        # Agrupar tipos pequenos em "Outros"
        threshold = total * 0.02  # 2% do total
        labels = []
        values = []
        
        outros_valor = 0
        for tipo, valor in distribuicao.items():
            if valor >= threshold:
                labels.append(tipo)
                values.append(int(valor))
            else:
                outros_valor += valor
        
        if outros_valor > 0:
            labels.append('Outros')
            values.append(int(outros_valor))
        
        return {
            'labels': labels,
            'values': values
        }
    
    def get_melhores_horarios(self, top_n=10):
        """
        Retorna dados para o gráfico de melhores horários de envio
        
        Args:
            top_n: Número de horários a retornar (padrão: 10)
        
        Returns:
            dict: Dados de performance por horário
        """
        por_hora = self.df.groupby('Hora').agg({
            'Enviados': 'sum',
            'Aberturas Únicas': 'sum',
            'Taxa_Abertura': 'mean'
        }).sort_values('Aberturas Únicas', ascending=False).head(top_n)
        
        # Formatar horários
        labels = [f"{int(h):02d}:00" if not pd.isna(h) else "N/A" for h in por_hora.index]
        
        return {
            'labels': labels,
            'enviados': por_hora['Enviados'].tolist(),
            'aberturas': por_hora['Aberturas Únicas'].tolist(),
            'taxa_abertura': [round(x, 2) for x in por_hora['Taxa_Abertura'].tolist()]
        }
    
    def get_top_campanhas(self, top_n=20, criterio='Taxa_Abertura'):
        """
        Retorna as top campanhas por critério
        
        Args:
            top_n: Número de campanhas a retornar (padrão: 20)
            criterio: Coluna para ordenação (padrão: 'Taxa_Abertura')
        
        Returns:
            list: Lista de dicionários com dados das campanhas
        """
        # Filtrar campanhas de teste
        df_filtrado = self.df[
            (~self.df['Assunto'].str.contains('teste', case=False, na=False)) &
            (self.df['Enviados'] >= 10)  # Mínimo de 10 envios
        ].copy()
        
        top = df_filtrado.nlargest(top_n, criterio)
        
        campanhas = []
        for _, row in top.iterrows():
            campanhas.append({
                'assunto': row['Assunto'],
                'tipo': row['Campanhas'],
                'data_envio': (row['Data de envio'] if isinstance(row['Data de envio'], str) else row['Data de envio'].strftime('%d/%m/%Y')) if pd.notna(row['Data de envio']) else '',
                'enviados': int(row['Enviados']),
                'entregues': int(row['Entregues']),
                'aberturas': int(row['Aberturas Únicas']),
                'cliques': int(row['Cliques únicos']),
                'taxa_entrega': round(row['Taxa_Entrega'], 2),
                'taxa_abertura': round(row['Taxa_Abertura'], 2),
                'taxa_clique': round(row['Taxa_Clique'], 2),
                'ctor': round(row['CTOR_Calc'], 2)
            })
        
        return campanhas
    
    def get_all_data_formatted(self):
        """
        Retorna todos os dados formatados para a tabela principal
        
        Returns:
            list: Lista de dicionários com todos os registros
        """
        all_records = []
        for _, row in self.df.iterrows():
            # Trata data como string ou datetime
            data_val = row.get('Data de envio')
            if pd.isna(data_val) or data_val == '':
                data_str = ''
            elif isinstance(data_val, str):
                data_str = data_val  # Já está em formato string
            elif hasattr(data_val, 'strftime'):
                data_str = data_val.strftime('%d/%m/%Y')  # É um datetime
            else:
                data_str = str(data_val)
            all_records.append({
                'tipo': str(row.get('Campanhas', '')),
                'data_envio': data_str,           # campo usado pelo filtro JS do card
                'data': data_str,                 # alias mantido para compatibilidade
                'horario': str(row.get('Horario', '')),
                'acao': str(row.get('Ações', '')),
                'assunto': str(row.get('Assunto', '')),
                'enviados': int(row.get('Enviados', 0)),
                'entregues': int(row.get('Entregues', 0)),
                'aberturas': int(row.get('Aberturas Únicas', 0)),
                'aberturas_unicas': int(row.get('Aberturas Únicas', 0)),  # alias para JS
                'cliques': int(row.get('Cliques únicos', 0)),
                'taxa_entrega': round(row.get('Taxa_Entrega', 0), 2),
                'taxa_abertura': round(row.get('Taxa_Abertura', 0), 2),
                'taxa_clique': round(row.get('Taxa_Clique', 0), 2),
                'ctor': round(row.get('CTOR_Calc', 0), 2)
            })
        return all_records

    def get_analise_completa(self):
        """
        Retorna análise completa com todos os dados necessários para o dashboard
        
        Returns:
            dict: Dicionário com todos os dados analíticos
        """
        return {
            'kpis': self.get_kpis(),
            'funil': self.get_funil_conversao(),
            'evolucao_temporal': self.get_evolucao_temporal(),
            'campanhas_por_tipo': self.get_campanhas_por_tipo(),
            'distribuicao_tipos': self.get_distribuicao_tipos(),
            'melhores_horarios': self.get_melhores_horarios(),
            'top_campanhas': self.get_top_campanhas(),
            'all_data': self.get_all_data_formatted(),
            'ultima_atualizacao': datetime.now().strftime('%d/%m/%Y %H:%M')
        }
    
    def export_to_json(self, output_path):
        """
        Exporta a análise completa para JSON
        
        Args:
            output_path: Caminho do arquivo JSON de saída
        """
        analise = self.get_analise_completa()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analise, f, ensure_ascii=False, indent=2)
        
        return output_path


def processar_dados_akna(excel_path, output_json_path=None):
    """
    Função auxiliar para processar dados AKNA do Excel
    
    Args:
        excel_path: Caminho do arquivo Excel
        output_json_path: Caminho opcional para salvar JSON (padrão: None)
    
    Returns:
        dict: Análise completa dos dados
    """
    # Ler Excel
    df = pd.read_excel(excel_path)
    
    # Criar analisador
    analytics = AknaAnalytics(df)
    
    # Gerar análise
    analise = analytics.get_analise_completa()
    
    # Salvar JSON se solicitado
    if output_json_path:
        analytics.export_to_json(output_json_path)
    
    return analise


if __name__ == '__main__':
    # Teste do módulo
    import sys
    
    if len(sys.argv) > 1:
        excel_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else 'akna_analytics.json'
        
        print(f"Processando: {excel_file}")
        analise = processar_dados_akna(excel_file, output_file)
        print(f"Análise salva em: {output_file}")
        print(f"\nKPIs Principais:")
        for key, value in analise['kpis'].items():
            print(f"  {key}: {value}")
    else:
        print("Uso: python akna_analytics.py <arquivo_excel> [arquivo_json_saida]")