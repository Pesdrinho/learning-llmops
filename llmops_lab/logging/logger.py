"""
Sistema de Logging Centralizado
"""

import logging
import sys

from pydantic_settings import BaseSettings


class LogConfig(BaseSettings):
    """Configuração de logging"""

    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_date_format: str = "%Y-%m-%d %H:%M:%S"

    class Config:
        env_file = ".env"
        extra = "ignore"


def setup_logger(
    name: str,
    level: str | None = None,
    format_string: str | None = None,
) -> logging.Logger:
    """
    Configura e retorna um logger

    Args:
        name: Nome do logger
        level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Formato customizado de log

    Returns:
        Logger configurado
    """
    config = LogConfig()

    # Define nível
    log_level = level or config.log_level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Cria logger
    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)

    # Remove handlers existentes para evitar duplicação
    logger.handlers.clear()

    # Cria handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)

    # Define formato
    fmt = format_string or config.log_format
    formatter = logging.Formatter(fmt, datefmt=config.log_date_format)
    console_handler.setFormatter(formatter)

    # Adiciona handler ao logger
    logger.addHandler(console_handler)

    # Previne propagação para evitar logs duplicados
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Retorna um logger já configurado ou cria um novo

    Args:
        name: Nome do logger (geralmente __name__)

    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)

    # Se logger ainda não foi configurado, configura agora
    if not logger.handlers:
        return setup_logger(name)

    return logger


# Logger padrão do módulo
logger = get_logger("llmops_lab")
