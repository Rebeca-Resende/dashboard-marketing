"""
Métricas de insights da Página Facebook (Meta Graph API).
"""
from datetime import datetime, timedelta


def _metric_value(val):
    if isinstance(val, dict):
        return int(sum(v for v in val.values() if isinstance(v, (int, float))))
    try:
        return int(val or 0)
    except (TypeError, ValueError):
        return 0


def _parse_series(entry):
    series = []
    total = 0
    if not entry:
        return 0, series
    for item in entry.get("values", []):
        num = _metric_value(item.get("value", 0))
        total += num
        end_time = item.get("end_time", "")
        try:
            dt = datetime.strptime(end_time[:10], "%Y-%m-%d")
            label = dt.strftime("%d/%m")
        except ValueError:
            label = end_time[:10] if end_time else ""
        series.append({"label": label, "value": num, "date_iso": end_time[:10] if end_time else ""})
    return total, series


def _align_series(current, previous):
    labels = [p["label"] for p in current]
    dates_iso = [p.get("date_iso", "") for p in current]
    atual = [p["value"] for p in current]
    anterior = [p["value"] for p in previous]
    while len(anterior) < len(atual):
        anterior.insert(0, 0)
    if len(anterior) > len(atual):
        anterior = anterior[-len(atual):]
    return {"labels": labels, "dates_iso": dates_iso, "atual": atual, "anterior": anterior}


def _format_duration_ms(total_ms):
    if total_ms <= 0:
        return "0s"
    total_sec = int(total_ms / 1000)
    if total_sec < 60:
        return f"{total_sec}s"
    return f"{total_sec // 60}m {total_sec % 60}s"


def empty_facebook_insights():
    return {
        "visualizacoes": 0,
        "interacoes_insights": 0,
        "cliques": 0,
        "visitas": 0,
        "seguidores_periodo": 0,
        "visualizadores": 0,
        "videos_reels": 0,
        "tempo_visualizacao": "0s",
        "tempo_visualizacao_ms": 0,
        "visitas_historico": {"labels": [], "dates_iso": [], "atual": [], "anterior": []},
        "seguidores_historico": {"labels": [], "dates_iso": [], "atual": [], "anterior": []},
        "visualizadores_historico": {"labels": [], "dates_iso": [], "atual": [], "anterior": []},
        "alcance": 0,
    }


def fetch_facebook_insights(page_id, access_token, days=90):
    import requests

    if not page_id or not access_token:
        return empty_facebook_insights()

    since_dt = datetime.now() - timedelta(days=days)
    since = int(since_dt.timestamp())
    until = int(datetime.now().timestamp())
    prev_since = int((since_dt - timedelta(days=days)).timestamp())
    prev_until = since

    base_url = f"https://graph.facebook.com/v18.0/{page_id}/insights"

    def _query(metric_list, p_since, p_until):
        params = {
            "metric": metric_list,
            "period": "day",
            "since": p_since,
            "until": p_until,
            "access_token": access_token,
        }
        try:
            resp = requests.get(base_url, params=params, timeout=20).json()
            if "error" in resp:
                print(f"  [Facebook Insights] {resp['error'].get('message', resp['error'])}")
                return []
            return resp.get("data", [])
        except Exception as exc:
            print(f"  [Facebook Insights] Erro: {exc}")
            return []

    current = _query(
        "page_media_view,page_posts_impressions_organic,page_post_engagements,"
        "page_views_total,page_total_actions,page_video_complete_views_30s,"
        "page_video_view_time,page_daily_follows",
        since, until,
    )
    prev_visitas = _query("page_views_total", prev_since, prev_until)
    prev_follows = _query("page_daily_follows", prev_since, prev_until)
    prev_visualizadores = _query("page_posts_impressions_organic", prev_since, prev_until)

    by_name = {item.get("name"): item for item in current if item.get("name")}

    visualizacoes, _ = _parse_series(by_name.get("page_media_view"))
    visualizadores, visualizadores_series = _parse_series(by_name.get("page_posts_impressions_organic"))
    interacoes_insights, _ = _parse_series(by_name.get("page_post_engagements"))
    visitas, visitas_series = _parse_series(by_name.get("page_views_total"))
    cliques, _ = _parse_series(by_name.get("page_total_actions"))
    videos_reels, _ = _parse_series(by_name.get("page_video_complete_views_30s"))
    tempo_ms, _ = _parse_series(by_name.get("page_video_view_time"))
    seguidores_periodo, seguidores_series = _parse_series(by_name.get("page_daily_follows"))

    prev_entry = prev_visitas[0] if prev_visitas else None
    _, prev_visitas_series = _parse_series(prev_entry)
    visitas_hist = _align_series(visitas_series, prev_visitas_series)

    prev_follows_entry = prev_follows[0] if prev_follows else None
    _, prev_seguidores_series = _parse_series(prev_follows_entry)
    seguidores_hist = _align_series(seguidores_series, prev_seguidores_series)

    prev_visualizadores_entry = prev_visualizadores[0] if prev_visualizadores else None
    _, prev_visualizadores_series = _parse_series(prev_visualizadores_entry)
    visualizadores_hist = _align_series(visualizadores_series, prev_visualizadores_series)

    result = {
        "visualizacoes": visualizacoes,
        "interacoes_insights": interacoes_insights,
        "cliques": cliques,
        "visitas": visitas,
        "seguidores_periodo": seguidores_periodo,
        "visualizadores": visualizadores,
        "videos_reels": videos_reels,
        "tempo_visualizacao": _format_duration_ms(tempo_ms),
        "tempo_visualizacao_ms": tempo_ms,
        "visitas_historico": visitas_hist,
        "seguidores_historico": seguidores_hist,
        "visualizadores_historico": visualizadores_hist,
        "alcance": visualizadores,
    }
    if visualizacoes or visualizadores or visitas:
        print(
            f"  [OK] Facebook Insights: {visualizacoes} visualizações, "
            f"{visualizadores} visualizadores, {visitas} visitas, {seguidores_periodo} novos seguidores"
        )
    return result
