#!/usr/bin/env python3
"""
Script de diagnóstico do Search Console para verificar configurações
"""

import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

def check_search_console():
    """Verifica configurações do Search Console"""
    
    print("🔍 DIAGNÓSTICO DO SEARCH CONSOLE")
    print("=" * 50)
    
    # Verificar se service_account.json existe
    if not os.path.exists('service_account.json'):
        print("❌ service_account.json não encontrado")
        return
    
    try:
        # Carregar credenciais
        scopes = ['https://www.googleapis.com/auth/webmasters.readonly']
        creds = service_account.Credentials.from_service_account_file(
            'service_account.json', scopes=scopes
        )
        
        # Conectar ao Search Console
        gsc = build('searchconsole', 'v1', credentials=creds)
        
        print("✅ Conectado ao Search Console")
        print()
        
        # Listar todos os sites verificados
        print("📋 SITES VERIFICADOS NO SEARCH CONSOLE:")
        print("-" * 50)
        
        try:
            sites = gsc.sites().list().execute()
            if 'siteEntry' in sites:
                for site in sites['siteEntry']:
                    site_url = site['siteUrl']
                    permission_level = site['permissionLevel']
                    print(f"🌐 {site_url}")
                    print(f"   Permissão: {permission_level}")
                    print()
            else:
                print("❌ Nenhum site verificado encontrado")
                print("   Verifique se o site foi adicionado ao Search Console")
                return
        except Exception as e:
            print(f"❌ Erro ao listar sites: {e}")
            return
        
        # Testar consulta em cada site
        print("📊 TESTANDO CONSULTAS:")
        print("-" * 50)
        
        from datetime import datetime, timedelta
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=30)
        
        for site in sites.get('siteEntry', []):
            site_url = site['siteUrl']
            print(f"\n🔍 Testando: {site_url}")
            
            try:
                # Consulta simples sem filtros
                response = gsc.searchanalytics().query(
                    siteUrl=site_url,
                    body={
                        "startDate": start_dt.strftime("%Y-%m-%d"),
                        "endDate": end_dt.strftime("%Y-%m-%d"),
                        "dimensions": [],  # Sem filtros
                        "rowLimit": 10
                    }
                ).execute()
                
                rows = response.get("rows", [])
                if rows:
                    total_impressions = sum(int(r.get("impressions", 0)) for r in rows)
                    total_clicks = sum(int(r.get("clicks", 0)) for r in rows)
                    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
                    avg_position = sum(float(r.get("position", 0)) for r in rows) / len(rows)
                    
                    print(f"   ✅ Dados encontrados:")
                    print(f"   📈 Impressões: {total_impressions:,}")
                    print(f"   👆 Cliques: {total_clicks:,}")
                    print(f"   📊 CTR: {avg_ctr:.2f}%")
                    print(f"   📍 Posição média: {avg_position:.1f}")
                else:
                    print(f"   ⚠️ Sem dados no período (últimos 30 dias)")
                    print("   Tente um período maior ou verifique se há dados no Search Console")
                    
            except Exception as e:
                print(f"   ❌ Erro na consulta: {e}")
        
        print("\n📋 RECOMENDAÇÕES:")
        print("-" * 50)
        print("1. Verifique se o site correto está verificado no Search Console")
        print("2. Confirme se há dados de performance no período solicitado")
        print("3. O Search Console pode levar até 48h para mostrar dados recentes")
        print("4. Certifique-se que a API está habilitada no Google Cloud Console")
        
    except Exception as e:
        print(f"❌ Erro geral: {e}")
        print("\n🔧 SOLUÇÕES POSSÍVEIS:")
        print("1. Habilite a API Search Console no Google Cloud Console")
        print("2. Verifique as permissões da conta de serviço")
        print("3. Confirme se o site está verificado no Search Console")

if __name__ == '__main__':
    check_search_console()
