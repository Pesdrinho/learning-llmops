"""
Configurações da Aplicação

Define configurações globais e parâmetros do sistema.
"""

import os

from llmops_lab.secrets import manager as secrets


class Config:
    """Configurações globais da aplicação"""

    def __init__(self):
        sm = secrets.get_secrets_manager()

        self.app_env = os.getenv("APP_ENV", "development")
        self.app_version = "0.1.0"

        self.llm_model = "openai/gpt-4o-mini"
        self.llm_temperature = 0.7
        self.llm_max_tokens = 10000

        self.openrouter_api_key = sm.get_secret("OPENROUTER_API_KEY", None)
        self.openrouter_base_url = "https://openrouter.ai/api/v1"

        self.budget_usd_day = float(os.getenv("BUDGET_USD_DAY", "15.0"))

        self.exports_dir = os.getenv("EXPORTS_DIR", "exports/analyses")

        self.max_retry_attempts = 2

    @property
    def is_production(self) -> bool:
        """Verifica se está em produção"""
        return bool(self.app_env == "production")

    @property
    def is_development(self) -> bool:
        """Verifica se está em desenvolvimento"""
        return bool(self.app_env == "development")


_config_instance: Config | None = None


def get_config() -> Config:
    """Retorna instância singleton de configuração"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
