FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY runtime ./runtime
COPY agents ./agents
COPY tools ./tools
COPY researchos_shared.py ./

RUN pip install --no-cache-dir -e .

ENV RUNTIME_HOST=0.0.0.0
ENV RUNTIME_PORT=8100
ENV DEV_AUTO_APPROVE=true
ENV MCP_HELLO_MODE=inprocess

EXPOSE 8100

CMD ["uvicorn", "runtime.researchos_runtime.server:app", "--host", "0.0.0.0", "--port", "8100"]
