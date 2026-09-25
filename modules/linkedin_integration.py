"""
Módulo de Integração LinkedIn
Combina dados da API LinkedIn com dados das planilhas manuais
"""

import pandas as pd
from modules.data_ingestion import DataIngestor, DataNormalizer


class LinkedInIntegration:
    """
    Integra dados da API LinkedIn com dados das planilhas manuais.
    """
    
    def __init__(self):
        self.ingestor = DataIngestor()
        self.normalizer = DataNormalizer()
    
    def consolidate_linkedin_data(self, api_data, account_type='reynaldo', df_manual=None):
        """
        Consolida dados da API com dados das planilhas.
        """
        # 1. Usar dados fornecidos ou ingerir se necessário
        if df_manual is None:
            manual_files = self.ingestor.ingest_all()
            category = f'linkedin_{account_type}'
            df_manual = manual_files.get(category, pd.DataFrame())
        
        # 3. Normalizar dados das planilhas
        detailed_data_manual = self.normalizer.normalize_linkedin(df_manual)
        
        # 4. Calcular métricas agregadas das planilhas
        metrics_summary = self._calculate_metrics_summary(detailed_data_manual)
        has_manual_data = len(detailed_data_manual) > 0
        api_connected = bool(api_data.get('connected', False))

        display_name = api_data.get('name', 'LinkedIn')
        if account_type == 'abiarb' and (not api_connected or display_name in ('Desconectado', 'LinkedIn')):
            display_name = 'ABIARB SINDIBOR'

        display_headline = api_data.get('headline')
        if not display_headline or display_headline in ('Sem headline definida', None):
            if account_type == 'abiarb':
                display_headline = 'Associação Brasileira da Indústria de Artefatos de Borracha'
            elif has_manual_data:
                display_headline = 'Dados atualizados via planilhas de rede'

        if api_connected and has_manual_data:
            data_source = 'api+planilha'
            status_label = 'Conectado — API + Planilha'
        elif api_connected:
            data_source = 'api'
            status_label = 'Conectado via API'
        elif has_manual_data:
            data_source = 'planilha'
            status_label = 'Ativo — Dados via Planilha'
        else:
            data_source = 'nenhum'
            status_label = 'Aguardando Conexão / Importação Manual'

        last_checked = api_data.get('last_checked')
        if not last_checked and has_manual_data and detailed_data_manual:
            last_checked = detailed_data_manual[0].get('data_publicacao') or detailed_data_manual[0].get('data')

        # 5. Consolidar: dados da API + dados das planilhas
        consolidated = {
            # Dados da API (perfil) — considera ativo se API ou planilha tiver dados
            "connected": api_connected or has_manual_data,
            "api_connected": api_connected,
            "has_data": has_manual_data,
            "data_source": data_source,
            "status_label": status_label,
            "id": api_data.get('id'),
            "name": display_name,
            "profile_pic": api_data.get('profile_pic'),
            "headline": display_headline,
            "summary": api_data.get('summary'),
            "last_checked": last_checked,
            
            # Dados das planilhas (métricas)
            "posts_count": len(detailed_data_manual),
            "total_impressoes": metrics_summary['impressoes_total'],
            "total_cliques": metrics_summary['cliques_total'],
            "total_reacoes": metrics_summary['reacoes_total'],
            "total_comentarios": metrics_summary['comentarios_total'],
            "total_compartilhamentos": metrics_summary['compartilhamentos_total'],
            "media_engajamento": metrics_summary['media_engajamento'],
            
            # Dados detalhados das planilhas
            "detailed_data_manual": detailed_data_manual,
            
            # Resumo por tipo de engajamento
            "resumo_metricas": {
                "impressoes": {
                    "organicas": metrics_summary['impressoes_organicas'],
                    "patrocinadas": metrics_summary['impressoes_patrocinadas'],
                    "total": metrics_summary['impressoes_total'],
                    "unicas_organicas": metrics_summary['impressoes_unicas_organicas']
                },
                "cliques": {
                    "organicos": metrics_summary['cliques_organicos'],
                    "patrocinados": metrics_summary['cliques_patrocinados'],
                    "total": metrics_summary['cliques_total']
                },
                "reacoes": {
                    "organicas": metrics_summary['reacoes_organicas'],
                    "patrocinadas": metrics_summary['reacoes_patrocinadas'],
                    "total": metrics_summary['reacoes_total']
                },
                "comentarios": {
                    "organicos": metrics_summary['comentarios_organicos'],
                    "patrocinados": metrics_summary['comentarios_patrocinados'],
                    "total": metrics_summary['comentarios_total']
                },
                "compartilhamentos": {
                    "organicos": metrics_summary['compartilhamentos_organicos'],
                    "patrocinados": metrics_summary['compartilhamentos_patrocinados'],
                    "total": metrics_summary['compartilhamentos_total']
                },
                "engajamento": {
                    "organico": metrics_summary['taxa_engajamento_organico'],
                    "patrocinado": metrics_summary['taxa_engajamento_patrocinado'],
                    "total": metrics_summary['taxa_engajamento_total']
                }
            }
        }
        
        return consolidated
    
    @staticmethod
    def _calculate_metrics_summary(detailed_data):
        summary = {
            'impressoes_organicas': 0, 'impressoes_patrocinadas': 0, 'impressoes_total': 0, 'impressoes_unicas_organicas': 0,
            'cliques_organicos': 0, 'cliques_patrocinados': 0, 'cliques_total': 0,
            'reacoes_organicas': 0, 'reacoes_patrocinadas': 0, 'reacoes_total': 0,
            'comentarios_organicos': 0, 'comentarios_patrocinados': 0, 'comentarios_total': 0,
            'compartilhamentos_organicos': 0, 'compartilhamentos_patrocinados': 0, 'compartilhamentos_total': 0,
            'taxa_engajamento_organico': '0%', 'taxa_engajamento_patrocinado': '0%', 'taxa_engajamento_total': '0%',
            'media_engajamento': '0%',
        }
        if not detailed_data: return summary
        for item in detailed_data:
            summary['impressoes_organicas'] += item.get('impressoes_organicas', 0)
            summary['impressoes_patrocinadas'] += item.get('impressoes_patrocinadas', 0)
            summary['impressoes_total'] += item.get('impressoes_total', 0)
            summary['impressoes_unicas_organicas'] += item.get('impressoes_unicas_organicas', 0)
            summary['cliques_organicos'] += item.get('cliques_organicos', 0)
            summary['cliques_patrocinados'] += item.get('cliques_patrocinados', 0)
            summary['cliques_total'] += item.get('cliques_total', 0)
            summary['reacoes_organicas'] += item.get('reacoes_organicas', 0)
            summary['reacoes_patrocinadas'] += item.get('reacoes_patrocinadas', 0)
            summary['reacoes_total'] += item.get('reacoes_total', 0)
            summary['comentarios_organicos'] += item.get('comentarios_organicos', 0)
            summary['comentarios_patrocinados'] += item.get('comentarios_patrocinados', 0)
            summary['comentarios_total'] += item.get('comentarios_total', 0)
            summary['compartilhamentos_organicos'] += item.get('compartilhamentos_organicos', 0)
            summary['compartilhamentos_patrocinados'] += item.get('compartilhamentos_patrocinados', 0)
            summary['compartilhamentos_total'] += item.get('compartilhamentos_total', 0)
        
        taxas_totais = []
        for item in detailed_data:
            taxa_tot = item.get('taxa_engajamento_total', '0%')
            try: taxas_totais.append(float(taxa_tot.rstrip('%')))
            except: pass
        if taxas_totais: summary['taxa_engajamento_total'] = f"{sum(taxas_totais) / len(taxas_totais):.2f}%"
        
        total_eng = summary['reacoes_total'] + summary['comentarios_total'] + summary['compartilhamentos_total']
        if summary['impressoes_total'] > 0:
            summary['media_engajamento'] = f"{(total_eng / summary['impressoes_total']) * 100:.2f}%"
        return summary
