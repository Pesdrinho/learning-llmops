"""
Pipeline RAG - Retrieval Augmented Generation

Composto por dois serviços:
1. vectorization_job: Processa documentos do GCS e gera embeddings
2. generation_api: API FastAPI para queries com RAG
"""
