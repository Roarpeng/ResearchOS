FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOCAL_OBJECTS_DIR=/data/objects \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md researchos_shared.py /app/
COPY knowledge /app/knowledge
COPY tools /app/tools
COPY gateway /app/gateway
COPY runtime /app/runtime
COPY agents /app/agents
COPY industrial /app/industrial

RUN pip install --no-cache-dir -e ".[dev,parsers]"

VOLUME ["/data/objects"]

ENTRYPOINT ["python", "-m", "knowledge.cli"]
CMD ["--help"]
