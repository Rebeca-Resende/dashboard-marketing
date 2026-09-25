"""
Métricas de YouTube Analytics (canal) — últimos 30 dias.
"""
import json
import os
from datetime import datetime, timedelta


def empty_rankings():
    return {
        "videos_mais_acessados": [],
        "trafego_geral": [],
        "trafego_externo": [],
    }


def empty_audiencia():
    return {
        "novos_espectadores": 0,
        "espectadores_recorrentes": 0,
        "espectadores_unicos": 0,
        "inscritos": "+0",
        "inscritos_valor": 0,
    }


def empty_grafico_tempo_inscritos():
    return {
        "labels": ["Inscritos", "Não inscritos"],
        "horas": [0, 0],
        "inscritos_horas": "0h",
        "nao_inscritos_horas": "0h",
        "disponivel": False,
    }


def empty_trafego_organico_pago():
    return {
        "organico_pct": "—",
        "pago_pct": "—",
        "organico_views": 0,
        "pago_views": 0,
        "disponivel": False,
    }


def empty_interacoes_videos():
    return {
        "curtidas": 0,
        "comentarios": 0,
        "compartilhamentos": 0,
        "fonte": "indisponivel",
    }


def empty_demografia():
    return {
        "idade": [],
        "genero": [],
        "disponivel": False,
    }


def empty_localizacao():
    return {
        "paises": [],
        "estados_br": [],
        "max_pct": 0,
        "disponivel": False,
    }


def empty_youtube_insights():
    return {
        "visualizacoes_canal": 0,
        "impressoes": 0,
        "taxa_cliques_impressoes": "0%",
        "duracao_media_visualizacao": "0m 0s",
        "tempo_exibicao_horas": "0h",
        "patrocinado_disponivel": False,
        "patrocinado": {
            "visualizacoes": 0,
            "impressoes": 0,
            "taxa_cliques_impressoes": "0%",
            "duracao_media_visualizacao": "0m 0s",
            "tempo_exibicao_horas": "0h",
        },
        "audiencia": empty_audiencia(),
        "rankings": empty_rankings(),
        "grafico_tempo_inscritos": empty_grafico_tempo_inscritos(),
        "trafego_organico_pago": empty_trafego_organico_pago(),
        "interacoes_videos": empty_interacoes_videos(),
        "demografia": empty_demografia(),
        "localizacao": empty_localizacao(),
        "analytics_fonte": "indisponivel",
    }


def _parse_post_date(valor):
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor
    texto = str(valor).strip()
    try:
        return datetime.strptime(texto[:10], "%d/%m/%Y")
    except ValueError:
        return None


def _filtrar_videos_periodo(videos, dias=30):
    limite = datetime.now() - timedelta(days=dias)
    filtrados = []
    for video in videos or []:
        dt = _parse_post_date(video.get("data_publicacao"))
        if dt and dt >= limite:
            filtrados.append(video)
    return filtrados


def _somar_interacoes_videos(videos, dias=30):
    recentes = _filtrar_videos_periodo(videos, dias=dias)
    alvo = recentes if recentes else (videos or [])
    curtidas = 0
    comentarios = 0
    for video in alvo:
        curt = int(video.get("curtidas", 0) or 0)
        comm = int(video.get("comentarios", 0) or 0)
        interacao = int(video.get("interacao", 0) or 0)
        if curt == 0 and comm == 0 and interacao > 0:
            curt = interacao
        curtidas += curt
        comentarios += comm
    return curtidas, comentarios


def _consultar_interacoes_oauth(yt_analytics, channel_id, days=30):
    if not yt_analytics or not channel_id:
        return None

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        resp = yt_analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics="likes,comments,shares",
        ).execute()
    except Exception as exc:
        print(f"  [YouTube Analytics] Interações (curtidas/comentários/compartilhamentos): {exc}")
        return None

    metricas = _extrair_metricas_resposta(
        resp.get("rows", []),
        resp.get("columnHeaders", []),
    )
    if not resp.get("rows"):
        return None

    curtidas = int(float(metricas.get("likes", 0) or 0))
    comentarios = int(float(metricas.get("comments", 0) or 0))
    compartilhamentos = int(float(metricas.get("shares", 0) or 0))
    return {
        "curtidas": curtidas,
        "comentarios": comentarios,
        "compartilhamentos": compartilhamentos,
        "fonte": "oauth",
    }


def _montar_interacoes_videos(yt_analytics_client, channel_id, videos=None, days=30):
    oauth_data = _consultar_interacoes_oauth(yt_analytics_client, channel_id, days=days)
    if oauth_data:
        return oauth_data

    curtidas, comentarios = _somar_interacoes_videos(videos, dias=days)
    return {
        "curtidas": curtidas,
        "comentarios": comentarios,
        "compartilhamentos": 0,
        "fonte": "api_key" if (curtidas or comentarios) else "indisponivel",
    }


def _formatar_duracao_segundos(segundos):
    try:
        total = int(float(segundos or 0))
    except (TypeError, ValueError):
        total = 0
    if total <= 0:
        return "0m 0s"
    minutos = total // 60
    secs = total % 60
    if minutos >= 60:
        horas = minutos // 60
        minutos = minutos % 60
        return f"{horas}h {minutos}m {secs}s"
    return f"{minutos}m {secs}s"


def _formatar_horas(minutos):
    try:
        total_min = float(minutos or 0)
    except (TypeError, ValueError):
        total_min = 0
    horas = total_min / 60
    if horas < 1:
        return f"{int(total_min)}min"
    if horas < 10:
        return f"{horas:.1f}h"
    return f"{int(round(horas))}h"


def _formatar_pct(valor):
    try:
        pct = float(valor or 0)
    except (TypeError, ValueError):
        pct = 0
    if pct <= 1:
        pct *= 100
    return f"{pct:.2f}%"


_TRAFEGO_GERAL_LABELS = {
    "RELATED_VIDEO": "Vídeos sugeridos",
    "YT_SEARCH": "Pesquisa do YouTube",
    "NO_LINK_OTHER": "Origem direta ou desconhecida",
    "EXT_URL": "Externa",
    "YT_CHANNEL": "Páginas do canal",
    "SUBSCRIBER": "Feed de inscrições",
    "NOTIFICATION": "Notificações",
    "PLAYLIST": "Playlists",
    "END_SCREEN": "Telas finais",
    "SHORTS": "Shorts",
    "YT_OTHER_PAGE": "Outras páginas do YouTube",
    "NO_LINK_EMBEDDED": "Incorporado em sites",
    "ADVERTISING": "Publicidade",
    "ANNOTATION": "Anotações",
    "HASHTAGS": "Hashtags",
    "LIVE_REDIRECT": "Redirecionamento ao vivo",
    "PROMOTED": "Promoção YouTube",
    "SOUND_PAGE": "Página de sons (Shorts)",
    "VIDEO_REMIXES": "Remixes de vídeo",
    "PRODUCT_PAGE": "Página de produto",
    "CAMPAIGN_CARD": "Card de campanha",
}


_IDADE_LABELS = {
    "age13-17": "13–17 anos",
    "age18-24": "18–24 anos",
    "age25-34": "25–34 anos",
    "age35-44": "35–44 anos",
    "age45-54": "45–54 anos",
    "age55-64": "55–64 anos",
    "age65-": "65+ anos",
}

_IDADE_ORDEM = [
    "age13-17",
    "age18-24",
    "age25-34",
    "age35-44",
    "age45-54",
    "age55-64",
    "age65-",
]

_GENERO_LABELS = {
    "female": "Feminino",
    "male": "Masculino",
    "user_specified": "Outro / não especificado",
}

_GENERO_ORDEM = ["female", "male", "user_specified"]


def _normalizar_percentual(valor):
    try:
        pct = float(valor or 0)
    except (TypeError, ValueError):
        pct = 0
    if pct <= 0:
        return 0.0
    if pct <= 1:
        pct *= 100
    return round(pct, 2)


def _parse_demografia_rows(rows, headers, dim_name, labels_map, ordem):
    if dim_name not in headers or "viewerPercentage" not in headers:
        return []

    dim_idx = headers.index(dim_name)
    pct_idx = headers.index("viewerPercentage")
    itens = []
    for row in rows:
        codigo = str(row[dim_idx] or "")
        valor = _normalizar_percentual(row[pct_idx])
        if valor <= 0:
            continue
        itens.append({
            "codigo": codigo,
            "label": labels_map.get(codigo, codigo.replace("_", " ").title()),
            "percentual": _formatar_pct(valor),
            "valor": valor,
        })

    ordem_map = {codigo: idx for idx, codigo in enumerate(ordem)}
    itens.sort(key=lambda item: ordem_map.get(item["codigo"], 999))
    return itens


def _consultar_demografia_dimensao(yt_analytics, channel_id, dimension, days=30):
    if not yt_analytics or not channel_id:
        return []

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        resp = yt_analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            dimensions=dimension,
            metrics="viewerPercentage",
            sort="-viewerPercentage",
            maxResults=25,
        ).execute()
    except Exception as exc:
        label = "Idade" if dimension == "ageGroup" else "Gênero"
        print(f"  [YouTube Analytics] Demografia ({label}): {exc}")
        return []

    headers = [h.get("name") for h in resp.get("columnHeaders", [])]
    rows = resp.get("rows", [])
    if dimension == "ageGroup":
        return _parse_demografia_rows(rows, headers, "ageGroup", _IDADE_LABELS, _IDADE_ORDEM)
    return _parse_demografia_rows(rows, headers, "gender", _GENERO_LABELS, _GENERO_ORDEM)


def _montar_demografia(yt_analytics_client, channel_id, days=30):
    idade = _consultar_demografia_dimensao(
        yt_analytics_client, channel_id, "ageGroup", days=days
    )
    genero = _consultar_demografia_dimensao(
        yt_analytics_client, channel_id, "gender", days=days
    )
    return {
        "idade": idade,
        "genero": genero,
        "disponivel": bool(idade or genero),
    }


_PAISES_LABELS = {
    "BR": "Brasil",
    "US": "Estados Unidos",
    "PT": "Portugal",
    "AR": "Argentina",
    "MX": "México",
    "CO": "Colômbia",
    "CL": "Chile",
    "PE": "Peru",
    "UY": "Uruguai",
    "PY": "Paraguai",
    "BO": "Bolívia",
    "EC": "Equador",
    "VE": "Venezuela",
    "CA": "Canadá",
    "GB": "Reino Unido",
    "DE": "Alemanha",
    "FR": "França",
    "IT": "Itália",
    "ES": "Espanha",
    "NL": "Países Baixos",
    "BE": "Bélgica",
    "CH": "Suíça",
    "AU": "Austrália",
    "NZ": "Nova Zelândia",
    "JP": "Japão",
    "CN": "China",
    "IN": "Índia",
    "KR": "Coreia do Sul",
    "ZA": "África do Sul",
    "AO": "Angola",
    "MZ": "Moçambique",
    "ID": "Indonésia",
    "PH": "Filipinas",
    "MY": "Malásia",
    "SG": "Singapura",
    "RU": "Rússia",
    "PL": "Polônia",
    "SE": "Suécia",
    "NO": "Noruega",
    "DK": "Dinamarca",
    "FI": "Finlândia",
    "IE": "Irlanda",
    "AT": "Áustria",
    "IL": "Israel",
    "TR": "Turquia",
    "SA": "Arábia Saudita",
    "AE": "Emirados Árabes",
}


def _label_pais(codigo):
    cod = str(codigo or "").upper().strip()
    return _PAISES_LABELS.get(cod, cod)


def _label_provincia(codigo):
    texto = str(codigo or "").strip()
    if not texto:
        return "Desconhecido"
    if texto.upper().startswith("BR-"):
        return texto[3:].replace("_", " ")
    return texto.replace("_", " ")


def _parse_localizacao_rows(rows, headers, dim_name, label_fn):
    if dim_name not in headers or "viewerPercentage" not in headers:
        return []

    dim_idx = headers.index(dim_name)
    pct_idx = headers.index("viewerPercentage")
    itens = []
    for row in rows:
        codigo = str(row[dim_idx] or "")
        valor = _normalizar_percentual(row[pct_idx])
        if valor <= 0:
            continue
        itens.append({
            "codigo": codigo,
            "label": label_fn(codigo),
            "percentual": _formatar_pct(valor),
            "valor": valor,
        })

    itens.sort(key=lambda item: item["valor"], reverse=True)
    return itens


def _consultar_localizacao_oauth(yt_analytics, channel_id, days=30):
    if not yt_analytics or not channel_id:
        return empty_localizacao()

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    base_params = {
        "ids": f"channel=={channel_id}",
        "startDate": start_date,
        "endDate": end_date,
        "metrics": "viewerPercentage",
        "sort": "-viewerPercentage",
        "maxResults": 25,
    }

    paises = []
    try:
        resp_paises = yt_analytics.reports().query(
            **base_params,
            dimensions="country",
        ).execute()
        headers = [h.get("name") for h in resp_paises.get("columnHeaders", [])]
        paises = _parse_localizacao_rows(
            resp_paises.get("rows", []),
            headers,
            "country",
            _label_pais,
        )
    except Exception as exc:
        print(f"  [YouTube Analytics] Localização (países): {exc}")

    estados_br = []
    try:
        resp_estados = yt_analytics.reports().query(
            **base_params,
            dimensions="province",
            filters="country==BR",
        ).execute()
        headers = [h.get("name") for h in resp_estados.get("columnHeaders", [])]
        estados_br = _parse_localizacao_rows(
            resp_estados.get("rows", []),
            headers,
            "province",
            _label_provincia,
        )
    except Exception as exc:
        print(f"  [YouTube Analytics] Localização (estados BR): {exc}")

    max_pct = 0.0
    if paises:
        max_pct = max(max_pct, max(item["valor"] for item in paises))
    if estados_br:
        max_pct = max(max_pct, max(item["valor"] for item in estados_br))

    return {
        "paises": paises,
        "estados_br": estados_br,
        "max_pct": round(max_pct, 2),
        "disponivel": bool(paises or estados_br),
    }


def _montar_localizacao(yt_analytics_client, channel_id, days=30):
    return _consultar_localizacao_oauth(yt_analytics_client, channel_id, days=days)


def _mapa_videos(videos):
    mapa = {}
    for video in videos or []:
        vid = str(video.get("id", ""))
        if vid:
            mapa[vid] = video
    return mapa


def _ranking_percentual(itens, chave_views="views"):
    total = sum(int(item.get(chave_views, 0) or 0) for item in itens)
    if total <= 0:
        return itens
    for item in itens:
        views = int(item.get(chave_views, 0) or 0)
        item["percentual"] = _formatar_pct(views / total)
    return itens


def _ranking_videos_fallback(videos, limit=10):
    ordenados = sorted(
        videos or [],
        key=lambda v: int(v.get("visualizacoes", 0) or 0),
        reverse=True,
    )[:limit]
    ranking = []
    for idx, video in enumerate(ordenados, start=1):
        views = int(video.get("visualizacoes", 0) or 0)
        if views <= 0:
            continue
        ranking.append({
            "rank": idx,
            "titulo": video.get("titulo_descricao", "Sem título"),
            "visualizacoes": views,
            "link": video.get("link_permanente", ""),
        })
    return ranking


def _consultar_videos_top_oauth(yt_analytics, channel_id, videos_map, days=30, limit=10):
    if not yt_analytics or not channel_id:
        return []

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        resp = yt_analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            dimensions="video",
            metrics="views",
            sort="-views",
            maxResults=limit,
        ).execute()
    except Exception as exc:
        print(f"  [YouTube Analytics] Top vídeos: {exc}")
        return []

    headers = [h.get("name") for h in resp.get("columnHeaders", [])]
    rows = resp.get("rows", [])
    if "video" not in headers or "views" not in headers:
        return []

    vid_idx = headers.index("video")
    views_idx = headers.index("views")
    ranking = []
    for idx, row in enumerate(rows[:limit], start=1):
        video_id = str(row[vid_idx])
        views = int(float(row[views_idx] or 0))
        if views <= 0:
            continue
        meta = videos_map.get(video_id, {})
        ranking.append({
            "rank": idx,
            "titulo": meta.get("titulo_descricao", video_id),
            "visualizacoes": views,
            "link": meta.get("link_permanente", f"https://www.youtube.com/watch?v={video_id}"),
        })
    return ranking


def _consultar_trafego_oauth(yt_analytics, channel_id, days=30, externo=False):
    if not yt_analytics or not channel_id:
        return []

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    params = {
        "ids": f"channel=={channel_id}",
        "startDate": start_date,
        "endDate": end_date,
        "metrics": "views",
        "sort": "-views",
        "maxResults": 25,
    }

    if externo:
        params["dimensions"] = "insightTrafficSourceDetail"
        params["filters"] = "insightTrafficSourceType==EXT_URL"
    else:
        params["dimensions"] = "insightTrafficSourceType"

    try:
        resp = yt_analytics.reports().query(**params).execute()
    except Exception as exc:
        label = "Tráfego externo" if externo else "Tráfego geral"
        print(f"  [YouTube Analytics] {label}: {exc}")
        return []

    headers = [h.get("name") for h in resp.get("columnHeaders", [])]
    rows = resp.get("rows", [])
    dim_name = "insightTrafficSourceDetail" if externo else "insightTrafficSourceType"
    if dim_name not in headers or "views" not in headers:
        return []

    dim_idx = headers.index(dim_name)
    views_idx = headers.index("views")
    itens = []
    for row in rows:
        codigo = str(row[dim_idx] or "")
        views = int(float(row[views_idx] or 0))
        if views <= 0:
            continue
        if externo:
            origem = codigo.replace("http://", "").replace("https://", "").strip("/") or "Desconhecida"
        else:
            origem = _TRAFEGO_GERAL_LABELS.get(codigo, codigo.replace("_", " ").title())
        itens.append({
            "origem": origem,
            "codigo": codigo,
            "views": views,
        })

    return _ranking_percentual(itens)


def _consultar_tempo_inscritos_oauth(yt_analytics, channel_id, days=30):
    if not yt_analytics or not channel_id:
        return None

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        resp = yt_analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            dimensions="subscribedStatus",
            metrics="estimatedMinutesWatched",
            sort="-estimatedMinutesWatched",
        ).execute()
    except Exception as exc:
        print(f"  [YouTube Analytics] Tempo de exibição (inscritos): {exc}")
        return None

    headers = [h.get("name") for h in resp.get("columnHeaders", [])]
    rows = resp.get("rows", [])
    if "subscribedStatus" not in headers or "estimatedMinutesWatched" not in headers:
        return None

    status_idx = headers.index("subscribedStatus")
    minutes_idx = headers.index("estimatedMinutesWatched")
    minutos_por_status = {}
    for row in rows:
        codigo = str(row[status_idx] or "")
        minutos = float(row[minutes_idx] or 0)
        if minutos <= 0:
            continue
        minutos_por_status[codigo] = minutos_por_status.get(codigo, 0) + minutos

    if not minutos_por_status:
        return None

    inscritos_min = minutos_por_status.get("SUBSCRIBED", 0)
    nao_inscritos_min = minutos_por_status.get("UNSUBSCRIBED", 0)
    return {
        "labels": ["Inscritos", "Não inscritos"],
        "horas": [round(inscritos_min / 60, 2), round(nao_inscritos_min / 60, 2)],
        "inscritos_horas": _formatar_horas(inscritos_min),
        "nao_inscritos_horas": _formatar_horas(nao_inscritos_min),
        "disponivel": True,
    }


def _consultar_trafego_organico_pago_oauth(yt_analytics, channel_id, days=30):
    if not yt_analytics or not channel_id:
        return None

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        resp = yt_analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            dimensions="insightTrafficSourceType",
            metrics="views",
            sort="-views",
            maxResults=50,
        ).execute()
    except Exception as exc:
        print(f"  [YouTube Analytics] Tráfego orgânico/pago: {exc}")
        return None

    headers = [h.get("name") for h in resp.get("columnHeaders", [])]
    rows = resp.get("rows", [])
    if "insightTrafficSourceType" not in headers or "views" not in headers:
        return None

    dim_idx = headers.index("insightTrafficSourceType")
    views_idx = headers.index("views")
    pago_views = 0
    organico_views = 0
    for row in rows:
        codigo = str(row[dim_idx] or "")
        views = int(float(row[views_idx] or 0))
        if views <= 0:
            continue
        if codigo == "ADVERTISING":
            pago_views += views
        else:
            organico_views += views

    total = pago_views + organico_views
    if total <= 0:
        return None

    return {
        "organico_pct": _formatar_pct(organico_views / total),
        "pago_pct": _formatar_pct(pago_views / total),
        "organico_views": organico_views,
        "pago_views": pago_views,
        "disponivel": True,
    }


def _montar_rankings(yt_analytics_client, channel_id, videos=None, days=30):
    videos_map = _mapa_videos(videos)
    ranking_videos = _consultar_videos_top_oauth(
        yt_analytics_client, channel_id, videos_map, days=days
    )
    if not ranking_videos:
        ranking_videos = _ranking_videos_fallback(videos, limit=10)

    trafego_geral = _consultar_trafego_oauth(yt_analytics_client, channel_id, days=days, externo=False)
    trafego_externo = _consultar_trafego_oauth(yt_analytics_client, channel_id, days=days, externo=True)

    return {
        "videos_mais_acessados": ranking_videos,
        "trafego_geral": trafego_geral,
        "trafego_externo": trafego_externo,
    }


def _extrair_metricas_resposta(rows, headers):
    if not rows:
        return {}
    header_names = [h.get("name") for h in headers]
    valores = rows[0]
    return {
        name: valores[idx]
        for idx, name in enumerate(header_names)
        if idx < len(valores)
    }


def _formatar_inscritos(valor):
    try:
        num = int(valor)
    except (TypeError, ValueError):
        num = 0
    return f"+{num}" if num > 0 else str(num)


def _somar_coluna(rows, headers, nome):
    if not rows:
        return 0
    header_names = [h.get("name") for h in headers]
    if nome not in header_names:
        return 0
    idx = header_names.index(nome)
    total = 0
    for row in rows:
        if idx < len(row):
            try:
                total += int(float(row[idx] or 0))
            except (TypeError, ValueError):
                continue
    return total


def _carregar_snapshot_inscritos(path, dias=30):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            historico = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None
    if not historico:
        return None
    limite = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
    candidatos = [item for item in historico if item.get("date", "") <= limite]
    if not candidatos:
        return historico[0].get("subscribers")
    return sorted(candidatos, key=lambda x: x.get("date", ""))[0].get("subscribers")


def _salvar_snapshot_inscritos(path, subscribers):
    historico = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                historico = json.load(fh)
        except (json.JSONDecodeError, OSError):
            historico = []
    hoje = datetime.now().strftime("%Y-%m-%d")
    if historico and historico[-1].get("date") == hoje:
        historico[-1]["subscribers"] = subscribers
    else:
        historico.append({"date": hoje, "subscribers": subscribers})
    historico = historico[-400:]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(historico, fh, ensure_ascii=False, indent=2)
    return historico


def _inscritos_por_snapshot(subscribers_atual, snapshot_path, dias=30):
    _salvar_snapshot_inscritos(snapshot_path, subscribers_atual)
    anterior = _carregar_snapshot_inscritos(snapshot_path, dias=dias)
    if anterior is None:
        return 0
    try:
        return int(subscribers_atual) - int(anterior)
    except (TypeError, ValueError):
        return 0


def _consultar_audiencia_oauth(yt_analytics, channel_id, days=30):
    if not yt_analytics or not channel_id:
        return None

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    base = {
        "ids": f"channel=={channel_id}",
        "startDate": start_date,
        "endDate": end_date,
    }
    resultado = empty_audiencia()

    try:
        subs_resp = yt_analytics.reports().query(
            **base,
            metrics="subscribersGained,subscribersLost",
        ).execute()
        gained = _somar_coluna(subs_resp.get("rows", []), subs_resp.get("columnHeaders", []), "subscribersGained")
        lost = _somar_coluna(subs_resp.get("rows", []), subs_resp.get("columnHeaders", []), "subscribersLost")
        net = gained - lost
        resultado["inscritos_valor"] = net
        resultado["inscritos"] = _formatar_inscritos(net)
    except Exception as exc:
        print(f"  [YouTube Analytics] Inscritos: {exc}")

    metricas_viewer = (
        "newViewers",
        "returningViewers",
        "uniqueViewers",
    )
    for metric in metricas_viewer:
        try:
            resp = yt_analytics.reports().query(**base, metrics=metric).execute()
            valor = _somar_coluna(resp.get("rows", []), resp.get("columnHeaders", []), metric)
            if metric == "newViewers":
                resultado["novos_espectadores"] = valor
            elif metric == "returningViewers":
                resultado["espectadores_recorrentes"] = valor
            elif metric == "uniqueViewers":
                resultado["espectadores_unicos"] = valor
        except Exception:
            continue

    if (
        not resultado["espectadores_unicos"]
        and resultado["novos_espectadores"]
        and resultado["espectadores_recorrentes"]
    ):
        resultado["espectadores_unicos"] = (
            resultado["novos_espectadores"] + resultado["espectadores_recorrentes"]
        )

    if any([
        resultado["novos_espectadores"],
        resultado["espectadores_recorrentes"],
        resultado["espectadores_unicos"],
        resultado["inscritos_valor"],
    ]):
        return resultado
    return None


def _montar_audiencia(
    yt_analytics_client,
    channel_id,
    subscribers_atual=0,
    snapshot_path="data/history/youtube_subscribers.json",
    days=30,
):
    audiencia = empty_audiencia()
    oauth_data = _consultar_audiencia_oauth(yt_analytics_client, channel_id, days=days)
    if oauth_data:
        audiencia.update(oauth_data)
        return audiencia

    delta = _inscritos_por_snapshot(subscribers_atual, snapshot_path, dias=days)
    audiencia["inscritos_valor"] = delta
    audiencia["inscritos"] = _formatar_inscritos(delta)
    return audiencia


def _consultar_analytics_oauth(yt_analytics, channel_id, days=30, paid=False):
    if not yt_analytics or not channel_id:
        return None

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    metrics = (
        "views,impressions,impressionClickThroughRate,averageViewDuration,"
        "estimatedMinutesWatched"
    )
    params = {
        "ids": f"channel=={channel_id}",
        "startDate": start_date,
        "endDate": end_date,
        "metrics": metrics,
    }
    if paid:
        params["filters"] = "insightTrafficSourceType==ADVERTISING"

    try:
        resp = yt_analytics.reports().query(**params).execute()
        return _extrair_metricas_resposta(
            resp.get("rows", []),
            resp.get("columnHeaders", []),
        )
    except Exception as exc:
        print(f"  [YouTube Analytics] {'Patrocinado' if paid else 'Orgânico'}: {exc}")
        return None


def _montar_payload(metricas, fonte="oauth"):
    views = int(float(metricas.get("views", 0) or 0))
    impressions = int(float(metricas.get("impressions", 0) or 0))
    ctr = metricas.get("impressionClickThroughRate", 0)
    avg_duration = metricas.get("averageViewDuration", 0)
    minutes = float(metricas.get("estimatedMinutesWatched", 0) or 0)

    if impressions > 0 and not ctr:
        ctr_calc = views / impressions
    else:
        ctr_calc = ctr

    return {
        "visualizacoes_canal": views,
        "impressoes": impressions,
        "taxa_cliques_impressoes": _formatar_pct(ctr_calc),
        "duracao_media_visualizacao": _formatar_duracao_segundos(avg_duration),
        "tempo_exibicao_horas": _formatar_horas(minutes),
        "analytics_fonte": fonte,
    }


def _fallback_api_key(videos, channel_total_views=0, dias=30):
    recentes = _filtrar_videos_periodo(videos, dias=dias)
    views = sum(int(v.get("visualizacoes", 0) or 0) for v in recentes)
    if views <= 0:
        views = int(channel_total_views or 0)

    return {
        "visualizacoes_canal": views,
        "impressoes": 0,
        "taxa_cliques_impressoes": "0%",
        "duracao_media_visualizacao": "0m 0s",
        "tempo_exibicao_horas": "0h",
        "analytics_fonte": "api_key",
    }


def fetch_youtube_insights(
    yt_analytics_client,
    channel_id,
    videos=None,
    channel_total_views=0,
    subscribers_atual=0,
    days=30,
):
    base = empty_youtube_insights()
    base["audiencia"] = _montar_audiencia(
        yt_analytics_client,
        channel_id,
        subscribers_atual=subscribers_atual,
        days=days,
    )
    base["rankings"] = _montar_rankings(
        yt_analytics_client,
        channel_id,
        videos=videos,
        days=days,
    )
    tempo_inscritos = _consultar_tempo_inscritos_oauth(
        yt_analytics_client, channel_id, days=days
    )
    if tempo_inscritos:
        base["grafico_tempo_inscritos"] = tempo_inscritos

    trafego_split = _consultar_trafego_organico_pago_oauth(
        yt_analytics_client, channel_id, days=days
    )
    if trafego_split:
        base["trafego_organico_pago"] = trafego_split

    base["interacoes_videos"] = _montar_interacoes_videos(
        yt_analytics_client,
        channel_id,
        videos=videos,
        days=days,
    )
    base["demografia"] = _montar_demografia(
        yt_analytics_client,
        channel_id,
        days=days,
    )
    base["localizacao"] = _montar_localizacao(
        yt_analytics_client,
        channel_id,
        days=days,
    )

    organic = _consultar_analytics_oauth(yt_analytics_client, channel_id, days=days, paid=False)
    if organic:
        base.update(_montar_payload(organic, fonte="oauth"))
        paid = _consultar_analytics_oauth(yt_analytics_client, channel_id, days=days, paid=True)
        if paid and any(float(paid.get(k, 0) or 0) > 0 for k in paid):
            base["patrocinado_disponivel"] = True
            base["patrocinado"].update(_montar_payload(paid, fonte="oauth"))
        print(
            f"  [OK] YouTube Analytics: {base['visualizacoes_canal']} views, "
            f"{base['impressoes']} impressões, CTR {base['taxa_cliques_impressoes']}, "
            f"{len(base['rankings']['videos_mais_acessados'])} vídeos no ranking"
        )
        return base

    fallback = _fallback_api_key(videos, channel_total_views, dias=days)
    base.update(fallback)
    if base["visualizacoes_canal"] or base["rankings"]["videos_mais_acessados"]:
        print(
            f"  [AVISO] YouTube Analytics OAuth indisponível — "
            f"usando visualizações via API Key ({base['visualizacoes_canal']}), "
            f"{len(base['rankings']['videos_mais_acessados'])} vídeos no ranking"
        )
    return base
