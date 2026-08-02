# ResearchOS 前端文档

前端是 ResearchOS 的流式研究控制台：以 WebSocket 事件驱动展示规划、取证、引用、人工中断与报告，而不是传统「一问一答聊天框」的静态页。

## 文档索引

| 文档 | 内容 |
|------|------|
| [01-ux-principles.md](./01-ux-principles.md) | 流式步骤、引用、人工中断等 UX 原则 |
| [02-research-console.md](./02-research-console.md) | 研究控制台信息架构、状态与组件边界 |

## 产品定位（前端视角）

- **不是**通用 Chat UI 皮肤
- **是**一次研究任务的执行仪表：时间线 + 证据 + 报告
- 品牌与产品名在首屏应清晰可辨（落地营销页若后续独立，遵循仓库前端设计约束）

## 技术方向（架构约定）

| 项 | 约定 |
|----|------|
| 框架 | 现代 React（实现阶段锁定具体元框架，如 Next.js） |
| 数据 | REST 创建/查询 + WebSocket 实时 |
| 状态 | 以 `task_id` 为中心的任务态；事件 `seq` 为序 |
| 鉴权 | Bearer；401 静默 refresh |
| 国际化 | 首期中文优先，文案可抽离 |
| 无障碍 | 中断对话框可键盘操作；状态变化有非仅颜色的提示 |

## 与后端契约

- API：[../api/README.md](../api/README.md)
- 事件：[../api/05-websocket-events.md](../api/05-websocket-events.md)
- 研究：[../api/03-research-api.md](../api/03-research-api.md)

前端不得直连 Qdrant、Neo4j、LiteLLM、MinIO 管理端或 Runtime 内部端口。

## 目录约定（目标）

```
frontend/
├── app/                    # 路由与页面
├── features/
│   ├── auth/
│   ├── research/           # 控制台、时间线、中断
│   ├── knowledge/          # 知识空间管理（次要）
│   └── reports/
├── shared/
│   ├── api/
│   ├── ws/
│   └── ui/
└── styles/
```

## 实现状态

Architecture Phase：本文定义交互与结构契约，实现时以事件协议为准做集成测试（模拟事件流）。
