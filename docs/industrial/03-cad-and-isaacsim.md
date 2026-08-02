# CAD 与 Isaac Sim

本文覆盖两类工程智能扩展：**CAD 资产理解**与 **Isaac Sim 仿真试验**。二者通过 MCP 接入 Agent，服务方案验证、干涉/可达性讨论、以及仿真指标驱动的研究报告。

## 共同原则

- 大文件走 MinIO；Agent 只持有 object key 与元数据
- 仿真与 CAD 内核运行在独立算力节点，失败不得拖垮 Gateway
- 昂贵操作（导入复杂装配、长时仿真）默认 `human_interrupt`
- 结果写回任务 `artifacts` 与可选知识库，形成可追溯试验记录

---

## CAD

### 目标能力

- 提取零件/装配元数据（名称、数量、材料属性若存在）
- 从说明文档与模型注释对齐 BOM 线索
- 对照标准件库与企业内部选型规范做研究问答
- 生成「设计变更影响」研究草稿（仍需工程师确认）

### MCP：`mcp-cad`

| 工具 | 说明 |
|------|------|
| `cad.asset.register` | 注册 MinIO 中的 STEP/IGES/厂商格式衍生件 |
| `cad.meta.extract` | 元数据与粗略结构树 |
| `cad.bom.suggest` | 基于结构树与知识库的 BOM 建议 |
| `cad.view.thumbnail` | 生成预览图（异步作业） |
| `cad.diff.revisions` | 两版本结构差异（若可解析） |

完整几何内核（Occt 等）可作为 worker 依赖；超时与内存上限必配。

### 知识图谱

`CADModel`—CONTAINS→`Part`；`Part`—REFERENCES→`Standard`；`Assembly`—USED_IN→`Robot`/`Cell`。

### 护栏

- 不覆盖 PLM 系统中的正式版本；只读同步或导出副本
- 专有格式注意许可证；优先中性格式（STEP）做研究副本

---

## Isaac Sim

### 目标能力

- 在沙箱中加载场景（USD）并运行规定时长的试验
- 回报指标：碰撞次数、末端轨迹误差、周期时间等（由场景定义）
- 将试验配置与指标写入报告，支持方案对比研究
- 与 ROS2 sidecar 可选联调（仍属沙箱）

### 部署形态

Isaac Sim **不**进入默认 `docker-compose.yml` 核心路径。推荐：

```
deploy/docker-compose.industrial.yml  →  isaac-mcp 代理
独立 GPU 主机 / NGC 容器             →  真实 Isaac Sim
```

Agent 经 `mcp-isaac` 调用代理；代理负责队列、配额与结果回收到 MinIO。

### MCP：`mcp-isaac`

| 工具 | 说明 |
|------|------|
| `isaac.scene.list` | 可用场景模板 |
| `isaac.trial.submit` | 提交试验（参数：场景、时长、种子、机器人资产） |
| `isaac.trial.status` | 作业状态 |
| `isaac.trial.artifacts` | 日志、指标 JSON、视频/截图 object keys |
| `isaac.trial.cancel` | 取消排队或运行中试验 |

### 资源治理

| 项 | 建议 |
|----|------|
| 并发试验 / 工作空间 | 1–2 |
| 最大时长 | 可配，默认 ≤ 30 min |
| GPU 队列 | FIFO + 用户配额 |
| 费用/算力提示 | 提交前 interrupt 展示预估 |

### 与研究 API 的结合

`mode=industrial` 且工具白名单含 `isaac.*` 时：

1. Planner 可提出「仿真验证」步骤
2. 提交前 `interrupt.required`（确认场景与时长）
3. Worker 异步跑完 → `tool.finished` + artifacts
4. Writer 将指标表写入报告「仿真验证」节并引用 artifact

---

## 端到端示例

**查询**：评估某末端夹爪在窄通道抓取场景的碰撞风险，对比两种安装姿态。

1. CAD MCP 注册夹爪与通道模型副本  
2. 映射到 Isaac 场景模板  
3. 两次 `trial.submit`（姿态 A/B）  
4. 回收碰撞与周期指标  
5. 生成对比报告 + 视频链接（预签名）  

## 验收切片

1. CAD：STEP 样本提取结构树与缩略图作业成功  
2. Isaac：mock 后端可走通 submit→status→artifacts（无 GPU 的 CI）  
3. 真实 GPU 环境：短场景试验指标 JSON schema 稳定  
4. 未批准时 `trial.submit` 被 Gateway/Runtime 拒绝  

## 非目标

- 取代专业 CAD/PLM 平台  
- 在 CI 中默认运行完整 Isaac（过重）；CI 只用 mock  
- 由 Agent 自动签发量产设计变更  

## 路线建议

1. 先 CAD 元数据 + 知识库（无 GPU）  
2. 再 Isaac mock MCP 打通任务产物  
3. 最后接真实 GPU 节点与 ROS2 联调  

与 [03-gpu-and-ollama.md](../deployment/03-gpu-and-ollama.md) 一致：核心 LLM GPU 与仿真 GPU 资源池分离规划。
