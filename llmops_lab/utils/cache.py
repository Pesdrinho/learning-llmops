"""
Sistema de Cache Simples baseado em Hash
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


class SimpleCache:
    """Cache em memória com TTL"""

    def __init__(self, ttl_seconds: int = 3600):
        """
        Inicializa o cache

        Args:
            ttl_seconds: Tempo de vida dos itens em segundos (padrão: 1 hora)
        """
        self.ttl_seconds = ttl_seconds
        self._cache: dict = {}
        self._timestamps: dict = {}

    def _generate_key(self, data: Any) -> str:
        """
        Gera chave hash para os dados

        Args:
            data: Dados para cachear (deve ser serializável em JSON)

        Returns:
            Hash SHA256 dos dados
        """
        if isinstance(data, str):
            content = data
        else:
            content = json.dumps(data, sort_keys=True)

        return hashlib.sha256(content.encode()).hexdigest()

    def _is_expired(self, key: str) -> bool:
        """Verifica se item expirou"""
        if key not in self._timestamps:
            return True

        timestamp = self._timestamps[key]
        age = datetime.now() - timestamp

        return bool(age > timedelta(seconds=self.ttl_seconds))

    def get(self, key: str) -> Any | None:
        """
        Recupera item do cache

        Args:
            key: Chave do item

        Returns:
            Item do cache ou None se não encontrado/expirado
        """
        if key not in self._cache:
            logger.debug(f"Cache miss: {key[:16]}...")
            return None

        if self._is_expired(key):
            logger.debug(f"Cache expired: {key[:16]}...")
            self.delete(key)
            return None

        logger.debug(f"Cache hit: {key[:16]}...")
        return self._cache[key]

    def set(self, key: str, value: Any):
        """
        Armazena item no cache

        Args:
            key: Chave do item
            value: Valor a armazenar
        """
        self._cache[key] = value
        self._timestamps[key] = datetime.now()
        logger.debug(f"Cache set: {key[:16]}...")

    def get_or_generate(self, data: Any, generator_func, *args, **kwargs) -> Any:
        """
        Recupera do cache ou gera usando função

        Args:
            data: Dados para gerar a chave
            generator_func: Função para gerar valor se não estiver em cache
            *args, **kwargs: Argumentos para a função geradora

        Returns:
            Valor do cache ou gerado
        """
        key = self._generate_key(data)
        cached = self.get(key)

        if cached is not None:
            return cached

        # Gera novo valor
        value = generator_func(*args, **kwargs)
        self.set(key, value)

        return value

    async def async_get_or_generate(self, data: Any, async_generator_func, *args, **kwargs) -> Any:
        """
        Versão assíncrona de get_or_generate

        Args:
            data: Dados para gerar a chave
            async_generator_func: Função assíncrona para gerar valor
            *args, **kwargs: Argumentos para a função geradora

        Returns:
            Valor do cache ou gerado
        """
        key = self._generate_key(data)
        cached = self.get(key)

        if cached is not None:
            return cached

        # Gera novo valor
        value = await async_generator_func(*args, **kwargs)
        self.set(key, value)

        return value

    def delete(self, key: str):
        """Remove item do cache"""
        if key in self._cache:
            del self._cache[key]
        if key in self._timestamps:
            del self._timestamps[key]

    def clear(self):
        """Limpa todo o cache"""
        self._cache.clear()
        self._timestamps.clear()
        logger.info("Cache limpo")

    def cleanup_expired(self):
        """Remove todos os itens expirados"""
        expired_keys = [key for key in self._cache.keys() if self._is_expired(key)]

        for key in expired_keys:
            self.delete(key)

        if expired_keys:
            logger.info(f"Removidos {len(expired_keys)} itens expirados do cache")

    def size(self) -> int:
        """Retorna quantidade de itens no cache"""
        return len(self._cache)

    def stats(self) -> dict:
        """Retorna estatísticas do cache"""
        valid_items = sum(1 for key in self._cache.keys() if not self._is_expired(key))

        return {
            "total_items": len(self._cache),
            "valid_items": valid_items,
            "expired_items": len(self._cache) - valid_items,
            "ttl_seconds": self.ttl_seconds,
        }


class DatabaseCache(SimpleCache):
    """Cache persistente usando PostgreSQL"""

    def __init__(self, db_connection, table_name: str = "cache", ttl_seconds: int = 3600):
        """
        Inicializa cache com banco de dados

        Args:
            db_connection: Conexão com banco de dados
            table_name: Nome da tabela de cache
            ttl_seconds: TTL em segundos
        """
        super().__init__(ttl_seconds)
        self.db = db_connection
        self.table_name = table_name

    async def get(self, key: str) -> Any | None:
        """Recupera do banco de dados"""
        try:
            query = f"""
                SELECT value, created_at
                FROM {self.table_name}
                WHERE key = $1
            """
            row = await self.db.fetchrow(query, key)

            if not row:
                return None

            # Verifica expiração
            age = datetime.now() - row["created_at"]
            if age > timedelta(seconds=self.ttl_seconds):
                await self.delete(key)
                return None

            return json.loads(row["value"])
        except Exception as e:
            logger.error(f"Erro ao recuperar do cache DB: {e}")
            return None

    async def set(self, key: str, value: Any):
        """Armazena no banco de dados"""
        try:
            query = f"""
                INSERT INTO {self.table_name} (key, value, created_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (key) DO UPDATE
                SET value = $2, created_at = $3
            """
            await self.db.execute(query, key, json.dumps(value), datetime.now())
        except Exception as e:
            logger.error(f"Erro ao armazenar no cache DB: {e}")

    async def delete(self, key: str):
        """Remove do banco de dados"""
        try:
            query = f"DELETE FROM {self.table_name} WHERE key = $1"
            await self.db.execute(query, key)
        except Exception as e:
            logger.error(f"Erro ao deletar do cache DB: {e}")


# Instância global de cache em memória
_global_cache: SimpleCache | None = None


def get_cache(ttl_seconds: int = 3600) -> SimpleCache:
    """
    Retorna instância global de cache

    Args:
        ttl_seconds: TTL em segundos (usado apenas na primeira criação)

    Returns:
        Instância de cache
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = SimpleCache(ttl_seconds)
    return _global_cache
