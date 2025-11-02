"""
Rotas da API Blackbox

Módulo que organiza os diferentes endpoints de inferência.
"""

from routes.chat_completion import router as chat_completion_router
from routes.dataset_generator import router as dataset_generator_router

__all__ = [
    "chat_completion_router",
    "dataset_generator_router",
]
