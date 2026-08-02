# GPU 与 Ollama

ResearchOS **不绑定**云模型。通过 LiteLLM 可将推理路由到本地 **Ollama**（或其他 OpenAI 兼容本地服务）。GPU 用于加速本地 LLM，以及 Phase 5 的 Isaac Sim 等仿真负载（仿真通常独立主机，不与 API 栈强行同容器）。

## 何时启用本地模型

| 场景 | 建议 |
|------|------|
| 演示 / 离线 POC | Ollama CPU 或小 GPU |
| 私有数据禁止出站 | 仅 Ollama / 内网 vLLM，关闭云 Key |
| 日常研发 | 云强模型 + 本地弱模型分流（摘要/嵌入可本地） |
| 工业现场气隙 | 预下载模型到 `ollama_models` 卷，断网运行 |

## Ollama 在 Compose 中的位置

```
Runtime / Knowledge Worker
        │
        ▼
     LiteLLM  ──model_name: local──►  Ollama (:11434)
        │
        └── model_name: default ──►  Cloud APIs（可选）
```

应用代码只看逻辑名 `local` / `default`，不直连 Ollama HTTP（便于日后换成 vLLM）。

## GPU Compose 覆盖（概念）

`deploy/docker-compose.gpu.yml`：

```yaml
services:
  ollama:
    profiles: ["gpu"]
    image: ollama/ollama:latest
    volumes:
      - ollama_models:/root/.ollama
    networks: [ros_internal]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped

volumes:
  ollama_models:
```

宿主机要求：

1. NVIDIA 驱动
2. [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
3. `docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi` 成功

无 GPU 时仍可跑 Ollama CPU，但吞吐量显著下降；此时建议仅用于嵌入或小参数对话模型。

## 模型拉取

进入 Ollama 容器或使用 API：

```bash
docker compose --profile gpu exec ollama ollama pull qwen2.5:14b
docker compose --profile gpu exec ollama ollama pull nomic-embed-text
```

嵌入模型可与对话模型分离：Knowledge Worker 的 embedding 走 `local-embed`，研究对话走 `local` 或云 `strong`。

LiteLLM 片段：

```yaml
model_list:
  - model_name: local
    litellm_params:
      model: ollama/qwen2.5:14b
      api_base: http://ollama:11434

  - model_name: local-embed
    litellm_params:
      model: ollama/nomic-embed-text
      api_base: http://ollama:11434
```

环境变量：

```bash
OLLAMA_BASE_URL=http://ollama:11434
LITELLM_DEFAULT_MODEL=local
EMBEDDING_MODEL_PROFILE=local-embed
```

## 资源与并发

| 模型体量 | 显存粗估 | 建议并发 |
|----------|----------|----------|
| 3B–7B | 6–10 GB | 2–4 |
| 14B | 12–16 GB+ | 1–2 |
| 32B+ | 24 GB+ | 1，慎用长上下文 |

在 Gateway/Runtime 侧对 `model_profile=local` 实施更严的 `max_steps` 与队列，避免打满 GPU。

## 与云模型混部策略

推荐路由策略：

1. **Planner / Reviewer**：`strong`（云）或高质量本地
2. **Research 工具循环中的短摘要**：`local` 或 `default` 轻量
3. **Writer 终稿**：`strong`
4. **Embedding**：尽量本地稳定模型，保证索引与查询同模型

通过任务 `options.model_profile` 与系统默认档位覆盖，而不是改代码。

## 气隙（Air-gap）操作

1. 有网环境 `ollama pull` 所需模型
2. 打包 `ollama_models` 卷或 `~/.ollama/models`
3. 导入目标环境卷
4. 清空所有云 API Key；LiteLLM 仅保留 `local*` 路由
5. 关闭 `enable_web` 默认值（配置层），仅企业知识库 + 本地工具

## Isaac Sim / 工业 GPU（Phase 5 前瞻）

- Isaac Sim 通常运行在独立 GPU 工作站或云 GPU 节点，经 MCP `isaac.*` 工具被 Agent 调用
- **不要**把 Isaac Sim 塞进与 PostgreSQL 相同的默认 Compose 文件；使用独立 `docker-compose.industrial.yml` 或外部 endpoint
- ResearchOS 核心栈的 GPU 优先级：先保证 LLM/嵌入；仿真按需连接

## 故障排查

| 现象 | 排查 |
|------|------|
| LiteLLM 502 到 Ollama | 容器网络、`OLLAMA_BASE_URL`、模型是否已 pull |
| CUDA 不可见 | Toolkit 安装、`nvidia-smi`、Compose `devices` 段 |
| 响应极慢 | 换小模型、减 `num_ctx`、限制并发任务 |
| 嵌入维度不匹配 | 更换 embed 模型后必须全量 reindex |

## 安全注意

- Ollama 端口仅挂载在 `ros_internal`，**不要**对公网暴露 `11434`
- 模型文件视为企业资产；备份与访问控制与 MinIO 同级讨论
- 本地模型仍可能产生幻觉：工业结论必须保留引用与人工审核门禁
