"""
Carrega métricas do site secundário (GA4 + Search Console).
Configure em config.json > site_secondary (ou site_conecta legado).
"""
from modules.site_config import secondary_site_profile
from modules.sites_dashboard import empty_site_payload, load_site_dashboard


def empty_conecta_payload(status="Aguardando integração da API", config=None):
    return empty_site_payload(status, secondary_site_profile(config), include_representacao=False)


def load_conecta_dashboard(
    ga4_client,
    property_id,
    oauth_creds=None,
    search_console=None,
    config=None,
):
    profile = secondary_site_profile(config)
    if not property_id:
        return empty_conecta_payload("Aguardando integração da API", config)
    return load_site_dashboard(
        ga4_client,
        property_id,
        profile,
        oauth_creds=oauth_creds,
        search_console=search_console,
    )
