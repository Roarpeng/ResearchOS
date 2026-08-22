# Industrial Intelligence Roadmap

> 实施状态以代码为准；本文件与 `ROADMAP.md` Phase 5 同步维护。

## Phase 1 Industrial Foundation — Done

- [x] Industrial Knowledge Model（`agents/plc/tia/kg.py`：Project/Block/Variable/Network/TagTable/Tag）
- [x] MCP Framework（`tools/_mcp_compat.py` + 各 server；安全基座 `tools/security.py`：scope 目录、角色画像、SSRF 防护、配额、审计）

## Phase 2 TIA Integration — Done

- [x] Openness Server（C# net481 stdio，V17–V20 反射兼容，15 个工具）
- [x] Project Reader（`surface.py` 全表面：UDT/标签/监视/强制/TO/报警/ProDiag/CFC/Safety/HMI/OPC UA/硬件 AML）
- [x] XML Export（`openness_cli.py` + `industrial/tia_adapter/ExportProject.ps1`，Linux 免 PowerShell 路径）

## Phase 3 PLC Intelligence — Done

- [x] PLC Parser（SimaticML LAD/FBD/STL/SCL/GRAPH；折叠覆盖 CoilTON/数学框/CALCULATE/系统时间/FBD 门等）
- [x] PLC IR（表达式代数 AND/OR/NOT/Arith/Func/Raw + AssignStmt + GraphStep）
- [x] Graph Import（块级 CALLS/WRITES/READS/TYPED_AS/NEXT + **设备层 Device/TechnologyObject/Alarm + HAS_DEVICE/RUNS_TO/HAS_ALARM**；Neo4j 发布或内存图）

## Phase 4 Engineering Copilot — Done（只读闭环）+ HITL 写回

- [x] PLC Review（死块/多写者/无联锁输出/安规写入分析，引用门禁）
- [x] Code Generation（SCL 规则翻译 + `TODO[]` 结构化兜底 + LLM 提示）
- [x] Optimization（解耦提取、SCL 改写、多实例耦合、HITL 确认计划）
- [x] 只读对话检索（KG 边 + SCL 片段 citation，不臆造 CALLS）
- [x] 写回闭环（ChangeSet → import_bundle → Openness Import → 编译门禁 → `.zap` 归档；F 块拒绝、Know-how 不解密、路径白名单）
- [x] 新增只读工具：`plc.st.parse` / `plc.ld.summarize` / `plc.diff.routines`（KG 边差集）/ `plc.opcua.read`（锁定占位）
- [x] 手册检索知识化：`KnowledgeBackedPlcDocsConnector`（知识库优先，静态目录兜底）
- [x] Motion Agent / Failure Analysis Agent（只读：轴链视图 / 5-Why 反向追踪，证据仅引真实图边）

## Phase 5 Digital Twin — Mock 闭环 Done / 真机待接

- [x] ROS2：只读工作区扫描（package.xml/msg/srv/action 解析）+ `mcp-ros2`（codegen 默认关闭）
- [x] IsaacSim：`mcp-isaac` mock 后端走通 `submit(approval 门禁)→status→artifacts`（指标按种子确定，CI 可断言；真实 GPU 节点经代理接入）
- [x] CAD：`mcp-cad` STEP 结构树/版本差集/BOM 知识检索（无几何内核；缩略图作业显式禁用）
- [ ] Robot/AGV 域模型：待定义
- [ ] 真实 GPU 环境：短场景试验指标 JSON schema 与 NGC 容器对接

## 后续候选（按影响排序）

1. Isaac Sim 仿真任务 MCP（mock 打通产物流）
2. 多项目/租户知识隔离仪表盘（Gateway 聚合视图）
3. Graphiti 时序知识层选型验证（Neo4j 主路径不变）
4. OPC UA 只读网关（需现场环境与安全评审）
