# 机器人与 ROS2

本文描述 ResearchOS 在机器人软件与 ROS2 生态中的扩展目标：让 Agent 能检索机器人工程知识、理解包与接口，并在护栏下辅助开发与选型研究。

## 问题域

工业与科研团队常见需求：

- 某型号协作臂的控制接口、力控能力与安全认证对比（选型研究）
- 在现有 ROS2 工作空间中查找「哪个包提供某消息/服务」
- 根据错误日志推断驱动、中间件或 TF 配置问题
- 生成或审查 `launch`、参数 YAML、QoS 建议（人工合并）

这些任务适合 Deep Research + 代码/工作空间 MCP，而不是一次性聊天。

## 架构位置

```
Industrial / Research Agent
        │
        ├── mcp-ros2        （工作空间内省、话题/节点只读、文档）
        ├── mcp-search/kb   （手册、标准、竞品白皮书）
        └── mcp-github      （开源驱动与 issue）
        │
        ▼
Hybrid GraphRAG（Robot / Driver / Standard 实体）
```

## MCP：`mcp-ros2`（目标能力）

| 工具 | 权限 | 说明 |
|------|------|------|
| `ros2.workspace.list_packages` | 读 | 列出工作空间包 |
| `ros2.pkg.inspect` | 读 | package.xml、依赖、导出接口 |
| `ros2.interface.show` | 读 | msg/srv/action 定义 |
| `ros2.topic.list` / `echo_sample` | 读 | 需连接运行中的 DDS 域；采样限长 |
| `ros2.node.info` | 读 | 节点图元数据 |
| `ros2.docs.search` | 读 | 本地 rosdistro 文档索引 |
| `ros2.codegen.suggest_launch` | 生成 | 返回建议文本，不直接写盘除非授权 |
| `ros2.workspace.apply_patch` | 写 | **默认关闭**；需 interrupt 批准 |

## ROS2 发行版与环境

- 通过环境变量声明目标 distro（如 `humble`、`jazzy`）
- MCP server 运行在含 ROS2 的容器或侧车中，与 Gateway 隔离
- 多机器人/多域：`ROS_DOMAIN_ID` 按工作空间配置，禁止 Agent 扫描未授权域

Compose 概念：`ros2-sidecar` profile，仅内部网络。

## 知识入库

建议进入知识空间的语料：

- 厂商手册 PDF、安全手册
- URDF/xacro 说明与变更记录
- 内部故障案例（脱敏）
- ISO 10218、ISO/TS 15066 等标准摘要（注意版权合规）

图谱抽取关注：Robot 型号 —HAS_FEATURE→ 力控；—IMPLEMENTS_STANDARD→ ISO/TS 15066；Driver —SUPPORTS→ ROS2 Distro。

## 研究模式示例

**查询**：对比 UR / Franka / 某国产臂在 ROS2 力控接口与安全认证上的差异。

**期望循环**：

1. Planner 拆解：规格、ROS2 驱动成熟度、认证、生态
2. Knowledge hybrid 检索内部测评 + 标准
3. Web MCP（若允许）取公开文档
4. Reviewer 检查引用与过时风险
5. Writer 输出选型报告；工业模板含「验证计划」章节

## 人机中断点

| 场景 | 默认策略 |
|------|----------|
| 仅调研报告 | `on_review` |
| 连接真实机器人 echo | 每次批准 |
| 写入工作空间文件 | 每次批准 + diff 预览 |
| 发送运动指令 | **禁止** 除非独立「运动控制」产品范围外扩并单独 ADR |

ResearchOS Phase 5 明确：**不做运动控制产品**；最多到「配置与诊断建议」。

## 与前端

`mode=industrial` 时控制台可显示「工具域：ROS2」标签与更醒目的中断条。不强制单独 App；同一 Research Console。

## 验收切片（建议）

1. 只读检查本地假工作空间包列表与接口展示
2. 针对「某 msg 定义」问题生成带引用说明
3. 关闭写工具时，Agent 无法调用 `apply_patch`
4. 报告含至少一条标准类 citation

## 非目标

- 替代完整 IDE / 调试器
- 自动在产线机器人上部署节点
- 保证生成代码不加测即可上线
