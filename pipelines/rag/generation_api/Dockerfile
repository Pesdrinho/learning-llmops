FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pipelines/rag/generation_api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY llmops_lab/ /app/llmops_lab/
COPY pipelines/rag/generation_api/ /app/pipelines/rag/generation_api/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8888

EXPOSE 8888

CMD ["uvicorn", "pipelines.rag.generation_api.main:app", "--host", "0.0.0.0", "--port", "8888", "--reload", "--log-level", "info"]
