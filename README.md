# Dashboard de Marketing

Painel único em HTML para acompanhar canais digitais, sites e e-mail marketing. O time de comunicação deixa de depender de várias ferramentas abertas ao mesmo tempo: um script Python consolida as fontes, grava cache local e gera um arquivo `dashboard.html` que abre no navegador, com filtros por período, gráficos e exportação para PDF.

## O que este projeto resolve

- **Visão fragmentada** — métricas espalhadas entre Meta, Google, planilhas e ferramentas de e-mail.
- **Relatório manual demorado** — montagem repetida de planilhas e capturas de tela para reuniões.
- **Falhas parciais de API** — quando uma integração cai, o gerador pode reutilizar o último cache válido em vez de deixar abas vazias.
- **Dados híbridos** — combina APIs em tempo (quase) real com Excel atualizado pela equipe (campanhas, acessos a ferramentas, posts LinkedIn).

Não é um SaaS nem um backend em produção: é um **gerador estático** versionável, pensado para rodar na máquina ou em agendamento interno, com credenciais só no ambiente local.

## O que o dashboard mostra

Interface por abas, alimentada por um único JSON embutido no HTML na geração.

| Área | Origem típica | Exemplos de métricas / conteúdo |
|------|----------------|----------------------------------|
| Instagram & Facebook | Meta Graph API | publicações, alcance, interações, evolução no tempo |
| YouTube | YouTube Data + Analytics (OAuth) | views, inscritos, vídeos, audiência, rankings |
| Sites | Google Analytics 4 (+ Search Console) | usuários, engajamento, páginas, cliques e impressões orgânicas |
| E-mail (Akna) | Planilhas exportadas | envios, aberturas, cliques, funil, horários, campanhas |
| IOB | Planilhas de acesso | logins, uso por grupo, distribuição |
| LinkedIn | Planilha + API (quando configurada) | posts, engajamento, impressões |
| Visão geral | Agregação | comparativos entre canais, resumos assistidos por IA (opcional) |

Recursos de front-end incluem filtro de datas, tooltips de glossário, gráficos Chart.js e fluxo de exportação PDF no próprio navegador.

## Como funciona (fluxo)

1. **`generate_dashboard.py`** instancia o cliente em `modules/` e busca dados de cada fonte (com tratamento de erro por canal).
2. Resultados são normalizados, deduplicados quando necessário e mesclados com **`data/history/`** se uma fonte vier vazia na execução atual.
3. O template Jinja2 em **`templates/`** + assets em **`static/`** produzem **`dashboard.html`** (arquivo grande, gerado — não versionado).
4. Você abre o HTML localmente ou via **`run_server.py`** para evitar restrições de `file://` em alguns recursos.

Scripts auxiliares: **`autenticar_google_oauth.py`** (token OAuth Google), **`RESET_HISTORY.py`** (limpar cache), **`diagnose_search_console.py`** (teste GSC).

## Requisitos

- Python 3.10+
- Credenciais e tokens configurados localmente (`config.json`, opcionalmente `service_account.json` e `token.json`)
- Planilhas `.xlsx` em `data/input/akna`, `data/input/iob` e `data/input/linkedin` (ou paths via variáveis de ambiente — ver `modules/data_paths.py`)
- Chave OpenAI apenas se usar resumos/comparativos automáticos

## Instalação

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate   # Linux/macOS

pip install -r requirements.txt
copy config.example.json config.json   # Windows
# cp config.example.json config.json   # Linux/macOS
```

Edite `config.json` com suas chaves (URLs dos sites em `site_primary` / `site_secondary`, IDs GA4, tokens). Nunca commite credenciais — use o `.gitignore`.

O repositório **não inclui** `dashboard.html` nem dados de exemplo: após configurar, rode `python generate_dashboard.py` localmente para gerar o HTML com dados reais (APIs + planilhas).

OAuth Google (YouTube Analytics + Search Console):

```bash
python autenticar_google_oauth.py
```

## Uso

```bash
python generate_dashboard.py
```

Abra `dashboard.html`. Depois de mudar JS/CSS em `static/`, recarregue com Ctrl+F5.

## Estrutura do repositório

| Caminho | Papel |
|---------|--------|
| `modules/` | APIs, planilhas, cache Parquet/JSON, regras de validação |
| `templates/` | Layout e partials HTML |
| `static/` | Estilos, gráficos, filtros, PDF |
| `config.example.json` | Modelo de configuração |
| `data/input/` | Planilhas manuais (Akna, IOB, LinkedIn) — vazias no clone |
| `data/history/` | Cache gerado em runtime (pasta vazia no clone) |


