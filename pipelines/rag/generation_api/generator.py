"""Gerador de respostas usando LLM via OpenRouter"""

import json
import time

import httpx

from llmops_lab.logging.logger import get_logger
from pipelines.rag.generation_api.config import (
    GENERATION_MAX_TOKENS,
    GENERATION_MODEL,
    GENERATION_TEMPERATURE,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
)
from pipelines.rag.generation_api.models import SourceChunk
from pipelines.rag.generation_api.prompts.rag import get_rag_prompt

logger = get_logger(__name__)


class RAGGenerator:
    """Gerador de respostas RAG usando LLM"""

    def __init__(
        self,
        api_key: str = OPENROUTER_API_KEY,
        model: str = GENERATION_MODEL,
        temperature: float = GENERATION_TEMPERATURE,
        max_tokens: int = GENERATION_MAX_TOKENS,
    ):
        self.api_key = api_key
        self.base_url = OPENROUTER_BASE_URL
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(
        self, query: str, chunks: list[SourceChunk], model: str | None = None
    ) -> tuple[str, dict]:
        """
        Gera resposta baseada na query e contexto recuperado

        Args:
            query: Pergunta do usuário
            chunks: Chunks recuperados para contexto
            model: Modelo LLM opcional (sobrescreve padrão)

        Returns:
            Tupla (resposta, metadata)
        """
        start_time = time.time()

        context = self._format_context(chunks)

        prompt_template, prompt_config = get_rag_prompt()

        messages = self._build_messages(prompt_template, query, context)

        model_to_use = model or self.model
        logger.info(f"Gerando resposta usando modelo: {model_to_use}")

        response_text, usage = self._call_llm(messages, model_to_use)

        latency_ms = int((time.time() - start_time) * 1000)

        metadata = {
            "model": model_to_use,
            "prompt_version": prompt_config.version,
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "latency_ms": latency_ms,
            "chunks_retrieved": len(chunks),
        }

        logger.info(
            f"Resposta gerada em {latency_ms}ms "
            f"(in: {metadata['input_tokens']}, out: {metadata['output_tokens']} tokens)"
        )

        return response_text, metadata

    def _format_context(self, chunks: list[SourceChunk]) -> str:
        """Formata chunks em contexto estruturado"""
        if not chunks:
            return "Nenhum contexto relevante encontrado."

        context_parts = []
        for idx, chunk in enumerate(chunks, 1):
            context_parts.append(
                f"[Fonte {idx}: {chunk.source_id} | Similaridade: {chunk.similarity:.2f}]\n"
                f"{chunk.content}"
            )

        context = "\n\n---\n\n".join(context_parts)

        logger.info(
            f"Contexto formatado: {len(chunks)} chunks, "
            f"{len(context)} caracteres, "
            f"~{len(context.split())} palavras"
        )

        return context

    def _build_messages(self, template, query: str, context: str) -> list[dict]:
        """Constrói mensagens usando o template do prompt"""
        formatted = template.format_messages(query=query, context=context)

        messages = []
        for msg in formatted:
            role = "system" if msg.type == "system" else "user"
            messages.append({"role": role, "content": msg.content})

            logger.debug(
                f"Mensagem construída - Role: {role}, Tamanho: {len(msg.content)} caracteres"
            )

        return messages

    def _call_llm(self, messages: list[dict], model: str) -> tuple[str, dict]:
        """
        Chama a API do OpenRouter

        Args:
            messages: Lista de mensagens formatadas
            model: Modelo a usar

        Returns:
            Tupla (resposta, usage_info)
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        payload_size = len(json.dumps(payload))
        logger.info(
            f"Preparando requisição ao OpenRouter - "
            f"Modelo: {model}, "
            f"Mensagens: {len(messages)}, "
            f"Payload: {payload_size} bytes"
        )

        logger.debug("=" * 80)
        logger.debug("PAYLOAD COMPLETO:")
        logger.debug(json.dumps(payload, indent=2, ensure_ascii=False))
        logger.debug("=" * 80)

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions", headers=headers, json=payload
                )

                logger.info(f"Status da resposta: {response.status_code}")

                if response.status_code != 200:
                    logger.error("=" * 80)
                    logger.error("ERRO NA RESPOSTA DO OPENROUTER:")
                    logger.error(f"Status Code: {response.status_code}")
                    logger.error(f"Headers: {dict(response.headers)}")
                    logger.error(f"Body: {response.text}")
                    logger.error("=" * 80)

                response.raise_for_status()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTPStatusError capturado: {e}")
            logger.error(f"Resposta do servidor: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao chamar OpenRouter: {e}", exc_info=True)
            raise

        result = response.json()

        response_text = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})

        logger.info(f"Resposta recebida com sucesso - Tokens usados: {usage}")

        return response_text, usage
