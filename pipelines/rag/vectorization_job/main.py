"""
Pipeline de Vetorização - Cloud Run Job

Orquestra o processo completo de:
1. Carregar documentos do GCS
2. Aplicar chunking (padrão ou dinâmico)
3. Gerar embeddings
4. Salvar no PostgreSQL
"""

import sys

from llmops_lab.logging.logger import get_logger
from pipelines.rag.vectorization_job.chunker import ChunkerFactory
from pipelines.rag.vectorization_job.db_writer import DBWriter
from pipelines.rag.vectorization_job.embedder import Embedder
from pipelines.rag.vectorization_job.gcs_loader import GCSLoader

logger = get_logger(__name__)


class VectorizationPipeline:
    """Pipeline completo de vetorização de documentos"""

    def __init__(self):
        self.gcs_loader = GCSLoader()
        self.embedder = Embedder()
        self.db_writer = DBWriter()

    def run(self) -> int:
        """
        Executa o pipeline completo

        Returns:
            Código de saída (0 = sucesso, 1 = falha)
        """
        try:
            logger.info("=" * 80)
            logger.info("Iniciando Pipeline de Vetorização RAG")
            logger.info("=" * 80)

            existing_documents = self.db_writer.get_existing_documents()

            documents_to_process = self.gcs_loader.get_documents_to_process(existing_documents)

            if not documents_to_process:
                logger.info("Nenhum documento novo ou modificado encontrado. Pipeline finalizado.")
                return 0

            logger.info(f"Total de documentos a processar: {len(documents_to_process)}")

            success_count = 0
            failure_count = 0

            for idx, doc in enumerate(documents_to_process, 1):
                logger.info("-" * 80)
                logger.info(
                    f"Processando documento {idx}/{len(documents_to_process)}: {doc.source_id}"
                )
                logger.info("-" * 80)

                try:
                    self._process_document(doc)
                    success_count += 1
                    logger.info(f"✓ Documento {doc.source_id} processado com sucesso")

                except Exception as e:
                    failure_count += 1
                    error_msg = f"Erro ao processar documento: {str(e)}"
                    logger.error(f"✗ {error_msg}")

                    try:
                        self.db_writer.mark_document_failed(doc, error_msg)
                    except Exception as db_error:
                        logger.error(f"Erro ao marcar documento como falho: {db_error}")

            logger.info("=" * 80)
            logger.info("Pipeline de Vetorização Finalizado")
            logger.info(f"Sucesso: {success_count} | Falhas: {failure_count}")
            logger.info("=" * 80)

            return 0 if failure_count == 0 else 1

        except Exception as e:
            logger.error(f"Erro crítico no pipeline: {e}", exc_info=True)
            return 1

    def _process_document(self, doc) -> None:
        """
        Processa um único documento

        Args:
            doc: Documento a ser processado
        """
        self.db_writer.start_document_processing(doc)

        logger.info(f"Aplicando chunking ao documento ({len(doc.content)} chars)")
        chunker = ChunkerFactory.get_chunker(doc.content)
        chunks = chunker.chunk(doc.content)
        logger.info(f"Documento dividido em {len(chunks)} chunks")

        logger.info("Gerando embeddings para os chunks")
        embeddings = self.embedder.embed_chunks(chunks)
        logger.info(f"Gerados {len(embeddings)} embeddings")

        metadata = {
            "filename": doc.filename,
            "gcs_path": doc.gcs_path,
            "content_hash": doc.content_hash,
        }

        logger.info("Salvando chunks e embeddings no banco de dados")
        self.db_writer.save_chunks(doc, chunks, embeddings, metadata)

        self.db_writer.mark_document_processed(doc, len(chunks))


def main():
    """Entry point do job"""
    pipeline = VectorizationPipeline()
    exit_code = pipeline.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
