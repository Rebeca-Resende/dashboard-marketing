"""
Constantes e helpers GA4 — uma propriedade distinta por site.

IDs vêm apenas do config.json (site_primary / site_secondary).
"""
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)

KEY_SITE_PRIMARY = "Site institucional"
KEY_SITE_SECONDARY = "Site secundário"

GA4_DATE_RANGE = [DateRange(start_date="30daysAgo", end_date="yesterday")]
GA4_HISTORICO_DATE_RANGE = [DateRange(start_date="90daysAgo", end_date="yesterday")]


def ga4_property_path(property_id: str) -> str:
    """Formata o resource name GA4: properties/123456789"""
    pid = str(property_id or "").strip()
    if not pid:
        return ""
    if pid.startswith("properties/"):
        return pid
    return f"properties/{pid}"


def build_base_report_request(property_id: str) -> RunReportRequest:
    """Request base de validação — uma consulta por propriedade."""
    return RunReportRequest(
        property=ga4_property_path(property_id),
        dimensions=[Dimension(name="date")],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="sessions"),
            Metric(name="screenPageViews"),
        ],
        date_ranges=GA4_DATE_RANGE,
    )


def resolve_property_ids(config=None):
    """
    Resolve IDs das propriedades a partir do config.json.
    Retorna dict {nome_amigavel: property_id} (string vazia se não configurado).
    """
    config = config or {}
    primary_cfg = config.get("site_primary") or config.get("site_borracha", {})
    secondary_cfg = config.get("site_secondary") or config.get("site_conecta", {})
    ga_cfg = config.get("google_analytics", {})
    props_cfg = ga_cfg.get("property_ids", {}) if isinstance(ga_cfg.get("property_ids"), dict) else {}

    site_id = (
        primary_cfg.get("ga4_property_id")
        or props_cfg.get(KEY_SITE_PRIMARY)
        or props_cfg.get("Site institucional")
        or ""
    )
    secondary_id = (
        secondary_cfg.get("ga4_property_id")
        or props_cfg.get(KEY_SITE_SECONDARY)
        or props_cfg.get("Abiarb Conecta")
        or ""
    )

    return {
        KEY_SITE_PRIMARY: str(site_id).strip(),
        KEY_SITE_SECONDARY: str(secondary_id).strip(),
    }
