"""Carrega extratos IOB a partir de planilhas .xlsx/.csv (pasta `data/input/iob` ou `DASHBOARD_IOB_DIR`)."""
import json
import os
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

from modules.data_paths import IOB_DIR

NETWORK_IOB_DIR = IOB_DIR
LOCAL_IOB_DIR = os.path.join("data", "input", "iob")
HISTORY_JSON = os.path.join("data", "history", "iob_access.json")

REQUIRED_COLUMNS = [
    "DATA E HORA AÇÃO",
    "AÇÃO 1",
    "AÇÃO 2",
    "AÇÃO 3",
    "AÇÃO 4",
]

COLUMN_HINTS = [
    (["DATA", "HORA"], "DATA E HORA AÇÃO"),
    (["ACAO", "1"], "AÇÃO 1"),
    (["ACAO", "2"], "AÇÃO 2"),
    (["ACAO", "3"], "AÇÃO 3"),
    (["ACAO", "4"], "AÇÃO 4"),
]


def _ascii_fold(text):
    if text is None:
        return ""
    s = unicodedata.normalize("NFKD", str(text))
    return s.encode("ascii", "ignore").decode("ascii")


def _normalize_col(name):
    if name is None:
        return ""
    s = str(name).strip().strip("'\"")
    s = re.sub(r"\s+", " ", s).upper()
    return _ascii_fold(s)


def _find_column(df, target):
    target_n = _normalize_col(target)
    for col in df.columns:
        if _normalize_col(col) == target_n:
            return col
    return None


def _find_column_by_hints(df, hints):
    for col in df.columns:
        norm = _normalize_col(col)
        if all(h in norm for h in hints):
            return col
    return None


def _resolve_columns(df):
    """Mapeia colunas obrigatórias mesmo com variações de encoding/nome."""
    mapping = {}
    missing = []
    for hints, label in COLUMN_HINTS:
        col = _find_column(df, label) or _find_column_by_hints(df, hints)
        mapping[label] = col
        if not col:
            missing.append(label)
    return mapping, missing


def _parse_datetime(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        dayfirst = not re.match(r"^\d{4}-\d{2}-\d{2}", s)
        return pd.to_datetime(value, dayfirst=dayfirst).to_pydatetime()
    except Exception:
        return None


def _classify_grupo(acao1, acao3, acao4):
    a1 = (acao1 or "").upper()
    a3 = (acao3 or "").lower()
    a4 = (acao4 or "").lower()

    if a1 == "IOB_PLAY":
        return "IOB Play — Vídeos"
    if "trabalhista" in a3 or "previdenci" in a3:
        return "Trabalhista e Previdenciária"
    if a1 == "ACESSO_SIMULADORES" or "reforma" in a3 or "desoneracao" in a4:
        return "Reforma Tributária"
    if a1 in (
        "NCM",
        "CONSULTA_NCM",
        "FERRAMENTAS_HOME",
        "ACESSO_DOC_PESQUISA_GERAL_HOME_AREA_TEMATICA",
        "ACESSO_DOC_PESQUISA_HOME_AREA_TEMATICA",
    ) or "fiscal" in a3 or "tribut" in a3:
        return "Fiscal e Tributárias"
    if a1 in ("LOGIN_USUARIO", "LOGOUT_USUARIO"):
        return "—"
    return "Outros / Não identificado"


def _tipo_evento(acao1):
    a1 = (acao1 or "").upper()
    if a1 == "LOGIN_USUARIO":
        return "Login"
    if a1 == "LOGOUT_USUARIO":
        return "Logout"
    return "Acesso a ferramenta"


def _records_from_dataframe(df):
    col_map, missing = _resolve_columns(df)

    records = []
    for _, row in df.iterrows():
        dt = _parse_datetime(row.get(col_map["DATA E HORA AÇÃO"]))
        a1 = str(row.get(col_map["AÇÃO 1"], "") or "").strip()
        a2 = str(row.get(col_map["AÇÃO 2"], "") or "").strip()
        a3 = str(row.get(col_map["AÇÃO 3"], "") or "").strip()
        a4 = str(row.get(col_map["AÇÃO 4"], "") or "").strip()
        if not any([dt, a1, a2, a3, a4]):
            continue
        grupo = _classify_grupo(a1, a3, a4)
        records.append({
            "data_hora": dt.strftime("%d/%m/%Y %H:%M") if dt else "",
            "data_hora_iso": dt.isoformat() if dt else "",
            "acao_1": a1,
            "acao_2": a2,
            "acao_3": a3,
            "acao_4": a4,
            "grupo_ferramenta": grupo,
            "tipo_evento": _tipo_evento(a1),
        })

    return records, missing


def _build_analytics(records, source_file="", source_files=None, status=""):
    tool_records = [r for r in records if r.get("tipo_evento") == "Acesso a ferramenta"]
    counter = Counter(r.get("grupo_ferramenta", "Outros / Não identificado") for r in tool_records)
    labels = list(counter.keys())
    values = [counter[k] for k in labels]
    total_tools = sum(values) or 1
    percentages = [round(v / total_tools * 100, 2) for v in values]

    files = source_files or ([source_file] if source_file else [])
    files = [f for f in files if f]

    kpis = {
        "total_registros": len(records),
        "total_logins": sum(1 for r in records if r.get("tipo_evento") == "Login"),
        "total_logouts": sum(1 for r in records if r.get("tipo_evento") == "Logout"),
        "total_acessos_ferramenta": len(tool_records),
    }

    status_msg = status
    if not status_msg:
        if records and len(files) > 1:
            status_msg = f"Extrato IOB consolidado ({len(files)} planilhas, {len(records)} registros)"
        elif records:
            status_msg = "Extrato IOB carregado"
        else:
            status_msg = "Nenhum registro IOB"

    return {
        "source_file": source_file or (files[0] if len(files) == 1 else ""),
        "source_files": files,
        "status": status_msg,
        "columns_ok": True,
        "missing_columns": [],
        "kpis": kpis,
        "grafico_grupos": {"labels": labels, "values": values},
        "grafico_distribuicao": {
            "labels": labels,
            "values": values,
            "percentages": percentages,
        },
        "all_data": records,
        "validation": {
            "total_extrato": len(records),
            "total_processado": len(records),
            "compativel": True,
            "planilhas": len(files),
        },
    }


def _is_valid_spreadsheet(filename):
    lower = filename.lower()
    if lower.startswith("~$"):
        return False
    return lower.endswith((".xlsx", ".xls", ".csv"))


def _list_network_spreadsheets(network_dir):
    """Lista .xlsx/.xls/.csv na pasta de rede (sem depender só do Path.glob)."""
    if not network_dir or not os.path.isdir(network_dir):
        return []

    files = []
    try:
        for name in os.listdir(network_dir):
            if not _is_valid_spreadsheet(name):
                continue
            full = os.path.join(network_dir, name)
            if os.path.isfile(full):
                files.append(full)
    except OSError as exc:
        print(f"  [AVISO] Nao foi possivel listar {network_dir}: {exc}")
    return files


def _latest_spreadsheet_from_dir(directory):
    files = _list_network_spreadsheets(directory)
    if not files:
        return None
    return max(files, key=lambda p: os.path.getmtime(p))


def _all_spreadsheets_from_dirs(*directories):
    """Lista todas as planilhas válidas, sem duplicar caminhos."""
    seen = set()
    files = []
    for directory in directories:
        if not directory:
            continue
        for path in _list_network_spreadsheets(directory):
            norm = os.path.normcase(os.path.abspath(path))
            if norm in seen:
                continue
            seen.add(norm)
            files.append(path)
    return sorted(files, key=lambda p: os.path.getmtime(p))


def _dedupe_records(records):
    """Remove registros duplicados entre planilhas sobrepostas."""
    seen = set()
    unique = []
    for row in records:
        key = (
            row.get("data_hora_iso") or row.get("data_hora") or "",
            row.get("acao_1") or "",
            row.get("acao_2") or "",
            row.get("acao_3") or "",
            row.get("acao_4") or "",
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)

    def _sort_key(item):
        iso = item.get("data_hora_iso") or ""
        return iso

    unique.sort(key=_sort_key, reverse=True)
    return unique


def _pick_detail_sheet(sheet_names):
    for name in sheet_names:
        if "detalhes" in _normalize_col(name).lower():
            return name
    for name in sheet_names:
        if "acesso" in _normalize_col(name).lower() and "detalhe" not in _normalize_col(name).lower():
            continue
    return sheet_names[0] if sheet_names else 0


def _read_excel(path):
    xl = pd.ExcelFile(path)
    sheet = _pick_detail_sheet(xl.sheet_names)
    return pd.read_excel(path, sheet_name=sheet)


def _load_from_path(path):
    df = _read_excel(path)
    records, missing = _records_from_dataframe(df)
    if missing:
        print(f"  [AVISO] IOB colunas ausentes em {os.path.basename(path)}: {', '.join(missing)}")
    for row in records:
        row["source_file"] = os.path.basename(path)
    return records, missing, path


def _load_all_from_paths(paths):
    all_records = []
    source_files = []
    missing_all = set()
    per_file = []

    for path in paths:
        try:
            records, missing, loaded_path = _load_from_path(path)
            all_records.extend(records)
            source_files.append(loaded_path)
            missing_all.update(missing)
            per_file.append((os.path.basename(loaded_path), len(records)))
            print(f"  [OK] IOB: {len(records)} registros de {loaded_path}")
        except Exception as exc:
            print(f"  [AVISO] Falha ao ler planilha IOB ({path}): {exc}")

    merged = _dedupe_records(all_records)
    if len(merged) < len(all_records):
        print(f"  [Dedup] IOB: {len(all_records)} -> {len(merged)} registros após consolidar planilhas")

    analytics = _build_analytics(
        merged,
        source_file=source_files[0] if len(source_files) == 1 else NETWORK_IOB_DIR,
        source_files=source_files,
        status=(
            f"Extrato IOB consolidado ({len(source_files)} planilhas, {len(merged)} registros)"
            if source_files and merged else "Planilha vazia"
        ),
    )
    analytics["columns_ok"] = len(missing_all) == 0
    analytics["missing_columns"] = sorted(missing_all)
    payload = {
        "analytics": analytics,
        "status": analytics["status"],
        "source_file": analytics.get("source_file", ""),
        "source_files": source_files,
    }
    _save_history(analytics)
    if per_file:
        resumo = ", ".join(f"{name}: {count}" for name, count in per_file)
        print(f"  [OK] IOB consolidado: {len(merged)} registros ({resumo})")
    return payload


def load_iob_dashboard():
    """Carrega e consolida todas as planilhas .xlsx da pasta IOB."""
    paths = _all_spreadsheets_from_dirs(NETWORK_IOB_DIR, LOCAL_IOB_DIR)
    if paths:
        try:
            return _load_all_from_paths(paths)
        except Exception as exc:
            print(f"  [AVISO] Falha ao consolidar planilhas IOB: {exc}")

    if not paths:
        print(f"  [AVISO] Nenhum .xlsx em {NETWORK_IOB_DIR} nem em {LOCAL_IOB_DIR}")

    if os.path.exists(HISTORY_JSON):
        try:
            with open(HISTORY_JSON, "r", encoding="utf-8") as fh:
                analytics = json.load(fh)
            print(
                f"  [OK] IOB: {analytics.get('kpis', {}).get('total_registros', 0)} "
                f"registros (historico JSON - rede indisponivel)"
            )
            return {
                "analytics": analytics,
                "status": analytics.get("status", "Historico IOB"),
                "source_file": analytics.get("source_file", HISTORY_JSON),
            }
        except Exception as exc:
            print(f"  [AVISO] Falha ao ler {HISTORY_JSON}: {exc}")

    empty = _build_analytics([], status=f"Nenhum arquivo em {NETWORK_IOB_DIR}")
    return {"analytics": empty, "status": empty["status"], "source_file": ""}


def _save_history(analytics):
    try:
        os.makedirs(os.path.dirname(HISTORY_JSON), exist_ok=True)
        with open(HISTORY_JSON, "w", encoding="utf-8") as fh:
            json.dump(analytics, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass
