#!/usr/bin/env python3
"""
Servidor HTTP simples para servir o Dashboard de Informativos
Resolve problemas de CORS ao abrir arquivo como file://
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Configurações
PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        """Adiciona headers CORS para evitar problemas de cross-origin"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        super().end_headers()
    
    def do_GET(self):
        """Trata requisições GET"""
        if self.path == '/':
            self.path = '/dashboard.html'
        return super().do_GET()
    
    def log_message(self, format, *args):
        """Customiza mensagens de log"""
        print(f"[{self.log_date_time_string()}] {format % args}")

def run_server():
    """Inicia o servidor HTTP"""
    try:
        with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
            print(
                f"\nDashboard - servidor iniciado\n"
                f"  URL: http://localhost:{PORT}\n"
                f"  Pasta: {DIRECTORY}\n"
                f"  Ctrl+C para encerrar\n"
            )
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nServidor parado.")
        sys.exit(0)
    except OSError as e:
        if e.errno == 48:  # Port already in use
            print(f"Erro: porta {PORT} ja esta em uso.")
            print("Feche o outro servidor ou altere PORT em run_server.py.")
        else:
            print(f"Erro: {e}")
        sys.exit(1)

if __name__ == '__main__':
    run_server()
