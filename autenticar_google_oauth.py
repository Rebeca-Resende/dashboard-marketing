"""
Gera token.json para YouTube Analytics e Google Search Console (OAuth).

Execute uma vez na pasta do projeto:
    python autenticar_google_oauth.py

Depois rode novamente:
    python generate_dashboard.py
"""
import json
import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
]

CONFIG_PATH = "config.json"
TOKEN_PATH = "token.json"


def main():
    if not os.path.exists(CONFIG_PATH):
        raise SystemExit(f"Arquivo {CONFIG_PATH} não encontrado.")

    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)

    oauth = cfg.get("google_oauth", {})
    client_config = {
        "installed": {
            "client_id": oauth.get("client_id"),
            "client_secret": oauth.get("client_secret"),
            "auth_uri": oauth.get("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
            "token_uri": oauth.get("token_uri", "https://oauth2.googleapis.com/token"),
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    print(f"OK: {TOKEN_PATH} criado com sucesso.")
    print("Agora execute: python generate_dashboard.py")


if __name__ == "__main__":
    main()
