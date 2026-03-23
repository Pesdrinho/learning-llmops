"""Configurações do Pipeline de Vetorização"""

import os

from llmops_lab.logging.logger import get_logger
from llmops_lab.secrets.manager import get_secrets_manager

logger = get_logger(__name__)
secrets = get_secrets_manager()

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "llmops-rag-docs")
GCS_PROJECT_ID = os.getenv("GCP_PROJECT_ID", secrets.project_id)

# Configuração do banco de dados com fallback para DATABASE_URL_SYNC
DB_HOST = os.getenv("DB_HOST") or secrets.get_secret("DB_HOST")
DB_USER = os.getenv("DB_USER") or secrets.get_secret("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD") or secrets.get_secret("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME") or secrets.get_secret("DB_NAME")
DB_PORT = os.getenv("DB_PORT") or secrets.get_secret("DB_PORT") or "5432"

if DB_HOST and DB_USER and DB_PASSWORD and DB_NAME and DB_PORT:
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    logger.info(f"Database URL construída: postgresql://***:***@{DB_HOST}:{DB_PORT}/{DB_NAME}")
else:
    logger.warning(
        f"Usando DATABASE_URL_SYNC como fallback. "
        f"Componentes configurados: HOST={bool(DB_HOST)}, USER={bool(DB_USER)}, "
        f"PASS={bool(DB_PASSWORD)}, DB={bool(DB_NAME)}, PORT={bool(DB_PORT)}"
    )
    DATABASE_URL = secrets.get_secret("DATABASE_URL_SYNC")

OPENAI_API_KEY = secrets.get_secret("OPENAI_API_KEY")
OPENROUTER_API_KEY = secrets.get_secret("OPENROUTER_API_KEY")

CHUNKING_THRESHOLD_CHARS = 5000
STANDARD_CHUNK_SIZE = 500
STANDARD_CHUNK_OVERLAP = 100
EMBEDDING_MODEL = "openai/text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
EMBEDDING_BATCH_SIZE = 100

DYNAMIC_CHUNKING_MODEL = "google/gemini-2.5-flash"
