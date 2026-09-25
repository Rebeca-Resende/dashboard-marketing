import os
import shutil
import glob

def reset_history():
    history_dir = os.path.join('data', 'history')
    if os.path.exists(history_dir):
        print(f"Limpando diretório de histórico: {history_dir}")
        # Remove todos os arquivos .parquet e .json no diretório de histórico
        files = glob.glob(os.path.join(history_dir, "*.parquet")) + glob.glob(os.path.join(history_dir, "*.json"))
        for f in files:
            try:
                os.remove(f)
                print(f"  Removido: {f}")
            except Exception as e:
                print(f"  Erro ao remover {f}: {e}")
    
    # Também remove o dashboard.html antigo para garantir renovação
    if os.path.exists('dashboard.html'):
        os.remove('dashboard.html')
        print("Removido dashboard.html antigo.")

    print("\n✅ Reset concluído. O próximo 'python generate_dashboard.py' fará um carregamento completo.")

if __name__ == "__main__":
    reset_history()
