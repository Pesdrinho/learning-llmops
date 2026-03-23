import argparse
import asyncio
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llmops_lab.db.connectors import AsyncDatabaseConnection
from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


async def get_daily_costs(db: AsyncDatabaseConnection, days: int = 7) -> list[dict]:
    """Retorna custos diários dos últimos N dias"""
    query = """
        SELECT
            DATE(ts) as date,
            COUNT(*) as requests,
            SUM(input_tokens) as total_input_tokens,
            SUM(output_tokens) as total_output_tokens,
            SUM(cost_usd) as total_cost_usd,
            AVG(latency_ms) as avg_latency_ms
        FROM observability.llm_logs
        WHERE ts >= $1
        GROUP BY DATE(ts)
        ORDER BY DATE(ts) DESC
    """

    start_date = date.today() - timedelta(days=days)
    rows = await db.fetch(query, start_date)

    return [dict(row) for row in rows]


async def get_costs_by_model(db: AsyncDatabaseConnection, days: int = 7) -> list[dict]:
    """Retorna custos agrupados por modelo"""
    query = """
        SELECT
            model,
            COUNT(*) as requests,
            SUM(input_tokens) as total_input_tokens,
            SUM(output_tokens) as total_output_tokens,
            SUM(cost_usd) as total_cost_usd,
            AVG(latency_ms) as avg_latency_ms
        FROM observability.llm_logs
        WHERE ts >= $1
        GROUP BY model
        ORDER BY total_cost_usd DESC
    """

    start_date = date.today() - timedelta(days=days)
    rows = await db.fetch(query, start_date)

    return [dict(row) for row in rows]


async def get_budget_status(db: AsyncDatabaseConnection) -> dict:
    """Retorna status do budget diário"""
    query = """
        SELECT COALESCE(SUM(cost_usd), 0) as spent_today
        FROM observability.spend_ledger
        WHERE DATE(ts) = $1
    """

    row = await db.fetchrow(query, date.today())
    spent_today = Decimal(str(row["spent_today"]))

    # Budget configurado
    import yaml

    config_path = Path(__file__).parent.parent / "llmops_lab" / "config" / "models.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    daily_limit = Decimal(str(config.get("budget", {}).get("daily_limit_usd", 15.0)))

    return {
        "spent_today_usd": float(spent_today),
        "limit_usd": float(daily_limit),
        "remaining_usd": float(daily_limit - spent_today),
        "usage_pct": float(spent_today / daily_limit * 100) if daily_limit > 0 else 0,
    }


async def get_top_expensive_requests(db: AsyncDatabaseConnection, limit: int = 10) -> list[dict]:
    """Retorna requests mais caros"""
    query = """
        SELECT
            ts,
            model,
            input_tokens,
            output_tokens,
            cost_usd,
            latency_ms,
            status
        FROM observability.llm_logs
        WHERE ts >= $1
        ORDER BY cost_usd DESC
        LIMIT $2
    """

    start_date = datetime.now() - timedelta(days=7)
    rows = await db.fetch(query, start_date, limit)

    return [dict(row) for row in rows]


def format_currency(value: float) -> str:
    """Formata valor como moeda"""
    return f"${value:.4f}"


def format_number(value: int) -> str:
    """Formata número com separador de milhares"""
    return f"{value:,}"


def print_report(daily_costs, costs_by_model, budget_status, top_requests):
    """Imprime relatório formatado"""

    print()
    print("=" * 80)
    print(" " * 25 + "RELATÓRIO DE CUSTOS - LLMOps Lab")
    print("=" * 80)
    print()

    # Budget do dia
    print("📊 STATUS DO BUDGET (HOJE)")
    print("-" * 80)
    print(f"Gasto:       {format_currency(budget_status['spent_today_usd'])}")
    print(f"Limite:      {format_currency(budget_status['limit_usd'])}")
    print(f"Disponível:  {format_currency(budget_status['remaining_usd'])}")
    print(f"Uso:         {budget_status['usage_pct']:.1f}%")

    # Indicador visual
    bar_length = 40
    filled = int(budget_status["usage_pct"] / 100 * bar_length)
    bar = "█" * filled + "░" * (bar_length - filled)
    print(f"\n[{bar}] {budget_status['usage_pct']:.1f}%")
    print()

    # Custos diários
    print("📅 CUSTOS DIÁRIOS (ÚLTIMOS 7 DIAS)")
    print("-" * 80)
    print(f"{'Data':<12} {'Requests':>10} {'Input Tokens':>15} {'Output Tokens':>15} {'Custo':>12}")
    print("-" * 80)

    total_requests = 0
    total_input = 0
    total_output = 0
    total_cost = 0

    for row in daily_costs:
        total_requests += row["requests"]
        total_input += row["total_input_tokens"] or 0
        total_output += row["total_output_tokens"] or 0
        total_cost += row["total_cost_usd"] or 0

        print(
            f"{row['date']!s:<12} "
            f"{row['requests']:>10,} "
            f"{row['total_input_tokens'] or 0:>15,} "
            f"{row['total_output_tokens'] or 0:>15,} "
            f"{format_currency(row['total_cost_usd'] or 0):>12}"
        )

    print("-" * 80)
    print(
        f"{'TOTAL':<12} "
        f"{total_requests:>10,} "
        f"{total_input:>15,} "
        f"{total_output:>15,} "
        f"{format_currency(total_cost):>12}"
    )
    print()

    # Custos por modelo
    print("🤖 CUSTOS POR MODELO")
    print("-" * 80)
    print(f"{'Modelo':<40} {'Requests':>10} {'Tokens':>15} {'Custo':>12}")
    print("-" * 80)

    for row in costs_by_model[:10]:  # Top 10
        total_tokens = (row["total_input_tokens"] or 0) + (row["total_output_tokens"] or 0)
        print(
            f"{row['model']:<40} "
            f"{row['requests']:>10,} "
            f"{total_tokens:>15,} "
            f"{format_currency(row['total_cost_usd'] or 0):>12}"
        )
    print()

    # Top requests mais caros
    print("💰 TOP 10 REQUESTS MAIS CAROS")
    print("-" * 80)
    print(f"{'Timestamp':<20} {'Modelo':<25} {'Tokens':>10} {'Custo':>12}")
    print("-" * 80)

    for row in top_requests:
        total_tokens = (row["input_tokens"] or 0) + (row["output_tokens"] or 0)
        ts = row["ts"].strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"{ts:<20} "
            f"{row['model']:<25} "
            f"{total_tokens:>10,} "
            f"{format_currency(row['cost_usd'] or 0):>12}"
        )

    print()
    print("=" * 80)
    print()


async def main():
    parser = argparse.ArgumentParser(description="Relatório de custos LLMOps Lab")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Número de dias para análise (padrão: 7)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Formato de output (padrão: text)",
    )

    args = parser.parse_args()

    # Conecta ao banco
    db = AsyncDatabaseConnection()
    await db.connect()

    try:
        # Coleta dados
        daily_costs = await get_daily_costs(db, args.days)
        costs_by_model = await get_costs_by_model(db, args.days)
        budget_status = await get_budget_status(db)
        top_requests = await get_top_expensive_requests(db)

        if args.format == "json":
            import json

            report = {
                "budget_status": budget_status,
                "daily_costs": daily_costs,
                "costs_by_model": costs_by_model,
                "top_expensive_requests": top_requests,
            }
            print(json.dumps(report, indent=2, default=str))
        else:
            print_report(daily_costs, costs_by_model, budget_status, top_requests)

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
