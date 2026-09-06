# scientific.manuscript — 论文垂直域

纯 Python、无重依赖的论文域核心(可本地运行/测试),供 Runtime 的 Writer/Reviewer 与前端编辑器调用。
设计见 `docs/adr/0010`、`docs/scientific/merge/SCIENTIFIC-DOMAIN-SPEC.md`。

## 模块

| 模块 | 职责 |
|---|---|
| `stages.py` | 七阶段状态机(outline→exported),前向迁移 + review→drafting 返工环 |
| `draft.py` | 分节骨架组装(outline+chunks → Markdown 分节 + provenance) |
| `provenance/` | 论断↔chunk↔来源 记录 + 引用核验(可注入 mcp-scholar) |
| `release_gate.py` | 放行闸:幽灵引用/无源论断/缺 AI 声明 → 阻断导出 |
| `journalize.py` | 分节 → 期刊样式 HTML + 投稿清单(用 `scientific/journal_styles/*.json`) |
| `prompts.py` | Writer/Reviewer 域规则提示词 + AI 声明模板 |

## 端到端闭环(当前已可测,无 LLM)

```text
outline ──► draft.assemble_sections(chunks) ──► release_gate.run_release_gate(records)
             (provenance 三级溯源)                  (幽灵引用/无源/无声明 任一阻断)
        ──► journalize.render_html(sections, style) + build_manifest()
```

外部输入由 MCP 工具提供:`tools/vault`(资料摄取)、`tools/scholar`(引用查表/核验)、
`tools/plot`(数据→图)。前端 `frontend/src/manuscript/`(VaultPanel、FigureCanvas)经 Gateway
`/api/v1/vault/*`、`/api/v1/knowledge/*` 调用。

## runtime 接线方案(下一步)

1. **Writer**:LangGraph 节点内调用 `prompts.WRITER_SYSTEM_PROMPT` 约束 LLM,产出分节草稿后落
   `draft.DraftSection`(每节带 provenance),而非裸 Markdown;
2. **Reviewer**:草稿 → `release_gate.run_release_gate(records, ai_disclosure=..., scholar_verify=...)`,
   阻断则不进入 journalize;
3. **阶段迁移**:用 `stages.Stage` 驱动 TaskState(goal/plan/evidence/result),`waiting_input` 承载大纲 HITL;
4. **模型**:经 LiteLLM 逻辑模型名 writer/reviewer;`prompts.py` 规则作为 system prompt 前缀注入。

## 测试

```bash
uv run --with pytest -- python -m pytest tests/test_manuscript.py tests/test_draft.py tests/test_journalize.py -q
```
