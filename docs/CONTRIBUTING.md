# 贡献指南（架构阶段）

欢迎为 [ResearchOS](https://github.com/Roarpeng/ResearchOS) 贡献文档与代码。当前仓库处于 **Architecture Phase（Phase 0）**：优先补全与对齐架构契约，再进入基础设施与运行时实现。

## 当前阶段目标

1. 保持愿景、架构、API、部署、前端、工业扩展文档完整且互链一致  
2. 用 ADR 记录重要决策变更  
3. 为 Phase 1+ 预留清晰目录（`gateway/`、`runtime/`、`deploy/` 等），避免无契约实现  

## 你能贡献什么

### 文档（优先）

- 澄清歧义、补示例、修正与选型表冲突的表述  
- 新增 ADR（`docs/adr/`）说明「为何选 / 为何不选」  
- 翻译或润色（中文为架构期首选语言；关键专有名词保留英文）  
- 为 API 事件/字段补充边界情况（仍属契约，不是空头 stub）  

### 代码（架构期约束）

架构期接受的代码型贡献通常限于：

- 仓库骨架与空模块占位（需在 README/文档中声明「未实现」）  
- Compose 示例、配置样例、脚本草稿（不含真实密钥）  
- 文档站点或 lint（如 markdown 链接检查）  

大规模业务实现请等待 Phase 1+ 议题，或先提交设计 RFC/ADR。

## 开始之前

1. 阅读：  
   - [Vision](./00-Vision.md)  
   - [Architecture](./01-Architecture.md)  
   - [源对话摘要](./reference/source-conversation-summary.md)  
   - [架构速查](./reference/architecture-decision-summary.md)  
2. 搜索现有 `docs/**` 与 ADR，避免重复提案  
3. 若改动影响接口或部署拓扑，同步更新对应 API/部署文档  

## 文档结构约定

```
docs/
├── 00–05                 总纲
├── api/                  Gateway 与 REST/WS 契约
├── deployment/           Compose、配置、私有化、观测
├── frontend/             UX 与控制台
├── industrial/           Phase 5 扩展
├── knowledge/ runtime/ agents/ mcp/ workflows/ core/
├── reference/            溯源与速查
├── adr/                  架构决策记录
└── CONTRIBUTING.md       本文件
```

- 文件使用完整 Markdown：**禁止**只含标题的 stub  
- 中文叙述 + 必要英文标识符（服务名、字段、事件名）  
- 链接使用相对路径，便于仓库内浏览  

## ADR 建议模板

```markdown
# ADR-XXXX 标题

- 状态: Proposed | Accepted | Superseded
- 日期: YYYY-MM-DD

## 背景
## 决策
## 备选方案
## 后果
## 关联文档
```

编号递增；Superseded 的 ADR 保留并指向新文档。

## 变更流程

1. Fork / 建分支：`docs/...` 或 `feat/...`  
2. 小步提交；文档与契约变更写清动机  
3. 自检：  
   - 是否与六条设计原则冲突？  
   - n8n 是否仍被误写为 Agent 主链路？  
   - API 字段是否与 `docs/api` 一致？  
4. 发起 Pull Request：说明影响范围（API / 部署 / 前端 / 工业）  
5. 维护者审查：优先一致性与可实现性，而非文采  

## 提交信息建议

```
docs: 澄清 WebSocket interrupt 与 REST 的职责边界
docs(adr): 接受 LiteLLM 作为唯一模型入口
chore: 添加 markdown 链接检查
```

## 安全与隐私

- 禁止提交 API Key、证书、客户拓扑、真实竞品内部数据  
- 示例使用明显占位符（`change_me`、`ws_01H...`）  
- 工业相关文档必须保留「默认只读 / 人工批准」安全表述  

## 行为准则（简版）

- 尊重不同背景的贡献者  
- 争议对事不对人；用 ADR 沉淀分歧  
- 不把对话营销话术直接贴进架构正文；溯源放 `docs/reference`  

## 阶段演进后

进入 Phase 1+ 后，本文件将补充：开发环境启动、测试要求、代码风格、CI 徽章等。**在那之前，以文档契约为唯一合并标准。**

## 联系与议题

- 仓库：https://github.com/Roarpeng/ResearchOS  
- 建议用 GitHub Issues 标记：`docs`、`architecture`、`phase-0`、`industrial`  

感谢你帮助把 ResearchOS 建成开放的研究操作系统底座。
