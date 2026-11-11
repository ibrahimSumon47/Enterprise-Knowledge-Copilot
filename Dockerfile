# Image for the FastAPI service, built from the repository root.
# Render's default Dockerfile path is ./Dockerfile, so the build context is the
# repo root and every COPY below resolves without extra settings.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/appuser/.cache/huggingface \
    FASTEMBED_CACHE_PATH=/home/appuser/.cache/fastembed \
    FLASHRANK_CACHE_DIR=/home/appuser/.cache/flashrank

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd -m -u 1000 appuser

COPY api/ /app/
COPY data/corpus.jsonl /app/data/corpus.jsonl

RUN mkdir -p /home/appuser/.cache \
    && chown -R appuser /app /home/appuser

USER appuser

# Bake the ONNX weights into the image so a cold start does not download them.
RUN python -c "from fastembed import TextEmbedding; from flashrank import Ranker; list(TextEmbedding(model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2').embed(['warm up'])); Ranker(model_name='ms-marco-TinyBERT-L-2-v2', cache_dir='/home/appuser/.cache/flashrank')"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD curl -fsS "http://localhost:${PORT:-8000}/health" || exit 1

# Render injects PORT; fall back to 8000 for local docker runs.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
