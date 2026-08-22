# ADR-0008: PLC Gateway 与 Workbench 模块边界

## Status

Accepted

## Context

PLC 网关能力最初集中在 `gateway/app/services/plc_jobs.py`，前端工作台逻辑集中在 `frontend/src/App.tsx`。随着上传解析、知识图谱构建、SCL 展示、模块理解、优化建议和 HITL 回写继续增长，这两个入口成为高风险修改点：

- 后端难以区分作业存储、摄取编排、聊天路由、证据渲染和回写职责。
- 前端领域转换、工作台状态和面板组合耦合在同一个组件树中。
- Routers、Chat services 和 focused tests 已经依赖 `plc_jobs.py` 的稳定导入面。

## Decision

### 后端

`gateway/app/services/plc_jobs.py` 保持为 **compatibility facade**，继续暴露既有公共符号、编排缝和测试缝。实现放在内聚的 `gateway/app/services/plc/` 子模块中：

| Module | Ownership |
|---|---|
| `paths.py` | 上传保存、允许路径、zip 安全 |
| `job_store.py` | Job CRUD、进度、分析、导出、聊天记录 |
| `ingest.py` | TIA 导入编排、IR block 列表、源 XML 收集 |
| `logic_graph.py` | OB 扫描周期图与逻辑图刷新 |
| `changesets.py` | 变更提议、优化提议、HITL 回写编排 |
| `chat_intents.py` | 聊天意图与 @ 提示解析 |
| `evidence/` | 聊天证据抽取与渲染包；模块职责见下表 |
| `chat_evidence.py` | 兼容层：re-export `evidence/*` 的既有私有助手 |
| `writeback_views.py` | 回写确认、优化预览与执行 recap |
| `chat_router.py` | 聊天响应路由与编排 |

### Evidence Package

`gateway/app/services/plc/evidence/` 是当前的证据实现边界：

| Module | Ownership |
|---|---|
| `blocks.py` | Block 元数据、查询聚焦、关联关系、IO 标记和网络标题 |
| `cards.py` | 模块理解卡片、功能描述和运行时解释 |
| `instances.py` | KG 实例查找与 evidence-gated 实例描述 |
| `nested.py` | Typed AS 嵌套负载与嵌套 FB 展示 |
| `optimize.py` | 优化提示和风险提示的紧凑渲染 |
| `scl.py` | SCL 表达式转换、Folded 逻辑提取、来源解析和 Markdown 渲染 |
| `shared.py` | 共享日志、文本截断和网络标题解析工具 |
| `signal.py` | 信号追踪渲染 |

### 前端

`frontend/src/App.tsx` 只保留应用级组装。PLC 领域模型和工作台数据变换放在 `frontend/src/plc/`：

- `canvasModel.ts`: job 到 knowledge canvas 的规范化与派生模型。
- `detail.ts`: 进度、回写提示、SCL diff 和详情展示变换。
- `CoverageStrip.tsx`: PLC 覆盖度展示。
- `usePlcWorkspace.ts`: topics、active job、消息、上传草稿、busy/status、interrupts、canvas、chat scope、events、citations 和视图 tab 的 workspace 状态与编排。

面板级组合放在 `frontend/src/workbench/`：

- `useTriSplit.ts` / `layout.ts`: 三栏布局、尺寸约束和折叠状态。
- `model.ts`: chat、scope、citation 与工作台消息模型。
- `collections.ts`: events、interrupts 和 citations 的合并规则。
- `HistoryPane.tsx`: 历史话题列表、打开、新建、删除和折叠交互。
- `ChatPane.tsx`: 对话面板组合，包括 composer、scope prompts、interrupt bar 和消息列表。
- `ChatMessages.tsx`: 聊天消息列表的组合与交互。
- `ResearchWorkspace.tsx`: 研究视图组合，包括 canvas/timeline/citations tab、知识画布、覆盖度和 PLC 操作。
- `SettingsModal.tsx`: 设置弹窗容器。

## Compatibility Rules

1. Routers、跨服务调用方和新 focused tests 继续从 `gateway.app.services.plc_jobs` 导入稳定公共 API。
2. Facade 不新增业务规则；它只做 re-export、少量向后兼容包装和显式测试缝维护。
3. 新后端逻辑按职责进入对应子模块：存储进 `job_store.py`，摄取进 `ingest.py`，聊天意图进入 `chat_intents.py`，新证据抽取或渲染进入对应的 `evidence/` 模块，变更和回写进入 changeset/writeback 模块。
4. 已由 facade re-export 的私有符号是兼容缝，不得静默删除；新代码不应依赖“patch facade 私有符号必然改变子模块内部调用”的假设。
5. 新 PLC 领域模型、workspace 状态和数据变换进入 `frontend/src/plc/`；三栏布局、聊天面板和通用工作台组合进入 `frontend/src/workbench/`。
6. 边界变化必须同步更新 [PLC Intelligence Architecture](../architecture/ResearchOS_PLC_Intelligence.md)。

## Consequences

### Positive

- 降低 `plc_jobs.py` 和 `App.tsx` 的单点回归风险。
- 解析、理解、优化和 HITL 回写可以独立审查与演进。
- Facade 保持外部导入和关键测试缝稳定。

### Negative / Cost

- 兼容门面会让真实调用路径多一层间接性。
- 旧测试若 patch facade 私有符号，可能不再拦截子模块内部直接调用。
- `chat_evidence.py` 的兼容导出面仍需保持稳定；调整 evidence 内部分工时不得静默破坏旧测试缝和调用方导入。

## Alternatives Considered

| Alternative | Conclusion |
|---|---|
| 继续扩展单体 `plc_jobs.py` / `App.tsx` | 否决：变更半径大，职责无法独立验证 |
| 立即删除 facade 并强制全部调用方迁移 | 否决：破坏 routers、chat services 和现有测试导入面 |
| 仅按技术层拆分 utils/models/components | 部分采用：前端分层有用，但必须保留 PLC 领域边界 |
