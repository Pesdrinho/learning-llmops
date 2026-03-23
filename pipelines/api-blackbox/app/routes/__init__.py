"""
Rotas da API Blackbox

Módulo que organiza os diferentes endpoints de inferência.
"""

from routes.chat_completion import router as chat_completion_router
from routes.dataset_generator import router as dataset_generator_router
from routes.dataset_utils import (
    export_dataset_to_jsonl,
    get_dataset_statistics,
    split_dataset,
    update_quality_scores,
)

__all__ = [
    "chat_completion_router",
    "dataset_generator_router",
    "export_dataset_to_jsonl",
    "get_dataset_statistics",
    "split_dataset",
    "update_quality_scores",
]
