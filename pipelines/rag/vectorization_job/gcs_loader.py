"""Carregador de documentos do Google Cloud Storage"""

import hashlib
from dataclasses import dataclass

from google.cloud import storage

from llmops_lab.logging.logger import get_logger
from pipelines.rag.vectorization_job.config import GCS_BUCKET_NAME, GCS_PROJECT_ID

logger = get_logger(__name__)


@dataclass
class Document:
    """Representação de um documento"""

    source_id: str
    content: str
    content_hash: str
    filename: str
    gcs_path: str


class GCSLoader:
    """Carregador de documentos do GCS com verificação de hash"""

    def __init__(self, bucket_name: str = GCS_BUCKET_NAME, project_id: str | None = GCS_PROJECT_ID):
        self.bucket_name = bucket_name
        self.project_id = project_id
        self.storage_client = storage.Client(project=project_id) if project_id else storage.Client()
        self.bucket = self.storage_client.bucket(bucket_name)

    def list_markdown_files(self) -> list[str]:
        """Lista todos os arquivos .md no bucket"""
        blobs = self.bucket.list_blobs()
        markdown_files = [blob.name for blob in blobs if blob.name.endswith(".md")]
        logger.info(
            f"Encontrados {len(markdown_files)} arquivos Markdown no bucket {self.bucket_name}"
        )
        return markdown_files

    def load_document(self, blob_name: str) -> Document:
        """Carrega um documento do GCS e calcula seu hash"""
        blob = self.bucket.blob(blob_name)
        content = blob.download_as_text(encoding="utf-8")

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        source_id = blob_name.replace("/", "_").replace(".md", "")

        doc = Document(
            source_id=source_id,
            content=content,
            content_hash=content_hash,
            filename=blob_name.split("/")[-1],
            gcs_path=f"gs://{self.bucket_name}/{blob_name}",
        )

        logger.debug(f"Documento carregado: {blob_name} (hash: {content_hash[:8]}...)")
        return doc

    def get_documents_to_process(self, existing_hashes: dict[str, str]) -> list[Document]:
        """
        Retorna lista de documentos que precisam ser processados

        Args:
            existing_hashes: Dicionário {source_id: content_hash} dos documentos já processados

        Returns:
            Lista de documentos novos ou modificados
        """
        markdown_files = self.list_markdown_files()
        documents_to_process = []

        for blob_name in markdown_files:
            try:
                doc = self.load_document(blob_name)

                existing_hash = existing_hashes.get(doc.source_id)

                if existing_hash is None:
                    logger.info(f"Novo documento encontrado: {doc.source_id}")
                    documents_to_process.append(doc)
                elif existing_hash != doc.content_hash:
                    logger.info(f"Documento modificado: {doc.source_id}")
                    documents_to_process.append(doc)
                else:
                    logger.debug(f"Documento já processado e sem alterações: {doc.source_id}")

            except Exception as e:
                logger.error(f"Erro ao carregar documento {blob_name}: {e}")
                continue

        logger.info(f"Total de documentos a processar: {len(documents_to_process)}")
        return documents_to_process
