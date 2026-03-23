"""
Router OpenRouter - Cliente para OpenRouter API

OpenRouter é um gateway que unifica acesso a múltiplos provedores de LLM:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Meta (Llama)
- Mistral
- Google (Gemini)
- E muitos outros

Vantagens do OpenRouter:
1. **API Unificada**: Uma interface para todos os modelos
2. **Fallback Automático**: Se um modelo falha, tenta outro
3. **Preços Competitivos**: Routing inteligente para melhor custo-benefício
4. **Rate Limiting**: Gerenciado pelo OpenRouter
5. **Billing Centralizado**: Uma fatura, múltiplos providers

Como funciona:
    Nossa API → OpenRouter API → Provider (OpenAI/Anthropic/etc) → Modelo LLM

Documentação OpenRouter: https://openrouter.ai/docs
"""

import json
import os
from collections.abc import AsyncGenerator

import httpx
from models import ChatMessage, ChatRequest, UsageInfo
from tenacity import retry, stop_after_attempt, wait_exponential

from llmops_lab.logging.logger import get_logger
from llmops_lab.secrets.manager import get_secret

logger = get_logger(__name__)


class OpenRouterClient:
    """
    Cliente HTTP para OpenRouter API

    Responsabilidades:
    - Fazer chamadas ao OpenRouter
    - Converter formato das mensagens
    - Tratar erros e retry automático
    - Suportar streaming (opcional)

    Attributes:
        api_key: Chave da API OpenRouter
        base_url: URL base do OpenRouter
        client: Cliente HTTP async (httpx)
    """

    # URL base do OpenRouter
    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str | None = None):
        """
        Inicializa cliente OpenRouter

        Args:
            api_key: Chave da API OpenRouter (se None, busca do env/secrets)

        Raises:
            ValueError: Se API key não encontrada

        Exemplo:
            >>> client = OpenRouterClient()
            >>> # ou
            >>> client = OpenRouterClient(api_key="sk-or-...")
        """
        # Busca API key (ordem: parâmetro → Secret Manager → .env)
        self.api_key = api_key or get_secret("OPENROUTER_API_KEY")

        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY não encontrada. Configure em .env ou Secret Manager."
            )

        # Cria cliente HTTP
        # httpx = requests moderno, com suporte async
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": os.getenv("APP_URL", "http://localhost:8000"),
                "X-Title": "LLMOps Lab - API Blackbox",
            },
            timeout=60.0,  # Timeout de 60s (LLMs podem demorar)
        )

        logger.info("OpenRouterClient inicializado")

    async def __aenter__(self):
        """Context manager enter (async with)"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - fecha cliente"""
        await self.close()

    async def close(self):
        """Fecha conexões HTTP"""
        await self.client.aclose()
        logger.info("OpenRouterClient fechado")

    def _convert_messages(self, messages: list[ChatMessage]) -> list[dict]:
        """
        Converte mensagens do formato interno para OpenRouter

        Formato OpenRouter (compatível OpenAI):
            [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]

        Args:
            messages: Lista de ChatMessage (Pydantic)

        Returns:
            Lista de dicts no formato OpenRouter

        Exemplo:
            >>> client = OpenRouterClient()
            >>> msgs = [ChatMessage(role="user", content="Olá!")]
            >>> converted = client._convert_messages(msgs)
            >>> converted
            [{"role": "user", "content": "Olá!"}]
        """
        return [
            {"role": msg.role, "content": msg.content, **({"name": msg.name} if msg.name else {})}
            for msg in messages
        ]

    @retry(
        stop=stop_after_attempt(3),  # Máximo 3 tentativas
        wait=wait_exponential(multiplier=1, min=2, max=10),  # Backoff exponencial
        reraise=True,  # Re-levanta exceção após todas as tentativas
    )
    async def chat_completion(self, request: ChatRequest) -> dict:
        """
        Cria uma chat completion via OpenRouter

        Tenacity Retry Strategy:
        - Tenta até 3 vezes
        - Espera exponencial: 2s, 4s, 8s
        - Se falhar 3x, levanta exceção

        Por que retry?
        - APIs podem ter instabilidade momentânea
        - Rate limits temporários
        - Timeouts de rede

        Args:
            request: Objeto ChatRequest com parâmetros

        Returns:
            Dicionário com resposta do OpenRouter

        Raises:
            httpx.HTTPStatusError: Erro HTTP (4xx, 5xx)
            httpx.TimeoutException: Timeout

        Exemplo:
            >>> client = OpenRouterClient()
            >>> req = ChatRequest(
            ...     messages=[ChatMessage(role="user", content="Olá!")],
            ...     model="openai/gpt-4o-mini"
            ... )
            >>> resp = await client.chat_completion(req)
            >>> print(resp["choices"][0]["message"]["content"])
            "Olá! Como posso ajudar?"
        """
        # Converte mensagens
        messages = self._convert_messages(request.messages)

        # Monta payload no formato OpenRouter
        # Documentação: https://openrouter.ai/docs#models
        payload = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            **({"max_tokens": request.max_tokens} if request.max_tokens else {}),
            "stream": request.stream,
        }

        logger.debug(f"Enviando request para OpenRouter: {request.model}")

        try:
            # POST /chat/completions
            response = await self.client.post("/chat/completions", json=payload)

            # Levanta exceção se status 4xx ou 5xx
            response.raise_for_status()

            # Parse JSON
            data = response.json()

            logger.info(
                f"Resposta recebida: {data['usage']['total_tokens']} tokens | "
                f"Modelo: {data.get('model', request.model)}"
            )

            return data

        except httpx.HTTPStatusError as e:
            # Erros HTTP (400, 401, 403, 404, 429, 500, etc)
            logger.error(f"HTTP Error {e.response.status_code}: {e.response.text}")

            # Parse erro do OpenRouter
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", {}).get("message", str(e))
            except json.JSONDecodeError:
                error_msg = e.response.text

            # Re-levanta com mensagem clara
            raise Exception(f"OpenRouter API Error ({e.response.status_code}): {error_msg}") from e

        except httpx.TimeoutException as e:
            logger.error(f"Timeout ao chamar OpenRouter: {e}")
            raise Exception("Request ao OpenRouter expirou (timeout 60s)") from e

        except Exception as e:
            logger.error(f"Erro inesperado ao chamar OpenRouter: {e}")
            raise

    async def chat_completion_stream(self, request: ChatRequest) -> AsyncGenerator[dict, None]:
        """
        Cria chat completion com streaming (Server-Sent Events)

        Streaming = resposta enviada em chunks incrementais

        Vantagens do streaming:
        - Latência percebida menor (usuário vê resposta aparecendo)
        - Melhor UX para respostas longas
        - Permite cancelamento antecipado

        Formato SSE (Server-Sent Events):
            data: {"choices": [{"delta": {"content": "Ol"}}]}
            data: {"choices": [{"delta": {"content": "á!"}}]}
            data: [DONE]

        Args:
            request: ChatRequest com stream=True

        Yields:
            Dicionários com chunks de resposta

        Exemplo:
            >>> client = OpenRouterClient()
            >>> req = ChatRequest(
            ...     messages=[ChatMessage(role="user", content="Conte até 5")],
            ...     model="openai/gpt-4o-mini",
            ...     stream=True
            ... )
            >>> async for chunk in client.chat_completion_stream(req):
            ...     if "choices" in chunk:
            ...         delta = chunk["choices"][0].get("delta", {})
            ...         if "content" in delta:
            ...             print(delta["content"], end="", flush=True)
        """
        # Força stream=True
        request.stream = True

        messages = self._convert_messages(request.messages)

        payload = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            **({"max_tokens": request.max_tokens} if request.max_tokens else {}),
            "stream": True,
        }

        logger.debug(f"Iniciando stream para {request.model}")

        try:
            # Stream context
            async with self.client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()

                # Lê linha por linha (SSE)
                async for line in response.aiter_lines():
                    # Formato SSE: "data: {...}"
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: "

                        # Fim do stream
                        if data == "[DONE]":
                            break

                        # Parse JSON
                        try:
                            import json

                            chunk = json.loads(data)
                            yield chunk
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"Erro no streaming: {e}")
            raise

    def extract_usage(self, response: dict) -> UsageInfo:
        """
        Extrai informações de uso (tokens) da resposta

        Formato OpenRouter response:
            {
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30
                }
            }

        Args:
            response: Resposta do OpenRouter (dict)

        Returns:
            UsageInfo com contagem de tokens

        Exemplo:
            >>> client = OpenRouterClient()
            >>> response = await client.chat_completion(request)
            >>> usage = client.extract_usage(response)
            >>> print(f"Total: {usage.total_tokens} tokens")
        """
        usage_data = response.get("usage", {})

        return UsageInfo(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

    def extract_message(self, response: dict) -> ChatMessage:
        """
        Extrai a mensagem de resposta

        Formato OpenRouter response:
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "..."
                        }
                    }
                ]
            }

        Args:
            response: Resposta do OpenRouter

        Returns:
            ChatMessage com resposta do assistente

        Exemplo:
            >>> client = OpenRouterClient()
            >>> response = await client.chat_completion(request)
            >>> message = client.extract_message(response)
            >>> print(message.content)
            "Olá! Como posso ajudar?"
        """
        # Pega primeira choice (geralmente só há uma)
        choice = response["choices"][0]
        message_data = choice["message"]

        # Validação defensiva: conteúdo não pode estar vazio
        content = message_data.get("content", "").strip()
        if not content:
            logger.error(
                f"Modelo retornou resposta vazia! "
                f"Model: {response.get('model')}, "
                f"Finish reason: {choice.get('finish_reason')}"
            )
            raise ValueError(
                "O modelo retornou uma resposta vazia. "
                "Isso pode indicar um problema com o prompt ou com o modelo escolhido."
            )

        return ChatMessage(
            role=message_data["role"], content=content, name=message_data.get("name")
        )


# ========== FUNÇÃO HELPER ==========


async def create_openrouter_client() -> OpenRouterClient:
    """
    Factory function para criar cliente OpenRouter

    Útil para dependency injection no FastAPI.

    Returns:
        Cliente OpenRouter configurado

    Exemplo uso FastAPI:
        >>> from fastapi import Depends
        >>>
        >>> @app.post("/chat")
        >>> async def chat(
        ...     request: ChatRequest,
        ...     client: OpenRouterClient = Depends(create_openrouter_client)
        ... ):
        ...     response = await client.chat_completion(request)
        ...     return response
    """
    return OpenRouterClient()
