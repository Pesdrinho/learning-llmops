"""
Rota de Geração de Datasets

Endpoint para gerar datasets de fine-tuning no formato Qwen.
"""

import json
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from guards.guardrail_chain import create_dataset_generation_chain
from middleware.cost_limiter import CostLimiter
from models import ChatMessage, ChatRequest, DatasetGenerationRequest, DatasetGenerationResponse
from prompts.dataset_generation import (
    format_tool_schema,
    get_dataset_generation_prompt,
    get_diversity_description,
)
from router import OpenRouterClient

from llmops_lab.db.connectors import get_async_db
from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/chat/dataset-generator",
    response_model=DatasetGenerationResponse,
    summary="Geração de dataset para fine-tuning",
    description="Gera exemplos de treinamento no formato Qwen para tool calling",
    responses={
        200: {"description": "Dataset gerado com sucesso"},
        400: {"description": "Request inválido"},
        429: {"description": "Limite diário de custo excedido"},
        500: {"description": "Erro interno do servidor"},
    },
)
async def generate_dataset(request: DatasetGenerationRequest, http_request: Request):
    """
    Gera dataset de fine-tuning para tool calling

    Fluxo:
    1. Valida input
    2. Formata schema da tool
    3. Gera exemplos usando LLM
    4. Valida formato dos exemplos
    5. Retorna dataset formatado
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    api_key = http_request.headers.get("Authorization", "").replace("Bearer ", "")

    logger.info(
        f"[{request_id}] Dataset generation iniciado | "
        f"Tool: {request.tool_name} | "
        f"Exemplos: {request.num_examples}"
    )

    try:
        guardrail_chain = create_dataset_generation_chain()

        input_text = f"{request.tool_name}: {request.tool_description}"
        input_valid, input_violations = guardrail_chain.validate_input(input_text)

        if not input_valid:
            logger.warning(f"[{request_id}] Guardrails violados: {input_violations}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Guardrail violation: {input_violations[0]['reason']}",
            )

        prompt_template, prompt_config = get_dataset_generation_prompt()

        tool_schema_str = format_tool_schema(request.tool_schema)
        diversity_desc = get_diversity_description(request.diversity_level)

        formatted_prompt = prompt_template.format_messages(
            num_examples=request.num_examples,
            tool_name=request.tool_name,
            tool_description=request.tool_description,
            tool_schema=tool_schema_str,
            diversity_level=diversity_desc,
        )

        # Mapeamento de tipos LangChain -> ChatMessage
        role_mapping = {"human": "user", "ai": "assistant", "system": "system"}

        messages = [
            ChatMessage(role=role_mapping.get(msg.type, msg.type), content=msg.content)
            for msg in formatted_prompt
        ]

        chat_request = ChatRequest(
            messages=messages, model=request.model, temperature=0.7, max_tokens=4096
        )

        async with OpenRouterClient() as client:
            response = await client.chat_completion(chat_request)
            usage = client.extract_usage(response)
            message = client.extract_message(response)

        try:
            examples = json.loads(message.content)
        except json.JSONDecodeError:
            from guards.output_validator import OutputValidator

            validator = OutputValidator()
            extracted = validator.extract_json_from_text(message.content)

            if extracted is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="LLM did not return valid JSON for dataset generation",
                ) from None

            examples = extracted

        if not isinstance(examples, list):
            examples = [examples]

        # Log para debug
        logger.info(
            f"[{request_id}] Exemplos gerados: {len(examples)} | "
            f"Primeira amostra: {json.dumps(examples[0] if examples else {}, indent=2)[:200]}"
        )

        from guards.output_validator import create_dataset_validator

        validator = create_dataset_validator()
        validation_result = validator.validate_tool_calls(examples)

        if not validation_result.is_valid:
            logger.warning(
                f"[{request_id}] Exemplos não passaram na validação: "
                f"{validation_result.reason}. Tentando correção automática..."
            )

            # Tenta corrigir: se não tem 'messages', assume que cada item É uma mensagem
            # e encapsula no formato esperado
            corrected_examples = []
            for example in examples:
                if "messages" not in example and isinstance(example, dict):
                    # Se parece ser uma mensagem direta, encapsula
                    corrected_examples.append({"messages": [example]})
                else:
                    corrected_examples.append(example)

            # Valida novamente
            validation_result = validator.validate_tool_calls(corrected_examples)
            if validation_result.is_valid:
                examples = corrected_examples
                logger.info(f"[{request_id}] Correção automática bem-sucedida!")
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Dataset validation failed: {validation_result.reason}",
                )

        limiter = CostLimiter()
        cost_usd = limiter.calculate_cost(
            model=request.model,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )

        latency_ms = int((time.time() - start_time) * 1000)

        db = get_async_db()
        if not db.pool:
            await db.connect()

        async with db.pool.acquire() as conn:
            # 1. Log geral da geração
            log_query = """
                INSERT INTO observability.llm_logs (
                    user_id, model, provider,
                    prompt_masked, response_masked,
                    input_tokens, output_tokens, cost_usd,
                    latency_ms, status,
                    inference_type, prompt_version
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id
            """

            log_result = await conn.fetchrow(
                log_query,
                request.user_id or "anonymous",
                request.model,
                "openrouter",
                f"Tool: {request.tool_name}, Examples: {request.num_examples}",
                json.dumps({"examples_count": len(examples), "format": request.output_format}),
                usage.prompt_tokens,
                usage.completion_tokens,
                cost_usd,
                latency_ms,
                "success",
                "dataset_generation",
                prompt_config.version,
            )

            log_id = log_result["id"]

            # 2. Salva cada exemplo na tabela de fine-tuning
            ft_insert_query = """
                INSERT INTO finetune.ft_pairs (
                    prompt, output, meta, dataset, quality_score
                ) VALUES ($1, $2, $3, $4, $5)
            """

            saved_count = 0
            for idx, example in enumerate(examples):
                # Debug: log estrutura do exemplo
                logger.debug(
                    f"[{request_id}] Processando exemplo {idx + 1}: "
                    f"type={type(example)}, keys={list(example.keys()) if isinstance(example, dict) else 'N/A'}"
                )

                # Valida estrutura do exemplo
                if not isinstance(example, dict) or "messages" not in example:
                    logger.warning(
                        f"[{request_id}] Exemplo {idx + 1} com estrutura inválida, pulando: {example}"
                    )
                    continue

                messages = example.get("messages", [])
                if not messages or not isinstance(messages, list):
                    logger.warning(
                        f"[{request_id}] Exemplo {idx + 1} sem mensagens válidas, pulando"
                    )
                    continue

                # Extrai prompt (última mensagem do user)
                user_messages = [
                    msg for msg in messages if isinstance(msg, dict) and msg.get("role") == "user"
                ]
                prompt_text = user_messages[-1].get("content", "").strip() if user_messages else ""

                if not prompt_text:
                    logger.warning(f"[{request_id}] Exemplo {idx + 1} sem prompt válido, pulando")
                    continue

                # Extrai tool calls do assistant
                assistant_messages = [
                    msg
                    for msg in messages
                    if isinstance(msg, dict) and msg.get("role") == "assistant"
                ]

                output_data = {}
                if assistant_messages:
                    last_assistant = assistant_messages[-1]
                    if "tool_calls" in last_assistant and last_assistant["tool_calls"]:
                        tool_call = last_assistant["tool_calls"][0]
                        output_data = {
                            "tool": tool_call.get("name", request.tool_name),
                            "arguments": tool_call.get("arguments", {}),
                        }

                # Se não tem output válido, pula
                if not output_data:
                    logger.warning(
                        f"[{request_id}] Exemplo {idx + 1} sem tool_calls válidos, pulando"
                    )
                    continue

                # Metadados completos
                meta = {
                    "tool_name": request.tool_name,
                    "model_used": request.model,
                    "generation_request_id": request_id,
                    "log_id": log_id,
                    "example_index": idx,
                    "diversity_level": request.diversity_level,
                    "full_messages": messages,
                }

                # Insere no banco
                try:
                    await conn.execute(
                        ft_insert_query,
                        prompt_text,
                        json.dumps(output_data, ensure_ascii=False),
                        json.dumps(meta, ensure_ascii=False),
                        "generated",
                        None,
                    )
                    saved_count += 1
                    logger.debug(
                        f"[{request_id}] Exemplo {idx + 1} salvo com sucesso: "
                        f"prompt_len={len(prompt_text)}, tool={output_data.get('tool')}"
                    )
                except Exception as e:
                    logger.error(
                        f"[{request_id}] Erro ao salvar exemplo {idx + 1}: {e}", exc_info=True
                    )

            logger.info(
                f"[{request_id}] {saved_count}/{len(examples)} exemplos persistidos em finetune.ft_pairs"
            )

        await limiter.record_spend(
            api_key=api_key or None, model=request.model, cost_usd=cost_usd, db=db
        )

        logger.info(
            f"[{request_id}] Dataset generation concluído | "
            f"Exemplos gerados: {len(examples)} | "
            f"Persistidos: {len(examples)} | "
            f"Custo: ${cost_usd:.6f} | "
            f"Latência: {latency_ms}ms"
        )

        # Log de amostra dos exemplos para auditoria
        for i, example in enumerate(examples[:3]):  # Log primeiros 3 exemplos
            logger.debug(
                f"[{request_id}] Exemplo {i + 1}/{len(examples)}: "
                f"{json.dumps(example, ensure_ascii=False)[:300]}..."
            )

        return DatasetGenerationResponse(
            examples=examples,
            count=len(examples),
            format=request.output_format,
            tool_name=request.tool_name,
            cost_usd=cost_usd,
            model_used=request.model,
            latency_ms=latency_ms,
            created_at=datetime.now(),
            request_id=request_id,
        )

    except HTTPException:
        raise

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)

        logger.error(f"[{request_id}] Erro na geração de dataset: {e}", exc_info=True)

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
                    "dataset_generation",
                )
        except Exception:
            pass

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get(
    "/chat/dataset-generator/download/{request_id}",
    summary="Download dataset em formato JSONL",
    description="Baixa dataset gerado no formato JSONL para fine-tuning",
)
async def download_dataset(request_id: str, format: str = "jsonl"):
    """
    Endpoint alternativo para download de datasets gerados

    Nota: Esta implementação é simplificada. Em produção, você
    poderia armazenar datasets gerados e permitir download posterior.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Funcionalidade de download será implementada em versão futura",
    )
