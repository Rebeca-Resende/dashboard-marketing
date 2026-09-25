"""Perfis de sites GA4/GSC a partir do config.json (sem URLs fixas no código)."""


def _cfg_block(config, primary_key, legacy_key):
    config = config or {}
    block = config.get(primary_key) or config.get(legacy_key) or {}
    return block if isinstance(block, dict) else {}


def primary_site_profile(config=None):
    cfg = _cfg_block(config, "site_primary", "site_borracha")
    url = (cfg.get("url") or "").strip()
    return {
        "nome": cfg.get("name") or cfg.get("nome") or "Site principal",
        "id": "site-primary",
        "url": url,
        "gsc_site_url": (cfg.get("gsc_site_url") or url).strip(),
        "ga4_property_id": str(cfg.get("ga4_property_id") or "").strip(),
        "include_representacao": bool(cfg.get("include_representacao", True)),
    }


def secondary_site_profile(config=None):
    cfg = _cfg_block(config, "site_secondary", "site_conecta")
    url = (cfg.get("url") or "").strip()
    return {
        "nome": cfg.get("name") or cfg.get("nome") or "Site secundário",
        "id": "site-secondary",
        "url": url,
        "gsc_site_url": (cfg.get("gsc_site_url") or url).strip(),
        "ga4_property_id": str(cfg.get("ga4_property_id") or "").strip(),
        "include_representacao": False,
    }


def gsc_site_url_from_config(config=None, which="primary"):
    profile = primary_site_profile(config) if which == "primary" else secondary_site_profile(config)
    return profile.get("gsc_site_url") or profile.get("url") or ""
