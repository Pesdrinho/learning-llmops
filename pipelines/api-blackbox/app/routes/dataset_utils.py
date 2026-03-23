"""
Utilitários para Gerenciamento de Datasets de Fine-tuning

Funções auxiliares para exportar, validar e gerenciar datasets.
"""

import json
from typing import Any

from llmops_lab.db.connectors import AsyncDatabaseConnection
from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


async def export_dataset_to_jsonl(
    db: AsyncDatabaseConnection, dataset_name: str = "generated", output_path: str | None = None
) -> str:
    """
    Exporta dataset do banco para formato JSONL

    Args:
        db: Conexão com banco
        dataset_name: Nome do dataset a exportar
        output_path: Caminho para salvar (opcional)

    Returns:
        String JSONL ou path do arquivo salvo
    """
    query = """
        SELECT
            prompt,
            output,
            meta
        FROM finetune.ft_pairs
        WHERE dataset = $1
        ORDER BY created_at DESC
    """

    if not db.pool:
        await db.connect()

    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query, dataset_name)

    jsonl_lines = []
    for row in rows:
        # Reconstrói formato Qwen
        meta = json.loads(row["meta"]) if isinstance(row["meta"], str) else row["meta"]
        full_messages = meta.get("full_messages", [])

        if full_messages:
            jsonl_lines.append(json.dumps({"messages": full_messages}, ensure_ascii=False))

    jsonl_content = "\n".join(jsonl_lines)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(jsonl_content)
        logger.info(f"Dataset exportado para {output_path}: {len(jsonl_lines)} exemplos")
        return output_path

    return jsonl_content


async def get_dataset_statistics(
    db: AsyncDatabaseConnection, dataset_name: str | None = None
) -> dict[str, Any] | list[dict[str, Any]]:
    """
    Obtém estatísticas sobre datasets de fine-tuning

    Args:
        db: Conexão com banco
        dataset_name: Nome específico ou None para todos

    Returns:
        Dicionário com estatísticas (se dataset_name especificado) ou lista de dicionários (todos os datasets)
    """
    if not db.pool:
        await db.connect()

    async with db.pool.acquire() as conn:
        if dataset_name:
            query = """
                SELECT
                    dataset,
                    COUNT(*) as total_examples,
                    COUNT(DISTINCT meta->>'tool_name') as unique_tools,
                    AVG(quality_score) as avg_quality,
                    MIN(created_at) as first_created,
                    MAX(created_at) as last_created
                FROM finetune.ft_pairs
                WHERE dataset = $1
                GROUP BY dataset
            """
            result = await conn.fetchrow(query, dataset_name)
            return dict(result) if result else {}
        else:
            query = """
                SELECT
                    dataset,
                    COUNT(*) as total_examples,
                    COUNT(DISTINCT meta->>'tool_name') as unique_tools,
                    AVG(quality_score) as avg_quality,
                    MIN(created_at) as first_created,
                    MAX(created_at) as last_created
                FROM finetune.ft_pairs
                GROUP BY dataset
            """
            results = await conn.fetch(query)
            return [dict(row) for row in results]


async def update_quality_scores(db: AsyncDatabaseConnection, tool_name: str, score: float) -> int:
    """
    Atualiza quality_score para exemplos de uma tool específica

    Args:
        db: Conexão com banco
        tool_name: Nome da tool
        score: Score de qualidade (0.0-1.0)

    Returns:
        Número de registros atualizados
    """
    if not db.pool:
        await db.connect()

    query = """
        UPDATE finetune.ft_pairs
        SET quality_score = $1,
            is_validated = true
        WHERE meta->>'tool_name' = $2
          AND quality_score IS NULL
    """

    async with db.pool.acquire() as conn:
        result = await conn.execute(query, score, tool_name)

    # Extract number of updated rows from result string "UPDATE N"
    updated = int(result.split()[-1]) if result else 0
    logger.info(f"Updated quality_score={score} for {updated} examples of tool '{tool_name}'")

    return updated


async def split_dataset(
    db: AsyncDatabaseConnection,
    source_dataset: str = "generated",
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
) -> dict[str, int]:
    """
    Divide dataset em train/val/test

    Args:
        db: Conexão com banco
        source_dataset: Dataset de origem
        train_ratio: Proporção para treino
        val_ratio: Proporção para validação
        test_ratio: Proporção para teste

    Returns:
        Dict com contagens por split
    """
    if abs(train_ratio + val_ratio + test_ratio - 1.0) > 0.01:
        raise ValueError("Ratios devem somar 1.0")

    if not db.pool:
        await db.connect()

    async with db.pool.acquire() as conn:
        # Pega todos os IDs do dataset
        ids_query = """
            SELECT id FROM finetune.ft_pairs
            WHERE dataset = $1
            ORDER BY RANDOM()
        """
        rows = await conn.fetch(ids_query, source_dataset)
        ids = [row["id"] for row in rows]

        total = len(ids)
        train_end = int(total * train_ratio)
        val_end = train_end + int(total * val_ratio)

        train_ids = ids[:train_end]
        val_ids = ids[train_end:val_end]
        test_ids = ids[val_end:]

        # Atualiza datasets
        update_query = """
            UPDATE finetune.ft_pairs
            SET dataset = $1
            WHERE id = ANY($2::bigint[])
        """

        await conn.execute(update_query, "train", train_ids)
        await conn.execute(update_query, "val", val_ids)
        await conn.execute(update_query, "test", test_ids)

        logger.info(
            f"Dataset split: train={len(train_ids)}, val={len(val_ids)}, test={len(test_ids)}"
        )

        return {"train": len(train_ids), "val": len(val_ids), "test": len(test_ids), "total": total}
