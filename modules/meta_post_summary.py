"""
Resumo de desempenho por postagens (Instagram e Facebook).
"""
from collections import defaultdict
from datetime import datetime, timedelta

_MESES_PT = (
    "jan.", "fev.", "mar.", "abr.", "mai.", "jun.",
    "jul.", "ago.", "set.", "out.", "nov.", "dez.",
)

_IG_FORMATO = {
    "VIDEO": "Reels/Vídeo",
    "REELS": "Reels/Vídeo",
    "IMAGE": "Imagem",
    "CAROUSEL_ALBUM": "Carrossel",
}

_FB_FORMATO = {
    "added_video": "Reels/Vídeo",
    "added_photos": "Imagem",
    "shared_story": "Story",
    "mobile_status_update": "Texto",
    "created_event": "Evento",
    "published_story": "Story",
}

_ENGAJAMENTO_LIMIAR = {
    "instagram": {"baixo": 0.5, "medio": 2.0},
    "facebook": {"baixo": 0.5, "medio": 2.0},
}


def empty_meta_resumo():
    return {
        "melhor_formato": "Sem dados suficientes para identificar o melhor formato.",
        "pico_interacoes": "Sem pico de interações identificado no período.",
        "engajamento": "Sem dados de engajamento no período.",
        "engajamento_nivel": "indisponivel",
        "engajamento_taxa": 0.0,
    }


def _parse_data_post(valor):
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor
    texto = str(valor).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(texto[:10] if fmt == "%Y-%m-%d" else texto, fmt)
        except ValueError:
            continue
    return None


def _formatar_data_pt(dt):
    return f"{dt.day} de {_MESES_PT[dt.month - 1]} de {dt.year}"


def _interacao_post(post):
    try:
        return int(post.get("interacao", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _taxa_post(post, followers):
    if followers <= 0:
        return 0.0
    taxa_txt = post.get("taxa_interacao")
    if taxa_txt:
        try:
            return float(str(taxa_txt).replace("%", "").strip())
        except ValueError:
            pass
    return (_interacao_post(post) / followers) * 100


def _filtrar_periodo(posts, dias=90):
    limite = datetime.now() - timedelta(days=dias)
    filtrados = []
    for post in posts or []:
        dt = _parse_data_post(post.get("data_publicacao") or post.get("timestamp"))
        if dt and dt >= limite:
            filtrados.append(post)
    return filtrados or list(posts or [])


def _melhor_formato(posts, platform):
    if not posts:
        return "Sem postagens para analisar o melhor formato."

    por_tipo = defaultdict(list)
    for post in posts:
        if platform == "instagram":
            tipo = post.get("tipos_publicacao") or "OUTRO"
            label = _IG_FORMATO.get(tipo, tipo.replace("_", " ").title())
        else:
            tipo = post.get("status_type") or post.get("tipos_publicacao") or ""
            if not tipo and "http" in str(post.get("titulo_descricao", "")).lower():
                tipo = "link"
            label = _FB_FORMATO.get(tipo, "Postagem" if not tipo else tipo.replace("_", " ").title())
        por_tipo[label].append(_interacao_post(post))

    medias = {
        label: (sum(vals) / len(vals))
        for label, vals in por_tipo.items()
        if vals
    }
    if not medias:
        return "Sem dados suficientes para identificar o melhor formato."

    melhor = max(medias, key=medias.get)
    return f"O melhor formato de postagem para maior alcance foi {melhor}"


def _pico_interacoes(posts):
    if not posts:
        return "Sem pico de interações identificado no período."

    por_data = defaultdict(int)
    datas_obj = {}
    for post in posts:
        dt = _parse_data_post(post.get("data_publicacao") or post.get("timestamp"))
        if not dt:
            continue
        chave = dt.strftime("%d/%m/%Y")
        por_data[chave] += _interacao_post(post)
        datas_obj[chave] = dt

    if not por_data or max(por_data.values()) <= 0:
        return "Sem pico de interações identificado no período."

    melhor_data = max(por_data, key=por_data.get)
    return f"Houve um pico de interações em {_formatar_data_pt(datas_obj[melhor_data])}"


def _avaliar_engajamento(posts, followers, platform):
    if not posts or followers <= 0:
        return "Sem dados de engajamento no período.", "indisponivel", 0.0

    taxas = [_taxa_post(p, followers) for p in posts if _interacao_post(p) >= 0]
    if not taxas:
        return "Sem dados de engajamento no período.", "indisponivel", 0.0

    media = sum(taxas) / len(taxas)
    limiar = _ENGAJAMENTO_LIMIAR.get(platform, _ENGAJAMENTO_LIMIAR["instagram"])

    if media < limiar["baixo"]:
        return (
            f"Baixo engajamento ({media:.2f}%): revisar conteúdo e horário de postagem",
            "baixo",
            round(media, 2),
        )
    if media < limiar["medio"]:
        return (
            f"Engajamento moderado ({media:.2f}%): manter frequência e testar novos formatos",
            "medio",
            round(media, 2),
        )
    return (
        f"Bom engajamento ({media:.2f}%): manter a estratégia de conteúdo atual",
        "alto",
        round(media, 2),
    )


def build_meta_resumo(posts, followers, platform="instagram", dias=90):
    posts_uso = _filtrar_periodo(posts, dias=dias)
    eng_texto, eng_nivel, eng_taxa = _avaliar_engajamento(posts_uso, followers, platform)
    return {
        "melhor_formato": _melhor_formato(posts_uso, platform),
        "pico_interacoes": _pico_interacoes(posts),
        "engajamento": eng_texto,
        "engajamento_nivel": eng_nivel,
        "engajamento_taxa": eng_taxa,
    }
