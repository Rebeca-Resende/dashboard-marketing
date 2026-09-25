"""
Regras de validação para dados AKNA.

Linhas com Horario, Ações ou Assunto vazios são ignoradas na carga e na análise.
"""
import re
import unicodedata

import pandas as pd

REQUIRED_AKNA_FIELDS = (
    ("Horario", ("horario",)),
    ("Assunto", ("assunto",)),
    ("Ações", ("acoes", "acao", "acoes")),
)


def _ascii_fold(text):
    if text is None:
        return ""
    s = unicodedata.normalize("NFKD", str(text))
    s = s.encode("ascii", "ignore").decode("ascii").lower().strip()
    return re.sub(r"\s+", " ", s)


def _is_empty_value(val):
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    if isinstance(val, pd.Timestamp) and pd.isna(val):
        return True
    text = str(val).strip()
    return text == "" or text.lower() in ("nan", "none", "nat", "<na>")


def _find_column(df, *candidates):
    if df is None or df.empty:
        return None
    exact = {_ascii_fold(col): col for col in df.columns}
    for cand in candidates:
        key = _ascii_fold(cand)
        if key in exact:
            return exact[key]
    for col in df.columns:
        ncol = _ascii_fold(col)
        for cand in candidates:
            ckey = _ascii_fold(cand)
            if ckey and (ckey in ncol or ncol in ckey):
                return col
    return None


def resolve_akna_required_columns(df):
    """Retorna mapeamento {rótulo lógico: coluna no DataFrame}."""
    mapping = {}
    for label, aliases in REQUIRED_AKNA_FIELDS:
        col = _find_column(df, label, *aliases)
        if col:
            mapping[label] = col
    return mapping


def is_akna_row_valid(row, col_map=None):
    """True se Horario, Ações e Assunto estiverem preenchidos."""
    if col_map is None:
        if isinstance(row, pd.Series):
            col_map = resolve_akna_required_columns(row.to_frame().T)
        else:
            return False
    if len(col_map) < len(REQUIRED_AKNA_FIELDS):
        return False
    for label in ("Horario", "Assunto", "Ações"):
        col = col_map.get(label)
        if not col:
            return False
        value = row[col] if isinstance(row, pd.Series) else row.get(col)
        if _is_empty_value(value):
            return False
    return True


def filter_akna_dataframe(df, log_prefix="[AKNA]"):
    """
    Remove linhas onde Horario, Ações ou Assunto estiver vazio.
    Retorna cópia filtrada do DataFrame.
    """
    if df is None or df.empty:
        return df.copy() if df is not None else pd.DataFrame()

    col_map = resolve_akna_required_columns(df)
    missing = [label for label, _ in REQUIRED_AKNA_FIELDS if label not in col_map]
    if missing:
        print(
            f"  {log_prefix} AVISO: colunas obrigatórias ausentes "
            f"({', '.join(missing)}) — nenhum registro será importado."
        )
        return df.iloc[0:0].copy()

    mask = pd.Series(True, index=df.index)
    for col in col_map.values():
        mask &= ~df[col].apply(_is_empty_value)

    removed = int((~mask).sum())
    if removed:
        print(
            f"  {log_prefix} {removed} registro(s) ignorado(s) "
            f"(Horario, Ações ou Assunto vazio)"
        )
    return df.loc[mask].copy()


def filter_akna_records(records, log_prefix="[AKNA]"):
    """Filtra lista de dicts normalizados (horario/acoes/assunto)."""
    if not records:
        return []

    filtered = []
    for item in records:
        horario = item.get("horario")
        acao = item.get("acoes", item.get("acao"))
        assunto = item.get("assunto")
        if _is_empty_value(horario) or _is_empty_value(acao) or _is_empty_value(assunto):
            continue
        filtered.append(item)

    removed = len(records) - len(filtered)
    if removed:
        print(
            f"  {log_prefix} {removed} registro(s) ignorado(s) "
            f"(Horario, Ações ou Assunto vazio)"
        )
    return filtered
