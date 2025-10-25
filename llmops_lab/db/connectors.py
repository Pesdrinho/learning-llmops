"""
Conectores de Banco de Dados - Cloud SQL e Local
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast

import asyncpg
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from llmops_lab.logging.logger import get_logger
from llmops_lab.secrets import manager as secrets

logger = get_logger(__name__)

# Base para modelos SQLAlchemy
Base = declarative_base()


class DatabaseConfig:
    """Configuração de banco de dados"""

    def __init__(self):
        self.env = os.getenv("APP_ENV", "development")
        self.use_cloud_sql_proxy = os.getenv("USE_CLOUD_SQL_PROXY", "false").lower() == "true"

        # Carrega variáveis individuais primeiro
        self.db_connection_name: str = os.getenv("DB_CONNECTION_NAME", "")
        self.db_user: str = os.getenv("DB_USER", "llmops_user")
        self.db_password: str = os.getenv("DB_PASSWORD", "")
        self.db_name: str = os.getenv("DB_NAME", "llmops")
        self.db_host: str = os.getenv("DB_HOST", "localhost")
        self.db_port: str = os.getenv("DB_PORT", "5432")

        # URLs de conexão (tenta do secrets, valida antes de usar)
        database_url_async_raw = secrets.get_secret("DATABASE_URL", None)
        database_url_sync_raw = secrets.get_secret("DATABASE_URL_SYNC", None)

        # Só usa se for válida (não contém ${} não expandidos e tem formato correto)
        self.database_url_async: str = ""
        self.database_url_sync: str = ""
        
        if database_url_async_raw and "${" not in database_url_async_raw and "@" in database_url_async_raw:
            self.database_url_async = cast(str, database_url_async_raw)
        
        if database_url_sync_raw and "${" not in database_url_sync_raw and "@" in database_url_sync_raw:
            self.database_url_sync = cast(str, database_url_sync_raw)

    def get_async_url(self) -> str:
        """Retorna URL async"""
        if self.database_url_async:
            return self.database_url_async

        # Fallback para construção manual
        if self.use_cloud_sql_proxy:
            return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@/cloudsql/{self.db_connection_name}/{self.db_name}"

        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    def get_sync_url(self) -> str:
        """Retorna URL síncrona"""
        if self.database_url_sync:
            return self.database_url_sync

        # Fallback para construção manual
        if self.use_cloud_sql_proxy:
            return f"postgresql://{self.db_user}:{self.db_password}@/cloudsql/{self.db_connection_name}/{self.db_name}"

        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


class AsyncDatabaseConnection:
    """Conexão assíncrona com pool de conexões"""

    def __init__(self, config: DatabaseConfig | None = None):
        self.config = config or DatabaseConfig()
        self._pool: asyncpg.Pool | None = None
        self._engine: AsyncEngine | None = None
        self._session_factory: sessionmaker | None = None

    async def connect(self):
        """Cria pool de conexões"""
        if self._pool is None:
            url = self.config.get_async_url()
            logger.info(f"Conectando ao banco de dados (async): {url.split('@')[1]}")

            # Pool asyncpg para queries diretas
            self._pool = await asyncpg.create_pool(
                url.replace("postgresql+asyncpg://", "postgresql://"),
                min_size=2,
                max_size=10,
                command_timeout=60,
            )

            # Engine SQLAlchemy para ORM
            self._engine = create_async_engine(
                url,
                echo=os.getenv("DEBUG", "false").lower() == "true",
                pool_pre_ping=True,
            )

            # Session factory
            self._session_factory = sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            logger.info("Conexão com banco estabelecida (async)")

    async def disconnect(self):
        """Fecha pool de conexões"""
        if self._pool:
            await self._pool.close()
            logger.info("Pool de conexões fechado")

        if self._engine:
            await self._engine.dispose()
            logger.info("Engine SQLAlchemy fechada")

    @property
    def pool(self) -> asyncpg.Pool:
        """Retorna pool asyncpg"""
        if self._pool is None:
            raise RuntimeError("Database não conectado. Chame connect() primeiro.")
        return self._pool

    @property
    def engine(self) -> AsyncEngine:
        """Retorna engine SQLAlchemy"""
        if self._engine is None:
            raise RuntimeError("Database não conectado. Chame connect() primeiro.")
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager para sessão SQLAlchemy"""
        if self._session_factory is None:
            raise RuntimeError("Database não conectado. Chame connect() primeiro.")

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def execute(self, query: str, *args):
        """Executa query diretamente"""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        """Executa query e retorna todas as linhas"""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        """Executa query e retorna uma linha"""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        """Executa query e retorna um valor"""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)


class SyncDatabaseConnection:
    """Conexão síncrona para scripts e migrations"""

    def __init__(self, config: DatabaseConfig | None = None):
        self.config = config or DatabaseConfig()
        self._engine = None
        self._session_factory = None

    def connect(self):
        """Cria engine"""
        if self._engine is None:
            url = self.config.get_sync_url()
            logger.info(f"Conectando ao banco de dados (sync): {url.split('@')[1]}")

            self._engine = create_engine(
                url,
                echo=os.getenv("DEBUG", "false").lower() == "true",
                pool_pre_ping=True,
            )

            self._session_factory = sessionmaker(bind=self._engine)

            logger.info("Conexão com banco estabelecida (sync)")

    def disconnect(self):
        """Fecha engine"""
        if self._engine:
            self._engine.dispose()
            logger.info("Engine fechada")

    @property
    def engine(self):
        """Retorna engine"""
        if self._engine is None:
            raise RuntimeError("Database não conectado. Chame connect() primeiro.")
        return self._engine

    def session(self):
        """Retorna nova sessão"""
        if self._session_factory is None:
            raise RuntimeError("Database não conectado. Chame connect() primeiro.")
        return self._session_factory()


# Instâncias globais
_async_db: AsyncDatabaseConnection | None = None
_sync_db: SyncDatabaseConnection | None = None


def get_async_db() -> AsyncDatabaseConnection:
    """Retorna instância global de conexão async"""
    global _async_db
    if _async_db is None:
        _async_db = AsyncDatabaseConnection()
    return _async_db


def get_sync_db() -> SyncDatabaseConnection:
    """Retorna instância global de conexão sync"""
    global _sync_db
    if _sync_db is None:
        _sync_db = SyncDatabaseConnection()
    return _sync_db


# Context managers para uso em aplicações
@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager para sessão async"""
    db = get_async_db()
    if db._session_factory is None:
        await db.connect()

    async with db.session() as session:
        yield session
