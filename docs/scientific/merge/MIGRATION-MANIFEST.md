# 迁移清单与 R0 执行步骤(Migration Manifest & R0 Checklist)

用途:合并落地时按此执行。进程通道恢复后从 Step 1 开始,逐步勾选。
仓库事实截至 2026-09-06:ResearchOS = Roarpeng/ResearchOS(public, default main, Python/uv 单仓,
Phase 0–4 MVP Done,frontend/ 未落地);PaperHelp 仅存在于本机(未推送 GitHub)。

## 0. 前置检查

- [ ] pwsh/cmd 进程通道正常(当前故障 0xC0000142 已解决)
- [ ] `git --version`、`node -v`、`pnpm -v`、`uv --version`、`docker --version` 可用
- [ ] gh auth(推送/PR 到 Roarpeng/ResearchOS 需要;或由用户手动 push)
- [ ] 目标克隆位置:C:\Users\Lidou\Desktop\Project\Code\ResearchOS

## 1. R0 — 单仓整合与骨架

```bash
# 1.1 克隆 ResearchOS
cd C:\Users\Lidou\Desktop\Project\Code
git clone https://github.com/Roarpeng/ResearchOS.git
cd ResearchOS && git checkout -b feat/scientific-manuscript

# 1.2 PaperHelp 历史以子树并入(保 blame)
#    PaperHelp 仓库(本机)路径: C:\Users\Lidou\Desktop\Project\Code\PaperHelp
git subtree add --prefix apps/paperhelp <PaperHelp本地路径> feature/sprint3-4-alpha

# 1.3 正式化 ADR 0010–0012(内容见本仓库 docs/merge/adr-drafts/;
#     ResearchOS ADR 已编至 0009,论文域编号已避开冲突)
copy docs/merge/adr-drafts/ADR-001*.md 到 ResearchOS/docs/adr/
#     (ADR-0008/0009/0010 同名文件为 Superseded 指针,勿拷贝)
#     同时合并 ROADMAP Phase 6 提案(docs/merge/ROADMAP-phase6-proposal.md)

# 1.4 frontend/ TS workspace 骨架(已就绪:PaperHelp 仓库 frontend-port/)
#     将 frontend-port/ 整目录拷为 ResearchOS/frontend/(package.json workspace + turbo +
#     tsconfig 基座 + packages/api-client 契约骨架已含)
#     随后按依赖迁移:shared → ui → editor → figure → export → db → 页面 → api-client(端点核实)
```

## 2. PaperHelp → ResearchOS 路径映射

| PaperHelp(源) | ResearchOS(目标) | 动作 |
|---|---|---|
| apps/desktop/src/pages/* | frontend/apps/*(页面) | 迁移+接入 api-client |
| packages/shared | frontend/packages/shared | 迁移(stores/types/commands) |
| packages/ui | frontend/packages/ui | 迁移(shadcn) |
| packages/editor | frontend/packages/editor | 迁移(CitationNode 转真留 R2) |
| packages/figure | frontend/packages/figure | 迁移(Konva Figure Studio) |
| packages/export | frontend/packages/export | 迁移(浏览器渲染/PDF/投稿包) |
| packages/db | frontend/packages/db | 迁移(.paper 容器兼容层) |
| (无) | frontend/packages/api-client | 新建(Gateway REST/WS 客户端) |
| (无) | frontend/desktop | 可选 Tauri 壳(后续) |
| (无) | tools/mcp-vault · mcp-scholar · mcp-plot | 新建(Python MCP,ADR-0010) |
| (无) | scientific/ | 新建(域包) |
| docs/ResearchOS_Integration_Blueprint.md 等 | docs/merge/ 或 ResearchOS/docs/ | 归档到 ResearchOS |

## 3. 里程碑顺序(R0 → R1 → R2 → R3 → R4)

见 docs/merge/ROADMAP-phase6-proposal.md;验收标准沿用 PaperHelp v3.0 M0–M3。

## 4. 完成后清理

- [ ] 全部资产迁出后删除过渡目录 apps/paperhelp/(历史保留于 git)
- [ ] 更新 ResearchOS README Status、docs/README 索引、术语表
- [ ] PaperHelp 本仓库 README 顶部标注"已并入 ResearchOS,本仓库归档"
