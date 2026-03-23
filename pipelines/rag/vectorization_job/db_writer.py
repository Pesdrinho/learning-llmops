"""Escritor de dados no banco PostgreSQL"""

from contextlib import contextmanager
from datetime import datetime

import psycopg2
from psycopg2.extras import execute_values

from llmops_lab.logging.logger import get_logger
from pipelines.rag.vectorization_job.config import DATABASE_URL
from pipelines.rag.vectorization_job.gcs_loader import Document

logger = get_logger(__name__)


class DBWriter:
    """Escritor de documentos e chunks no banco de dados"""

    def __init__(self, database_url: str = DATABASE_URL):
        self.database_url = database_url

    @contextmanager
    def get_connection(self):
        """Context manager para conexão com o banco"""
        conn = psycopg2.connect(self.database_url)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Erro na transação do banco: {e}")
            raise
        finally:
            conn.close()

    def get_existing_documents(self) -> dict[str, str]:
        """
        Recupera documentos já processados do banco

        Returns:
            Dicionário {source_id: content_hash}
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source_id, content_hash
                    FROM rag.documents
                    WHERE status = 'processed'
                    """
                )
                results = cur.fetchall()

        documents = {row[0]: row[1] for row in results}
        logger.info(f"Encontrados {len(documents)} documentos já processados no banco")
        return documents

    def start_document_processing(self, doc: Document, title: str | None = None) -> int:
        """
        Marca documento como 'processing' e retorna o ID

        Args:
            doc: Documento a ser processado
            title: Título opcional do documento

        Returns:
            ID do documento no banco
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rag.documents
                        (source_id, source_type, title, url, content_hash, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_id)
                    DO UPDATE SET
                        content_hash = EXCLUDED.content_hash,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at,
                        error_message = NULL
                    RETURNING id
                    """,
                    (
                        doc.source_id,
                        "markdown",
                        title or doc.filename,
                        doc.gcs_path,
                        doc.content_hash,
                        "processing",
                        datetime.now(),
                        datetime.now(),
                    ),
                )
                result = cur.fetchone()
                doc_id: int = result[0] if result else 0

        logger.info(f"Documento {doc.source_id} marcado como 'processing' (ID: {doc_id})")
        return doc_id

    def save_chunks(
        self,
        doc: Document,
        chunks: list[str],
        embeddings: list[list[float]],
        metadata: dict | None = None,
    ) -> None:
        """
        Salva chunks com embeddings no banco

        Args:
            doc: Documento original
            chunks: Lista de chunks de texto
            embeddings: Lista de embeddings correspondentes
            metadata: Metadados opcionais para os chunks
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Número de chunks ({len(chunks)}) diferente do número de embeddings ({len(embeddings)})"
            )

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rag.doc_chunks WHERE source_id = %s", (doc.source_id,))

                values = [
                    (
                        doc.source_id,
                        "markdown",
                        doc.gcs_path,
                        chunk,
                        idx,
                        psycopg2.extras.Json(metadata or {}),
                        embeddings[idx],
                        datetime.now(),
                        datetime.now(),
                    )
                    for idx, chunk in enumerate(chunks)
                ]

                execute_values(
                    cur,
                    """
                    INSERT INTO rag.doc_chunks
                        (source_id, source_type, source_url, content, chunk_index,
                         metadata, embedding, created_at, updated_at)
                    VALUES %s
                    """,
                    values,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                )

        logger.info(f"Salvos {len(chunks)} chunks para documento {doc.source_id}")

    def mark_document_processed(self, doc: Document, total_chunks: int) -> None:
        """
        Marca documento como processado com sucesso

        Args:
            doc: Documento processado
            total_chunks: Número total de chunks gerados
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE rag.documents
                    SET status = %s,
                        total_chunks = %s,
                        processed_at = %s,
                        updated_at = %s,
                        error_message = NULL
                    WHERE source_id = %s
                    """,
                    ("processed", total_chunks, datetime.now(), datetime.now(), doc.source_id),
                )

        logger.info(f"Documento {doc.source_id} marcado como 'processed' ({total_chunks} chunks)")

    def mark_document_failed(self, doc: Document, error_message: str) -> None:
        """
        Marca documento como falho

        Args:
            doc: Documento que falhou
            error_message: Mensagem de erro
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE rag.documents
                    SET status = %s,
                        error_message = %s,
                        updated_at = %s
                    WHERE source_id = %s
                    """,
                    ("failed", error_message, datetime.now(), doc.source_id),
                )

        logger.error(f"Documento {doc.source_id} marcado como 'failed': {error_message}")
