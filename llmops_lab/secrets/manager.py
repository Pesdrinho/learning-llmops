"""
Gerenciador de Segredos - Secret Manager (GCP) + .env fallback
"""

import os

from dotenv import load_dotenv

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


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
        self._gcp_failed = False  # Track se GCP falhou para fazer fallback

        if self.use_gcp and not self.project_id:
            logger.warning("GCP_PROJECT_ID não configurado. Fazendo fallback para env vars")
            self.use_gcp = False

        self._client = None

        if self.use_gcp:
            logger.info(f"SecretsManager usando GCP Secret Manager (project: {self.project_id})")
        else:
            logger.info("SecretsManager usando variáveis de ambiente (.env)")

    @property
    def client(self):
        """Lazy load do client Secret Manager"""
        if self.use_gcp and self._client is None:
            from google.cloud import secretmanager

            self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def get_secret(self, secret_name: str, default: str | None = None) -> str | None:
        """
        Recupera um segredo do Secret Manager ou .env com fallback automático

        Estratégia:
        1. Se use_gcp=True: Tenta GCP Secret Manager primeiro
        2. Se GCP falhar: Faz fallback automático para env vars
        3. Se env var não existir: Retorna default

        Args:
            secret_name: Nome do segredo
            default: Valor padrão se não encontrado

        Returns:
            Valor do segredo ou None se não encontrado e sem default.
        """
        # Tenta GCP primeiro se configurado
        if self.use_gcp and not self._gcp_failed:
            gcp_value = self._get_from_gcp(secret_name, None)
            if gcp_value is not None:
                return gcp_value
            # Se GCP retornou None mas não deu erro, pode não existir no GCP
            # Mas não marca como falha ainda (pode ser que o secret simplesmente não existe)

        # Fallback para env vars (sempre tenta, mesmo se GCP estiver ativo)
        env_value = self._get_from_env(secret_name, None)
        if env_value is not None:
            # Se estava tentando GCP mas encontrou em env, avisa
            if self.use_gcp and not self._gcp_failed:
                logger.debug(f"Secret '{secret_name}' não encontrado no GCP, usando env var")
            return env_value

        # Retorna default se nada foi encontrado
        return default

    def _get_from_env(self, secret_name: str, default: str | None = None) -> str | None:
        """
        Recupera do .env e expande variáveis de ambiente no formato ${VAR}
        """
        value = os.getenv(secret_name, default)
        # Se value is None e default é None, retorna None (MyPy compatível)
        if value is None:
            return None
        # Expande variáveis de ambiente (${VAR} -> valor real)
        return os.path.expandvars(value)

    def _get_from_gcp(self, secret_name: str, default: str | None = None) -> str | None:
        """
        Recupera do Secret Manager GCP

        Returns:
            Valor do secret ou None se não encontrado/erro
        """
        try:
            if not self.client:
                if not self._gcp_failed:
                    logger.warning(
                        "GCP Secret Manager client não disponível. Fazendo fallback para env vars"
                    )
                    self._gcp_failed = True
                return None

            if not self.project_id:
                if not self._gcp_failed:
                    logger.warning("GCP_PROJECT_ID não configurado. Fazendo fallback para env vars")
                    self._gcp_failed = True
                return None

            secret_path = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
            response = self.client.access_secret_version(name=secret_path)

            # Verifica se a resposta tem payload válido
            if response.payload and response.payload.data:
                secret_value: str = response.payload.data.decode("UTF-8")
                logger.debug(f"Secret '{secret_name}' recuperado do GCP Secret Manager")
                return secret_value
            else:
                return None  # Secret não existe, não é erro

        except Exception as e:
            # Detecta problemas de autenticação/permissão
            error_str = str(e)
            if "PermissionDenied" in error_str or "403" in error_str:
                if not self._gcp_failed:
                    logger.error(
                        f"ERRO: Sem permissão para acessar Secret Manager GCP!\n"
                        f"  Verifique se o Service Account tem a role 'Secret Manager Secret Accessor'\n"
                        f"  Erro: {e}\n"
                        f"  Fazendo fallback para variáveis de ambiente"
                    )
                    self._gcp_failed = True
            elif "NotFound" in error_str or "404" in error_str:
                # Secret não existe, não é erro crítico
                logger.debug(f"Secret '{secret_name}' não encontrado no GCP Secret Manager")
            else:
                if not self._gcp_failed:
                    logger.warning(
                        f"Erro ao acessar GCP Secret Manager: {e}. Fazendo fallback para env vars"
                    )
                    self._gcp_failed = True

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
