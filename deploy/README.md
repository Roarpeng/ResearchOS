# Deploy (Phase 1)

Local data plane + LiteLLM + Gateway skeleton.

## 一键启动（Windows）

仓库根目录双击或命令行：

```bat
Start-ResearchOS.cmd
```

| 命令 | 行为 |
|------|------|
| `Start-ResearchOS.cmd` | 启动 Docker Desktop（若未开）→ `compose --profile plc up` → 构建/校验 **TIA Openness** CLI |
| `Start-ResearchOS.cmd Hybrid` | Docker **仅数据面** + 本机 Gateway/Frontend + Openness（推荐 `.ap19` / 写回） |
| `Stop-ResearchOS.cmd` | 停止宿主进程 + `docker compose down` |

PowerShell 等价：

```powershell
.\scripts\Start-ResearchOS.ps1
.\scripts\Start-ResearchOS.ps1 -Mode Hybrid
.\scripts\Stop-ResearchOS.ps1
```

常用开关：`-SkipDocker` / `-SkipOpenness` / `-NoBuild`。

Openness 为按需 CLI（非常驻守护）；脚本会写入 `RESEARCHOS_TIA_OPENNESS_EXE`，Hybrid 下宿主 Gateway 使用 `RESEARCHOS_TIA_OPENNESS=cli`。  
日志与 PID：`.researchos/logs`、`.researchos/run`。

访问：Frontend http://localhost:5173 · Gateway http://localhost:8000/api/v1/health/live

## Quick start（手动）

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
