# Deploy (Phase 1)

Local data plane + LiteLLM + Gateway skeleton.

## Quick start

```bash
cp deploy/env/.env.example deploy/env/.env
# edit change_me_* values

cd deploy/compose
docker compose --env-file ../env/.env up -d --build
```

- Gateway: http://localhost:8000/api/v1/health/live
- Frontend: http://localhost:5173 （compose 服务 `frontend`，nginx 反代 `/api` → gateway）
- LLM 配置 UI：前端 **LLM Settings**；API `GET/PUT /api/v1/settings/llm`

若本机 Docker 无法拉取镜像（DNS/代理），可先本机启动 Gateway + Vite：

```bash
uv run uvicorn gateway.app.main:app --host 0.0.0.0 --port 8000
cd frontend && npm run dev
```

## Profiles

| Profile | Services |
|---------|----------|
| (default) | postgres, redis, minio, qdrant, neo4j, litellm, gateway, **frontend** |
| `plc` | 同 default，并为 Gateway 注入 PLC 环境变量 / 工程目录挂载（见 [docs/deployment/06-plc-feature.md](../docs/deployment/06-plc-feature.md)） |
| `search` | opensearch |
| `export` | gotenberg |
| `automation` | n8n (**peripheral only**) |
| `gpu` | ollama |

```bash
docker compose --env-file ../env/.env --profile search --profile export up -d
# PLC Intelligence（XML/ZIP 可在容器 Gateway 解析；.ap19 需 Windows Openness 侧车）
docker compose --env-file ../env/.env --profile plc up -d
```

## Smoke

```bash
./scripts/smoke_infra.sh
```
