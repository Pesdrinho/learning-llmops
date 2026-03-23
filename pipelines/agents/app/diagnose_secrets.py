"""
Script de Diagnóstico de Secrets

Verifica o carregamento de variáveis de ambiente e secrets do GCP.
Execute este script para diagnosticar problemas com OPENROUTER_API_KEY.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Adiciona o diretório raiz ao path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("🔍 DIAGNÓSTICO DE SECRETS - OPENROUTER_API_KEY")
print("=" * 80)
print()

# 1. Verificar arquivo .env
print("1️⃣  VERIFICANDO ARQUIVO .env")
print("-" * 80)
env_file = project_root / ".env"
if env_file.exists():
    print(f"✅ Arquivo .env encontrado: {env_file}")
    print(f"   Caminho absoluto: {env_file.absolute()}")

    # Lê o arquivo e procura pela chave
    with open(env_file, encoding="utf-8") as f:
        lines = f.readlines()
        found = False
        for i, line in enumerate(lines, 1):
            if "OPENROUTER_API_KEY" in line:
                found = True
                # Mostra apenas os primeiros e últimos caracteres por segurança
                parts = line.split("=", 1)
                if len(parts) == 2:
                    key_value = parts[1].strip()
                    if key_value:
                        masked = (
                            key_value[:8] + "..." + key_value[-4:] if len(key_value) > 12 else "***"
                        )
                        print(f"   ✅ Linha {i}: OPENROUTER_API_KEY={masked}")
                    else:
                        print(f"   ⚠️  Linha {i}: OPENROUTER_API_KEY está vazia!")
                else:
                    print(f"   ⚠️  Linha {i}: Formato inválido: {line.strip()}")

        if not found:
            print("   ❌ OPENROUTER_API_KEY não encontrada no arquivo .env")
else:
    print(f"❌ Arquivo .env NÃO encontrado em: {env_file}")
    print(f"   Procurando em: {project_root}")
print()

# 2. Verificar variáveis de ambiente do sistema
print("2️⃣  VERIFICANDO VARIÁVEIS DE AMBIENTE DO SISTEMA")
print("-" * 80)
env_value = os.getenv("OPENROUTER_API_KEY")
if env_value:
    masked = env_value[:8] + "..." + env_value[-4:] if len(env_value) > 12 else "***"
    print(f"✅ OPENROUTER_API_KEY encontrada no ambiente: {masked}")
    print(f"   Tamanho: {len(env_value)} caracteres")
else:
    print("❌ OPENROUTER_API_KEY NÃO encontrada nas variáveis de ambiente do sistema")
print()

# 3. Testar load_dotenv
print("3️⃣  TESTANDO load_dotenv()")
print("-" * 80)

# Tenta carregar do diretório raiz
env_path = project_root / ".env"
if env_path.exists():
    result = load_dotenv(dotenv_path=env_path, override=False)
    print(f"✅ load_dotenv() executado: {result}")

    # Verifica novamente após load_dotenv
    env_value_after = os.getenv("OPENROUTER_API_KEY")
    if env_value_after:
        masked = (
            env_value_after[:8] + "..." + env_value_after[-4:]
            if len(env_value_after) > 12
            else "***"
        )
        print(f"✅ OPENROUTER_API_KEY após load_dotenv: {masked}")
    else:
        print("❌ OPENROUTER_API_KEY ainda não encontrada após load_dotenv")
else:
    print(f"❌ Arquivo .env não encontrado para load_dotenv: {env_path}")
print()

# 4. Testar SecretsManager
print("4️⃣  TESTANDO SecretsManager")
print("-" * 80)
try:
    from llmops_lab.secrets import manager as secrets

    sm = secrets.SecretsManager(use_gcp=False)  # Força uso de .env apenas
    print("✅ SecretsManager criado")
    print(f"   use_gcp: {sm.use_gcp}")
    print(f"   project_id: {sm.project_id}")

    # Testa get_secret
    secret_value = sm.get_secret("OPENROUTER_API_KEY", None)
    if secret_value:
        masked = secret_value[:8] + "..." + secret_value[-4:] if len(secret_value) > 12 else "***"
        print(f"✅ get_secret('OPENROUTER_API_KEY'): {masked}")
        print(f"   Tamanho: {len(secret_value)} caracteres")
    else:
        print("❌ get_secret('OPENROUTER_API_KEY') retornou None ou vazio")

    # Testa _get_from_env diretamente
    env_direct = sm._get_from_env("OPENROUTER_API_KEY", None)
    if env_direct:
        masked = env_direct[:8] + "..." + env_direct[-4:] if len(env_direct) > 12 else "***"
        print(f"✅ _get_from_env('OPENROUTER_API_KEY'): {masked}")
    else:
        print("❌ _get_from_env('OPENROUTER_API_KEY') retornou None ou vazio")

except Exception as e:
    print(f"❌ Erro ao testar SecretsManager: {e}")
    import traceback

    traceback.print_exc()
print()

# 5. Testar Config
print("5️⃣  TESTANDO Config")
print("-" * 80)
try:
    from config import get_config

    config = get_config()
    print("✅ Config criado")
    print(f"   app_env: {config.app_env}")

    api_key = config.openrouter_api_key
    if api_key:
        masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        print(f"✅ config.openrouter_api_key: {masked}")
        print(f"   Tamanho: {len(api_key)} caracteres")
        print(f"   Tipo: {type(api_key)}")
    else:
        print("❌ config.openrouter_api_key está None ou vazio")
        print(f"   Valor: {repr(api_key)}")

except Exception as e:
    print(f"❌ Erro ao testar Config: {e}")
    import traceback

    traceback.print_exc()
print()

# 6. Verificar GCP (se configurado)
print("6️⃣  VERIFICANDO GCP SECRET MANAGER")
print("-" * 80)
gcp_project = os.getenv("GCP_PROJECT_ID")
app_env = os.getenv("APP_ENV", "development")

if gcp_project:
    print(f"✅ GCP_PROJECT_ID configurado: {gcp_project}")
    print(f"   APP_ENV: {app_env}")

    if app_env == "production":
        print("   ⚠️  APP_ENV=production - SecretsManager tentará usar GCP primeiro")
    else:
        print("   ✅ APP_ENV=development - SecretsManager usará .env")

    # Testa com GCP habilitado
    try:
        sm_gcp = secrets.SecretsManager(use_gcp=True)
        print(f"   SecretsManager (GCP): use_gcp={sm_gcp.use_gcp}")

        secret_value_gcp = sm_gcp.get_secret("OPENROUTER_API_KEY", None)
        if secret_value_gcp:
            masked = (
                secret_value_gcp[:8] + "..." + secret_value_gcp[-4:]
                if len(secret_value_gcp) > 12
                else "***"
            )
            print(f"   ✅ get_secret com GCP: {masked}")
        else:
            print("   ⚠️  get_secret com GCP retornou None (pode estar usando fallback para .env)")
    except Exception as e:
        print(f"   ❌ Erro ao testar com GCP: {e}")
else:
    print("ℹ️  GCP_PROJECT_ID não configurado - usando apenas .env")
print()

# 7. Verificar diretório de trabalho atual
print("7️⃣  INFORMAÇÕES DO AMBIENTE")
print("-" * 80)
print(f"   Diretório de trabalho atual: {os.getcwd()}")
print(f"   Diretório do script: {Path(__file__).parent}")
print(f"   Diretório raiz do projeto: {project_root}")
print(f"   PYTHONPATH: {os.getenv('PYTHONPATH', 'não configurado')}")
print()

# 8. Resumo e recomendações
print("=" * 80)
print("📋 RESUMO E RECOMENDAÇÕES")
print("=" * 80)

issues = []

# Verifica se encontrou a chave em algum lugar
final_value = os.getenv("OPENROUTER_API_KEY")
if not final_value:
    issues.append("❌ OPENROUTER_API_KEY não encontrada em nenhum lugar")

if issues:
    print("\n⚠️  PROBLEMAS ENCONTRADOS:")
    for issue in issues:
        print(f"   {issue}")

    print("\n💡 SOLUÇÕES SUGERIDAS:")
    print("   1. Verifique se o arquivo .env está na raiz do projeto")
    print("   2. Verifique se OPENROUTER_API_KEY está definida no .env sem espaços extras")
    print("   3. Certifique-se de que o formato está correto: OPENROUTER_API_KEY=sk-or-v1-...")
    print("   4. Se estiver usando Docker, verifique se o .env está sendo copiado corretamente")
    print("   5. Se estiver em produção, verifique se o secret existe no GCP Secret Manager")
    print("   6. Execute este script novamente após fazer as correções")
else:
    print("\n✅ Tudo parece estar configurado corretamente!")
    print("   Se ainda houver problemas, verifique os logs da aplicação.")

print()
