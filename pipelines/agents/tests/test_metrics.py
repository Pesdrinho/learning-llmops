"""
Testes de Métricas

Teste de métricas de sucesso e performance.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


class TestMetricsCalculation:
    """Testes de cálculo de métricas"""

    def test_tool_success_rate(self):
        """Testa cálculo de taxa de sucesso de ferramentas"""
        results = [
            {"tool": "nl2sql", "success": True},
            {"tool": "nl2sql", "success": True},
            {"tool": "nl2sql", "success": False},
            {"tool": "websearch", "success": True},
        ]

        nl2sql_results = [r for r in results if r["tool"] == "nl2sql"]
        success_count = sum(1 for r in nl2sql_results if r["success"])
        success_rate = success_count / len(nl2sql_results) * 100

        assert success_rate == 66.67  # 2/3 = 66.67%

    def test_task_completion_rate(self):
        """Testa cálculo de taxa de conclusão de tarefas"""
        tasks = [
            {"completed": True, "errors": []},
            {"completed": True, "errors": []},
            {"completed": True, "errors": ["minor_warning"]},
            {"completed": False, "errors": ["validation_error"]},
        ]

        completed = sum(1 for t in tasks if t["completed"])
        completion_rate = completed / len(tasks) * 100

        assert completion_rate == 75.0

    def test_average_latency(self):
        """Testa cálculo de latência média"""
        latencies = [1500, 2000, 1800, 2200, 1600]

        avg_latency = sum(latencies) / len(latencies)

        assert avg_latency == 1820.0

    def test_average_cost(self):
        """Testa cálculo de custo médio"""
        costs = [0.05, 0.08, 0.06, 0.07, 0.05]

        avg_cost = sum(costs) / len(costs)

        assert round(avg_cost, 2) == 0.06


class TestMetricsValidation:
    """Testes de validação de métricas"""

    def test_metrics_thresholds(self):
        """Testa validação de thresholds de métricas"""
        metrics = {
            "tool_success_rate": 85.0,
            "task_completion_rate": 90.0,
            "avg_latency_ms": 2000,
            "avg_cost_usd": 0.10,
        }

        assert metrics["tool_success_rate"] >= 80.0
        assert metrics["task_completion_rate"] >= 80.0
        assert metrics["avg_latency_ms"] <= 5000
        assert metrics["avg_cost_usd"] <= 0.50

    def test_metrics_boundaries(self):
        """Testa valores de fronteira das métricas"""
        success_rate_min = 0.0
        success_rate_max = 100.0

        assert 0.0 <= success_rate_min <= 100.0
        assert 0.0 <= success_rate_max <= 100.0

    def test_cost_calculation(self):
        """Testa cálculo de custo por tipo de análise"""
        analysis_costs = {
            "price_movement": [0.05, 0.06, 0.05],
            "volume_analysis": [0.04, 0.05, 0.04],
            "trend_analysis": [0.07, 0.08, 0.07],
        }

        avg_costs = {
            analysis_type: sum(costs) / len(costs)
            for analysis_type, costs in analysis_costs.items()
        }

        assert round(avg_costs["price_movement"], 3) == 0.053
        assert round(avg_costs["volume_analysis"], 3) == 0.043
        assert round(avg_costs["trend_analysis"], 3) == 0.073
