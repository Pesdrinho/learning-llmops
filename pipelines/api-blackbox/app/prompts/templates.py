"""
Templates e Helpers de Prompts

Utilitários adicionais para trabalhar com prompts e cache.
"""

import hashlib
import json
from typing import Any

from models import ChatMessage

from llmops_lab.logging.logger import get_logger
from llmops_lab.utils.cache import get_cache

logger = get_logger(__name__)


def generate_cache_key_for_messages(
    messages: list[ChatMessage], model: str, temperature: float
) -> str:
    """
    Gera chave de cache para uma requisição de chat

    Args:
        messages: Lista de mensagens
        model: Modelo LLM
        temperature: Temperatura

    Returns:
        Hash SHA256 como chave de cache
    """
    messages_dict = [{"role": msg.role, "content": msg.content} for msg in messages]

    cache_data = {"messages": messages_dict, "model": model, "temperature": temperature}

    cache_str = json.dumps(cache_data, sort_keys=True)
    return hashlib.sha256(cache_str.encode()).hexdigest()


async def get_cached_response(
    messages: list[ChatMessage], model: str, temperature: float, ttl_seconds: int = 3600
) -> dict | None:
    """
    Tenta recuperar resposta do cache

    Args:
        messages: Lista de mensagens
        model: Modelo LLM
        temperature: Temperatura
        ttl_seconds: TTL do cache

    Returns:
        Resposta cacheada ou None
    """
    cache = get_cache(ttl_seconds)
    cache_key = generate_cache_key_for_messages(messages, model, temperature)

    cached = cache.get(cache_key)

    if cached:
        logger.info(f"Cache HIT para key {cache_key[:16]}...")
        return cached

    logger.debug(f"Cache MISS para key {cache_key[:16]}...")
    return None


async def cache_response(
    messages: list[ChatMessage],
    model: str,
    temperature: float,
    response: dict,
    ttl_seconds: int = 3600,
) -> None:
    """
    Armazena resposta no cache

    Args:
        messages: Lista de mensagens
        model: Modelo LLM
        temperature: Temperatura
        response: Resposta a cachear
        ttl_seconds: TTL do cache
    """
    cache = get_cache(ttl_seconds)
    cache_key = generate_cache_key_for_messages(messages, model, temperature)

    cache.set(cache_key, response)
    logger.info(f"Resposta cacheada com key {cache_key[:16]}...")


def clear_prompt_cache():
    """Limpa todo o cache de prompts"""
    cache = get_cache()
    cache.clear()
    logger.warning("Cache de prompts limpo completamente")


def get_cache_stats() -> dict[str, Any]:
    """
    Obtém estatísticas do cache

    Returns:
        Dicionário com estatísticas
    """
    cache = get_cache()
    return cache.stats()
