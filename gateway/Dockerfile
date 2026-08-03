# Build from repository root:
#   docker build -f gateway/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md researchos_shared.py ./
COPY gateway ./gateway

# Minimal install for gateway runtime (editable not required in image)
RUN pip install --upgrade pip \
    && pip install \
        "fastapi>=0.115.0" \
        "uvicorn[standard]>=0.32.0" \
        "pydantic>=2.9.0" \
        "pydantic-settings>=2.6.0" \
        "httpx>=0.27.0" \
        "redis>=5.2.0" \
        "asyncpg>=0.30.0" \
        "python-multipart>=0.0.12" \
        "PyJWT>=2.9.0" \
        "orjson>=3.10.0" \
        "structlog>=24.4.0" \
        "tenacity>=9.0.0"

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 --start-period=20s \
  CMD curl -sf http://127.0.0.1:8000/api/v1/health/live || exit 1

CMD ["uvicorn", "gateway.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
