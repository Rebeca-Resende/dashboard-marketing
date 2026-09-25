import requests
import json
import pandas as pd
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from openai import OpenAI
from modules.data_ingestion import DataIngestor, DataNormalizer
from modules.data_manager import DataManager
from modules.akna_analytics import AknaAnalytics
from modules.iob_dashboard import load_iob_dashboard
from modules.sites_dashboard import load_sites_dashboard
from modules.conecta_dashboard import load_conecta_dashboard, empty_conecta_payload
from modules.ga4_properties import (
    build_base_report_request,
    ga4_property_path,
    resolve_property_ids,
)
from modules.linkedin_integration import LinkedInIntegration
from modules.instagram_insights import fetch_instagram_insights, empty_instagram_insights
from modules.facebook_insights import fetch_facebook_insights, empty_facebook_insights
from modules.meta_post_summary import build_meta_resumo, empty_meta_resumo
from modules.youtube_insights import fetch_youtube_insights, empty_youtube_insights
from modules.multi_sheet_loader import load_akna_data_multi_sheet
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    OrderBy
)
from googleapiclient.discovery import build
from google.oauth2 import service_account
import os
import copy
import re
import unicodedata

class SocialAPIClient:
    def __init__(self, config_path='config.json'):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # OpenAI
        import os
        openai_key = os.environ.get("OPENAI_API_KEY") or self.config.get('openai', {}).get('api_key')
        self.openai_client = OpenAI(api_key=openai_key) if openai_key else None

        # YouTube Setup
        self.youtube = None
        self.yt_channel_id = None
        self._setup_youtube()

        # GA4 — mesma service account; uma consulta por propriedade
        ga_cfg = self.config.get("google_analytics", {})
        sa_path = ga_cfg.get("service_account_file", "service_account.json")
        self.ga4_client = self._setup_ga4(sa_path)

        from modules.ga4_properties import KEY_SITE_PRIMARY, KEY_SITE_SECONDARY
        from modules.site_config import primary_site_profile, secondary_site_profile, gsc_site_url_from_config

        self.ga4_property_ids = resolve_property_ids(self.config)
        self.ga4_property_id = self.ga4_property_ids[KEY_SITE_PRIMARY]
        self.ga4_conecta_property_id = self.ga4_property_ids[KEY_SITE_SECONDARY]
        self._primary_site_profile = primary_site_profile(self.config)
        self._secondary_site_profile = secondary_site_profile(self.config)
        self._gsc_primary_site_url = gsc_site_url_from_config(self.config, "primary")

        secondary_cfg = self.config.get("site_secondary") or self.config.get("site_conecta", {})
        self.site_conecta_enabled = bool(secondary_cfg.get("enabled", True))

        self.search_console = self._setup_search_console()
        
        # Meta
        self._setup_meta()
        # LinkedIn
        # Suporte a múltiplas contas
        self.linkedin_reynaldo_config = self.config.get('linkedin_reynaldo', {})
        self.linkedin_abiarb_config = self.config.get('linkedin_abiarb', {})

        # Akna
        self.akna_config = self.config.get('akna', {})

        # Ingestão e Persistência
        self.ingestor = DataIngestor()
        self.normalizer = DataNormalizer()
        self.data_manager = DataManager()

    def _setup_search_console(self):
        sa_path = 'service_account.json'
        if os.path.exists(sa_path):
            credentials = service_account.Credentials.from_service_account_file(
              sa_path,
              scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
     )
            return build("searchconsole", "v1", credentials=credentials)
        return None
       
    def testar_search_console(self):
      if not self.search_console:
        print("Search Console não inicializado")
        return

      site_url = self._gsc_primary_site_url if hasattr(self, "_gsc_primary_site_url") else ""
      if not site_url:
          print("Configure site_primary.gsc_site_url (ou url) no config.json para testar o Search Console.")
          return
      response = self.search_console.searchanalytics().query(
        siteUrl=site_url,
        body={
            "startDate": "2024-01-01",
            "endDate": "2024-01-31",
            "dimensions": ["query"],
            "rowLimit": 5
        }
    ).execute()

      print(response)

    GOOGLE_OAUTH_SCOPES = [
        'https://www.googleapis.com/auth/analytics.readonly',
        'https://www.googleapis.com/auth/youtube.readonly',
        'https://www.googleapis.com/auth/yt-analytics.readonly',
        'https://www.googleapis.com/auth/webmasters.readonly',
    ]

    def _load_google_creds(self):
        token_file = 'token.json'
        if not os.path.exists(token_file):
            return None
        try:
            creds = Credentials.from_authorized_user_file(token_file, self.GOOGLE_OAUTH_SCOPES)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(token_file, 'w', encoding='utf-8') as fh:
                    fh.write(creds.to_json())
            return creds
        except Exception as exc:
            print(f"  [AVISO] Falha ao carregar token OAuth ({token_file}): {exc}")
            print("  Execute: python autenticar_google_oauth.py")
            return None

    @staticmethod
    def _parse_record_date(item):
        """Extrai datetime de um registro (redes sociais, Akna, etc.)."""
        if isinstance(item.get('created_time'), datetime):
            return item.get('created_time')
        if isinstance(item.get('timestamp'), datetime):
            return item.get('timestamp')

        s = (
            item.get('data_publicacao')
            or item.get('data_envio')
            or item.get('data')
            or item.get('Data')
            or ''
        )
        if isinstance(s, datetime):
            return s
        if isinstance(s, pd.Timestamp):
            return s.to_pydatetime()

        if isinstance(s, str) and s.strip():
            if '/' in s:
                parts = s.strip().split('/')
                if len(parts) == 3:
                    try:
                        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                        return datetime(year, month, day)
                    except (ValueError, TypeError):
                        pass
            try:
                return datetime.fromisoformat(s.strip().rstrip('Z'))
            except (ValueError, TypeError):
                pass
        return None

    def _filter_last_30_days_for_ai(self, records):
        """
        Filtra registros dos últimos 30 dias (janela móvel ~1 mês).
        """
        if not records:
            return []

        cutoff = datetime.now() - timedelta(days=30)
        out = []
        for item in records:
            dt = self._parse_record_date(item)
            if dt and dt >= cutoff:
                out.append(item)
        return out

    def _filter_akna_last_month_for_ai(self, records):
        """
        Akna: apenas campanhas do último mês civil (ex.: em maio/2026 → abril/2026).
        Reduz drasticamente o volume enviado à OpenAI.
        """
        if not records:
            return []

        now = datetime.now()
        first_current = datetime(now.year, now.month, 1)
        if now.month == 1:
            first_prev = datetime(now.year - 1, 12, 1)
        else:
            first_prev = datetime(now.year, now.month - 1, 1)

        out = []
        for item in records:
            dt = self._parse_record_date(item)
            if dt and dt >= first_prev and dt < first_current:
                out.append(item)
        return out

    @staticmethod
    def _akna_summary_for_ai(akna_records):
        """KPIs de e-mail calculados só com as campanhas enviadas à IA (último mês)."""
        if not akna_records:
            return {
                'total_campanhas': 0,
                'total_enviados': 0,
                'total_aberturas': 0,
                'total_cliques': 0,
                'taxa_abertura': 0,
                'taxa_clique': 0,
                'taxa_entrega': 0,
                'ctor': 0,
                'periodo': 'último mês civil',
            }

        def num(key):
            total = 0
            for row in akna_records:
                val = row.get(key, 0)
                try:
                    total += int(float(val))
                except (TypeError, ValueError):
                    pass
            return total

        enviados = num('enviados')
        entregues = num('entregues')
        aberturas = num('aberturas_unicas') or num('aberturas_totais')
        cliques = num('cliques_unicos') or num('cliques_totais')

        taxa_entrega = round(entregues / enviados * 100, 2) if enviados else 0
        taxa_abertura = round(aberturas / entregues * 100, 2) if entregues else 0
        taxa_clique = round(cliques / entregues * 100, 2) if entregues else 0
        ctor = round(cliques / aberturas * 100, 2) if aberturas else 0

        return {
            'total_campanhas': len(akna_records),
            'total_enviados': enviados,
            'total_aberturas': aberturas,
            'total_cliques': cliques,
            'taxa_abertura': taxa_abertura,
            'taxa_clique': taxa_clique,
            'taxa_entrega': taxa_entrega,
            'ctor': ctor,
            'periodo': 'último mês civil',
        }

    def _analyze_with_batching(self, data_for_ai, batch_size=100):
        """
        Divide os dados em lotes menores para evitar ultrapassar o limite de tokens do OpenAI.
        Processa cada lote separadamente e consolida os resultados.
        
        Args:
            data_for_ai: Dicionário contendo os dados a analisar
            batch_size: Número máximo de registros por lote (padrão 100)
        
        Returns:
            Dicionário com o relatório consolidado e fontes
        """
        import time
        
        # Dicionário para armazenar análises por plataforma
        platform_analyses = {}
        
        # Extrair dados detalhados de cada plataforma
        platforms_data = {
            'youtube': data_for_ai.get('youtube', {}).get('detailed_data', []),
            'facebook': data_for_ai.get('facebook', {}).get('detailed_data', []),
            'instagram': data_for_ai.get('instagram', {}).get('detailed_data', []),
            'linkedin': data_for_ai.get('linkedin', {}).get('detailed_data', []),
            'akna': data_for_ai.get('akna_manual', {}).get('detailed_data', [])
        }
        
        # Resumos e métricas (enviar em um lote menor)
        summary_data = {
            'youtube_summary': {
                'subscribers': data_for_ai.get('youtube', {}).get('subscribers', 0),
                'total_views': data_for_ai.get('youtube', {}).get('total_views', 0)
            },
            'facebook_summary': {
                'followers': data_for_ai.get('facebook', {}).get('followers', 0),
                'total_interactions': data_for_ai.get('facebook', {}).get('total_interactions', 0)
            },
            'instagram_summary': {
                'followers': data_for_ai.get('instagram', {}).get('followers', 0),
                'total_interactions': data_for_ai.get('instagram', {}).get('total_interactions', 0)
            },
            'linkedin_summary': {
                'followers': data_for_ai.get('linkedin', {}).get('followers', 0),
                'total_interactions': data_for_ai.get('linkedin', {}).get('total_interactions', 0)
            },
            'email_marketing_summary': self._akna_summary_for_ai(
                platforms_data.get('akna', [])
            ),
            'sites': data_for_ai.get('sites', {}).get('metricas_principais', {})
        }
        
        print("\n🔄 Processando análise com OpenAI em lotes...")
        
        # Processar cada plataforma em lotes
        for platform_name, records in platforms_data.items():
            if not records:
                print(f"  ⏭️ {platform_name}: Sem dados")
                continue
            
            total_batches = (len(records) + batch_size - 1) // batch_size
            print(f"  📊 {platform_name}: {len(records)} registros em {total_batches} lote(s)")
            
            platform_analyses[platform_name] = []
            
            # Processar em lotes
            for batch_idx in range(total_batches):
                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, len(records))
                batch_records = records[start_idx:end_idx]
                
                try:
                    batch_prompt = f"""
Análise de dados do {platform_name.upper()}:

Registros ({batch_idx + 1}/{total_batches}):
{json.dumps(batch_records, indent=2, default=lambda x: x.isoformat() if hasattr(x, 'isoformat') else str(x))}

TAREFA: Analise estes registros do {platform_name}. Extraia:
1. Engajamento médio
2. Melhor e pior desempenho
3. Tendências identificadas

Responda de forma concisa (máximo 5 linhas).
"""
                    
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4.1-mini",
                        messages=[{"role": "user", "content": batch_prompt}],
                        max_tokens=500
                    )
                    
                    analysis = response.choices[0].message.content
                    platform_analyses[platform_name].append(analysis)
                    print(f"    ✓ Lote {batch_idx + 1}/{total_batches} processado")
                    
                    # Pequeno delay para respeitar rate limits
                    if batch_idx < total_batches - 1:
                        time.sleep(1)
                        
                except Exception as e:
                    print(f"    ⚠️ Erro no lote {batch_idx + 1}: {e}")
                    platform_analyses[platform_name].append(f"Erro ao processar lote: {e}")
        
        # 3. Gerar relatório consolidado com os resumos
        try:
            print(f"  📈 Gerando relatório consolidado...")
            
            consolidated_prompt = f"""
Objetivo: Gerar relatório comparativo de marcas REAIS do nicho terceiro setor.

RESUMO DE MÉTRICAS (últimos 30 dias):
{json.dumps(summary_data, indent=2)}

ANÁLISES DETALHADAS POR PLATAFORMA:
{json.dumps(platform_analyses, indent=2)}

TAREFA:
1. Monte uma tabela comparativa: Métrica | Valor Interno | Benchmark Nicho | Status
2. DÊ ATENÇÃO ESPECIAL ao E-MAIL MARKETING (taxas de abertura, cliques, CTR,CTOR)
3. Cite URLS de fontes reais (benchmarks de ONGs, sindicatos patronais, etc.)
4. Indique se está ACIMA, ABAIXO ou NA MÉDIA do setor
5. Inclua benchmarks específicos para email marketing (média do setor: 20-25% abertura, 2-3% CTR)
6. Suggira 3 ações concretas para melhorar o email marketing

Requisito: Use APENAS dados reais com fontes confiáveis (2024-2025).
Foque em comparativos de email marketing com benchmarks do terceiro setor.
"""
            
            final_response = self.openai_client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": consolidated_prompt}],
                max_tokens=2000
            )
            
            final_report = final_response.choices[0].message.content
            urls = re.findall(r'https?://[^\s\)\],]+', final_report)
            
            return {
                "report": final_report,
                "fontes": list(set(urls))
            }
            
        except Exception as e:
            print(f"  ❌ Erro ao gerar relatório consolidado: {e}")
            return {
                "report": "Erro ao gerar análise comparativa.",
                "fontes": []
            }

    def _setup_ga4(self, sa_path="service_account.json"):
        if os.path.exists(sa_path):
            return BetaAnalyticsDataClient.from_service_account_json(sa_path)
        print(f"  [AVISO] GA4: arquivo de credenciais não encontrado ({sa_path})")
        return None

    def _setup_youtube(self):
        """Configura o cliente do YouTube usando API Key ou OAuth2."""
        yt_config = self.config.get('youtube', {})
        api_key = yt_config.get('api_key')
        self.yt_channel_id = yt_config.get('channel_id')

        if api_key:
            # Prioridade para API Key separada
            try:
                self.youtube = build('youtube', 'v3', developerKey=api_key)
                print("YouTube configurado via API Key.")
            except Exception as e:
                print(f"Erro ao configurar YouTube via API Key: {e}")
        
        if not self.youtube:
            # Fallback para OAuth2 (comportamento original)
            self.creds = self._load_google_creds()
            if self.creds:
                try:
                    self.youtube = build('youtube', 'v3', credentials=self.creds)
                    print("YouTube configurado via OAuth2.")
                except Exception as e:
                    print(f"Erro ao configurar YouTube via OAuth2: {e}")

    def _get_yt_analytics_client(self):
        creds = self._load_google_creds()
        if not creds:
            return None
        try:
            return build('youtubeAnalytics', 'v2', credentials=creds)
        except Exception as exc:
            print(f"Erro ao configurar YouTube Analytics: {exc}")
            return None

    def _setup_meta(self):
        self.meta_config = self.config.get('meta', {})
        self.access_token = str(self.meta_config.get('access_token', '')).strip().replace('\n', '').replace('\r', '')
        self.page_id = str(self.meta_config.get('page_id', '')).strip()
        self.instagram_id = str(self.meta_config.get('instagram_id', '')).strip()

    def _format_duration(self, iso_duration):
        try:
            pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
            match = re.match(pattern, iso_duration)
            if not match: return "00:00:00"
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except: return "00:00:00"

    # Janela de lookback: posts dos últimos N dias são SEMPRE re-buscados
    # para capturar novos likes/comentários em publicações antigas.
    # Ajustado para 730 dias (2 anos) para garantir cobertura total de postagens recentes e antigas.
    ENGAGEMENT_LOOKBACK_DAYS = 730

    def _get_incremental_start_date(self, source_name):
        """
        Detecta a data de sincronização incremental com janela de lookback.

        Estratégia:
        - Se não houver histórico: retorna None (bootstrap completo).
        - Se houver histórico: usa (hoje - LOOKBACK_DAYS) como ponto de partida,
          garantindo que posts dos últimos 365 dias sejam sempre re-buscados para
          capturar curtidas/comentários tardios em publicações antigas.

        A deduplicação por ID em _save_and_deduplicate_meta garante que posts
        re-buscados atualizem o registro existente sem criar duplicatas.
        """
        last_date = self.data_manager.get_last_date(source_name)
        lookback_date = datetime.now() - timedelta(days=self.ENGAGEMENT_LOOKBACK_DAYS)

        if last_date is None:
            print(f"  ℹ️  Bootstrap: Nenhum histórico encontrado para '{source_name}'. Buscando todo o histórico...")
            return None

        last_date_dt = pd.to_datetime(last_date, errors='coerce')
        if pd.isna(last_date_dt):
            print(f"  ⚠️  Data inválida no histórico de '{source_name}'. Usando lookback de {self.ENGAGEMENT_LOOKBACK_DAYS} dias.")
            sync_from = lookback_date
        else:
            # Sempre re-busca os últimos 365 dias para pegar engajamentos tardios.
            # Se o último post for mais antigo que 30 dias, usa a data do último post
            # para não perder nenhum dado novo publicado nesse intervalo.
            sync_from = min(last_date_dt.to_pydatetime(), lookback_date)

        print(f"  ℹ️  Sincronização com lookback {self.ENGAGEMENT_LOOKBACK_DAYS}d: buscando desde {sync_from.strftime('%Y-%m-%d')}"
              f" (último registro: {last_date_dt.strftime('%Y-%m-%d') if not pd.isna(last_date_dt) else 'N/A'})")
        return sync_from

    def _save_and_deduplicate_meta(self, source_name, new_records):
        """
        Salva registros da API Meta com deduplicação por ID.
        Posts re-buscados pelo lookback têm seus dados de engajamento ATUALIZADOS
        (keep='last' garante que a versão mais nova, com mais likes/comentários, prevalece).
        """
        if not new_records:
            return

        df_new = pd.DataFrame(new_records)
        if 'id' in df_new.columns:
            df_new = self.data_manager._normalize_id_column(df_new, source_name)

        # Determina colunas-chave
        id_col = 'id' if 'id' in df_new.columns else None
        date_col = 'created_time' if 'created_time' in df_new.columns else (
                   'timestamp' if 'timestamp' in df_new.columns else
                   'data_publicacao' if 'data_publicacao' in df_new.columns else None)

        # Converte datas para datetime
        if date_col and date_col in df_new.columns:
            df_new[date_col] = pd.to_datetime(df_new[date_col], dayfirst=True, errors='coerce')

        file_path = self.data_manager._get_file_path(source_name)

        if os.path.exists(file_path):
            existing_df = pd.read_parquet(file_path)
            if id_col and id_col in existing_df.columns:
                existing_df = self.data_manager._normalize_id_column(existing_df, source_name)
            # Novos registros vêm após os existentes → drop_duplicates(keep='last')
            # garante que dados re-buscados (engajamento atualizado) sobrescrevem os antigos
            combined_df = pd.concat([existing_df, df_new], ignore_index=True)

            if id_col and id_col in combined_df.columns:
                dedup_cols = [id_col]
            elif date_col and date_col in combined_df.columns:
                dedup_cols = [date_col]
            else:
                dedup_cols = None

            if dedup_cols:
                before = len(combined_df)
                # DEBUG: Ver soma de interações antes
                inter_before = combined_df['interacao'].sum() if 'interacao' in combined_df.columns else 0
                
                combined_df.drop_duplicates(subset=dedup_cols, keep='last', inplace=True)
                
                # DEBUG: Ver soma de interações depois
                inter_after = combined_df['interacao'].sum() if 'interacao' in combined_df.columns else 0
                
                updated = before - len(combined_df)
                if updated:
                    diff_inter = inter_after - inter_before
                    print(f"    [Update] {updated} post(s) atualizados em '{source_name}' (Variação interações: {diff_inter:+})")

            if date_col and date_col in combined_df.columns:
                combined_df = combined_df.sort_values(by=date_col, ascending=False)

            combined_df = self.data_manager._sanitize_dtypes(combined_df)
            combined_df.to_parquet(file_path, index=False)
        else:
            df_new = self.data_manager._sanitize_dtypes(df_new)
            df_new.to_parquet(file_path, index=False)

    def get_youtube_data(self):
        if not self.youtube:
            return {"subscribers": 0, "total_views": 0, "detailed_data": []}
        try:
            # Se não tivermos o channel_id, tentamos descobrir (só funciona com OAuth2 mine=True)
            if not self.yt_channel_id:
                try:
                    ch_req = self.youtube.channels().list(part='id,statistics,snippet', mine=True)
                    ch_res = ch_req.execute()
                    if ch_res.get('items'):
                        self.yt_channel_id = ch_res['items'][0]['id']
                except Exception as e:
                    print(f"Não foi possível descobrir o channel_id automaticamente (mine=True requer OAuth2): {e}")
            
            if not self.yt_channel_id:
                print("Aviso: Nenhum YouTube Channel ID fornecido ou encontrado.")
                return {"subscribers": 0, "total_views": 0, "detailed_data": []}

            ch_request = self.youtube.channels().list(part='statistics,snippet', id=self.yt_channel_id)
            ch_response = ch_request.execute()
            if not ch_response.get('items'):
                return {"subscribers": 0, "total_views": 0, "detailed_data": []}
                
            stats = ch_response['items'][0]['statistics']
            
            # Determinar ponto de partida da sincronização com lookback
            sync_from = self._get_incremental_start_date("youtube")
            
            # Buscar vídeos com paginação
            detailed_videos = []
            next_page_token = None
            
            print(f"\n📺 Iniciando busca de vídeos no YouTube (com lookback {self.ENGAGEMENT_LOOKBACK_DAYS}d)...")
            while True:
                try:
                    v_request = self.youtube.search().list(
                        part='snippet', 
                        channelId=self.yt_channel_id, 
                        order='date', 
                        type='video', 
                        maxResults=50,
                        pageToken=next_page_token
                    )
                    v_response = v_request.execute()
                    
                    current_batch = v_response.get('items', [])
                    if not current_batch:
                        break

                    # Processar vídeos em lote para reduzir chamadas à API de estatísticas
                    video_ids = [item['id']['videoId'] for item in current_batch if 'videoId' in item['id']]
                    if not video_ids:
                        break
                    
                    # Buscar estatísticas de todos os vídeos do lote de uma vez (mais eficiente)
                    v_stats_req = self.youtube.videos().list(part='statistics,contentDetails', id=','.join(video_ids))
                    v_stats_res = v_stats_req.execute()
                    stats_map = {item['id']: item for item in v_stats_res.get('items', [])}

                    for item in current_batch:
                        try:
                            if 'videoId' not in item['id']: continue
                            v_id = item['id']['videoId']
                            
                            # Tratamento robusto de data para evitar NaT
                            raw_date = item['snippet']['publishedAt']
                            try:
                                dt_obj = datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%SZ")
                            except:
                                try:
                                    # Fallback para o pandas que é mais flexível
                                    dt_obj = pd.to_datetime(raw_date, format='%Y-%m-%dT%H:%M:%SZ', errors='coerce').to_pydatetime()
                                except:
                                    # Se falhar totalmente, usa a data atual mas NÃO descarta o vídeo
                                    print(f"    [Aviso] Falha ao ler data '{raw_date}' do vídeo {v_id}. Usando data atual.")
                                    dt_obj = datetime.now()

                            v_data = stats_map.get(v_id)
                            if not v_data: continue
                            
                            v_stats = v_data['statistics']
                            v_details = v_data['contentDetails']
                            
                            # Se estamos sincronizando incrementalmente, parar quando atingir dados antigos
                            if sync_from and dt_obj < sync_from:
                                # Nota: No YouTube, como a ordem é 'date' (descendente), 
                                # podemos parar a paginação quando atingirmos a data limite.
                                pass 

                            detailed_videos.append({
                                "id": v_id,
                                "data_publicacao": dt_obj.strftime("%d/%m/%Y"),
                                "horario": dt_obj.strftime("%H:%M"),
                                "titulo_descricao": item['snippet']['title'],
                                "link_permanente": f"https://www.youtube.com/watch?v={v_id}",
                                "visualizacoes": int(v_stats.get('viewCount', 0)),
                                "curtidas": int(v_stats.get('likeCount', 0)),
                                "comentarios": int(v_stats.get('commentCount', 0)),
                                "interacao": int(v_stats.get('likeCount', 0)) + int(v_stats.get('commentCount', 0)),
                                "duracao": self._format_duration(v_details.get('duration', 'PT0S')),
                                "created_time": dt_obj
                            })
                        except Exception as ve:
                            print(f"Erro ao processar vídeo individual: {ve}")
                            continue
                    
                    print(f"  → {len(detailed_videos)} vídeos coletados até agora...")
                    
                    # No YouTube, a ordem é descendente. 
                    # O usuário solicitou buscar o máximo possível para atualizar métricas.
                    last_video_date = detailed_videos[-1]['created_time'] if detailed_videos else None
                    if sync_from and last_video_date and last_video_date < sync_from:
                        # Continuamos buscando para atualizar métricas de vídeos antigos
                        pass
                        
                    next_page_token = v_response.get('nextPageToken')
                    if not next_page_token:
                        break
                        
                except Exception as se:
                    print(f"Erro na busca de vídeos: {se}")
                    break
            
            # Persistir dados coletados com deduplicação
            if detailed_videos:
                self._save_and_deduplicate_meta("youtube", detailed_videos)
                print(f"  ✓ {len(detailed_videos)} vídeos sincronizados para YouTube")
            
            return {
                "subscribers": int(stats.get('subscriberCount', 0)),
                "total_views": int(stats.get('viewCount', 0)),
                "detailed_data": detailed_videos
            }
        except Exception as e:
            print(f"Erro YouTube Real: {e}")
            return {"subscribers": 0, "total_views": 0, "detailed_data": []}

    def get_meta_data(self):
        data = {
            "facebook": {"followers": 0, "total_interactions": 0, "detailed_data": []},
            "instagram": {"followers": 0, "total_interactions": 0, "detailed_data": []}
        }
        if not self.access_token:
            return data

        # 1. Facebook - Sincronização Incremental
        try:
            if self.page_id:
                print(f"\n📱 Facebook ID: {self.page_id}")
                fb_url = f"https://graph.facebook.com/v18.0/{self.page_id}"
                fb_params = {
                    "fields": "followers_count,fan_count",
                    "access_token": self.access_token
                }
                fb_res = requests.get(fb_url, params=fb_params, timeout=10).json()
                data["facebook"]["followers"] = fb_res.get("followers_count") or fb_res.get("fan_count") or 0

                # Determinar ponto de partida da sincronização
                sync_from = self._get_incremental_start_date("meta_facebook")
                
                # Paginação para pegar posts
                posts_url = f"https://graph.facebook.com/v18.0/{self.page_id}/posts"
                posts_params = {
                    "fields": "id,message,created_time,permalink_url,status_type,insights.metric(post_engagements)",
                    "limit": 100,
                    "access_token": self.access_token
                }
                
                total_fb_inter = 0
                collected_fb_posts = []
                
                while posts_url:
                    print(f"  → Buscando posts Facebook...")
                    res = requests.get(posts_url, params=posts_params, timeout=15).json()
                    if "error" in res: 
                        print(f"  ❌ Erro na API FB: {res['error']}")
                        break
                    
                    for post in res.get("data", []):
                        dt_obj = datetime.strptime(post["created_time"], "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
                        
                        # Se estamos sincronizando incrementalmente, parar quando atingir dados antigos
                        if sync_from and dt_obj < sync_from:
                            # O usuário solicitou buscar "tudo sempre" para atualizar interações
                            # Então não paramos aqui, apenas registramos se necessário
                            pass

                        eng = 0
                        insights = post.get("insights", {}).get("data", [])
                        if insights:
                            eng = insights[0]["values"][0]["value"]
                        
                        total_fb_inter += eng
                        
                        # Coletar para persistência
                        collected_fb_posts.append({
                            "id": post.get("id"),
                            "data_publicacao": dt_obj.strftime("%d/%m/%Y"),
                            "horario": dt_obj.strftime("%H:%M"),
                            "created_time": dt_obj,  # Para deduplicação
                            "titulo_descricao": post.get("message", "Sem legenda")[:100],
                            "link_permanente": post.get("permalink_url"),
                            "interacao": eng,
                            "seguidores": data["facebook"]["followers"],
                            "status_type": post.get("status_type", ""),
                            "tipos_publicacao": post.get("status_type", ""),
                        })
                    

                    posts_url = res.get("paging", {}).get("next")
                    posts_params = {}
                
                # Persistir dados coletados com deduplicação
                if collected_fb_posts:
                    self._save_and_deduplicate_meta("meta_facebook", collected_fb_posts)
                    print(f"  ✓ {len(collected_fb_posts)} posts sincronizados para Facebook")
                
                data["facebook"]["total_interactions"] = total_fb_inter
                data["facebook"]["detailed_data"] = collected_fb_posts

                fb_insights = fetch_facebook_insights(self.page_id, self.access_token)
                data["facebook"].update(fb_insights)

        except Exception as e:
            print(f"  ❌ Erro Facebook: {e}")

        # 2. Instagram - Sincronização Incremental
        try:
            if self.instagram_id:
                print(f"\n📸 Instagram ID: {self.instagram_id}")
                ig_url = f"https://graph.facebook.com/v18.0/{self.instagram_id}"
                ig_params = {
                    "fields": "followers_count",
                    "access_token": self.access_token
                }
                ig_res = requests.get(ig_url, params=ig_params).json()
                data["instagram"]["followers"] = ig_res.get("followers_count", 0)

                # Determinar ponto de partida da sincronização
                sync_from = self._get_incremental_start_date("meta_instagram")
                
                media_url = f"https://graph.facebook.com/v18.0/{self.instagram_id}/media"
                media_params = {
                    "fields": "id,caption,permalink,timestamp,like_count,comments_count,media_type",
                    "limit": 100,
                    "access_token": self.access_token
                }
                
                total_ig_inter = 0
                collected_ig_media = []
                
                while media_url:
                    print(f"  → Buscando posts Instagram...")
                    res = requests.get(media_url, params=media_params, timeout=15).json()
                    if "error" in res: 
                        print(f"  ❌ Erro na API IG: {res['error']}")
                        break
                    
                    for media in res.get("data", []):
                        dt_obj = datetime.strptime(media["timestamp"], "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
                        
                        # Se estamos sincronizando incrementalmente, parar quando atingir dados antigos
                        if sync_from and dt_obj < sync_from:
                            # O usuário solicitou buscar "tudo sempre" para atualizar interações
                            # Então não paramos aqui, apenas registramos se necessário
                            pass

                        # Coleta de interações reais
                        likes = media.get("like_count", 0)
                        comments = media.get("comments_count", 0)
                        inter = likes + comments
                        
                        total_ig_inter += inter
                        
                        taxa = (inter / data["instagram"]["followers"] * 100) if data["instagram"]["followers"] > 0 else 0
                        
                        # Coletar para persistência
                        collected_ig_media.append({
                            "id": media.get("id"),
                            "data_publicacao": dt_obj.strftime("%d/%m/%Y"),
                            "horario": dt_obj.strftime("%H:%M"),
                            "timestamp": dt_obj,  # Para deduplicação
                            "titulo_descricao": media.get("caption", "Sem legenda")[:100],
                            "link_permanente": media.get("permalink"),
                            "interacao": inter,
                            "taxa_interacao": f"{taxa:.2f}%",
                            "tipos_publicacao": media.get("media_type", "IMAGE")
                        })
                    

                    media_url = res.get("paging", {}).get("next")
                    media_params = {}
                
                # Persistir dados coletados com deduplicação
                if collected_ig_media:
                    self._save_and_deduplicate_meta("meta_instagram", collected_ig_media)
                    print(f"  ✓ {len(collected_ig_media)} posts sincronizados para Instagram")
                
                data["instagram"]["total_interactions"] = total_ig_inter
                data["instagram"]["detailed_data"] = collected_ig_media

                insights = fetch_instagram_insights(self.instagram_id, self.access_token)
                data["instagram"].update(insights)

        except Exception as e:
            print(f"  ❌ Erro Instagram: {e}")
            
        return data

    def _verify_ga4_properties(self):
        """Valida conexão GA4 — uma RunReportRequest por propriedade."""
        if not self.ga4_client:
            print("  [AVISO] GA4: cliente não inicializado")
            return

        for nome, property_id in self.ga4_property_ids.items():
            if not str(property_id or "").strip():
                print(f"  [AVISO] GA4 {nome}: configure ga4_property_id em config.json")
                continue
            try:
                request = build_base_report_request(property_id)
                response = self.ga4_client.run_report(request)
                total_users = sum(
                    int(row.metric_values[0].value)
                    for row in (response.rows or [])
                )
                print(
                    f"  [OK] GA4 {nome} ({ga4_property_path(property_id)}): "
                    f"{total_users} usuários ativos no período"
                )
            except Exception as exc:
                print(
                    f"  [ERRO] GA4 {nome} ({ga4_property_path(property_id)}): {exc}"
                )

    def get_sites_data(self):
        return load_sites_dashboard(
            ga4_client=self.ga4_client,
            property_id=self.ga4_property_id,
            oauth_creds=self._load_google_creds(),
            search_console=self.search_console,
            profile=self._primary_site_profile,
        )

    def get_site_conecta_data(self):
        if not self.site_conecta_enabled or not self.ga4_conecta_property_id:
            return empty_conecta_payload("Aguardando integração da API", self.config)
        return load_conecta_dashboard(
            ga4_client=self.ga4_client,
            property_id=self.ga4_conecta_property_id,
            oauth_creds=self._load_google_creds(),
            search_console=self.search_console,
            config=self.config,
        )

    def get_all_sites_data(self):
        """Carrega ambas as propriedades GA4 (consulta separada para cada uma)."""
        self._verify_ga4_properties()
        return {
            "sites": self.get_sites_data(),
            "site_conecta": self.get_site_conecta_data(),
        }

    def _extract_campanhas_por_porte(self, akna_records, limit=15):
        """Filtra campanhas Akna relacionadas a Por Porte / Santa Catarina para contexto da IA."""
        if not akna_records:
            return []
        keywords = ("por porte", "santa catarina", " sc ", "beneficios por porte", "benefícios por porte")
        found = []
        for row in akna_records:
            text = " ".join([
                str(row.get("campanhas", "")),
                str(row.get("acoes", "")),
                str(row.get("assunto", "")),
            ]).lower()
            if any(k in text for k in keywords):
                found.append({
                    "tipo": row.get("campanhas", ""),
                    "data": row.get("data_envio", ""),
                    "acao": row.get("acoes", ""),
                    "assunto": (row.get("assunto", "") or "")[:120],
                    "enviados": row.get("enviados", 0),
                    "aberturas": row.get("aberturas_unicas", 0),
                    "cliques": row.get("cliques_unicos", 0),
                })
        return found[:limit]

    @staticmethod
    def _fold_estado(nome):
        if not nome:
            return ""
        s = unicodedata.normalize("NFKD", str(nome))
        s = s.encode("ascii", "ignore").decode("ascii").lower().strip()
        aliases = {
            "sao paulo": "sao paulo",
            "state of sao paulo": "sao paulo",
            "santa catarina": "santa catarina",
        }
        return aliases.get(s, s)

    @staticmethod
    def _classificar_representacao_patronal(estado, usuarios=0):
        """
        Representação = sindicato patronal territorial do setor de artefatos de borracha.

        Sim  → apenas estados com entidade patronal do setor naquele estado:
               SP (SINDIBOR) e RS (SINBORSUL).
        Fraca → indústria/presença setorial, mas sem sindicato patronal local exclusivo.
        Não  → sem representação patronal relevante no estado.
        """
        key = SocialAPIClient._fold_estado(estado)

        if key in ("sao paulo",):
            return "Sim", "SINDIBOR — sindicato patronal do setor (base territorial SP)"
        if key == "rio grande do sul":
            return "Sim", "SINBORSUL — sindicato patronal do setor (base territorial RS)"

        if key == "santa catarina":
            return "Fraca", "Indústria presente, sem sindicato patronal local de borracha"

        industria_sem_patronal = {
            "parana", "minas gerais", "rio de janeiro",
            "goias", "bahia", "ceara", "espirito santo", "distrito federal",
        }
        if key in industria_sem_patronal or usuarios >= 10:
            return "Fraca", "Sem sindicato patronal local exclusivo do setor"

        if usuarios >= 3:
            return "Fraca", "Tráfego pontual sem representação patronal local"

        return "Não", "Sem representação patronal territorial do setor"

    def _build_classificacao_oficial(self, estados_ga4):
        """Classificação autoritativa de representação — não depende da inferência da IA."""
        rows = []
        for item in estados_ga4:
            estado = str(item.get("estado", "")).strip()
            if not estado:
                continue
            usuarios = int(item.get("usuarios", 0) or 0)
            sessoes = int(item.get("sessoes", 0) or 0)
            rep, nota = self._classificar_representacao_patronal(estado, usuarios)
            rows.append({
                "estado": estado,
                "usuarios": usuarios,
                "sessoes": sessoes,
                "representacao": rep,
                "nota_representacao": nota,
            })
        return rows

    def _merge_tabela_estados(self, classificacao_oficial, ia_estados):
        """Combina classificação oficial com sugestões da IA (oportunidade/prioridade)."""
        ia_map = {}
        for row in ia_estados or []:
            estado = str(row.get("estado", "")).strip()
            if estado:
                ia_map[self._fold_estado(estado)] = row

        merged = []
        for base in classificacao_oficial:
            estado = base["estado"]
            ia = ia_map.get(self._fold_estado(estado), {})
            rep = base["representacao"]

            oportunidade = (ia.get("oportunidade") or "")[:120]
            if not oportunidade:
                if rep == "Sim":
                    oportunidade = "Fortalecer engajamento digital da base sindical local"
                elif rep == "Fraca" and self._fold_estado(estado) == "santa catarina":
                    oportunidade = "Ampliar campanhas Por Porte — sem sindicato patronal local"
                elif rep == "Fraca":
                    oportunidade = "Prospecção regional — indústria sem sindicato patronal local"
                else:
                    oportunidade = "Baixa prioridade — sem presença patronal no estado"

            prioridade = ia.get("prioridade", "Baixa")
            if rep == "Não" and base["usuarios"] <= 2:
                prioridade = "Baixa"
            elif rep == "Fraca" and base["usuarios"] >= 5:
                prioridade = ia.get("prioridade") or "Alta"
            elif rep == "Sim":
                prioridade = ia.get("prioridade") or "Alta"

            merged.append({
                "estado": estado,
                "usuarios": base["usuarios"],
                "sessoes": base["sessoes"],
                "representacao": rep,
                "oportunidade": oportunidade,
                "prioridade": prioridade,
            })

        merged.sort(
            key=lambda r: (
                self._prioridade_ordem(r.get("prioridade")),
                -r.get("usuarios", 0),
            )
        )
        return merged

    def _parse_ia_json_response(self, raw_text):
        """Extrai JSON da resposta da IA."""
        if not raw_text:
            return None
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return None
        return None

    @staticmethod
    def _prioridade_ordem(prioridade):
        p = (prioridade or "").lower()
        if "alta" in p:
            return 0
        if "média" in p or "media" in p:
            return 1
        return 2

    def _analyze_sites_representacao(self, sites_data, campanhas_por_porte=None):
        """Analisa representação regional via IA — retorno em tabelas estruturadas."""
        empty = {
            "status": "indisponivel",
            "fontes": [],
            "foco_santa_catarina": "",
            "tabela_estados": [],
            "acoes": [],
        }
        if not self.openai_client:
            empty["foco_santa_catarina"] = "OpenAI não configurada."
            return empty

        localidades = sites_data.get("localidades", {})
        estados = localidades.get("estados", [])
        esr = sites_data.get("estados_sem_representacao", {})
        sc = esr.get("santa_catarina", {})

        if not estados:
            empty["status"] = "sem_dados"
            empty["foco_santa_catarina"] = "Sem tráfego por estado no GA4."
            return empty

        classificacao_oficial = self._build_classificacao_oficial(estados)

        site_url = (getattr(self, "_primary_site_profile", {}) or {}).get("url") or ""
        org_nome = (getattr(self, "_primary_site_profile", {}) or {}).get("nome") or "organização"

        prompt = f"""
Sugira oportunidades de marketing regional para {org_nome}.

CLASSIFICAÇÃO OFICIAL DE REPRESENTAÇÃO PATRONAL (NÃO ALTERE — já definida):
- "Sim" = sindicato patronal territorial do setor no estado (apenas SP=SINDIBOR, RS=SINBORSUL)
- "Fraca" = indústria/tráfego sem sindicato patronal local exclusivo (ex: Santa Catarina)
- "Não" = sem representação patronal relevante

ESTADOS COM CLASSIFICAÇÃO JÁ DEFINIDA:
{json.dumps(classificacao_oficial, ensure_ascii=False)}

SANTA CATARINA (atenção: representação = Fraca, NÃO é Sim):
{json.dumps(sc, ensure_ascii=False)}

CAMPANHAS POR PORTE / SC (Akna):
{json.dumps((campanhas_por_porte or [])[:8], ensure_ascii=False)}

RESPONDA APENAS JSON válido:
{{
  "estados": [
    {{
      "estado": "Nome igual ao da lista acima",
      "oportunidade": "frase curta (máx 70 caracteres)",
      "prioridade": "Alta|Média|Baixa"
    }}
  ],
  "foco_santa_catarina": "frase curta: SC sem sindicato patronal local, foco campanhas Por Porte",
  "acoes": [
    {{"titulo": "Ação 1", "descricao": "máx 90 caracteres"}},
    {{"titulo": "Ação 2", "descricao": "máx 90 caracteres"}},
    {{"titulo": "Ação 3", "descricao": "máx 90 caracteres"}}
  ],
  "fontes": [{json.dumps(site_url) if site_url else '"URL do site institucional"'}]
}}

REGRAS:
- NÃO inclua campo representacao — já está definido oficialmente.
- Santa Catarina: prioridade pode ser Alta por campanhas Por Porte, mas NUNCA trate como tendo sindicato patronal local.
- oportunidade: máximo 70 caracteres.
"""

        try:
            print("  [IA] Analisando oportunidades regionais (representação via regras oficiais)...")
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or ""
            parsed = self._parse_ia_json_response(raw)
            if not parsed:
                tabela = self._merge_tabela_estados(classificacao_oficial, [])
                empty["status"] = "ok"
                empty["foco_santa_catarina"] = "SC: indústria presente, sem sindicato patronal local — foco em campanhas Por Porte."
                empty["tabela_estados"] = tabela
                return empty

            tabela = self._merge_tabela_estados(classificacao_oficial, parsed.get("estados", []))
            fontes = parsed.get("fontes", []) or ([site_url] if site_url else [])
            urls = re.findall(r"https?://[^\s\)\],]+", raw)
            fontes = list(set(fontes + urls))

            foco_sc = (parsed.get("foco_santa_catarina") or "").strip()
            if not foco_sc:
                foco_sc = "SC tem indústria de borracha, mas sem sindicato patronal local — priorizar campanhas Por Porte."

            return {
                "status": "ok",
                "fontes": fontes[:8],
                "foco_santa_catarina": foco_sc[:200],
                "tabela_estados": tabela,
                "acoes": (parsed.get("acoes") or [])[:3],
            }
        except Exception as exc:
            print(f"  [IA] Erro na análise de representação regional: {exc}")
            empty["status"] = "erro"
            empty["foco_santa_catarina"] = f"Erro: {exc}"
            return empty

    def get_akna_data(self):
        """
        Retorna status base da Akna.
        Os dados reais (taxa de abertura, campanhas, etc.) vêm do akna_manual
        que é alimentado pela planilha da pasta AKNA configurada.
        O card da visão geral já consome akna_manual.analytics.kpis diretamente.
        """
        akna_data = {
            "taxa_abertura": "0%",
            "taxa_cliques": "0%",
            "taxa_rejeicao": "0%",
            "total_envios": 0,
            "total_aberturas": 0,
            "total_cliques": 0,
            "status": "Via Planilha Manual"
        }
        return akna_data

        # Código abaixo mantido para referência futura (Pausado)
        user = self.akna_config.get('user')
        password = self.akna_config.get('pass')
        client_code = self.akna_config.get('client_code')
        
        if not client_code or client_code == "PREENCHER_AQUI":
            return akna_data
            
        url = "https://app.akna.com.br/emkt/int/integracao.php"
        pass_md5 = str(password).strip()
        
        # ESTRATÉGIA: Requisições diárias (limite de 24h conforme suporte) para os últimos 30 dias
        total_envios = 0
        total_aberturas = 0
        total_cliques = 0
        total_erros = 0
        success_count = 0
        last_error = None

        # Gerar intervalos de 24 horas para os últimos 30 dias
        intervals = []
        now = datetime.now()
        for i in range(30):
            # De 00:00:00 até 23:59:59 de cada dia
            base_day = now - timedelta(days=i)
            start_date = base_day.replace(hour=0, minute=0, second=0).strftime("%Y-%m-%d %H:%M:%S")
            end_date = base_day.replace(hour=23, minute=59, second=59).strftime("%Y-%m-%d %H:%M:%S")
            intervals.append((start_date, end_date))

        print(f"Iniciando coleta Akna: 30 requisições diárias (limite 24h)...")
        for idx, (data_ini, data_fim) in enumerate(intervals):
            # Tags corrigidas conforme suporte: datainicial e datafinal (SEM sublinhado, conforme imagem do suporte técnico)
            xml_payload = f"""<main><emkt trans="19.10"><datainicial>{data_ini}</datainicial><datafinal>{data_fim}</datafinal></emkt></main>"""
            payload = {
                'User': user,
                'Pass': pass_md5,
                'Client': str(client_code).strip(),
                'XML': xml_payload
            }
            
            # Lógica de Retry (3 tentativas por bloco)
            for attempt in range(3):
                try:
                    # Timeout ultra-longo de 120s por bloco
                    print(f"Bloco {idx+1}/6 - Tentativa {attempt+1} ({data_ini} até {data_fim})...")
                    response = requests.post(url, data=payload, timeout=120)
                    if response.status_code == 200:
                        if "id=\"00\"" in response.text:
                            try:
                                root = ET.fromstring(response.text)
                                for campanha in root.findall(".//CAMPANHA"):
                                    total_envios += int(campanha.get("ENVIADOS", 0))
                                    total_aberturas += int(campanha.get("ABERTURAS", 0))
                                    total_cliques += int(campanha.get("CLIQUES", 0))
                                    total_erros += int(campanha.get("ERROS", 0))
                                success_count += 1
                                print(f"Bloco {idx+1} concluído com sucesso.")
                                break 
                            except Exception as parse_err:
                                last_error = f"Erro Parse: {parse_err}"
                        else:
                            error_msg = "Erro nos parâmetros"
                            if "<error>" in response.text:
                                error_msg = response.text.split("<error>")[1].split("</error>")[0]
                            last_error = f"Erro Akna: {error_msg}"
                            print(f"Erro na API Akna: {error_msg}")
                            break 
                    else:
                        last_error = f"Erro HTTP: {response.status_code}"
                except Exception as e:
                    last_error = f"Timeout/Conexão: {str(e)}"
                    print(f"Timeout no bloco {idx+1}: {str(e)}")
                
                if attempt < 2:
                    time.sleep(3)
            
        # Consolidar resultados
        if success_count > 0:
            akna_data["status"] = "Conectado" if success_count == 30 else f"Conectado ({success_count}/30 dias)"
            akna_data["total_envios"] = total_envios
            akna_data["total_aberturas"] = total_aberturas
            akna_data["total_cliques"] = total_cliques
            
            if total_envios > 0:
                abertura_pct = (total_aberturas / total_envios) * 100
                clique_pct = (total_cliques / total_envios) * 100
                rejeicao_pct = (total_erros / total_envios) * 100
                
                akna_data["taxa_abertura"] = f"{abertura_pct:.1f}%"
                akna_data["taxa_cliques"] = f"{clique_pct:.1f}%"
                akna_data["taxa_rejeicao"] = f"{rejeicao_pct:.1f}%"
        else:
            akna_data["status"] = last_error or "Falha na conexão"
            
        return akna_data

    def get_linkedin_data(self, account_type='reynaldo'):
        """
        Apenas leitura. Retorna dados detalhados de controle da conta LinkedIn.
        """
        config = self.linkedin_reynaldo_config if account_type == 'reynaldo' else self.linkedin_abiarb_config
        profile = self._get_linkedin_profile(config)

        if not profile:
            return {
                "connected": False,
                "id": None,
                "name": "Desconectado",
                "profile_pic": None,
                "headline": None,
                "summary": None,
                "posts_count": 0,
                "total_likes": 0
            }

        return {
            "connected": True,
            "id": profile.get("id"),
            "name": f"{profile.get('localizedFirstName', '')} {profile.get('localizedLastName', '')}".strip() or profile.get('headline', {}).get('en_US', 'LinkedIn'),
            "profile_pic": profile.get("profilePicture", {}).get("displayImage"),
            "headline": profile.get("headline", {}).get("en_US", "Sem headline definida"),
            "summary": profile.get("summary", {}).get("en_US", "Sem descrição") if isinstance(profile.get("summary"), dict) else profile.get("summary", "Sem descrição"),
            "posts_count": profile.get("posts_count", 0),
            "total_likes": profile.get("total_likes", 0),
            "last_checked": datetime.now().strftime("%d/%m/%Y %H:%M")
        }

    def _get_linkedin_profile(self, config):
        """
        Busca perfil completo do LinkedIn com dados detalhados.
        Apenas leitura. Não publica absolutamente nada.
        """
        token = str(config.get('access_token', '')).strip()
        org_id = config.get('org_id') or config.get('organization_id')
        
        if not token:
            return None

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }

        profile_data = None
        # If an organization id is configured, try to fetch organization info and posts for that org
        if org_id:
            try:
                org_url = f"https://api.linkedin.com/v2/organizations/{org_id}?projection=(id,localizedName,logoV2)"
                org_res = requests.get(org_url, headers=headers)
                if org_res.status_code == 200:
                    org_data = org_res.json()
                    profile_data = {
                        'id': org_data.get('id'),
                        'localizedFirstName': '',
                        'localizedLastName': '',
                        'profilePicture': {'displayImage': None},
                        'headline': {'en_US': org_data.get('localizedName')},
                        'summary': org_data.get('description', '')
                    }
            except Exception:
                profile_data = None

        # If no org profile fetched, fall back to /userinfo (OpenID Connect) or /me
        if not profile_data:
            try:
                # Tenta primeiro /userinfo (novo padrão)
                url_userinfo = "https://api.linkedin.com/v2/userinfo"
                res_ui = requests.get(url_userinfo, headers=headers)
                if res_ui.status_code == 200:
                    ui = res_ui.json()
                    profile_data = {
                        'id': ui.get('sub'),
                        'localizedFirstName': ui.get('given_name', ''),
                        'localizedLastName': ui.get('family_name', ''),
                        'profilePicture': {'displayImage': ui.get('picture')},
                        'headline': {'en_US': 'Perfil LinkedIn'},
                        'summary': ''
                    }
                else:
                    # Fallback para /me
                    url_me = "https://api.linkedin.com/v2/me?projection=(id,localizedFirstName,localizedLastName,profilePicture(displayImage),headline,summary)"
                    res_me = requests.get(url_me, headers=headers)
                    if res_me.status_code == 200:
                        profile_data = res_me.json()
                    else:
                        return None
            except Exception:
                return None

        # Tentar buscar postagens recentes para contar (person or org)
        try:
            posts_count = 0
            total_likes = 0
            
            if org_id:
                author_urn = f"urn:li:organization:{org_id}"
                posts_url = f"https://api.linkedin.com/v2/ugcPosts?q=authors&authors=List({author_urn})&count=100"
                posts_response = requests.get(posts_url, headers=headers)
                if posts_response.status_code == 200:
                    posts_data = posts_response.json()
                    posts_count = posts_data.get('paging', {}).get('total', 0)
                    for post in posts_data.get('elements', [])[:10]:
                        likes = post.get('socialMetadata', {}).get('totalLikes', 0)
                        total_likes += likes
            
            profile_data['posts_count'] = posts_count
            profile_data['total_likes'] = total_likes
        except Exception:
            profile_data['posts_count'] = 0
            profile_data['total_likes'] = 0
        
        return profile_data

    def get_all_data(self):
        # ✅ CORREÇÃO: Força stdout para UTF-8 no Windows (evita UnicodeEncodeError com emojis)
        import sys, io
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass
        elif sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

        print("\n" + "="*60)
        print("CICLO DE SINCRONIZAÇÃO DE DADOS")
        print("="*60)
        
        # 1. Estatísticas do Histórico Existente
        print("\n📦 Verificando histórico persistente...")
        for source in ('meta_instagram', 'meta_facebook', 'youtube'):
            self.data_manager.repair_duplicates(source)
        hist_meta_fb = self.data_manager.load_data('meta_facebook')
        hist_meta_ig = self.data_manager.load_data('meta_instagram')
        hist_yt = self.data_manager.load_data('youtube')
        hist_akna = self.data_manager.load_data('akna')
        
        if len(hist_meta_fb) > 0:
            last_date_fb = self.data_manager.get_last_date('meta_facebook')
            print(f"  ✓ Facebook: {len(hist_meta_fb)} posts ({last_date_fb})")
        else:
            print(f"  ∘ Facebook: Sem histórico (será bootstrap)")
            
        if len(hist_meta_ig) > 0:
            last_date_ig = self.data_manager.get_last_date('meta_instagram')
            print(f"  ✓ Instagram: {len(hist_meta_ig)} posts ({last_date_ig})")
        else:
            print(f"  ∘ Instagram: Sem histórico (será bootstrap)")
        
        if len(hist_yt) > 0:
            print(f"  ✓ YouTube: {len(hist_yt)} vídeos")
        if len(hist_akna) > 0:
            print(f"  ✓ Akna: {len(hist_akna)} campanhas")

        # 2. Coleta Incremental de APIs
        print("\n🔄 Buscando dados novos nas APIs...")
        try:
            yt_data = self.get_youtube_data()
        except Exception as exc:
            print(f"  ❌ YouTube falhou: {exc}")
            yt_data = {"subscribers": 0, "total_views": 0, "detailed_data": []}

        try:
            meta_data = self.get_meta_data()
        except Exception as exc:
            print(f"  ❌ Meta falhou: {exc}")
            meta_data = {
                "facebook": {"followers": 0, "total_interactions": 0, "detailed_data": []},
                "instagram": {"followers": 0, "total_interactions": 0, "detailed_data": []},
            }

        try:
            sites_bundle = self.get_all_sites_data()
        except Exception as exc:
            print(f"  ❌ Sites/GA4 falhou: {exc}")
            sites_bundle = {"sites": {}, "site_conecta": {}}

        sites_data = sites_bundle.get("sites") or {}
        site_conecta_data = sites_bundle.get("site_conecta") or {}

        try:
            linkedin_reynaldo_api = self.get_linkedin_data('reynaldo')
        except Exception as exc:
            print(f"  ❌ LinkedIn Reynaldo falhou: {exc}")
            linkedin_reynaldo_api = {}

        try:
            linkedin_abiarb_api = self.get_linkedin_data('abiarb')
        except Exception as exc:
            print(f"  ❌ LinkedIn ABIARB falhou: {exc}")
            linkedin_abiarb_api = {}

        try:
            akna_api = self.get_akna_data()
        except Exception as exc:
            print(f"  ❌ Akna API falhou: {exc}")
            akna_api = {}

        # 3. Processamento de Planilhas Manuais
        print("\n📊 Processando planilhas manuais...")
        manual_files = self.ingestor.ingest_all()
        
        # Carregar AKNA de múltiplas planilhas (todas as pastas/arquivos do diretório)
        akna_loaded_from_folder = False
        try:
            df_akna_multi = load_akna_data_multi_sheet()
            if not df_akna_multi.empty:
                manual_files['akna'] = df_akna_multi
                akna_loaded_from_folder = True
                print(f"  ✓ AKNA: {len(df_akna_multi)} registros consolidados de múltiplas planilhas")
        except Exception as e:
            print(f"  ⚠️ Erro ao carregar múltiplas planilhas AKNA: {e}")
            print(f"  ℹ️ Usando fallback para carregamento padrão")
        
        # Salvar dados das planilhas manuais no histórico
        if not manual_files['akna'].empty:
            df_akna = manual_files['akna'].copy()
            if 'Horario' in df_akna.columns:
                df_akna['Horario'] = df_akna['Horario'].astype(str)
            if akna_loaded_from_folder:
                # Pasta AKNA é a fonte de verdade: substitui histórico antigo
                self.data_manager.replace_data('akna', df_akna)
            else:
                self.data_manager.save_data('akna', df_akna)
        if not manual_files['linkedin_reynaldo'].empty:
            self.data_manager.save_data('linkedin_reynaldo', manual_files['linkedin_reynaldo'])
        if not manual_files['linkedin_abiarb'].empty:
            self.data_manager.save_data('linkedin_abiarb', manual_files['linkedin_abiarb'])

        # 4. Consolidação Final (Fonte Única de Verdade: Histórico + Novos Dados)
        print("\n💾 Consolidando histórico...")
        hist_meta_fb = self.data_manager.load_data('meta_facebook')
        hist_meta_ig = self.data_manager.load_data('meta_instagram')
        hist_yt = self.data_manager.load_data('youtube')
        hist_akna = self.data_manager.load_data('akna')
        hist_li_reynaldo = self.data_manager.load_data('linkedin_reynaldo')
        hist_li_abiarb = self.data_manager.load_data('linkedin_abiarb')

        # Formatar dados para o Dashboard consumindo o histórico COMPLETO
        # ✅ Enviar TODOS os registros (sem limitação de 50)
        # YouTube Consolidação
        # Sempre priorizar a soma do histórico que agora contém as métricas atualizadas
        yt_total_views = int(hist_yt['visualizacoes'].sum()) if not hist_yt.empty and 'visualizacoes' in hist_yt.columns else yt_data.get('total_views', 0)
            
        video_mais_assistido = {"titulo": "N/A", "visualizacoes": 0, "watch_time": "0h"}
        if not hist_yt.empty and 'visualizacoes' in hist_yt.columns:
            top_video = hist_yt.sort_values(by='visualizacoes', ascending=False).iloc[0]
            video_mais_assistido = {
                "titulo": top_video.get('titulo_descricao', 'N/A'),
                "visualizacoes": int(top_video.get('visualizacoes', 0)),
                "watch_time": top_video.get('duracao', '0h')
            }

        yt_norm = self.normalizer.normalize_youtube(hist_yt)
        yt_insights = fetch_youtube_insights(
            self._get_yt_analytics_client(),
            self.yt_channel_id,
            videos=yt_norm,
            channel_total_views=yt_total_views,
            subscribers_atual=yt_data.get('subscribers', 0),
        )
        yt_final = {
            "subscribers": yt_data.get('subscribers', 0),
            "total_views": yt_total_views,
            "video_mais_assistido": video_mais_assistido,
            "detailed_data": yt_norm,
            **{k: yt_insights.get(k, v) for k, v in empty_youtube_insights().items()},
        }

        # Recarregar histórico após persistência para garantir que temos os dados atualizados
        hist_meta_fb = self.data_manager.load_data('meta_facebook')
        hist_meta_ig = self.data_manager.load_data('meta_instagram')
        hist_yt = self.data_manager.load_data('youtube')

        fb_base = meta_data.get("facebook", {})
        fb_insights = {k: fb_base.get(k, v) for k, v in empty_facebook_insights().items()}
        fb_final = {
            "followers": fb_base.get("followers", 0),
            "total_interactions": int(hist_meta_fb["interacao"].sum()) if not hist_meta_fb.empty and "interacao" in hist_meta_fb.columns else 0,
            "detailed_data": hist_meta_fb.to_dict(orient="records") if not hist_meta_fb.empty else [],
            **fb_insights,
        }
        fb_final["resumo"] = build_meta_resumo(
            fb_final["detailed_data"],
            fb_final["followers"],
            platform="facebook",
        )

        ig_base = meta_data.get("instagram", {})
        ig_insights = {k: ig_base.get(k, v) for k, v in empty_instagram_insights().items()}
        ig_final = {
            "followers": ig_base.get("followers", 0),
            "total_interactions": int(hist_meta_ig["interacao"].sum()) if not hist_meta_ig.empty and "interacao" in hist_meta_ig.columns else 0,
            "detailed_data": hist_meta_ig.to_dict(orient="records") if not hist_meta_ig.empty else [],
            **ig_insights,
        }
        ig_final["resumo"] = build_meta_resumo(
            ig_final["detailed_data"],
            ig_final["followers"],
            platform="instagram",
        )

        # LinkedIn Consolidação (Priorizando Histórico/Planilhas para métricas reais)
        li_integration = LinkedInIntegration()
        
        li_reynaldo_final = li_integration.consolidate_linkedin_data(linkedin_reynaldo_api, 'reynaldo', df_manual=hist_li_reynaldo)
        li_abiarb_final = li_integration.consolidate_linkedin_data(linkedin_abiarb_api, 'abiarb', df_manual=hist_li_abiarb)

        # Akna Consolidação com Analytics
        akna_norm = self.normalizer.normalize_akna(hist_akna)
        
        # Gerar análise completa usando o módulo AknaAnalytics
        akna_analytics_data = {}
        if not hist_akna.empty:
            try:
                analytics = AknaAnalytics(hist_akna)
                akna_analytics_data = analytics.get_analise_completa()
                print(f"  ✓ Análise AKNA gerada: {akna_analytics_data['kpis']['total_campanhas']} campanhas")
            except Exception as e:
                print(f"  ⚠️  Falha ao gerar análise AKNA: {e}")
                import traceback
                traceback.print_exc()
                akna_analytics_data = {
                    'kpis': {
                        'total_campanhas': 0, 'total_enviados': 0, 'total_entregues': 0,
                        'total_aberturas': 0, 'total_cliques': 0, 'total_nao_entregues': 0,
                        'total_remocoes': 0, 'total_spam': 0,
                        'taxa_entrega': 0, 'taxa_abertura': 0, 'taxa_clique': 0, 'ctor': 0
                    },
                    'funil': {'labels': [], 'values': [], 'percentages': []},
                    'evolucao_temporal': {'labels': [], 'enviados': [], 'aberturas': [], 'cliques': []},
                    'campanhas_por_tipo': {'labels': [], 'enviados': [], 'aberturas': [], 'cliques': []},
                    'distribuicao_tipos': {'labels': [], 'values': []},
                    'melhores_horarios': {'labels': [], 'enviados': [], 'aberturas': [], 'taxa_abertura': []},
                    'top_campanhas': [], 'all_data': [], 'ultima_atualizacao': ''
                }
        
        _default_analytics = {
            'kpis': {
                'total_campanhas': 0, 'total_enviados': 0, 'total_entregues': 0,
                'total_aberturas': 0, 'total_cliques': 0, 'total_nao_entregues': 0,
                'total_remocoes': 0, 'total_spam': 0,
                'taxa_entrega': 0, 'taxa_abertura': 0, 'taxa_clique': 0, 'ctor': 0
            },
            'funil': {'labels': [], 'values': [], 'percentages': []},
            'evolucao_temporal': {'labels': [], 'enviados': [], 'aberturas': [], 'cliques': []},
            'campanhas_por_tipo': {'labels': [], 'enviados': [], 'aberturas': [], 'cliques': []},
            'distribuicao_tipos': {'labels': [], 'values': []},
            'melhores_horarios': {'labels': [], 'enviados': [], 'aberturas': [], 'taxa_abertura': []},
            'top_campanhas': [], 'all_data': [], 'ultima_atualizacao': ''
        }
        if not isinstance(akna_analytics_data, dict) or 'kpis' not in akna_analytics_data:
            akna_analytics_data = _default_analytics
        else:
            for k, v in _default_analytics.items():
                if k not in akna_analytics_data:
                    akna_analytics_data[k] = v
                elif isinstance(v, dict) and isinstance(akna_analytics_data.get(k), dict):
                    for sk, sv in v.items():
                        akna_analytics_data[k].setdefault(sk, sv)

        akna_manual_summary = {
            "detailed_data": akna_norm,
            "analytics": akna_analytics_data,
            "youtube": yt_final
        }

        # Persistir JSON da AKNA Manual (para debug/consumo externo)
        try:
            os.makedirs(os.path.join('data', 'history'), exist_ok=True)
            akna_json_path = os.path.join('data', 'history', 'akna_manual.json')
            with open(akna_json_path, 'w', encoding='utf-8') as jf:
                json.dump(akna_manual_summary, jf, ensure_ascii=False, default=str)
            print(f"  ✓ Akna Manual JSON atualizado: {akna_json_path} ({len(akna_norm)} registros)")
        except Exception as e:
            print(f"  ⚠️  Falha ao salvar akna_manual.json: {e}")
        
        # Carregar benchmarks do nicho
        benchmarks = {}
        try:
            with open('benchmarks_nicho.json', 'r') as bfile:
                benchmarks = json.load(bfile)
        except:
            pass

        yt_final["novas_inscricoes"] = yt_insights.get("audiencia", {}).get("inscritos_valor", 0)

        # Calcular redes_sociais_media_interacao dinamicamente
        total_interacoes = 0
        total_redes = 0
        for rede_data in [fb_final, ig_final, yt_final]:
            inter = rede_data.get('total_interactions', 0)
            if inter and int(inter) > 0:
                total_interacoes += int(inter)
                total_redes += 1
        redes_sociais_media_interacao = round(total_interacoes / total_redes, 0) if total_redes > 0 else 0

        iob_data = load_iob_dashboard()

        data = {
            "youtube": yt_final,
            "instagram": ig_final,
            "facebook": fb_final,
            "linkedin": li_reynaldo_final,
            "linkedin_abiarb": li_abiarb_final,
            "sites": sites_data,
            "site_conecta": site_conecta_data,
            "akna": akna_api,
            "akna_manual": akna_manual_summary,
            "iob": iob_data,
            "benchmarks": benchmarks,
            "redes_sociais_media_interacao": int(redes_sociais_media_interacao),
            "last_update": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "google_search": sites_data.get("google_search", {
                "visualizacoes": "0", "cliques": "0", "ctr": "0%", "posicao": "0"
            })
        }
        
        # Resumo de sincronização
        print("\n" + "="*60)
        print("RESUMO DA SINCRONIZAÇÃO")
        print("="*60)
        print(f"✓ Facebook: {len(hist_meta_fb)} posts (Total: {fb_final['total_interactions']} interações)")
        print(f"✓ Instagram: {len(hist_meta_ig)} posts (Total: {ig_final['total_interactions']} interações)")
        print(f"✓ YouTube: {len(hist_yt)} vídeos")
        print(f"✓ Akna (manual): {len(akna_norm)} campanhas processadas")
        iob_kpis = iob_data.get("analytics", {}).get("kpis", {})
        print(f"✓ IOB: {iob_kpis.get('total_registros', 0)} registros de acesso")
        print(f"✓ LinkedIn Reynaldo: {len(hist_li_reynaldo)} posts")
        print(f"✓ LinkedIn ABIARB: {len(hist_li_abiarb)} posts")
        print("="*60 + "\n")
        
        if self.openai_client:
            data_for_ai = copy.deepcopy(data)
            total_for_ai = 0
            akna_total_before = 0

            for k, v in data_for_ai.items():
                if not isinstance(v, dict):
                    continue
                if k == 'akna_manual' and isinstance(v.get('detailed_data'), list):
                    akna_total_before = len(v['detailed_data'])
                    filtered = self._filter_akna_last_month_for_ai(v['detailed_data'])
                    v['detailed_data'] = filtered
                    total_for_ai += len(filtered)
                    now = datetime.now()
                    mes_ref = now.month - 1 if now.month > 1 else 12
                    ano_ref = now.year if now.month > 1 else now.year - 1
                    print(
                        f"  [IA] Akna: {len(filtered)} campanhas do mês {mes_ref:02d}/{ano_ref} "
                        f"(de {akna_total_before} no histórico completo)"
                    )
                    continue
                if 'detailed_data' in v and isinstance(v['detailed_data'], list):
                    filtered = self._filter_last_30_days_for_ai(v['detailed_data'])
                    total_for_ai += len(filtered)
                    v['detailed_data'] = filtered
                if 'detailed_data_manual' in v and isinstance(v['detailed_data_manual'], list):
                    filtered = self._filter_last_30_days_for_ai(v['detailed_data_manual'])
                    total_for_ai += len(filtered)
                    v['detailed_data_manual'] = filtered

            print(f"IA receberá {total_for_ai} registros (Akna: último mês civil; demais: 30 dias)")

            campanhas_por_porte = self._extract_campanhas_por_porte(
                data.get("akna_manual", {}).get("detailed_data", [])
            )
            if campanhas_por_porte:
                print(f"  [IA] Sites: {len(campanhas_por_porte)} campanhas Por Porte/SC para contexto")

            analise_sites = self._analyze_sites_representacao(
                data.get("sites", {}),
                campanhas_por_porte=campanhas_por_porte,
            )
            if isinstance(data.get("sites"), dict):
                esr = data["sites"].setdefault("estados_sem_representacao", {})
                esr["analise_ia"] = analise_sites
            
            # ✨ NOVO: Usar batching para evitar limite de tokens
            market_analysis = self._analyze_with_batching(data_for_ai, batch_size=100)
            data["market_analysis"] = market_analysis
        return data
    
    if __name__ == "__main__":
      client = SocialAPIClient()
      client.testar_search_console()