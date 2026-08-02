# 研究控制台（Research Console）

研究控制台是登录后的主工作面：创建研究任务、观察执行、处理中断、阅读与导出报告，并次要入口管理知识空间。

## 信息架构

```
┌─────────────────────────────────────────────────────────────┐
│  ResearchOS          [工作空间▾]     [知识库] [设置] [用户]   │
├──────────────┬──────────────────────────────┬───────────────┤
│ 任务列表      │  主时间线 / 报告预览            │ 引用与计划     │
│ · 进行中      │  · 阶段与步骤                  │ · Plan        │
│ · 已完成      │  · 流式文本                    │ · Citations   │
│ · 失败        │  · 中断条                      │ · Artifacts   │
│ [新建研究]    │                                │               │
└──────────────┴──────────────────────────────┴───────────────┘
```

桌面默认三栏；窄屏改为：列表抽屉 + 主栏 + 引用抽屉。

## 路由（目标）

| 路径 | 页面 |
|------|------|
| `/login` | 登录 |
| `/app` | 重定向到最近任务或空态 |
| `/app/tasks` | 任务列表 |
| `/app/tasks/new` | 新建研究（表单） |
| `/app/tasks/[taskId]` | 控制台主视图 |
| `/app/tasks/[taskId]/report` | 报告阅读/导出（可与主视图 Tab 合一） |
| `/app/knowledge` | 知识空间列表 |
| `/app/knowledge/[kbId]` | 文档与入库状态 |

## 新建研究表单

字段与 API `POST /research/tasks` 对齐：

- 问题（必填，多行）
- 模式：`quick` / `deep` / `industrial`（industrial 在 Phase 5 启用，未实现时禁用并说明）
- 知识空间多选
- 高级：语言、是否联网、是否强制引用、中断策略、模型档位、种子 URL、约束说明

提交成功后导航至 `/app/tasks/{id}` 并立即建连 WS。

空态文案应强调产品能力（自主研究、引用、知识沉淀），避免空洞聊天提示。

## 任务主视图状态机（UI）

| UI 态 | 来源 | 主区域 |
|-------|------|--------|
| `loading` | 首屏 REST | 骨架屏 |
| `live` | WS 已连接 | 时间线实时更新 |
| `reconnecting` | WS 断线 | 只读 + 横幅 |
| `interrupted` | status / 事件 | 时间线 + 中断面板 |
| `completed` | 终态 | 默认切到报告 Tab，保留过程 Tab |
| `failed` / `cancelled` | 终态 | 错误/原因 + 操作 |

## 模块边界

### `TaskListPanel`

- 查询 `GET /research/tasks`
- 显示状态点、标题（query 截断）、相对时间
- 轮询仅作辅；当前任务依赖 WS

### `Timeline`

- 消费有序事件，维护本地 `eventsBySeq`
- 渲染 plan/step/tool/message/review
- 纯展示 + 折叠交互；不直接改服务器状态

### `CitationRail`

- 监听 `citation.added` 与 REST `/citations` 首屏合并
- 负责高亮联动

### `InterruptDock`

- 仅 `interrupted` 可见
- 调用 interrupt REST
- 成功前禁用重复提交

### `ReportView`

- `GET .../report` + `content`
- Markdown 渲染、引用角标、导出按钮（pdf/markdown）
- 未就绪显示「报告生成中」并监听 `report.ready`

### `WsClient`

- 单例按 `taskId` 管理连接
- 处理 auth、ping/pong、replay、backoff
- 向功能层暴露事件回调或外部 store 更新

## 状态存储建议

以任务为键：

```ts
TaskViewState {
  task: TaskDetail
  lastSeq: number
  events: Map<number, Event>
  plan: Plan | null
  citations: Citation[]
  interrupt: Interrupt | null
  streams: Map<string, string>  // stream_id → 累积文本
  connection: 'connected' | 'connecting' | 'disconnected'
}
```

不必过早引入复杂全局 store；实现阶段按仓库 React 规范选择（若启用 React Compiler，避免多余 memo）。

## 权限与多工作空间

- 顶栏切换工作空间 → 刷新任务列表；进行中的 WS 需断开并提示
- 无 `research:write` 时隐藏新建与中断提交，只读过程
- 无 `knowledge:write` 时知识库只读

## 次要：知识库 UI

知识库页聚焦：

- 空间列表与创建
- 上传与入库进度（作业状态）
- 简单检索调试器（调用 `POST /knowledge/search`）便于管理员验收 Hybrid 效果

不做独立「知识聊天」替代研究控制台，以免产品叙事分裂。

## 性能

- 事件列表虚拟滚动（长任务上千事件）
- Markdown 重渲染限制在活跃 `stream_id` 段落
- 大报告按章节懒渲染

## 测试建议

1. **契约测试**：用固定事件 JSON fixture 驱动 Timeline 快照
2. **WS 模拟**：重放 → 实时 → 断线 → 续传
3. **中断流**：`interrupt.required` → 提交 → `resolved` → 继续 `message.delta`
4. **无障碍冒烟**：键盘完成一次中断决策

## 设计约束（落地时）

若控制台伴随营销落地页，遵循仓库前端设计规则（品牌首屏、避免通用 AI 紫白模板等）。**应用内控制台**以清晰信息密度与过程可读为先，可沿用产品 CSS 变量，但不堆砌卡片式营销模块。

## 完成定义（前端架构）

文档与事件协议齐全，且实现里程碑能演示：

1. 创建 deep 任务
2. 观看步骤与引用流式出现
3. 处理一次人工中断
4. 打开带引用的报告

即视为 Research Console MVP 达标。
