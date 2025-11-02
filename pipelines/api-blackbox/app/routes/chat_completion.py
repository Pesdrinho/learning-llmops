"""
Rota de Chat Completion com Guardrails

Endpoint especializado para chat com validações e segurança.
"""

import time
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from guards.guardrail_chain import create_default_chain, create_financial_chain
from middleware.cost_limiter import CostLimiter
from middleware.pii_masker import masker
from models import ChatCompletionRequest, ChatResponse
from prompts.chat import get_chat_prompt
from router import OpenRouterClient

from llmops_lab.db.connectors import get_async_db
from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/chat/completion",
    response_model=ChatResponse,
    summary="Chat completion com guardrails",
    description="Endpoint de chat com validações de segurança e tópicos",
    responses={
        200: {"description": "Resposta gerada com sucesso"},
        400: {"description": "Request inválido ou guardrail violado"},
        429: {"description": "Limite diário de custo excedido"},
        500: {"description": "Erro interno do servidor"},
    },
)
async def chat_completion(request: ChatCompletionRequest, http_request: Request):
    """
    Chat completion com guardrails integrados

    Fluxo:
    1. Valida input com guardrails (topic + injection)
    2. Aplica prompt template apropriado
    3. Mascara PII
    4. Envia para LLM
    5. Valida output
    6. Registra log
    7. Retorna resposta
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    api_key = http_request.headers.get("Authorization", "").replace("Bearer ", "")

    logger.info(
        f"[{request_id}] Chat completion iniciado | "
        f"Modelo: {request.model} | "
        f"Guardrails: {request.enable_guardrails}"
    )

    guardrails_triggered = []

    try:
        if request.enable_guardrails:
            if request.conversation_type == "financial_advisor":
                guardrail_chain = create_financial_chain(strict=False)
            else:
                guardrail_chain = create_default_chain(allowed_topics=request.allowed_topics)

            user_content = "\n".join(
                [msg.content for msg in request.messages if msg.role == "user"]
            )

            input_valid, input_violations = guardrail_chain.validate_input(user_content)

            if not input_valid:
                guardrails_triggered = [v["guard"] for v in input_violations]
                logger.warning(f"[{request_id}] Guardrails violados: {guardrails_triggered}")

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Guardrail violation: {input_violations[0]['reason']}",
                )

        masked_messages = []
        for msg in request.messages:
            if masker.has_pii(msg.content):
                logger.warning(
                    f"[{request_id}] PII detectado: {masker.detect_pii_types(msg.content)}"
                )

            masked_content = masker.mask(msg.content)
            masked_msg = msg.model_copy(update={"content": masked_content})
            masked_messages.append(masked_msg)

        request.messages = masked_messages

        async with OpenRouterClient() as client:
            response = await client.chat_completion(request)
            usage = client.extract_usage(response)
            message = client.extract_message(response)

        if request.enable_guardrails:
            output_valid, output_violations = guardrail_chain.validate_output(message.content)

            if not output_valid:
                output_guards_triggered = [v["guard"] for v in output_violations]
                guardrails_triggered.extend(output_guards_triggered)
                logger.warning(
                    f"[{request_id}] Output guardrails violados: {output_guards_triggered}"
                )

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Output validation failed: {output_violations[0]['reason']}",
                )

        limiter = CostLimiter()
        cost_usd = limiter.calculate_cost(
            model=request.model,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )

        prompt_text = "\n".join([f"{m.role}: {m.content}" for m in masked_messages])
        response_text = message.content
        latency_ms = int((time.time() - start_time) * 1000)

        _, prompt_config = get_chat_prompt(request.conversation_type)

        db = get_async_db()
        if not db.pool:
            await db.connect()

        log_query = """
            INSERT INTO observability.llm_logs (
                user_id, model, provider,
                prompt_masked, response_masked,
                input_tokens, output_tokens, cost_usd,
                latency_ms, status,
                inference_type, guardrails_triggered, prompt_version
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """

        async with db.pool.acquire() as conn:
            await conn.execute(
                log_query,
                request.user_id or "anonymous",
                request.model,
                "openrouter",
                prompt_text,
                response_text,
                usage.prompt_tokens,
                usage.completion_tokens,
                cost_usd,
                latency_ms,
                "success",
                "chat_completion",
                guardrails_triggered if guardrails_triggered else None,
                prompt_config.version,
            )

        await limiter.record_spend(
            api_key=api_key or None, model=request.model, cost_usd=cost_usd, db=db
        )

        logger.info(
            f"[{request_id}] Chat completion concluído | "
            f"Tokens: {usage.total_tokens} | "
            f"Custo: ${cost_usd:.6f} | "
            f"Latência: {latency_ms}ms | "
            f"Guardrails: {guardrails_triggered or 'none'}"
        )

        return ChatResponse(
            message=message,
            model=request.model,
            usage=usage,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            created_at=datetime.now(),
            request_id=request_id,
        )

    except HTTPException:
        raise

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)

        logger.error(f"[{request_id}] Erro no chat completion: {e}", exc_info=True)

        try:
            db = get_async_db()
            if not db.pool:
                await db.connect()

            log_query = """
                INSERT INTO observability.llm_logs (
                    user_id, model, provider,
                    prompt_masked, response_masked,
                    latency_ms, status, inference_type
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """

            async with db.pool.acquire() as conn:
                await conn.execute(
                    log_query,
                    request.user_id or "anonymous",
                    request.model,
                    "openrouter",
                    "error",
                    str(e),
                    latency_ms,
                    "error",
                    "chat_completion",
                )
        except Exception:
            pass

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
