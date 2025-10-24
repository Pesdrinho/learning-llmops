"""
Gerenciador de Segredos - Secret Manager (GCP) + .env fallback
"""

import os
from typing import cast

from dotenv import load_dotenv


class SecretsManager:
    """Gerenciador unificado de segredos com fallback para .env"""

    def __init__(self, use_gcp: bool = None):
        """
        Inicializa o gerenciador de segredos

        Args:
            use_gcp: Se True, usa Secret Manager. Se None, detecta automaticamente.
        """
        load_dotenv()

        if use_gcp is None:
            # Auto-detecta baseado no ambiente
            use_gcp = os.getenv("APP_ENV", "development") == "production"

        self.use_gcp = use_gcp
        self.project_id = os.getenv("GCP_PROJECT_ID")

        if self.use_gcp and not self.project_id:
            raise ValueError("GCP_PROJECT_ID não configurado para uso do Secret Manager")

        self._client = None

    @property
    def client(self):
        """Lazy load do client Secret Manager"""
        if self.use_gcp and self._client is None:
            from google.cloud import secretmanager

            self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def get_secret(self, secret_name: str, default: str | None = None) -> str | None:
        """
        Recupera um segredo do Secret Manager ou .env

        Args:
            secret_name: Nome do segredo
            default: Valor padrão se não encontrado

        Returns:
            Valor do segredo ou None se não encontrado e sem default.
        """
        if self.use_gcp:
            return self._get_from_gcp(secret_name, default)
        return self._get_from_env(secret_name, default)

    def _get_from_env(self, secret_name: str, default: str | None = None) -> str | None:
        """
        Recupera do .env
        """
        value = os.getenv(secret_name, default)
        # Se value is None e default é None, retorna None (MyPy compatível)
        return value

    def _get_from_gcp(self, secret_name: str, default: str | None = None) -> str | None:
        """
        Recupera do Secret Manager GCP
        """
        try:
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
            response = self.client.access_secret_version(request={"name": secret_path})
            return cast(str, response.payload.data.decode("UTF-8"))
        except Exception:
            if default is not None:
                return default
            # Se default é None e erro ocorre, retorna None (MyPy compatível)
            return None


# Singleton global
_secrets_manager: SecretsManager | None = None


def get_secrets_manager() -> SecretsManager:
    """Retorna instância singleton do SecretsManager"""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


# Funções de conveniência
def get_secret(secret_name: str, default: str | None = None) -> str:
    """Atalho para recuperar segredo"""
    value = get_secrets_manager().get_secret(secret_name, default)
    if value is None:
        raise ValueError(f"Segredo '{secret_name}' não encontrado e sem valor padrão.")
    return value


def get_api_key(provider: str) -> str:
    """Recupera API key de um provider"""
    key_map = {
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "langsmith": "LANGSMITH_API_KEY",
        "brapi": "BRAPI_TOKEN",
    }

    key_name = key_map.get(provider.lower())
    if not key_name:
        raise ValueError(f"Provider desconhecido: {provider}")

    return get_secret(key_name)


def get_db_url() -> str:
    """Recupera DATABASE_URL"""
    return get_secret("DATABASE_URL")


def get_db_url_sync() -> str:
    """Recupera DATABASE_URL síncrona"""
    return get_secret("DATABASE_URL_SYNC")
