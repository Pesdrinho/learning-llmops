"""Chunkers para segmentação de documentos"""

import json
from abc import ABC, abstractmethod

import httpx
import tiktoken

from llmops_lab.logging.logger import get_logger
from pipelines.rag.vectorization_job.config import (
    CHUNKING_THRESHOLD_CHARS,
    DYNAMIC_CHUNKING_MODEL,
    OPENROUTER_API_KEY,
    STANDARD_CHUNK_OVERLAP,
    STANDARD_CHUNK_SIZE,
)
from pipelines.rag.vectorization_job.prompts.chunking import get_dynamic_chunking_messages

logger = get_logger(__name__)


class BaseChunker(ABC):
    """Classe base para chunkers"""

    @abstractmethod
    def chunk(self, content: str) -> list[str]:
        """Divide o conteúdo em chunks"""
        pass


class StandardChunker(BaseChunker):
    """Chunker baseado em tokens com overlap fixo"""

    def __init__(
        self, chunk_size: int = STANDARD_CHUNK_SIZE, chunk_overlap: int = STANDARD_CHUNK_OVERLAP
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def chunk(self, content: str) -> list[str]:
        """
        Divide o conteúdo em chunks de tamanho fixo com overlap

        Args:
            content: Texto a ser segmentado

        Returns:
            Lista de chunks
        """
        tokens = self.encoding.encode(content)
        chunks = []

        start = 0
        while start < len(tokens):
            end = start + self.chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(chunk_text)

            start += self.chunk_size - self.chunk_overlap

        logger.debug(f"StandardChunker: {len(tokens)} tokens divididos em {len(chunks)} chunks")
        return chunks


class DynamicChunker(BaseChunker):
    """Chunker baseado em LLM para segmentação semântica"""

    def __init__(self, model: str = DYNAMIC_CHUNKING_MODEL, api_key: str = OPENROUTER_API_KEY):
        self.model = model
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"

    def chunk(self, content: str) -> list[str]:
        """
        Divide o conteúdo usando LLM para segmentação semântica

        Args:
            content: Texto a ser segmentado

        Returns:
            Lista de chunks semanticamente coerentes
        """
        messages = get_dynamic_chunking_messages(content)

        try:
            response = self._call_llm(messages)
            chunks = self._parse_response(response)

            if not chunks:
                logger.warning("DynamicChunker retornou vazio, usando fallback para chunk único")
                return [content]

            logger.debug(f"DynamicChunker: documento dividido em {len(chunks)} chunks semânticos")
            return chunks

        except Exception as e:
            logger.error(f"Erro no DynamicChunker: {e}. Usando fallback para chunk único.")
            return [content]

    def _call_llm(self, messages: list[dict[str, str]]) -> str:
        """Chama a API do OpenRouter"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 4000,
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()

        result = response.json()
        content: str = result["choices"][0]["message"]["content"]
        return content

    def _parse_response(self, response: str) -> list[str]:
        """
        Parse da resposta do LLM para extrair os chunks

        Args:
            response: Resposta do LLM

        Returns:
            Lista de chunks extraídos
        """
        response = response.strip()

        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()

        try:
            data = json.loads(response)
            chunks = data.get("chunks", [])

            if not isinstance(chunks, list):
                logger.error(f"Resposta do LLM não contém lista de chunks: {data}")
                return []

            return [chunk for chunk in chunks if isinstance(chunk, str) and chunk.strip()]

        except json.JSONDecodeError as e:
            logger.error(
                f"Erro ao fazer parse do JSON retornado pelo LLM: {e}\nResposta: {response[:500]}"
            )
            return []


class ChunkerFactory:
    """Factory para escolher o chunker apropriado baseado no conteúdo"""

    @staticmethod
    def get_chunker(content: str) -> BaseChunker:
        """
        Retorna o chunker apropriado baseado no tamanho do conteúdo

        Args:
            content: Conteúdo a ser segmentado

        Returns:
            Instância do chunker apropriado
        """
        content_length = len(content)

        if content_length > CHUNKING_THRESHOLD_CHARS:
            logger.info(f"Usando StandardChunker (conteúdo: {content_length} chars)")
            return StandardChunker()
        else:
            logger.info(f"Usando DynamicChunker (conteúdo: {content_length} chars)")
            return DynamicChunker()
