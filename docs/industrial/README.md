# 工业扩展（Phase 5）

Phase 5 **Engineering Intelligence / Engineering Copilot** 将 ResearchOS 从通用 Deep Research 延伸到工业与机器人工程场景：在同一套 Agent Runtime、MCP、Hybrid GraphRAG 之上，增加 Robotics、PLC、ROS2、Isaac Sim、CAD 等领域能力。

## 文档索引

| 文档 | 内容 |
|------|------|
| [01-robotics-and-ros2.md](./01-robotics-and-ros2.md) | 机器人知识、ROS2 工具与研究模式 |
| [02-plc-and-automation.md](./02-plc-and-automation.md) | PLC、工控自动化助手边界 |
| [03-cad-and-isaacsim.md](./03-cad-and-isaacsim.md) | CAD 资产与 Isaac Sim 仿真联动 |

## 为什么是「扩展」而不是新系统

工业场景仍需要：

- 多源调研（标准、手册、专利、竞品）
- 企业知识沉淀（图纸说明、故障案例、参数表）
- 可引用报告与人工审核

这些由 Phase 1–4 的平台能力提供。Phase 5 增加的是 **领域 MCP 工具、图谱本体扩展、模型/仿真桥、安全护栏**。

## 阶段依赖

```
Phase 0–1  基础设施
Phase 2    Agent Runtime + 流式 + interrupt
Phase 3    Hybrid GraphRAG
Phase 4    Deep Research Agent
Phase 5    工业扩展（本目录）
```

未完成 Phase 2–4 前，不建议实现真实设备写操作；可先做只读知识与离线仿真。

## 能力地图

| 域 | Agent 能做什么（目标） | 严格限制 |
|----|----------------------|----------|
| Robotics / ROS2 | 查包、读接口、生成 launch/参数建议、对比驱动 | 默认不直接写生产机器人 |
| PLC | 解读梯形图/结构化文本片段、对照手册、生成变更建议 | 不下发未审核程序到 PLC |
| CAD | 解析元数据、BOM 线索、标准件对照 | 不静默覆盖工程库原文件 |
| Isaac Sim | 启动场景、跑试验、回收指标 | 隔离 GPU 节点；资源配额 |

## 统一接入方式：MCP

所有工业能力以 MCP Server 暴露，例如：

- `mcp-ros2`
- `mcp-plc`
- `mcp-cad`
- `mcp-isaac`

Research / Industrial Agent 经工具注册表发现能力；Gateway 不实现工业协议细节。

## 知识本体扩展（GraphRAG）

在核心实体之外增加（示例）：

- `Robot`、`EndEffector`、`Controller`、`Driver`
- `PLC`、`IOPoint`、`LadderRoutine`、`AlarmCode`
- `CADModel`、`Part`、`Assembly`、`Material`
- `SimulationScene`、`TrialRun`

关系示例：`CONTROLLED_BY`、`MOUNTS`、`IMPLEMENTS_STANDARD`、`HAS_IO`、`SIMULATED_IN`。

## 任务模式

研究 API `mode=industrial`：

- 默认挂载工业 MCP 白名单
- 更严格的 human interrupt（涉及设备/仿真高成本时）
- 报告模板含「安全与验证」章节
- 可关闭公网搜索，仅企业库 + 标准库

## 安全总则

1. **默认只读**：对现场设备的写操作必须显式启用 + 双人批准（interrupt）
2. **环境隔离**：仿真/PLC 试验与生产网络分段
3. **审计**：工具调用入参出参摘要进任务产物
4. **标准优先**：安全相关结论必须引用 ISO/IEC/国标等，禁止裸模型断言

## 实现状态

- **PLC 只读切片（已落地）**：`agents/plc`（手册对照 / 变更建议 / 安全核查 / 可选 TIA→KG+SCL）+ `tools/plc` mcp-plc（`plc.manual.*` / `plc.alarm.explain` / `plc.tia.analyze`；下载永拒）+ `industrial/tia_adapter` Openness 导出。`mode=industrial` 时 Planner 插入 `plc` 步骤；可通过 `tia_export_dir` / `RESEARCHOS_TIA_EXPORTS` 指向你的导出目录。CLI：`researchos-tia-cli`。测试：`tests/unit/test_plc_agent.py`、`tests/unit/test_tia_pipeline.py`。
- Architecture Phase：其余域（ROS2 / CAD / Isaac Sim）仍为目标架构与边界描述。代码落地应单开 ADR，并先以「知识只读 + 仿真沙箱」垂直切片验收。
