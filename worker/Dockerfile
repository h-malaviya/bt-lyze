FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

COPY api ./api
COPY worker ./worker

CMD ["uv", "run", "--no-dev", "arq", "worker.settings.WorkerSettings", "--custom-log-dict", "worker.settings.ARQ_LOG_CONFIG"]
