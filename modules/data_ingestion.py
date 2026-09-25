import os
import pandas as pd
import glob
from datetime import datetime

from modules.data_paths import AKNA_DIR, LINKEDIN_DIR
from modules.akna_validation import filter_akna_dataframe, filter_akna_records

def convert_time_flexible(time_str):
    """
    Converte horário de forma robusta, tratando ambos os formatos HH:MM e HH:MM:SS.
    Evita warnings do pandas ao trabalhar com horários em formato inconsistente.
    
    Args:
        time_str: String contendo o horário (e.g., '15:30' ou '15:30:45')
    
    Returns:
        String em formato HH:MM, ou "00:00" se inválido
    """
    if pd.isna(time_str) or time_str == '' or time_str is None:
        return "00:00"
    
    time_str = str(time_str).strip()
    
    # Tenta formato HH:MM:SS primeiro
    try:
        dt = pd.to_datetime(time_str, format='%H:%M:%S', errors='raise')
        return dt.strftime('%H:%M')
    except (ValueError, TypeError):
        pass
    
    # Tenta formato HH:MM
    try:
        dt = pd.to_datetime(time_str, format='%H:%M', errors='raise')
        return dt.strftime('%H:%M')
    except (ValueError, TypeError):
        pass
    
    # Se nenhum formato funcionar, tenta conversão flexível (última tentativa)
    try:
        dt = pd.to_datetime(time_str, errors='coerce')
        if pd.notna(dt):
            return dt.strftime('%H:%M')
    except:
        pass
    
    # Se tudo falhar, retorna "00:00"
    return "00:00"


# Validação de datas - remover datas futuras
def validate_date(date_str):
    """Remove datas futuras (após data atual)"""
    if pd.isna(date_str) or date_str == '':
        return date_str
    
    try:
        parsed = pd.to_datetime(date_str, format='%d/%m/%Y', errors='coerce')
        if pd.notna(parsed):
            today = datetime.now()
            if parsed > today:
                print(f"⚠️ Data futura removida: {date_str}")
                return None
        return date_str
    except:
        return date_str


class DataIngestor:
    def __init__(self, base_path='data/input'):
        self.base_path = base_path
        self.categories = {
            'akna': 'akna',
            'linkedin_abiarb': 'linkedin_abiarb',
            'linkedin_reynaldo': 'linkedin_reynaldo'
        }

    def _find_files(self, category):
        """Encontra arquivos de entrada por categoria.

        AKNA manual: pasta `modules.data_paths.AKNA_DIR` (padrão `data/input/akna`).
        LinkedIn manual: pasta `LINKEDIN_DIR` (padrão `data/input/linkedin`).
        Seleciona o arquivo mais recente (Excel/CSV) conforme regras de nome por categoria.
        """
        # AKNA Manual: carrega TODOS os arquivos Excel/CSV da pasta
        if category == 'akna':
            network_dir = AKNA_DIR
            try:
                candidates = []
                if os.path.isdir(network_dir):
                    for root, _dirs, files in os.walk(network_dir):
                        for filename in files:
                            if filename.startswith('~$'):
                                continue
                            ext = os.path.splitext(filename)[1].lower()
                            if ext in ['.xlsx', '.xls', '.csv']:
                                candidates.append(os.path.join(root, filename))

                if candidates:
                    candidates.sort(key=lambda p: os.path.getmtime(p))
                    print(f"[AKNA Manual] Encontrados {len(candidates)} arquivo(s) em: {network_dir}")
                    return candidates

                print(f"[AKNA Manual] Nenhum arquivo encontrado em: {network_dir}. Usando fallback local em data/input/akna.")
            except Exception as e:
                print(f"[AKNA Manual] Falha ao acessar pasta ({network_dir}): {e}. Usando fallback local em data/input/akna.")

            path = os.path.join(self.base_path, category, '*')
            return glob.glob(path)

        # LinkedIn Manual
        if category in ['linkedin_reynaldo', 'linkedin_abiarb']:
            network_paths = {
                'linkedin_reynaldo': LINKEDIN_DIR,
                'linkedin_abiarb': LINKEDIN_DIR
            }
            network_dir = network_paths.get(category)
            try:
                candidates = []
                if os.path.isdir(network_dir):
                    # Usar glob.escape para lidar com caracteres especiais como '#'
                    search_pattern = os.path.join(glob.escape(network_dir), "*")
                    for fp in glob.glob(search_pattern):
                        ext = os.path.splitext(fp)[1].lower()
                        if ext in ['.xlsx', '.xls', '.csv']:
                            candidates.append(fp)
                
                if candidates:
                    candidates.sort(key=lambda p: os.path.getmtime(p))
                    picked = candidates[-1]
                    print(f"[{category.upper()}] Usando arquivo da rede: {picked}")
                    return [picked]
                else:
                    print(f"[{category.upper()}] Nenhum arquivo encontrado em: {network_dir}. Usando fallback local.")
            except Exception as e:
                print(f"[{category.upper()}] Falha ao acessar pasta de rede ({network_dir}): {e}. Usando fallback local.")

            path = os.path.join(self.base_path, category, '*')
            return glob.glob(path)

        # Demais categorias: comportamento padrão
        path = os.path.join(self.base_path, category, '*')
        return glob.glob(path)

    def _read_file(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext in ['.xlsx', '.xls']:
                # Tenta encontrar o cabeçalho correto se houver lixo no topo
                try:
                    df_raw = pd.read_excel(file_path, header=None)
                    header_row = 0
                    for i, row in df_raw.head(10).iterrows():
                        row_str = [str(c).lower() for c in row]
                        if any(k in row_str for k in ['campanhas', 'data de envio', 'assunto', 'data', 'date', 'impressões', 'cliques']):
                            header_row = i
                            break
                    return pd.read_excel(file_path, skiprows=header_row)
                except Exception as excel_error:
                    # Se falhar como Excel, tenta como TSV (arquivo de texto com extensão .xls)
                    print(f"[DEBUG] Falha ao ler como Excel: {excel_error}. Tentando como TSV...")
                    try:
                        df_raw = pd.read_csv(file_path, sep='\t', encoding='iso-8859-1', header=None)
                        header_row = 0
                        for i, row in df_raw.head(10).iterrows():
                            row_str = [str(c).lower() for c in row]
                            if any(k in row_str for k in ['campanhas', 'data de envio', 'assunto', 'data', 'date', 'impressões', 'cliques']):
                                header_row = i
                                break
                        return pd.read_csv(file_path, sep='\t', encoding='iso-8859-1', skiprows=header_row)
                    except Exception as tsv_error:
                        print(f"[DEBUG] Falha ao ler como TSV: {tsv_error}")
                        raise excel_error
            elif ext == '.csv':
                # Tenta detectar delimitador
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    first_line = f.readline()
                    sep = ';' if ';' in first_line else ','
                return pd.read_csv(file_path, sep=sep)
        except Exception as e:
            print(f"Erro ao ler arquivo {file_path}: {e}")
            return pd.DataFrame()

    def ingest_all(self):
        all_data = {}
        for cat_key, cat_folder in self.categories.items():
            files = self._find_files(cat_folder)
            cat_dfs = []
            for f in files:
                df = self._read_file(f)
                if not df.empty:
                    cat_dfs.append(df)
            
            if cat_dfs:
                combined = pd.concat(cat_dfs, ignore_index=True)
                if cat_key == 'akna':
                    combined = filter_akna_dataframe(combined, log_prefix="[AKNA Manual]")
                all_data[cat_key] = combined
            else:
                all_data[cat_key] = pd.DataFrame()
        
        return all_data

class DataNormalizer:
    @staticmethod
    def normalize_akna(df):
        if df.empty: return []
        df = filter_akna_dataframe(df.copy(), log_prefix="[AKNA normalize]")
        if df.empty:
            return []
        df.columns = [c.strip() for c in df.columns]
        mapping = {
            'Campanhas': 'campanhas',
            'Data de envio': 'data_envio',
            'Horario': 'horario',
            'Ações': 'acoes',
            'Assunto': 'assunto',
            'Enviados': 'enviados',
            'Entregues': 'entregues',
            'Porcentagem': 'porcentagem_entregues',
            'Aberturas Únicas': 'aberturas_unicas',
            'Aberturas Totais': 'aberturas_totais',
            'Porcentagem.1': 'porcentagem_aberturas',
            'Contatos': 'contatos',
            'Cliques únicos': 'cliques_unicos',
            'Cliques totais': 'cliques_totais',
            'CTOR': 'ctor',
            'CTR': 'ctr',
            'N.Entreg.': 'nao_entregues',
            'Porcentagem.2': 'porcentagem_nao_entregues',
            'Redes Sociais - Divulgações': 'rs_divulgacoes',
            'Redes Sociais - Visualizações': 'rs_visualizacoes',
            'Redes Sociais - Cliques': 'rs_cliques',
            'Indicações': 'indicacoes',
            'Remoções': 'remocoes',
            'Spam': 'spam'
        }
        for col in mapping.keys():
            if col not in df.columns:
                df[col] = 0
        df_norm = df[list(mapping.keys())].rename(columns=mapping)
        def format_date(val):
            if pd.isna(val): return ""
            if isinstance(val, datetime): return val.strftime('%d/%m/%Y')
            return str(val)
        def format_time(val):
            if pd.isna(val): return ""
            if isinstance(val, datetime): return val.strftime('%H:%M:%S')
            return str(val)
        df_norm['data_envio'] = df_norm['data_envio'].apply(format_date)
        df_norm['horario'] = df_norm['horario'].apply(format_time)
        pct_cols = ['porcentagem_entregues', 'porcentagem_aberturas', 'porcentagem_nao_entregues', 'ctor', 'ctr']
        for col in pct_cols:
            df_norm[col] = df_norm[col].apply(lambda x: f"{float(x)*100:.2f}%".replace('.', ',') if isinstance(x, (int, float)) and x != 0 else str(x))
        numeric_cols = ['enviados', 'entregues', 'aberturas_unicas', 'aberturas_totais', 'contatos', 
                        'cliques_unicos', 'cliques_totais', 'nao_entregues', 'rs_divulgacoes', 
                        'rs_visualizacoes', 'rs_cliques', 'indicacoes', 'remocoes', 'spam']
        for col in numeric_cols:
            df_norm[col] = pd.to_numeric(df_norm[col], errors='coerce').fillna(0)
            if (df_norm[col] % 1 == 0).all():
                df_norm[col] = df_norm[col].astype(int)
        records = df_norm.to_dict(orient='records')
        return filter_akna_records(records, log_prefix="[AKNA normalize]")

    @staticmethod
    def normalize_linkedin(df):
        if df.empty: return []
        df.columns = [c.strip() for c in df.columns]
        mapping = {
            'Data': 'Data', 'Date': 'Data',
            'Impressões (orgânicas)': 'impressoes_organicas', 'Impressions (organic)': 'impressoes_organicas',
            'Impressões (patrocinadas)': 'impressoes_patrocinadas', 'Impressions (sponsored)': 'impressoes_patrocinadas',
            'Impressões (total)': 'impressoes_total', 'Impressions (total)': 'impressoes_total',
            'Impressões únicas (orgânicas)': 'impressoes_unicas_organicas', 'Unique impressions (organic)': 'impressoes_unicas_organicas',
            'Cliques (orgânicos)': 'cliques_organicos', 'Clicks (organic)': 'cliques_organicos',
            'Cliques (patrocinados)': 'cliques_patrocinados', 'Clicks (sponsored)': 'cliques_patrocinados',
            'Cliques (total)': 'cliques_total', 'Clicks (total)': 'cliques_total',
            'Reações (orgânicas)': 'reacoes_organicas', 'Reactions (organic)': 'reacoes_organicas',
            'Reações (patrocinadas)': 'reacoes_patrocinadas', 'Reactions (sponsored)': 'reacoes_patrocinadas',
            'Reações (total)': 'reacoes_total', 'Reactions (total)': 'reacoes_total',
            'Comentários (orgânicos)': 'comentarios_organicos', 'Comments (organic)': 'comentarios_organicos',
            'Comentários (patrocinados)': 'comentarios_patrocinados', 'Comments (sponsored)': 'comentarios_patrocinados',
            'Comentários (total)': 'comentarios_total', 'Comments (total)': 'comentarios_total',
            'Compartilhamentos (orgânicos)': 'compartilhamentos_organicos', 'Shares (organic)': 'compartilhamentos_organicos',
            'Compartilhamentos (patrocinados)': 'compartilhamentos_patrocinados', 'Shares (sponsored)': 'compartilhamentos_patrocinados',
            'Compartilhamentos (total)': 'compartilhamentos_total', 'Shares (total)': 'compartilhamentos_total',
            'Taxa de engajamento (orgânico)': 'taxa_engajamento_organico', 'Engagement rate (organic)': 'taxa_engajamento_organico',
            'Taxa de engajamento (patrocinado)': 'taxa_engajamento_patrocinado', 'Engagement rate (sponsored)': 'taxa_engajamento_patrocinado',
            'Taxa de engajamento (total)': 'taxa_engajamento_total', 'Engagement rate (total)': 'taxa_engajamento_total',
            'Título': 'Título', 'Title': 'Título', 'Descrição': 'Título', 'Description': 'Título',
            'Link': 'link', 'URL': 'link'
        }
        norm_data = []
        for _, row in df.iterrows():
            item = {'Data': '', 'Título': '', 'link': '', 'impressoes_organicas': 0, 'impressoes_patrocinadas': 0, 'impressoes_total': 0, 'impressoes_unicas_organicas': 0, 'cliques_organicos': 0, 'cliques_patrocinados': 0, 'cliques_total': 0, 'reacoes_organicas': 0, 'reacoes_patrocinadas': 0, 'reacoes_total': 0, 'comentarios_organicos': 0, 'comentarios_patrocinados': 0, 'comentarios_total': 0, 'compartilhamentos_organicos': 0, 'compartilhamentos_patrocinados': 0, 'compartilhamentos_total': 0, 'taxa_engajamento_organico': '0%', 'taxa_engajamento_patrocinado': '0%', 'taxa_engajamento_total': '0%'}
            for col_orig, col_norm in mapping.items():
                if col_orig in row.index:
                    val = row[col_orig]
                    if col_norm == 'Data':
                        if pd.notna(val):
                            # Normaliza qualquer formato para dd/mm/yyyy
                            try:
                                dt = pd.to_datetime(str(val), dayfirst=True, errors='coerce')
                                if pd.isna(dt):
                                    dt = pd.to_datetime(str(val), dayfirst=False, errors='coerce')
                                item['Data'] = dt.strftime('%d/%m/%Y') if pd.notna(dt) else str(val)
                            except Exception:
                                item['Data'] = str(val)
                        else:
                            item['Data'] = ''
                    elif col_norm in ['Título', 'link']: item[col_norm] = str(val) if pd.notna(val) else ''
                    elif col_norm.startswith('taxa_engajamento'):
                        if pd.notna(val):
                            val_str = str(val).strip()
                            if '%' not in val_str:
                                try:
                                    val_float = float(val_str.replace(',', '.'))
                                    item[col_norm] = f"{val_float:.2f}%" if val_float < 1 else f"{val_float:.2f}%"
                                except: item[col_norm] = val_str
                            else: item[col_norm] = val_str
                    else:
                        try:
                            if pd.notna(val): item[col_norm] = int(float(str(val).replace(',', '.')))
                        except: item[col_norm] = 0
            norm_data.append(item)
        return norm_data

    @staticmethod
    def normalize_youtube(df):
        if df.empty: return []
        cols = ['data_publicacao', 'horario', 'titulo_descricao', 'link_permanente', 'visualizacoes', 'curtidas', 'comentarios', 'interacao', 'duracao']
        if 'data_publicacao' in df.columns:
            df['data_publicacao_dt'] = pd.to_datetime(df['data_publicacao'], dayfirst=True, errors='coerce')
            df['data_publicacao_dt'] = df['data_publicacao_dt'].fillna(pd.Timestamp.now())
            df['data_publicacao'] = df['data_publicacao_dt'].dt.strftime('%d/%m/%Y')
        if 'horario' in df.columns:
            df['horario'] = df['horario'].apply(convert_time_flexible)
        for col in cols:
            if col not in df.columns: df[col] = ""
        df['visualizacoes'] = pd.to_numeric(df['visualizacoes'], errors='coerce').fillna(0).astype(int)
        df['curtidas'] = pd.to_numeric(df['curtidas'], errors='coerce').fillna(0).astype(int)
        df['comentarios'] = pd.to_numeric(df['comentarios'], errors='coerce').fillna(0).astype(int)
        df['interacao'] = pd.to_numeric(df['interacao'], errors='coerce').fillna(0).astype(int)
        return df[cols].to_dict(orient='records')