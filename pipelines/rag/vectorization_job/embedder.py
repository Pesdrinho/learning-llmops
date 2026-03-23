"""Gerador de embeddings usando OpenAI"""

from openai import OpenAI

from llmops_lab.logging.logger import get_logger
from pipelines.rag.vectorization_job.config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    OPENAI_API_KEY,
)

logger = get_logger(__name__)


class Embedder:
    """Gerador de embeddings com batching e retry"""

    def __init__(
        self,
        api_key: str = OPENAI_API_KEY,
        model: str = EMBEDDING_MODEL,
        batch_size: int = EMBEDDING_BATCH_SIZE,
    ):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.batch_size = batch_size
        self.dimensions = EMBEDDING_DIMENSIONS

    def embed_chunks(self, chunks: list[str]) -> list[list[float]]:
        """
        Gera embeddings para uma lista de chunks com batching

        Args:
            chunks: Lista de textos para gerar embeddings

        Returns:
            Lista de embeddings (vetores de floats)
        """
        all_embeddings = []
        total_chunks = len(chunks)

        logger.info(
            f"Gerando embeddings para {total_chunks} chunks em batches de {self.batch_size}"
        )

        for i in range(0, total_chunks, self.batch_size):
            batch = chunks[i : i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (total_chunks + self.batch_size - 1) // self.batch_size

            logger.debug(f"Processando batch {batch_num}/{total_batches} ({len(batch)} chunks)")

            try:
                embeddings = self._embed_batch(batch)
                all_embeddings.extend(embeddings)

            except Exception as e:
                logger.error(f"Erro ao processar batch {batch_num}: {e}")
                raise

        logger.info(f"Total de {len(all_embeddings)} embeddings gerados com sucesso")
        return all_embeddings

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Gera embeddings para um batch de textos

        Args:
            texts: Lista de textos do batch

        Returns:
            Lista de embeddings
        """
        response = self.client.embeddings.create(
            model=self.model, input=texts, encoding_format="float"
        )

        embeddings = [item.embedding for item in response.data]

        if len(embeddings) != len(texts):
            raise ValueError(
                f"Número de embeddings ({len(embeddings)}) "
                f"diferente do número de textos ({len(texts)})"
            )

        for embedding in embeddings:
            if len(embedding) != self.dimensions:
                raise ValueError(
                    f"Dimensão do embedding ({len(embedding)}) "
                    f"diferente da esperada ({self.dimensions})"
                )

        return embeddings

    def embed_single(self, text: str) -> list[float]:
        """
        Gera embedding para um único texto

        Args:
            text: Texto para gerar embedding

        Returns:
            Vetor de embedding
        """
        embeddings = self.embed_chunks([text])
        return embeddings[0]
