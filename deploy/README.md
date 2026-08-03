# Deploy (Phase 1)

Local data plane + LiteLLM + Gateway skeleton.

## Quick start

```bash
cp deploy/env/.env.example deploy/env/.env
# edit change_me_* values

cd deploy/compose
docker compose --env-file ../env/.env up -d
```

Gateway: http://localhost:8000/api/v1/health/live

## Profiles

| Profile | Services |
|---------|----------|
| (default) | postgres, redis, minio, qdrant, neo4j, litellm, gateway |
| `search` | opensearch |
| `export` | gotenberg |
| `automation` | n8n (**peripheral only**) |
| `gpu` | ollama |

```bash
docker compose --env-file ../env/.env --profile search --profile export up -d
```

## Smoke

```bash
./scripts/smoke_infra.sh
```
