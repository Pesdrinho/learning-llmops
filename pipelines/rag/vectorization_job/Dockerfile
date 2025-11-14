FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pipelines/rag/vectorization_job/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY llmops_lab/ /app/llmops_lab/
COPY pipelines/rag/vectorization_job/ /app/pipelines/rag/vectorization_job/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "pipelines.rag.vectorization_job.main"]
