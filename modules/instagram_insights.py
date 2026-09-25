"""
Métricas de insights do Instagram (Meta Graph API).
"""
from datetime import datetime, timedelta

# A Graph API do Instagram rejeita intervalos maiores que 30 dias entre since/until.
MAX_INSIGHT_RANGE_DAYS = 30


def _time_chunks(since_dt, until_dt, max_days=MAX_INSIGHT_RANGE_DAYS):
    chunks = []
    start = since_dt
    while start < until_dt:
        end = min(start + timedelta(days=max_days), until_dt)
        chunks.append((int(start.timestamp()), int(end.timestamp())))
        start = end
    return chunks or [(int(since_dt.timestamp()), int(until_dt.timestamp()))]


def _merge_total_value_entries(entries):
    if not entries:
        return None
    merged = dict(entries[-1])
    merged["total_value"] = {"value": sum(_total_value(entry) for entry in entries)}
    return merged


def _merge_series_entries(entries):
    if not entries:
        return None
    values_by_date = {}
    for entry in entries:
        for item in entry.get("values", []):
            key = item.get("end_time", "")
            if key:
                values_by_date[key] = item
    merged = dict(entries[-1])
    merged["values"] = [values_by_date[key] for key in sorted(values_by_date)]
    return merged


def _merge_breakdown_entries(entries):
    if not entries:
        return None
    totals = {}
    for entry in entries:
        tv = entry.get("total_value", {})
        for block in tv.get("breakdowns", []):
            for result in block.get("results", []):
                dims = tuple(result.get("dimension_values", []))
                totals[dims] = totals.get(dims, 0) + int(result.get("value", 0) or 0)
    if not totals:
        return entries[-1]
    merged = dict(entries[-1])
    merged.setdefault("total_value", {})["breakdowns"] = [{
        "results": [
            {"dimension_values": list(dims), "value": value}
            for dims, value in totals.items()
        ]
    }]
    return merged


def _total_value(entry):
    """Extrai valor agregado (metric_type=total_value)."""
    if not entry:
        return 0
    tv = entry.get("total_value", {})
    val = tv.get("value", 0)
    if isinstance(val, dict):
        return int(sum(v for v in val.values() if isinstance(v, (int, float))))
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _parse_time_series(entry):
    """Extrai série diária de uma métrica."""
    series = []
    if not entry:
        return 0, series
    total = 0
    for item in entry.get("values", []):
        val = item.get("value", 0)
        if isinstance(val, dict):
            val = sum(v for v in val.values() if isinstance(v, (int, float)))
        try:
            num = int(val)
        except (TypeError, ValueError):
            num = 0
        total += num
        end_time = item.get("end_time", "")
        try:
            dt = datetime.strptime(end_time[:10], "%Y-%m-%d")
            label = dt.strftime("%d/%m")
        except ValueError:
            label = end_time[:10] if end_time else ""
        series.append({"label": label, "value": num, "date_iso": end_time[:10] if end_time else ""})
    return total, series


def _follows_from_breakdown(entry):
    """Extrai novos seguidores (FOLLOWER) de follows_and_unfollows."""
    if not entry:
        return 0
    tv = entry.get("total_value", {})
    for block in tv.get("breakdowns", []):
        for result in block.get("results", []):
            dims = result.get("dimension_values", [])
            if dims and dims[0] == "FOLLOWER":
                try:
                    return int(result.get("value", 0))
                except (TypeError, ValueError):
                    return 0
    return 0


def _bucket_daily_to_labels(daily_series, labels):
    """Distribui série diária nos mesmos rótulos do gráfico de visitas."""
    if not labels:
        return [], []
    if not daily_series:
        return labels, [0] * len(labels)
    chunk = max(1, len(daily_series) // len(labels))
    atual = []
    for i in range(len(labels)):
        block = daily_series[i * chunk:] if i == len(labels) - 1 else daily_series[i * chunk:(i + 1) * chunk]
        atual.append(sum(p["value"] for p in block))
    return labels, atual


def _align_series(current, previous):
    labels = [p["label"] for p in current]
    atual = [p["value"] for p in current]
    anterior = [p["value"] for p in previous]
    while len(anterior) < len(atual):
        anterior.insert(0, 0)
    if len(anterior) > len(atual):
        anterior = anterior[-len(atual):]
    return {"labels": labels, "atual": atual, "anterior": anterior}


def _weekly_profile_views(base_url, access_token, days=30, chunk_days=7):
    """Monta série semanal de visitas ao perfil (API só retorna total_value)."""
    series = []
    end_dt = datetime.now()
    chunks = max(1, days // chunk_days)
    for i in range(chunks):
        chunk_end = end_dt - timedelta(days=i * chunk_days)
        chunk_start = chunk_end - timedelta(days=chunk_days)
        params = {
            "metric": "profile_views",
            "period": "day",
            "metric_type": "total_value",
            "since": int(chunk_start.timestamp()),
            "until": int(chunk_end.timestamp()),
            "access_token": access_token,
        }
        try:
            import requests
            resp = requests.get(base_url, params=params, timeout=15).json()
            if "error" in resp:
                continue
            data = resp.get("data", [])
            val = _total_value(data[0]) if data else 0
            series.insert(0, {
                "label": chunk_end.strftime("%d/%m"),
                "value": val,
                "date_iso": chunk_end.strftime("%Y-%m-%d"),
                "date_start_iso": chunk_start.strftime("%Y-%m-%d"),
            })
        except Exception:
            continue
    total = sum(p["value"] for p in series)
    return total, series


def empty_instagram_insights():
    return {
        "visualizacoes": 0,
        "alcance": 0,
        "visitas": 0,
        "cliques": 0,
        "cliques_disponivel": False,
        "seguidores_periodo": 0,
        "visitas_historico": {"labels": [], "dates_iso": [], "atual": [], "anterior": []},
        "seguidores_historico": {"labels": [], "dates_iso": [], "atual": [], "anterior": []},
        "alcance_historico": {"labels": [], "dates_iso": [], "atual": []},
        "interacoes_insights": 0,
    }


def fetch_instagram_insights(instagram_id, access_token, days=30):
    import requests

    if not instagram_id or not access_token:
        return empty_instagram_insights()

    until_dt = datetime.now()
    since_dt = until_dt - timedelta(days=days)
    prev_until_dt = since_dt
    prev_since_dt = prev_until_dt - timedelta(days=days)

    base_url = f"https://graph.facebook.com/v18.0/{instagram_id}/insights"

    def _query(metric_list, p_since, p_until, extra=None):
        params = {
            "metric": metric_list,
            "period": "day",
            "since": p_since,
            "until": p_until,
            "access_token": access_token,
        }
        if extra:
            params.update(extra)
        try:
            resp = requests.get(base_url, params=params, timeout=20).json()
            if "error" in resp:
                print(f"  [Instagram Insights] {resp['error'].get('message', resp['error'])}")
                return []
            return resp.get("data", [])
        except Exception as exc:
            print(f"  [Instagram Insights] Erro: {exc}")
            return []

    def _query_range(metric_list, start_dt, end_dt, extra=None):
        grouped = {}
        for p_since, p_until in _time_chunks(start_dt, end_dt):
            for item in _query(metric_list, p_since, p_until, extra):
                name = item.get("name")
                if name:
                    grouped.setdefault(name, []).append(item)

        merged = []
        use_total_merge = extra and extra.get("metric_type") == "total_value"
        use_breakdown_merge = extra and extra.get("breakdown")
        for name, items in grouped.items():
            if use_breakdown_merge:
                entry = _merge_breakdown_entries(items)
            elif use_total_merge:
                entry = _merge_total_value_entries(items)
            else:
                entry = _merge_series_entries(items)
            if entry:
                entry["name"] = name
                merged.append(entry)
        return merged

    totals_data = _query_range(
        "views,profile_views,total_interactions,website_clicks",
        since_dt, until_dt,
        extra={"metric_type": "total_value"},
    )
    prev_totals = _query_range(
        "profile_views",
        prev_since_dt, prev_until_dt,
        extra={"metric_type": "total_value"},
    )
    prev_follows_data = _query_range(
        "follows_and_unfollows",
        prev_since_dt, prev_until_dt,
        extra={"metric_type": "total_value", "breakdown": "follow_type"},
    )
    series_data = _query_range("reach,follower_count", since_dt, until_dt)

    totals_by = {item.get("name"): item for item in totals_data if item.get("name")}
    series_by = {item.get("name"): item for item in series_data if item.get("name")}

    visualizacoes = _total_value(totals_by.get("views"))
    visitas = _total_value(totals_by.get("profile_views"))
    cliques = _total_value(totals_by.get("website_clicks"))
    interacoes_api = _total_value(totals_by.get("total_interactions"))

    alcance, reach_series = _parse_time_series(series_by.get("reach"))
    seguidores_periodo, follower_daily = _parse_time_series(series_by.get("follower_count"))

    _, visitas_weekly = _weekly_profile_views(base_url, access_token, days=min(days, 30))
    prev_visitas_total = _total_value(prev_totals[0] if prev_totals else None)
    prev_seguidores_total = _follows_from_breakdown(
        prev_follows_data[0] if prev_follows_data else None
    )

    visitas_labels = [p["label"] for p in visitas_weekly]
    visitas_dates_iso = [p.get("date_iso", "") for p in visitas_weekly]
    visitas_date_start_iso = [p.get("date_start_iso", "") for p in visitas_weekly]
    visitas_atual = [p["value"] for p in visitas_weekly]
    visitas_anterior = []

    if visitas_labels:
        prev_per_week = max(0, prev_visitas_total // max(1, len(visitas_labels)))
        visitas_anterior = [prev_per_week] * len(visitas_labels)
    elif reach_series:
        prev_reach_data = _query_range("reach", prev_since_dt, prev_until_dt)
        prev_entry = prev_reach_data[0] if prev_reach_data else None
        _, prev_reach = _parse_time_series(prev_entry)
        aligned = _align_series(reach_series, prev_reach)
        visitas_labels = aligned["labels"]
        visitas_atual = aligned["atual"]
        visitas_anterior = aligned["anterior"]

    seguidores_labels, seguidores_atual = _bucket_daily_to_labels(follower_daily, visitas_labels)

    seguidores_anterior = []
    if seguidores_labels:
        prev_seg_per_week = max(0, prev_seguidores_total // max(1, len(seguidores_labels)))
        seguidores_anterior = [prev_seg_per_week] * len(seguidores_labels)

    alcance_labels = [p["label"] for p in reach_series]
    alcance_dates_iso = [p.get("date_iso", "") for p in reach_series]
    alcance_atual = [p["value"] for p in reach_series]

    result = {
        "visualizacoes": visualizacoes,
        "alcance": alcance,
        "visitas": visitas,
        "cliques": cliques,
        "cliques_disponivel": False,  # oculto até volume mínimo; valor mantido em cliques
        "seguidores_periodo": seguidores_periodo,
        "visitas_historico": {
            "labels": visitas_labels,
            "dates_iso": visitas_dates_iso,
            "date_start_iso": visitas_date_start_iso,
            "atual": visitas_atual,
            "anterior": visitas_anterior,
        },
        "seguidores_historico": {
            "labels": seguidores_labels,
            "dates_iso": visitas_dates_iso,
            "date_start_iso": visitas_date_start_iso,
            "atual": seguidores_atual,
            "anterior": seguidores_anterior,
        },
        "alcance_historico": {
            "labels": alcance_labels,
            "dates_iso": alcance_dates_iso,
            "atual": alcance_atual,
        },
        "interacoes_insights": interacoes_api,
    }
    if visualizacoes or alcance or visitas:
        print(
            f"  [OK] Instagram Insights: {visualizacoes} views, "
            f"{alcance} alcance, {visitas} visitas, {seguidores_periodo} novos seguidores"
        )
    return result
