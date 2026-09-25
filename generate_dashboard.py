import json
import datetime
import sys
import io
import os
import pandas as pd
from jinja2 import Environment, FileSystemLoader

from modules.conecta_dashboard import empty_conecta_payload
from modules.data_paths import DATA_PATHS
from modules.sites_dashboard import empty_sites_payload
from modules.facebook_insights import empty_facebook_insights
from modules.instagram_insights import empty_instagram_insights
from modules.youtube_insights import empty_youtube_insights

DASHBOARD_CACHE_PATH = os.path.join('data', 'history', 'dashboard_cache.json')

# ✅ CORREÇÃO: Força stdout UTF-8 no Windows para evitar UnicodeEncodeError com emojis
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
elif sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Configuração do Jinja2
FILE_LOADER = FileSystemLoader('templates')
ENV = Environment(loader=FILE_LOADER)
def json_serial(obj):
    if isinstance(obj, (datetime.datetime, datetime.date, pd.Timestamp)):
        if pd.isna(obj):
            return None
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def custom_json_dumps(obj):
    return json.dumps(obj, default=json_serial)

ENV.filters['json_dumps'] = custom_json_dumps

def render_template(template_name, context):
    """Renderiza um template Jinja2 com o contexto fornecido."""
    template = ENV.get_template(template_name)
    return template.render(context)

def get_empty_dashboard_payload():
    """Estrutura vazia do dashboard quando APIs/planilhas ainda não foram carregadas."""
    return {
        "last_update": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "instagram": {
            **empty_instagram_insights(),
            "total_interactions": "0",
            "followers": "0",
            "detailed_data": [],
            "alcance": "0",
            "visitas": "0",
        },
        "facebook": {
            **empty_facebook_insights(),
            "total_interactions": "0",
            "followers": "0",
            "detailed_data": [],
            "alcance": "0",
            "visitas": "0",
        },
        "youtube": {
            **empty_youtube_insights(),
            "total_views": "0",
            "subscribers": "0",
            "detailed_data": [],
            "novas_inscricoes": "0",
            "video_mais_assistido": {"titulo": "N/A", "visualizacoes": "0", "watch_time": "0h"},
        },
        "linkedin": {"connected": False, "posts_count": 0, "total_likes": 0, "detailed_data": [], "impressoes": "0", "followers": "0", "visitas": "0", "total_interactions": "0"},
        "linkedin_abiarb": {"connected": False, "posts_count": 0, "total_likes": 0, "detailed_data": []},
        "akna": {"taxa_abertura": "0%", "status": "Aguardando Conexão", "total_envios": 0, "total_aberturas": 0, "total_cliques": 0},
        # ✅ CORREÇÃO: akna_manual precisa ter a chave "analytics" com sub-estrutura
        # para que o template {{ data.akna_manual.analytics.kpis.total_campanhas }} funcione
        "iob": {
            "status": "Aguardando extrato IOB",
            "source_file": "",
            "analytics": {
                "kpis": {
                    "total_registros": 0,
                    "total_logins": 0,
                    "total_logouts": 0,
                    "total_acessos_ferramenta": 0,
                },
                "grafico_grupos": {"labels": [], "values": []},
                "grafico_distribuicao": {"labels": [], "values": [], "percentages": []},
                "all_data": [],
            },
        },
        "akna_manual": {
            "detailed_data": [],
            "analytics": {
                "kpis": {
                    "total_campanhas": 0, "total_enviados": 0, "total_entregues": 0,
                    "total_aberturas": 0, "total_cliques": 0, "total_nao_entregues": 0,
                    "total_remocoes": 0, "total_spam": 0,
                    "taxa_entrega": 0, "taxa_abertura": 0, "taxa_clique": 0, "ctor": 0
                },
                "funil": {"labels": [], "values": [], "percentages": []},
                "evolucao_temporal": {"labels": [], "enviados": [], "aberturas": [], "cliques": []},
                "campanhas_por_tipo": {"labels": [], "enviados": [], "aberturas": [], "cliques": []},
                "distribuicao_tipos": {"labels": [], "values": []},
                "melhores_horarios": {"labels": [], "enviados": [], "aberturas": [], "taxa_abertura": []},
                "top_campanhas": [],
                "all_data": [],
                "ultima_atualizacao": ""
            }
        },
        "sites": empty_sites_payload("Aguardando configuração"),
        "site_conecta": empty_conecta_payload("Aguardando configuração"),
        "gsc_diario": [],
        "google_search": {"visualizacoes": "0", "cliques": "0", "ctr": "0%", "posicao": "0"},
        "redes_sociais_media_interacao": "0",
        "comparacao_ia": {"relatorio": "Aguardando dados para gerar relatório..."},
        "market_analysis": {"report": "Gerando relatório...", "fontes": []}
    }

def load_dashboard_cache():
    if not os.path.exists(DASHBOARD_CACHE_PATH):
        return None
    try:
        with open(DASHBOARD_CACHE_PATH, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception as exc:
        print(f"Aviso: cache do dashboard ilegível ({exc})")
        return None


def save_dashboard_cache(data):
    try:
        os.makedirs(os.path.dirname(DASHBOARD_CACHE_PATH), exist_ok=True)
        with open(DASHBOARD_CACHE_PATH, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, ensure_ascii=False, default=json_serial)
    except Exception as exc:
        print(f"Aviso: não foi possível salvar cache do dashboard ({exc})")


def _section_is_empty(section):
    if section is None:
        return True
    if isinstance(section, list):
        return len(section) == 0
    if not isinstance(section, dict):
        return False
    if section.get('detailed_data') == [] and not section.get('followers') and not section.get('total_views'):
        return True
    status = str(section.get('status_integracao', ''))
    if status.startswith('Erro') or status == 'GA4 Desconectado':
        return True
    return False


def merge_dashboard_data(fresh, cached):
    """Preserva dados anteriores quando a API retorna vazio ou erro parcial."""
    if not cached:
        return fresh
    merged = dict(cached)
    merged.update(fresh)
    for key in ('instagram', 'facebook', 'youtube', 'sites', 'site_conecta', 'akna_manual', 'iob', 'linkedin_abiarb'):
        fresh_sec = fresh.get(key)
        cached_sec = cached.get(key)
        if _section_is_empty(fresh_sec) and cached_sec:
            merged[key] = cached_sec
    merged['last_update'] = fresh.get('last_update') or cached.get('last_update')
    return merged

def generate_dashboard():
    """Busca os dados e gera o dashboard HTML conectando a todas as APIs."""
    print("1. Inicializando o cliente de API...")
    data = get_empty_dashboard_payload()
    cached_data = load_dashboard_cache()
    
    # Garante que o diretório de trabalho seja o do script para encontrar as pastas de data
    original_dir = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    try:
        from modules.api_client import SocialAPIClient
        config_path = 'config.json'
        if not os.path.isfile(config_path):
            raise FileNotFoundError(
                "config.json não encontrado. Copie config.example.json → config.json e preencha suas credenciais."
            )
        client = SocialAPIClient(config_path=config_path)
        
        print("2. Conectando e buscando dados de todas as APIs (Meta, YouTube, IA, etc.)...")
        api_data = client.get_all_data()
        
        if api_data:
            data['last_update'] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            # Mescla os dados da API com a estrutura base
            for key in api_data:
                if key in data and isinstance(data[key], dict) and isinstance(api_data[key], dict):
                    data[key].update(api_data[key])
                else:
                    data[key] = api_data[key]

            if cached_data:
                data = merge_dashboard_data(data, cached_data)
                print("Cache anterior aplicado onde a API retornou vazio ou erro.")

            # ✅ CORREÇÃO: Garante que akna_manual sempre tenha a chave "analytics"
            # mesmo que a API retorne um dict sem ela (falha parcial)
            akna_m = data.get('akna_manual', {})
            if not isinstance(akna_m.get('analytics'), dict):
                akna_m['analytics'] = data['akna_manual']['analytics'] if isinstance(
                    data.get('akna_manual', {}).get('analytics'), dict
                ) else {
                    'kpis': {
                        'total_campanhas': 0, 'total_enviados': 0, 'total_entregues': 0,
                        'total_aberturas': 0, 'total_cliques': 0, 'total_nao_entregues': 0,
                        'total_remocoes': 0, 'total_spam': 0,
                        'taxa_entrega': 0, 'taxa_abertura': 0, 'taxa_clique': 0, 'ctor': 0
                    },
                    'funil': {'labels': [], 'values': [], 'percentages': []},
                    'evolucao_temporal': {'labels': [], 'enviados': [], 'aberturas': [], 'cliques': []},
                    'campanhas_por_tipo': {'labels': [], 'enviados': [], 'aberturas': [], 'cliques': []},
                    'distribuicao_tipos': {'labels': [], 'values': []},
                    'melhores_horarios': {'labels': [], 'enviados': [], 'aberturas': [], 'taxa_abertura': []},
                    'top_campanhas': [], 'all_data': [], 'ultima_atualizacao': ''
                }
            data['akna_manual'] = akna_m

            iob_m = data.get('iob', {})
            if not isinstance(iob_m.get('analytics'), dict):
                iob_m['analytics'] = data['iob']['analytics'] if isinstance(
                    data.get('iob', {}).get('analytics'), dict
                ) else get_empty_dashboard_payload()['iob']['analytics']
            data['iob'] = iob_m

            print("Sucesso: Dados das APIs carregados.")
            save_dashboard_cache(data)
        else:
            print("Aviso: A API retornou dados vazios.")
            if cached_data:
                data = merge_dashboard_data(data, cached_data)
                print("Usando cache do dashboard anterior.")
            
    except Exception as e:
        print(f"\nERRO NA CONEXÃO COM AS APIS: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        print("-" * 50)
        if cached_data:
            data = merge_dashboard_data(get_empty_dashboard_payload(), cached_data)
            data['last_update'] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M") + " (cache)"
            print("Dashboard será gerado com dados em cache da última execução bem-sucedida.")
        else:
            print("O script continuará para gerar o HTML com estrutura vazia ou cache parcial.")
            print("DICA: Execute python autenticar_google_oauth.py para YouTube Analytics e Search Console.")
        print("-" * 50)

    # Contexto para o template
    context = {
        "data": data,
        "data_paths": DATA_PATHS,
        "json_dumps": custom_json_dumps
    }
    
    print("3. Renderizando o template HTML com a nova tela Akna Manual integrada...")
    try:
        html_output = render_template('dashboard_template.html', context)
        
        with open('dashboard.html', 'w', encoding='utf-8') as f:
            f.write(html_output)
        
        print("4. Dashboard gerado com sucesso em: dashboard.html")
        return True
        
    except Exception as e:
        print(f"ERRO CRÍTICO na renderização do template: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    generate_dashboard()