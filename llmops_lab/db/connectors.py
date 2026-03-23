"""
Conectores de Banco de Dados - Cloud SQL e Local
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

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
    """Configuração simplificada - parâmetros diretos sem URL"""

    def __init__(self):
        self.env = os.getenv("APP_ENV", "development")

        # Carrega secrets
        sm = secrets.get_secrets_manager()

        # Credenciais obrigatórias
        self.user = sm.get_secret("DB_USER", os.getenv("DB_USER", "postgres"))
        self.password = sm.get_secret("DB_PASSWORD", os.getenv("DB_PASSWORD", ""))
        self.database = sm.get_secret("DB_NAME", os.getenv("DB_NAME", "postgres"))

        # Configuração de conexão
        self.connection_name = sm.get_secret(
            "DB_CONNECTION_NAME", os.getenv("DB_CONNECTION_NAME", "")
        )
        self.use_cloud_sql = bool(self.connection_name and self.env == "production")

        # Host/Port (só para desenvolvimento)
        if self.use_cloud_sql:
            # Cloud SQL via Unix Socket
            self.host = f"/cloudsql/{self.connection_name}"
            self.port = None
            logger.info(f"[Cloud SQL Socket] {self.connection_name}")
        else:
            # Local/TCP
            self.host = sm.get_secret("DB_HOST", os.getenv("DB_HOST", "localhost"))
            self.port = int(sm.get_secret("DB_PORT", os.getenv("DB_PORT", "5432")))
            logger.info(f"[TCP] {self.host}:{self.port}")

        # Validação
        if not self.password:
            raise ValueError("DB_PASSWORD não configurado!")

        logger.info(
            f"DB Config: user={self.user}, db={self.database}, cloud_sql={self.use_cloud_sql}"
        )

    def get_async_params(self) -> dict:
        """Retorna parâmetros para asyncpg.create_pool()"""
        params = {
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "host": self.host,
            "timeout": 60,  # Timeout generoso para Cloud SQL
        }

        # Só adiciona port se não for Unix socket
        if self.port:
            params["port"] = self.port

        return params

    def get_sqlalchemy_url(self) -> str:
        """Retorna URL para SQLAlchemy (fallback)"""
        if self.use_cloud_sql:
            return f"postgresql+asyncpg://{self.user}:{self.password}@/{self.database}?host={self.host}"
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


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
            # Parâmetros diretos (sem URL)
            params = self.config.get_async_params()

            logger.info(
                f"Conectando: host={params['host']}, db={params['database']}, user={params['user']}"
            )

            # Pool asyncpg com parâmetros individuais
            self._pool = await asyncpg.create_pool(
                **params,
                min_size=1,  # Reduz carga no startup
                max_size=10,
                command_timeout=90,
            )

            # Engine SQLAlchemy (fallback para ORM)
            url = self.config.get_sqlalchemy_url()
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

            logger.info("Conexao estabelecida (async)")

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
            url = self.config.get_sqlalchemy_url().replace("+asyncpg", "")

            logger.info(
                f"Conectando (sync): host={self.config.host}, "
                f"db={self.config.database}, user={self.config.user}"
            )

            self._engine = create_engine(
                url,
                echo=os.getenv("DEBUG", "false").lower() == "true",
                pool_pre_ping=True,
            )

            self._session_factory = sessionmaker(bind=self._engine)

            logger.info("Conexao estabelecida (sync)")

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
