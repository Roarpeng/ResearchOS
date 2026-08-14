# Deploy (Phase 1)

Local data plane + LiteLLM + Gateway skeleton.

## 一键启动（Windows）

**拓扑约定：** 除 **TIA Openness CLI（必须 Windows）** 外，前端 nginx、Gateway、数据面全部跑 Docker。

仓库根目录双击或命令行（`.cmd` 为 ASCII，避免中文 Windows 控制台乱码）：

```bat
Start-ResearchOS.cmd
```

| 命令 | 行为 |
|------|------|
| `Start-ResearchOS.cmd` | Docker 全栈（**nginx 前端** + gateway + 数据面）；每次把当前 `frontend/` 打进镜像；准备 Windows Openness CLI |
| `Start-ResearchOS.cmd HostGateway` | 同上，但 Gateway 改本机进程以便调用 Openness 处理 `.ap19`（前端仍 Docker nginx） |
| `Start-ResearchOS.cmd Build` | 强制整栈 `docker compose --build`（需能解析 `auth.docker.io`） |
| `Stop-ResearchOS.cmd` | 停止宿主进程 + `docker compose down` |

PowerShell 等价：

```powershell
.\scripts\Start-ResearchOS.ps1
.\scripts\Start-ResearchOS.ps1 -HostGateway
.\scripts\Start-ResearchOS.ps1 -Build
.\scripts\Stop-ResearchOS.ps1
```

常用开关：`-SkipDocker` / `-SkipOpenness` / `-Build` / `-NoBuild`（跳过 frontend 镜像重建）/ `-HostGateway`。  
Full 启动会本机 `npm run build` + overlay 进 `researchos-frontend`（不依赖 Docker Hub 拉 node/nginx）。  
若本机已有镜像但 Docker Hub DNS 失败，勿加 `-Build`；脚本在 `-Build` 失败时也会自动回退到已有镜像。

Openness 为按需 Windows CLI（非常驻守护）；脚本会写入 `RESEARCHOS_TIA_OPENNESS_EXE`。  
Linux 容器内 **无法** 执行该 exe：日常用上传 `.zap` / SimaticML；需要 Gateway 直接 Openness 时用 `HostGateway`。  
日志与 PID：`.researchos/logs`、`.researchos/run`。

访问：Frontend http://localhost:5173（Docker nginx） · Gateway http://localhost:8000/api/v1/health/live

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
