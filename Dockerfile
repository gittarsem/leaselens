FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/tmp/huggingface \
    FLASHRANK_CACHE_DIR=/tmp/flashrank \
    PORT=7860

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

RUN mkdir -p /tmp/huggingface /tmp/flashrank && chmod -R 777 /tmp/huggingface /tmp/flashrank
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')" || true
RUN python -c "from flashrank import Ranker; Ranker()" || true
RUN chmod -R 777 /tmp/huggingface /tmp/flashrank

COPY . .

EXPOSE 7860
CMD ["sh", "-c", "uvicorn api.server:app --host 0.0.0.0 --port ${PORT:-7860}"]
