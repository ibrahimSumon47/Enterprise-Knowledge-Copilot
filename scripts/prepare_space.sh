#!/usr/bin/env bash
# Stage the FastAPI service as a self-contained Hugging Face Space.
# The Space build context is the Space repo root, so paths are flattened here.
set -euo pipefail

rm -rf .space
mkdir -p .space/app .space/data

cp api/requirements.txt .space/requirements.txt
cp -r api/app/. .space/app/
cp data/corpus.jsonl .space/data/corpus.jsonl
cp api/README.md .space/README.md

cat > .space/Dockerfile <<'DOCKER'
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/data/hf \
    TRANSFORMERS_CACHE=/data/hf \
    SENTENCE_TRANSFORMERS_HOME=/data/hf \
    PORT=7860

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

RUN python - <<'PY'
from sentence_transformers import SentenceTransformer, CrossEncoder
SentenceTransformer("intfloat/multilingual-e5-small")
CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
PY

COPY app ./app
COPY data ./data

RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD curl -fsS http://localhost:7860/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
DOCKER

cat > .space/.gitignore <<'IGNORE'
.hf/
__pycache__/
*.pyc
IGNORE

echo "staged $(du -sh .space | cut -f1) in .space/"
