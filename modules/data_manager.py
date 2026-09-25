import os
import pandas as pd
from datetime import datetime

class DataManager:
    META_ID_SOURCES = frozenset({'meta_instagram', 'meta_facebook'})
    ID_DEDUP_SOURCES = frozenset({
        'meta_instagram', 'meta_facebook', 'youtube',
    })

    def __init__(self, storage_path='data/history'):
        self.storage_path = storage_path
        os.makedirs(self.storage_path, exist_ok=True)

    def _get_file_path(self, source_name):
        return os.path.join(self.storage_path, f"{source_name}.parquet")

    def _normalize_id_column(self, df, source_name=None):
        if df.empty or 'id' not in df.columns:
            return df
        df = df.copy()
        if source_name == 'youtube':
            df['id'] = df['id'].astype(str).str.strip()
            df = df[df['id'].notna() & (df['id'] != '') & (df['id'] != 'nan')]
            return df
        if source_name in self.META_ID_SOURCES or source_name is None:
            df['id'] = pd.to_numeric(df['id'], errors='coerce')
            df = df.dropna(subset=['id'])
            df['id'] = df['id'].astype('int64')
        else:
            df['id'] = df['id'].astype(str).str.strip()
            df = df[df['id'].notna() & (df['id'] != '') & (df['id'] != 'nan')]
        return df

    def repair_duplicates(self, source_name):
        """Remove duplicatas persistentes por id e regrava o parquet."""
        if source_name not in self.ID_DEDUP_SOURCES:
            return 0
        file_path = self._get_file_path(source_name)
        if not os.path.exists(file_path):
            return 0
        df = pd.read_parquet(file_path)
        if df.empty or 'id' not in df.columns:
            return 0
        df = self._normalize_id_column(df, source_name)
        before = len(df)
        df = df.drop_duplicates(subset=['id'], keep='last')
        removed = before - len(df)
        if removed:
            date_col = self._get_date_column(df)
            if date_col and date_col in df.columns:
                df = df.sort_values(by=date_col, ascending=False)
            df = self._sanitize_dtypes(df)
            df.to_parquet(file_path, index=False)
            print(f"    [Repair] {source_name}: {before} -> {len(df)} registros ({removed} duplicatas removidas)")
        return removed

    def save_data(self, source_name, df):
        """Salva ou anexa dados ao arquivo Parquet da fonte, garantindo unicidade."""
        if df.empty:
            return
        
        file_path = self._get_file_path(source_name)
        
        # Garantir que a coluna de data seja datetime para comparação
        date_col = self._get_date_column(df)
        if date_col:
            # Normaliza qualquer formato de data para datetime64 puro antes de comparar.
            # Isso garante que "01/06/2026" e "2026-01-06 00:00:00" sejam tratados como iguais.
            df[date_col] = self._normalize_date_column(df[date_col])

            if df[date_col].isna().any():
                count_nat = df[date_col].isna().sum()
                print(f"    [Aviso] {count_nat} registros com data invalida. Preenchendo com data atual.")
                df[date_col] = df[date_col].fillna(pd.Timestamp.now().normalize())

        if os.path.exists(file_path):
            existing_df = pd.read_parquet(file_path)

            # Normalizar o histórico existente também (pode estar em formato diferente)
            if date_col and date_col in existing_df.columns:
                existing_df[date_col] = self._normalize_date_column(existing_df[date_col])

            combined_df = pd.concat([existing_df, df], ignore_index=True)

            # Normalizar coluna de data no combined antes de deduplicar
            if date_col and date_col in combined_df.columns:
                combined_df[date_col] = self._normalize_date_column(combined_df[date_col])

            dedup_columns = self._get_dedup_columns(source_name, combined_df, date_col)

            if dedup_columns:
                before = len(combined_df)
                combined_df.drop_duplicates(subset=dedup_columns, keep='last', inplace=True)
                print(f"    [Dedup] {dedup_columns} | {before} -> {len(combined_df)} registros")
            else:
                print(f"    [Dedup] AVISO: Nenhuma coluna de deduplicacao encontrada!")

            if date_col and date_col in combined_df.columns:
                combined_df = combined_df.sort_values(by=date_col, ascending=False)

            # ✅ CORREÇÃO: Sanitizar colunas object para evitar ArrowTypeError no Parquet
            # Ocorre quando uma coluna foi salva como int anteriormente e agora chega como str
            combined_df = self._sanitize_dtypes(combined_df)

            combined_df.to_parquet(file_path, index=False)
        else:
            # Primeira vez: apenas salvar
            df = self._sanitize_dtypes(df)
            df.to_parquet(file_path, index=False)

    def replace_data(self, source_name, df):
        """Substitui completamente o histórico de uma fonte (fonte única de verdade)."""
        if df.empty:
            return
        file_path = self._get_file_path(source_name)
        date_col = self._get_date_column(df)
        if date_col:
            df = df.copy()
            df[date_col] = self._normalize_date_column(df[date_col])
            df = df.sort_values(by=date_col, ascending=False)
        df = self._sanitize_dtypes(df.copy())
        df.to_parquet(file_path, index=False)
        print(f"    [Replace] {source_name}: {len(df)} registros (historico substituido)")

    def load_data(self, source_name):
        """Carrega o histórico completo de uma fonte."""
        file_path = self._get_file_path(source_name)
        if os.path.exists(file_path):
            df = pd.read_parquet(file_path)
            if source_name in self.ID_DEDUP_SOURCES and not df.empty and 'id' in df.columns:
                df = self._normalize_id_column(df, source_name)
                if df.duplicated(subset=['id']).any():
                    before = len(df)
                    df = df.drop_duplicates(subset=['id'], keep='last')
                    print(f"    [Dedup load] {source_name}: {before} -> {len(df)} registros")
                    date_col = self._get_date_column(df)
                    if date_col and date_col in df.columns:
                        df = df.sort_values(by=date_col, ascending=False)
                    df = self._sanitize_dtypes(df)
                    df.to_parquet(file_path, index=False)
            return df
        return pd.DataFrame()

    def get_last_date(self, source_name):
        """Retorna a data mais recente registrada para uma fonte."""
        df = self.load_data(source_name)
        if df.empty:
            return None
        date_col = self._get_date_column(df)
        if date_col:
            dates = self._normalize_date_column(df[date_col])
            return dates.max() if not dates.dropna().empty else None
        return None

    def get_historical_count(self, source_name):
        """Retorna a quantidade de registros históricos para uma fonte."""
        df = self.load_data(source_name)
        return len(df) if not df.empty else 0

    def _normalize_date_column(self, series):
        """
        Normaliza qualquer formato de data para datetime64 puro (meia-noite, sem timezone).
        Aceita: dd/mm/yyyy, yyyy-mm-dd, "2026-01-06 00:00:00", ISO 8601, Timestamp, etc.
        Garante que formatos diferentes da mesma data sejam tratados como iguais na deduplicação.
        """
        # Tenta dayfirst=True primeiro (padrão brasileiro dd/mm/yyyy)
        parsed = pd.to_datetime(series, dayfirst=True, errors='coerce', utc=False)
        # Para valores que falharam, tenta sem dayfirst (ISO, yyyy-mm-dd, etc.)
        mask_nat = parsed.isna()
        if mask_nat.any():
            fallback = pd.to_datetime(series[mask_nat], dayfirst=False, errors='coerce', utc=False)
            parsed = parsed.copy()
            parsed[mask_nat] = fallback
        # Remove timezone e normaliza para meia-noite
        if hasattr(parsed, 'dt'):
            if parsed.dt.tz is not None:
                parsed = parsed.dt.tz_localize(None)
            parsed = parsed.dt.normalize()
        return parsed

    def _get_date_column(self, df):
        """Identifica a coluna de data no DataFrame."""
        possible_cols = [
            'data', 'data_envio', 'Data de envio', 'date',
            'created_time', 'data_publicacao', 'timestamp',
        ]
        for col in possible_cols:
            if col in df.columns:
                return col
        return None

    def _get_dedup_columns(self, source_name, combined_df, date_col):
        """Define colunas de deduplicação por fonte de dados."""
        if source_name == 'akna' or 'Campanhas' in combined_df.columns or 'campanhas' in combined_df.columns:
            cols = []
            for candidate in ['Campanhas', 'campanhas', 'Assunto', 'assunto', 'Data de envio', 'data_envio', 'Horario', 'horario']:
                if candidate in combined_df.columns:
                    cols.append(candidate)
            if cols:
                return cols
            return []

        if 'id' in combined_df.columns:
            return ['id']

        if date_col and 'titulo' in combined_df.columns and combined_df['titulo'].isna().all():
            return [date_col]

        if date_col and 'titulo' in combined_df.columns:
            return [date_col, 'titulo']

        if date_col:
            return [date_col]

        return []

    def _sanitize_dtypes(self, df):
        """
        Garante que colunas com tipo 'object' (strings mistas) sejam convertidas
        para string pura antes de salvar em Parquet, evitando ArrowTypeError quando
        o schema anterior esperava int e recebe str (ex: coluna 'Data' do LinkedIn).
        """
        for col in df.columns:
            if col == 'id':
                as_str = df[col].astype(str).str.strip()
                as_num = pd.to_numeric(as_str, errors='coerce')
                if as_num.notna().all() and as_str.str.match(r'^\d+$').all():
                    df[col] = as_num.astype('int64')
                else:
                    df[col] = as_str.replace('nan', '')
                continue
            if df[col].dtype == object:
                # Se todos os valores não-nulos forem numéricos, converte para número
                try:
                    converted = pd.to_numeric(df[col], errors='raise')
                    df[col] = converted
                except (ValueError, TypeError):
                    # Caso contrário, força string para evitar tipo misto
                    df[col] = df[col].astype(str).replace('nan', '')
        return df

    def get_summary_metrics(self, source_name, metrics_map):
        """Calcula métricas agregadas do histórico real."""
        df = self.load_data(source_name)
        if df.empty:
            return {m: 0 for m in metrics_map.values()}
        
        summary = {}
        for raw_col, target_name in metrics_map.items():
            if raw_col in df.columns:
                summary[target_name] = df[raw_col].sum()
            else:
                summary[target_name] = 0
        return summary