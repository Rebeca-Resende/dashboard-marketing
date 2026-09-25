"""Pastas de planilhas manuais (relativas ao projeto; sobrescreva via variáveis de ambiente)."""
import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _input_dir(env_var: str, subdir: str) -> str:
    override = os.environ.get(env_var, "").strip()
    if override:
        return override
    return str(_ROOT / "data" / "input" / subdir)


AKNA_DIR = _input_dir("DASHBOARD_AKNA_DIR", "akna")
IOB_DIR = _input_dir("DASHBOARD_IOB_DIR", "iob")
LINKEDIN_DIR = _input_dir("DASHBOARD_LINKEDIN_DIR", "linkedin")

DATA_PATHS = {
    "akna": AKNA_DIR,
    "iob": IOB_DIR,
    "linkedin": LINKEDIN_DIR,
}
