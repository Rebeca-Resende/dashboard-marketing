"""
Carrega métricas expandidas do site (GA4 + Search Console) para a aba Sites.
"""
import json
import os
import unicodedata
from datetime import datetime, timedelta
from urllib.parse import urlparse

from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    OrderBy,
)

from modules.ga4_properties import (
    GA4_DATE_RANGE,
    GA4_HISTORICO_DATE_RANGE,
    ga4_property_path,
)
from modules.site_config import primary_site_profile

DATE_RANGE = GA4_DATE_RANGE
GSC_SUMMARY_DAYS = 30
GSC_HISTORICO_DAYS = 90
GA4_RETRY_ATTEMPTS = 3
GA4_RETRY_DELAY_SEC = 2

DEFAULT_PRIMARY_SITE_PROFILE = primary_site_profile(None)

BR_ESTADOS = [
    "Acre", "Alagoas", "Amapá", "Amazonas", "Bahia", "Ceará",
    "Distrito Federal", "Espírito Santo", "Goiás", "Maranhão",
    "Mato Grosso", "Mato Grosso do Sul", "Minas Gerais", "Pará",
    "Paraíba", "Paraná", "Pernambuco", "Piauí", "Rio de Janeiro",
    "Rio Grande do Norte", "Rio Grande do Sul", "Rondônia", "Roraima",
    "Santa Catarina", "São Paulo", "Sergipe", "Tocantins",
]

DIAS_SEMANA = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]

SITE_CACHE_DIR = os.path.join("data", "history")


def _site_cache_path(profile_id):
    safe_id = (profile_id or "site").replace("/", "_")
    return os.path.join(SITE_CACHE_DIR, f"site_{safe_id}.json")


def _save_site_cache(profile_id, payload):
    try:
        os.makedirs(SITE_CACHE_DIR, exist_ok=True)
        cached = dict(payload)
        cached["cached_at"] = datetime.now().strftime("%d/%m/%Y %H:%M")
        with open(_site_cache_path(profile_id), "w", encoding="utf-8") as fh:
            json.dump(cached, fh, ensure_ascii=False)
    except Exception as exc:
        print(f"  [AVISO] Não foi possível salvar cache do site ({profile_id}): {exc}")


def _load_site_cache(profile_id):
    path = _site_cache_path(profile_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        print(f"  [AVISO] Falha ao ler cache do site ({profile_id}): {exc}")
        return None


def _ascii_fold(text):
    if text is None:
        return ""
    s = unicodedata.normalize("NFKD", str(text))
    return s.encode("ascii", "ignore").decode("ascii").lower().strip()


def normalize_estado(region_name):
    if not region_name:
        return ""
    s = str(region_name).strip()
    for prefix in ("State of ", "Estado de ", "Province of ", "Estado "):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s.strip()


def _match_estado(region_name, estados_list):
    norm = _ascii_fold(normalize_estado(region_name))
    for estado in estados_list:
        if _ascii_fold(estado) == norm:
            return estado
        if norm in _ascii_fold(estado) or _ascii_fold(estado) in norm:
            return estado
    return normalize_estado(region_name)


def empty_site_payload(status="GA4 Desconectado", profile=None, include_representacao=None):
    profile = profile or DEFAULT_PRIMARY_SITE_PROFILE
    rep = include_representacao if include_representacao is not None else profile.get("include_representacao", True)
    payload = {
        "nome": profile.get("nome", "Site"),
        "id": profile.get("id", "site"),
        "url": profile.get("url", ""),
        "ga4_property": ga4_property_path(profile.get("ga4_property_id", "")) if profile.get("ga4_property_id") else "",
        "status_integracao": status,
        "metricas_principais": {
            "usuarios_ativos": 0, "novos_usuarios": 0, "sessoes": 0,
            "visualizacoes": 0, "tempo_engajamento": "0s", "taxa_rejeicao": "0%",
            "taxa_engajamento": "0%", "vistas_por_usuario": "0",
        },
        "origem_trafego": {},
        "paginas_mais_visitadas": [],
        "paginas_diario": [],
        "dispositivos": {},
        "historico_7d": {
            "labels": [], "dates_iso": [], "usuarios": [], "vistas": [], "sessoes": [],
            "novos_usuarios": [], "taxa_rejeicao": [], "taxa_engajamento": [], "duracao_sessao": [],
        },
        "canais_diario": [],
        "gsc_diario": [],
        "google_search": {"visualizacoes": "0", "cliques": "0", "ctr": "0%", "posicao": "0", "fonte": "search_console"},
        "seo_fonte": "search_console",
        "gsc_status": "indisponivel",
        "atividade": {
            "sessoes": 0, "visualizacoes": 0, "eventos": 0,
            "por_hora": {"labels": [], "usuarios": []},
            "por_dia_semana": {"labels": [], "usuarios": []},
            "engajamento_diario": {"labels": [], "taxa": []},
        },
        "seo_ranking": {
            "top_queries": [], "top_pages": [],
            "evolucao": {"labels": [], "cliques": [], "impressoes": [], "posicao": []},
        },
        "localidades": {"estados": [], "cidades": [], "paises": []},
    }
    if rep:
        payload["estados_sem_representacao"] = {
            "trafego_por_estado": [],
            "santa_catarina": {"usuarios": 0, "sessoes": 0, "percentual": "0%"},
            "analise_ia": {
                "status": "pendente",
                "fontes": [],
                "foco_santa_catarina": "",
                "tabela_estados": [],
                "acoes": [],
            },
        }
    return payload


def empty_sites_payload(status="GA4 Desconectado", profile=None):
    return empty_site_payload(status, profile or DEFAULT_PRIMARY_SITE_PROFILE)


def _run_ga4(ga4_client, property_id, dimensions, metrics, limit=None, order_metric=None, date_ranges=None):
    if not ga4_client:
        return None
    dims = [Dimension(name=d) for d in dimensions]
    mets = [Metric(name=m) for m in metrics]
    kwargs = {
        "property": ga4_property_path(property_id),
        "dimensions": dims,
        "metrics": mets,
        "date_ranges": date_ranges or DATE_RANGE,
    }
    if limit:
        kwargs["limit"] = limit
    if order_metric:
        kwargs["order_bys"] = [
            OrderBy(metric=OrderBy.MetricOrderBy(metric_name=order_metric), desc=True)
        ]
    import time
    last_exc = None
    for attempt in range(1, GA4_RETRY_ATTEMPTS + 1):
        try:
            return ga4_client.run_report(RunReportRequest(**kwargs))
        except Exception as exc:
            last_exc = exc
            if attempt < GA4_RETRY_ATTEMPTS:
                print(f"  [GA4] Tentativa {attempt}/{GA4_RETRY_ATTEMPTS} falhou: {exc}. Retentando...")
                time.sleep(GA4_RETRY_DELAY_SEC * attempt)
    print(f"  [GA4] Falha após {GA4_RETRY_ATTEMPTS} tentativas: {last_exc}")
    return None


def _get_gsc_client(oauth_creds=None, search_console=None):
    if search_console:
        return search_console
    if oauth_creds:
        try:
            from googleapiclient.discovery import build as gsc_build
            return gsc_build("searchconsole", "v1", credentials=oauth_creds)
        except Exception:
            pass
    if os.path.exists("service_account.json"):
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build as gsc_build
            scopes = ["https://www.googleapis.com/auth/webmasters.readonly"]
            creds = service_account.Credentials.from_service_account_file(
                "service_account.json", scopes=scopes
            )
            return gsc_build("searchconsole", "v1", credentials=creds)
        except Exception:
            pass
    return None


def _domain_from_url(url):
    if not url:
        return ""
    host = urlparse(url).netloc or url
    return host.lower().replace("www.", "").strip("/")


def _resolve_gsc_site_url(gsc, configured_url):
    """Encontra a URL exata cadastrada no Search Console para o domínio."""
    if not gsc or not configured_url:
        return configured_url
    try:
        entries = gsc.sites().list().execute().get("siteEntry", [])
        urls = [
            e.get("siteUrl", "")
            for e in entries
            if e.get("siteUrl") and e.get("permissionLevel") != "siteUnverifiedUser"
        ]
        if not urls:
            return configured_url

        domain = _domain_from_url(configured_url)
        normalized_cfg = configured_url.rstrip("/")

        for candidate in urls:
            if candidate.rstrip("/") == normalized_cfg:
                return candidate
        for candidate in urls:
            if domain and domain in _domain_from_url(candidate):
                return candidate
        for candidate in urls:
            if domain and candidate == f"sc-domain:{domain}":
                return candidate
    except Exception as exc:
        print(f"  [Search Console] Erro ao listar sites: {exc}")
    return configured_url


def _gsc_has_data(gsc_rows, seo_ranking):
    if gsc_rows:
        return True
    if seo_ranking.get("top_queries") or seo_ranking.get("top_pages"):
        return True
    return False


def _build_seo_ga4_organic_fallback(ga4_client, property_id, base_url=""):
    """
    Fallback quando Search Console não está configurado:
    usa tráfego orgânico do GA4 (páginas de entrada + sessões).
    """
    seo = {
        "top_queries": [],
        "top_pages": [],
        "evolucao": {"labels": [], "cliques": [], "impressoes": [], "posicao": []},
    }
    google_search = {
        "visualizacoes": "0",
        "cliques": "0",
        "ctr": "0%",
        "posicao": "—",
        "fonte": "ga4_organico",
    }
    if not ga4_client:
        return google_search, seo

    page_stats = {}
    total_sessions = 0
    total_views = 0

    res_pages = _run_ga4(
        ga4_client, property_id,
        ["landingPage", "sessionDefaultChannelGroup"],
        ["sessions", "screenPageViews"],
        limit=100, order_metric="sessions",
    )
    if res_pages:
        for row in res_pages.rows:
            channel = row.dimension_values[1].value or ""
            if "Organic" not in channel:
                continue
            page = row.dimension_values[0].value or "/"
            sess = int(row.metric_values[0].value)
            views = int(row.metric_values[1].value)
            if page not in page_stats:
                page_stats[page] = {"sessoes": 0, "views": 0}
            page_stats[page]["sessoes"] += sess
            page_stats[page]["views"] += views
            total_sessions += sess
            total_views += views

    sorted_pages = sorted(page_stats.items(), key=lambda x: x[1]["sessoes"], reverse=True)[:15]
    for page, stats in sorted_pages:
        if page in ("(not set)", "(none)", ""):
            continue
        views = stats["views"]
        sess = stats["sessoes"]
        ctr = (sess / views * 100) if views > 0 else 0
        display_page = page
        if base_url and page.startswith("/"):
            display_page = base_url.rstrip("/") + page
        elif len(display_page) > 80:
            display_page = display_page[:77] + "..."
        seo["top_pages"].append({
            "page": display_page,
            "cliques": sess,
            "impressoes": views,
            "ctr": f"{ctr:.1f}%",
            "posicao": "—",
        })

    res_daily = _run_ga4(
        ga4_client, property_id,
        ["date", "sessionDefaultChannelGroup"],
        ["sessions", "screenPageViews"],
    )
    if res_daily:
        daily = {}
        for row in res_daily.rows:
            channel = row.dimension_values[1].value or ""
            if "Organic" not in channel:
                continue
            raw_date = row.dimension_values[0].value
            sess = int(row.metric_values[0].value)
            views = int(row.metric_values[1].value)
            if raw_date not in daily:
                daily[raw_date] = {"sessoes": 0, "views": 0}
            daily[raw_date]["sessoes"] += sess
            daily[raw_date]["views"] += views

        for raw_date in sorted(daily.keys()):
            try:
                dt = datetime.strptime(raw_date, "%Y%m%d")
                seo["evolucao"]["labels"].append(dt.strftime("%d/%m"))
            except ValueError:
                seo["evolucao"]["labels"].append(raw_date)
            seo["evolucao"]["cliques"].append(daily[raw_date]["sessoes"])
            seo["evolucao"]["impressoes"].append(daily[raw_date]["views"])
            seo["evolucao"]["posicao"].append(0)

    if total_sessions > 0 or total_views > 0:
        ctr_val = (total_sessions / total_views * 100) if total_views > 0 else 0
        google_search = {
            "visualizacoes": str(total_views),
            "cliques": str(total_sessions),
            "ctr": f"{ctr_val:.1f}%",
            "posicao": "—",
            "fonte": "ga4_organico",
        }

    return google_search, seo


def _gsc_date_range(days=GSC_SUMMARY_DAYS):
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)
    return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")


def _query_gsc(gsc, gsc_site_url="", dimensions=None, row_limit=10, days=GSC_SUMMARY_DAYS):
    if not gsc:
        return []
    start_date, end_date = _gsc_date_range(days=days)
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "rowLimit": row_limit,
    }
    if dimensions:
        body["dimensions"] = dimensions
    try:
        resp = gsc.searchanalytics().query(
            siteUrl=gsc_site_url, body=body
        ).execute()
        return resp.get("rows", [])
    except Exception as exc:
        print(f"  [Search Console] Erro na consulta ({dimensions}): {exc}")
        return []


def _fetch_gsc_diario(gsc, gsc_site_url=""):
    """Histórico diário GSC para filtro no frontend."""
    diario = []
    for row in _query_gsc(
        gsc, gsc_site_url, dimensions=["date"], row_limit=25000, days=GSC_HISTORICO_DAYS
    ):
        keys = row.get("keys", [])
        if not keys:
            continue
        diario.append({
            "date": keys[0],
            "impressoes": int(row.get("impressions", 0)),
            "cliques": int(row.get("clicks", 0)),
            "ctr": float(row.get("ctr", 0)),
            "posicao": float(row.get("position", 0)),
        })
    diario.sort(key=lambda item: item["date"])
    return diario


def _parse_gsc_summary(rows):
    if not rows:
        return {"visualizacoes": "0", "cliques": "0", "ctr": "0%", "posicao": "0"}
    total_impressions = sum(int(r.get("impressions", 0)) for r in rows)
    total_clicks = sum(int(r.get("clicks", 0)) for r in rows)
    avg_ctr = total_clicks / total_impressions if total_impressions > 0 else 0
    avg_position = (
        sum(float(r.get("position", 0)) for r in rows) / len(rows) if rows else 0
    )
    return {
        "visualizacoes": str(total_impressions),
        "cliques": str(total_clicks),
        "ctr": f"{avg_ctr * 100:.1f}%",
        "posicao": f"{avg_position:.1f}",
    }


def _build_seo_ranking(gsc, gsc_site_url=""):
    seo = {"top_queries": [], "top_pages": [], "evolucao": {"labels": [], "cliques": [], "impressoes": [], "posicao": []}}
    if not gsc:
        return seo

    for row in _query_gsc(gsc, gsc_site_url, dimensions=["query"], row_limit=15):
        keys = row.get("keys", [])
        if not keys:
            continue
        seo["top_queries"].append({
            "query": keys[0],
            "cliques": int(row.get("clicks", 0)),
            "impressoes": int(row.get("impressions", 0)),
            "ctr": f"{row.get('ctr', 0) * 100:.1f}%",
            "posicao": f"{row.get('position', 0):.1f}",
        })

    for row in _query_gsc(gsc, gsc_site_url, dimensions=["page"], row_limit=15):
        keys = row.get("keys", [])
        if not keys:
            continue
        page = keys[0]
        if len(page) > 80:
            page = page[:77] + "..."
        seo["top_pages"].append({
            "page": page,
            "cliques": int(row.get("clicks", 0)),
            "impressoes": int(row.get("impressions", 0)),
            "ctr": f"{row.get('ctr', 0) * 100:.1f}%",
            "posicao": f"{row.get('position', 0):.1f}",
        })

    for row in _query_gsc(gsc, gsc_site_url, dimensions=["date"], row_limit=30):
        keys = row.get("keys", [])
        if not keys:
            continue
        try:
            dt = datetime.strptime(keys[0], "%Y-%m-%d")
            seo["evolucao"]["labels"].append(dt.strftime("%d/%m"))
        except ValueError:
            seo["evolucao"]["labels"].append(keys[0])
        seo["evolucao"]["cliques"].append(int(row.get("clicks", 0)))
        seo["evolucao"]["impressoes"].append(int(row.get("impressions", 0)))
        seo["evolucao"]["posicao"].append(round(float(row.get("position", 0)), 1))

    return seo


def _build_trafego_regional(estados_trafego):
    """Monta tráfego regional real (GA4) — representação é analisada por IA depois."""
    trafego_por_estado = []
    total_usuarios = 0

    for item in estados_trafego:
        estado = _match_estado(item["estado"], BR_ESTADOS)
        usuarios = item.get("usuarios", 0)
        sessoes = item.get("sessoes", 0)
        total_usuarios += usuarios
        trafego_por_estado.append({
            "estado": estado,
            "usuarios": usuarios,
            "sessoes": sessoes,
        })

    trafego_por_estado.sort(key=lambda x: x["usuarios"], reverse=True)

    sc = next(
        (e for e in trafego_por_estado if _ascii_fold(e["estado"]) == _ascii_fold("Santa Catarina")),
        {"usuarios": 0, "sessoes": 0},
    )
    sc_usuarios = sc.get("usuarios", 0)
    sc_sessoes = sc.get("sessoes", 0)
    pct = (sc_usuarios / total_usuarios * 100) if total_usuarios > 0 else 0

    return {
        "trafego_por_estado": trafego_por_estado,
        "santa_catarina": {
            "usuarios": sc_usuarios,
            "sessoes": sc_sessoes,
            "percentual": f"{pct:.1f}%",
        },
        "analise_ia": {
            "status": "pendente",
            "fontes": [],
            "foco_santa_catarina": "",
            "tabela_estados": [],
            "acoes": [],
        },
    }


def load_site_dashboard(
    ga4_client,
    property_id,
    profile=None,
    oauth_creds=None,
    search_console=None,
):
    """Carrega dados completos de um site via GA4 e Search Console."""
    profile = profile or DEFAULT_PRIMARY_SITE_PROFILE
    gsc_site_url = profile.get("gsc_site_url") or profile.get("url") or ""
    include_rep = profile.get("include_representacao", True)

    if not ga4_client or not property_id:
        return empty_site_payload("GA4 Desconectado", profile)

    try:
        # Métricas principais
        res_main = _run_ga4(
            ga4_client, property_id, [], [
                "activeUsers", "newUsers", "sessions", "screenPageViews",
                "averageSessionDuration", "bounceRate", "engagementRate",
                "screenPageViewsPerUser", "eventCount",
            ]
        )
        main_metrics = {
            "usuarios_ativos": 0, "novos_usuarios": 0, "sessoes": 0,
            "visualizacoes": 0, "tempo_engajamento": "0s", "taxa_rejeicao": "0%",
            "taxa_engajamento": "0%", "vistas_por_usuario": "0",
        }
        total_eventos = 0
        if res_main and res_main.rows:
            row = res_main.rows[0]
            main_metrics["usuarios_ativos"] = int(row.metric_values[0].value)
            main_metrics["novos_usuarios"] = int(row.metric_values[1].value)
            main_metrics["sessoes"] = int(row.metric_values[2].value)
            main_metrics["visualizacoes"] = int(row.metric_values[3].value)
            avg_duration = float(row.metric_values[4].value)
            main_metrics["tempo_engajamento"] = f"{int(avg_duration // 60)}m {int(avg_duration % 60)}s"
            main_metrics["taxa_rejeicao"] = f"{float(row.metric_values[5].value) * 100:.1f}%"
            main_metrics["taxa_engajamento"] = f"{float(row.metric_values[6].value) * 100:.1f}%"
            main_metrics["vistas_por_usuario"] = f"{float(row.metric_values[7].value):.2f}"
            total_eventos = int(row.metric_values[8].value)

        # Canais
        res_traffic = _run_ga4(
            ga4_client, property_id, ["sessionDefaultChannelGroup"], ["activeUsers"]
        )
        traffic_data = {}
        if res_traffic:
            traffic_data = {
                row.dimension_values[0].value: int(row.metric_values[0].value)
                for row in res_traffic.rows
            }

        # Canais por dia (90 dias — filtro na aba individual do site)
        res_channels_daily = _run_ga4(
            ga4_client, property_id,
            ["date", "sessionDefaultChannelGroup"],
            ["activeUsers"],
            date_ranges=GA4_HISTORICO_DATE_RANGE,
        )
        canais_diario = []
        if res_channels_daily:
            for row in res_channels_daily.rows:
                date_raw = row.dimension_values[0].value
                canal = row.dimension_values[1].value
                usuarios = int(row.metric_values[0].value)
                try:
                    dt = datetime.strptime(date_raw, "%Y%m%d")
                    date_iso = dt.strftime("%Y-%m-%d")
                except ValueError:
                    date_iso = date_raw
                canais_diario.append({"date": date_iso, "canal": canal, "usuarios": usuarios})

        # Páginas
        res_pages = _run_ga4(
            ga4_client, property_id,
            ["pageTitle", "pagePath"], ["screenPageViews"],
            limit=10, order_metric="screenPageViews",
        )
        pages_data = []
        if res_pages:
            pages_data = [
                {
                    "titulo": row.dimension_values[0].value,
                    "url": row.dimension_values[1].value,
                    "vistas": int(row.metric_values[0].value),
                }
                for row in res_pages.rows
            ]

        # Páginas por dia (90 dias — filtro na Visão Geral e aba Site)
        paginas_diario = []
        try:
            res_pages_daily = _run_ga4(
                ga4_client, property_id,
                ["date", "pageTitle", "pagePath"],
                ["screenPageViews"],
                limit=25000,
                order_metric="screenPageViews",
                date_ranges=GA4_HISTORICO_DATE_RANGE,
            )
            if res_pages_daily:
                for row in res_pages_daily.rows:
                    date_raw = row.dimension_values[0].value
                    try:
                        dt = datetime.strptime(date_raw, "%Y%m%d")
                        date_iso = dt.strftime("%Y-%m-%d")
                    except ValueError:
                        date_iso = date_raw
                    paginas_diario.append({
                        "date": date_iso,
                        "titulo": row.dimension_values[1].value,
                        "url": row.dimension_values[2].value,
                        "vistas": int(row.metric_values[0].value),
                    })
        except Exception as exc:
            print(f"  [AVISO] paginas_diario ({profile.get('nome', 'site')}): {exc}")
            cached = _load_site_cache(profile.get("id"))
            if cached and cached.get("paginas_diario"):
                paginas_diario = cached["paginas_diario"]

        # Dispositivos
        res_devices = _run_ga4(
            ga4_client, property_id, ["deviceCategory"], ["activeUsers", "sessions"]
        )
        devices_data = {}
        device_label_map = {"desktop": "Desktop", "mobile": "Mobile", "tablet": "Tablet"}
        if res_devices:
            for row in res_devices.rows:
                raw_cat = row.dimension_values[0].value.lower()
                label = device_label_map.get(raw_cat, raw_cat.capitalize())
                devices_data[label] = int(row.metric_values[0].value)

        # Histórico diário (90 dias para filtros por mês no PDF)
        res_hist = _run_ga4(
            ga4_client, property_id, ["date"],
            [
                "activeUsers", "screenPageViews", "sessions", "newUsers",
                "bounceRate", "engagementRate", "averageSessionDuration",
            ],
            order_metric=None,
            date_ranges=GA4_HISTORICO_DATE_RANGE,
        )
        labels, dates_iso, users, views, sessions_hist = [], [], [], [], []
        novos_usuarios_hist, bounce_hist, engagement_hist, duration_hist = [], [], [], []
        if res_hist:
            sorted_rows = sorted(res_hist.rows, key=lambda r: r.dimension_values[0].value)
            for row in sorted_rows:
                dt = datetime.strptime(row.dimension_values[0].value, "%Y%m%d")
                labels.append(dt.strftime("%d/%m/%Y"))
                dates_iso.append(dt.strftime("%Y-%m-%d"))
                users.append(int(row.metric_values[0].value))
                views.append(int(row.metric_values[1].value))
                sessions_hist.append(int(row.metric_values[2].value))
                novos_usuarios_hist.append(int(row.metric_values[3].value))
                bounce_hist.append(round(float(row.metric_values[4].value) * 100, 1))
                engagement_hist.append(round(float(row.metric_values[5].value) * 100, 1))
                duration_hist.append(float(row.metric_values[6].value))

        # Atividade por hora
        res_hour = _run_ga4(ga4_client, property_id, ["hour"], ["activeUsers"])
        hora_labels, hora_users = [], []
        if res_hour:
            hour_data = {int(r.dimension_values[0].value): int(r.metric_values[0].value) for r in res_hour.rows}
            for h in range(24):
                hora_labels.append(f"{h:02d}h")
                hora_users.append(hour_data.get(h, 0))

        # Atividade por dia da semana
        res_dow = _run_ga4(ga4_client, property_id, ["dayOfWeek"], ["activeUsers"])
        dow_labels, dow_users = [], []
        if res_dow:
            dow_data = {int(r.dimension_values[0].value): int(r.metric_values[0].value) for r in res_dow.rows}
            for i, nome in enumerate(DIAS_SEMANA):
                dow_labels.append(nome)
                dow_users.append(dow_data.get(i, 0))

        # Engajamento diário
        res_eng = _run_ga4(ga4_client, property_id, ["date"], ["engagementRate"])
        eng_labels, eng_dates_iso, eng_taxa = [], [], []
        if res_eng:
            sorted_eng = sorted(res_eng.rows, key=lambda r: r.dimension_values[0].value)
            for row in sorted_eng:
                dt = datetime.strptime(row.dimension_values[0].value, "%Y%m%d")
                eng_labels.append(dt.strftime("%d/%m/%Y"))
                eng_dates_iso.append(dt.strftime("%Y-%m-%d"))
                eng_taxa.append(round(float(row.metric_values[0].value) * 100, 1))

        atividade = {
            "sessoes": main_metrics["sessoes"],
            "visualizacoes": main_metrics["visualizacoes"],
            "eventos": total_eventos,
            "por_hora": {"labels": hora_labels, "usuarios": hora_users},
            "por_dia_semana": {"labels": dow_labels, "usuarios": dow_users},
            "engajamento_diario": {"labels": eng_labels, "dates_iso": eng_dates_iso, "taxa": eng_taxa},
        }

        # Localidades — estados (Brasil)
        res_region = _run_ga4(
            ga4_client, property_id,
            ["country", "region"], ["activeUsers", "sessions"],
            limit=50, order_metric="activeUsers",
        )
        estados_trafego = []
        paises = []
        if res_region:
            pais_counter = {}
            for row in res_region.rows:
                pais = row.dimension_values[0].value
                regiao = row.dimension_values[1].value
                usuarios = int(row.metric_values[0].value)
                sessoes = int(row.metric_values[1].value)
                pais_counter[pais] = pais_counter.get(pais, 0) + usuarios
                if pais in ("Brazil", "Brasil"):
                    estados_trafego.append({
                        "estado": normalize_estado(regiao),
                        "usuarios": usuarios,
                        "sessoes": sessoes,
                    })
            paises = [
                {"pais": k, "usuarios": v}
                for k, v in sorted(pais_counter.items(), key=lambda x: x[1], reverse=True)
            ]

        # Cidades
        res_cities = _run_ga4(
            ga4_client, property_id,
            ["city", "region"], ["activeUsers"],
            limit=20, order_metric="activeUsers",
        )
        cidades = []
        if res_cities:
            for row in res_cities.rows:
                cidades.append({
                    "cidade": row.dimension_values[0].value,
                    "estado": normalize_estado(row.dimension_values[1].value),
                    "usuarios": int(row.metric_values[0].value),
                })

        localidades = {
            "estados": sorted(estados_trafego, key=lambda x: x["usuarios"], reverse=True),
            "cidades": cidades,
            "paises": paises[:15],
        }

        estados_rep_data = _build_trafego_regional(estados_trafego) if include_rep else None

        # Search Console (com fallback GA4 orgânico se sem permissão)
        gsc = _get_gsc_client(oauth_creds, search_console)
        resolved_gsc_url = _resolve_gsc_site_url(gsc, gsc_site_url)
        gsc_rows = _query_gsc(gsc, resolved_gsc_url, dimensions=None, row_limit=1, days=GSC_SUMMARY_DAYS)
        google_search = _parse_gsc_summary(gsc_rows)
        google_search["fonte"] = "search_console"
        seo_ranking = _build_seo_ranking(gsc, resolved_gsc_url)
        gsc_diario = _fetch_gsc_diario(gsc, resolved_gsc_url) if gsc else []
        seo_fonte = "search_console"
        gsc_status = "ok"

        if not _gsc_has_data(gsc_rows, seo_ranking):
            gsc_status = "sem_permissao"
            google_search_fb, seo_ranking_fb = _build_seo_ga4_organic_fallback(
                ga4_client, property_id, profile.get("url", "")
            )
            cliques_fb = int(str(google_search_fb.get("cliques", 0)).replace("—", "0") or 0)
            if cliques_fb > 0 or seo_ranking_fb.get("top_pages"):
                google_search = google_search_fb
                seo_ranking = seo_ranking_fb
                seo_fonte = "ga4_organico"
                print(
                    f"  [AVISO] Search Console sem acesso para {profile.get('nome', 'site')} "
                    f"({resolved_gsc_url}) — SEO via tráfego orgânico GA4"
                )
            else:
                print(
                    f"  [AVISO] Search Console sem dados para {profile.get('nome', 'site')} "
                    f"({resolved_gsc_url})"
                )
        elif gsc:
            print(
                f"  [OK] Search Console ({profile.get('nome', 'site')}): "
                f"{google_search['cliques']} cliques, {len(seo_ranking['top_queries'])} queries"
            )

        result = {
            "nome": profile.get("nome", "Site"),
            "id": profile.get("id", "site"),
            "url": profile.get("url", ""),
            "ga4_property": ga4_property_path(property_id),
            "status_integracao": "ok",
            "metricas_principais": main_metrics,
            "origem_trafego": traffic_data,
            "canais_diario": canais_diario,
            "paginas_mais_visitadas": pages_data,
            "paginas_diario": paginas_diario,
            "dispositivos": devices_data,
            "historico_7d": {
                "labels": labels,
                "dates_iso": dates_iso,
                "usuarios": users,
                "vistas": views,
                "sessoes": sessions_hist,
                "novos_usuarios": novos_usuarios_hist,
                "taxa_rejeicao": bounce_hist,
                "taxa_engajamento": engagement_hist,
                "duracao_sessao": duration_hist,
            },
            "google_search": google_search,
            "gsc_diario": gsc_diario,
            "seo_fonte": seo_fonte,
            "gsc_status": gsc_status,
            "atividade": atividade,
            "seo_ranking": seo_ranking,
            "localidades": localidades,
        }
        if include_rep and estados_rep_data:
            result["estados_sem_representacao"] = estados_rep_data
        _save_site_cache(profile.get("id"), result)
        return result

    except Exception as exc:
        print(f"Erro GA4 Site Dashboard ({profile.get('nome', 'site')}): {exc}")
        import traceback
        traceback.print_exc()
        cached = _load_site_cache(profile.get("id"))
        if cached:
            cached = dict(cached)
            cached["status_integracao"] = (
                f"Dados em cache ({cached.get('cached_at', 'anterior')}) — "
                f"GA4 indisponível no momento"
            )
            print(
                f"  [OK] Site {profile.get('nome', 'site')}: "
                f"usando cache ({cached.get('metricas_principais', {}).get('usuarios_ativos', 0)} usuários)"
            )
            return cached
        return empty_site_payload("Erro GA4", profile)


def load_sites_dashboard(
    ga4_client,
    property_id,
    oauth_creds=None,
    search_console=None,
    profile=None,
):
    """Carrega dados do site principal (GA4 + Search Console)."""
    return load_site_dashboard(
        ga4_client,
        property_id,
        profile or DEFAULT_PRIMARY_SITE_PROFILE,
        oauth_creds=oauth_creds,
        search_console=search_console,
    )
