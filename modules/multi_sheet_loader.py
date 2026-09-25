"""
CARREGADOR DE MÚLTIPLAS PLANILHAS
Lê todas as planilhas de um diretório (incluindo subpastas) e consolida os dados
"""

import glob
import os

import pandas as pd

from modules.data_paths import AKNA_DIR
from modules.akna_validation import filter_akna_dataframe

SUPPORTED_EXTENSIONS = {'.xlsx', '.xls', '.csv'}


class MultiSheetLoader:
    """Carregador de múltiplas planilhas de um diretório"""

    def __init__(self, network_dir=None):
        self.network_dir = network_dir or AKNA_DIR
        self.months_map = {
            'janeiro': '01',
            'fevereiro': '02',
            'março': '03',
            'marco': '03',
            'abril': '04',
            'maio': '05',
            'junho': '06',
            'julho': '07',
            'agosto': '08',
            'setembro': '09',
            'outubro': '10',
            'novembro': '11',
            'dezembro': '12',
        }

    def _detect_month_from_name(self, name):
        """Detecta o mês a partir do nome de pasta ou arquivo."""
        name_lower = name.lower().strip()

        for month_name, month_num in self.months_map.items():
            if month_name in name_lower:
                return month_num, month_name.capitalize()

        return None, None

    def _collect_spreadsheet_paths(self):
        """Lista recursivamente todos os arquivos de planilha no diretório."""
        paths = []

        if not os.path.isdir(self.network_dir):
            return paths

        for root, _dirs, files in os.walk(self.network_dir):
            rel_root = os.path.relpath(root, self.network_dir)
            parent_hint = os.path.basename(root) if rel_root != '.' else ''

            for filename in sorted(files):
                ext = os.path.splitext(filename)[1].lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue
                if filename.startswith('~$'):
                    continue

                full_path = os.path.join(root, filename)
                month_num, month_name = self._detect_month_from_name(parent_hint)
                if not month_name:
                    month_num, month_name = self._detect_month_from_name(filename)

                paths.append({
                    'path': full_path,
                    'filename': filename,
                    'month_num': month_num,
                    'month_name': month_name,
                    'relative_dir': rel_root,
                })

        return paths

    def _read_excel_file(self, file_path):
        """Lê arquivo Excel com detecção automática de cabeçalho"""
        try:
            df_raw = pd.read_excel(file_path, header=None)
            header_row = 0

            for i, row in df_raw.head(10).iterrows():
                row_str = [str(c).lower() for c in row]
                if any(k in row_str for k in ['campanhas', 'data de envio', 'assunto', 'data', 'date', 'impressões', 'cliques']):
                    header_row = i
                    break

            df = pd.read_excel(file_path, skiprows=header_row)
            print(f"   ✅ Lido: {os.path.basename(file_path)} ({len(df)} registros)")
            return df

        except Exception as e:
            print(f"   ⚠️ Erro ao ler {file_path}: {e}")
            return pd.DataFrame()

    def _read_csv_file(self, file_path):
        """Lê arquivo CSV com detecção automática de delimitador"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline()
                sep = ';' if ';' in first_line else ','

            df = pd.read_csv(file_path, sep=sep)
            print(f"   ✅ Lido: {os.path.basename(file_path)} ({len(df)} registros)")
            return df

        except Exception as e:
            print(f"   ⚠️ Erro ao ler {file_path}: {e}")
            return pd.DataFrame()

    def _read_file(self, file_path):
        """Lê arquivo detectando formato automaticamente"""
        ext = os.path.splitext(file_path)[1].lower()

        if ext in ['.xlsx', '.xls']:
            return self._read_excel_file(file_path)
        if ext == '.csv':
            return self._read_csv_file(file_path)

        print(f"   ⚠️ Formato não suportado: {file_path}")
        return pd.DataFrame()

    def load_all_sheets(self):
        """
        Carrega todas as planilhas do diretório (recursivo) e consolida em uma única tabela.

        Returns:
            DataFrame com todos os dados consolidados
        """
        print(f"\n📂 Carregando planilhas de: {self.network_dir}")
        print("=" * 70)

        all_dfs = []

        try:
            spreadsheet_paths = self._collect_spreadsheet_paths()
            if not spreadsheet_paths:
                print(f"❌ Nenhuma planilha encontrada em: {self.network_dir}")
                return pd.DataFrame()

            print(f"📋 Encontrados {len(spreadsheet_paths)} arquivo(s) de planilha\n")

            for item in spreadsheet_paths:
                file_path = item['path']
                rel_dir = item['relative_dir']
                label = file_path if rel_dir == '.' else f"{rel_dir}\\{item['filename']}"
                print(f"📄 Arquivo: {label}")

                if item['month_name']:
                    print(f"   Mês detectado: {item['month_name']} ({item['month_num']})")

                df = self._read_file(file_path)
                if df.empty:
                    continue

                df = filter_akna_dataframe(df, log_prefix=f"[AKNA {item['filename']}]")
                if df.empty:
                    continue

                df['source_file'] = item['filename']
                if item['month_name']:
                    df['mes'] = item['month_name']
                    df['mes_num'] = int(item['month_num'])

                all_dfs.append(df)

            if not all_dfs:
                print(f"❌ Nenhum dado legível em: {self.network_dir}")
                return pd.DataFrame()

            print("\n" + "=" * 70)
            print("🔗 Consolidando dados...")

            consolidated = pd.concat(all_dfs, ignore_index=True)
            print(f"✅ Total de registros consolidados: {len(consolidated)}")

            date_col = next(
                (c for c in consolidated.columns if str(c).strip().lower() in ('data de envio', 'data_envio', 'data')),
                None,
            )
            if date_col:
                dates = pd.to_datetime(consolidated[date_col], dayfirst=True, errors='coerce')
                valid = dates.dropna()
                if not valid.empty:
                    print(f"📅 Período: {valid.min().strftime('%d/%m/%Y')} → {valid.max().strftime('%d/%m/%Y')}")
                    print("📊 Resumo por mês (data de envio):")
                    for period, count in valid.dt.to_period('M').value_counts().sort_index().items():
                        print(f"   - {period}: {count} registros")

            if 'mes' in consolidated.columns:
                print("\n📊 Resumo por pasta/arquivo:")
                for mes in consolidated['mes'].dropna().unique():
                    count = len(consolidated[consolidated['mes'] == mes])
                    print(f"   - {mes}: {count} registros")

            print("=" * 70 + "\n")
            return consolidated

        except Exception as e:
            print(f"❌ Erro ao carregar planilhas: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()


def load_akna_data_multi_sheet(network_dir=None):
    """Carrega e consolida todas as planilhas AKNA de um diretório."""
    loader = MultiSheetLoader(network_dir or AKNA_DIR)
    return loader.load_all_sheets()


if __name__ == '__main__':
    df = load_akna_data_multi_sheet()
    print(f"\nDataFrame shape: {df.shape}")
    if not df.empty:
        print(f"Colunas: {df.columns.tolist()}")
