"""Retriever para busca vetorial no PostgreSQL"""

import httpx
import psycopg2

from llmops_lab.logging.logger import get_logger
from pipelines.rag.generation_api.config import (
    DATABASE_URL,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TOP_K,
    EMBEDDING_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
)
from pipelines.rag.generation_api.models import SourceChunk

logger = get_logger(__name__)


class RAGRetriever:
    """Retriever para busca de chunks similares no banco"""

    def __init__(
        self,
        database_url: str = DATABASE_URL,
        openrouter_api_key: str = OPENROUTER_API_KEY,
        embedding_model: str = EMBEDDING_MODEL,
    ):
        self.database_url = database_url
        self.openrouter_api_key = openrouter_api_key
        self.embedding_model = embedding_model
        self.base_url = OPENROUTER_BASE_URL

    def retrieve(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        filter_metadata: dict | None = None,
    ) -> list[SourceChunk]:
        """
        Recupera chunks similares à query

        Args:
            query: Pergunta do usuário
            top_k: Número de chunks a retornar
            similarity_threshold: Threshold mínimo de similaridade
            filter_metadata: Filtros opcionais por metadata

        Returns:
            Lista de chunks recuperados
        """
        logger.info(f"Recuperando chunks para query: '{query[:100]}...'")

        query_embedding = self._generate_embedding(query)

        chunks = self._search_similar_chunks(
            query_embedding, top_k, similarity_threshold, filter_metadata
        )

        logger.info(f"Recuperados {len(chunks)} chunks com similaridade >= {similarity_threshold}")
        return chunks

    def _generate_embedding(self, text: str) -> list[float]:
        """
        Gera embedding para o texto usando OpenRouter (compatível com OpenAI API)

        Args:
            text: Texto para gerar embedding

        Returns:
            Vetor de embedding
        """
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.embedding_model,
            "input": text,
            "encoding_format": "float",
        }

        logger.debug(
            f"Chamando OpenRouter embeddings - modelo: {self.embedding_model}, "
            f"tamanho do texto: {len(text)}"
        )

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
            )
            if response.status_code != 200:
                logger.error(
                    f"Falha ao obter embedding do OpenRouter: "
                    f"status={response.status_code}, body={response.text}"
                )
                response.raise_for_status()

        result = response.json()
        embedding: list[float] = result["data"][0]["embedding"]
        logger.debug(f"Embedding gerado com {len(embedding)} dimensões")
        return embedding

    def _search_similar_chunks(
        self,
        query_embedding: list[float],
        top_k: int,
        similarity_threshold: float,
        filter_metadata: dict | None = None,
    ) -> list[SourceChunk]:
        """
        Busca chunks similares no banco usando a função SQL

        Args:
            query_embedding: Vetor de embedding da query
            top_k: Número máximo de chunks
            similarity_threshold: Threshold mínimo
            filter_metadata: Filtros opcionais

        Returns:
            Lista de chunks recuperados
        """
        conn = psycopg2.connect(self.database_url)

        try:
            with conn.cursor() as cur:
                embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

                if filter_metadata:
                    import json

                    metadata_json = json.dumps(filter_metadata)
                    cur.execute(
                        """
                        SELECT * FROM rag.search_similar_chunks(
                            %s::vector(1536),
                            %s,
                            %s,
                            %s::jsonb
                        )
                        """,
                        (embedding_str, similarity_threshold, top_k, metadata_json),
                    )
                else:
                    cur.execute(
                        """
                        SELECT * FROM rag.search_similar_chunks(
                            %s::vector(1536),
                            %s,
                            %s
                        )
                        """,
                        (embedding_str, similarity_threshold, top_k),
                    )

                results = cur.fetchall()

            chunks = []
            for row in results:
                chunk = SourceChunk(
                    source_id=row[1],
                    content=row[2],
                    metadata=row[3] or {},
                    similarity=float(row[4]),
                )
                chunks.append(chunk)

            return chunks

        finally:
            conn.close()

    def format_context(self, chunks: list[SourceChunk]) -> str:
        """
        Formata os chunks recuperados em contexto para o prompt

        Args:
            chunks: Lista de chunks recuperados

        Returns:
            Contexto formatado como string
        """
        if not chunks:
            return "Nenhum contexto relevante encontrado."

        context_parts = []
        for idx, chunk in enumerate(chunks, 1):
            context_parts.append(
                f"[Fonte {idx}: {chunk.source_id} | Similaridade: {chunk.similarity:.2f}]\n"
                f"{chunk.content}\n"
            )

        return "\n---\n\n".join(context_parts)
