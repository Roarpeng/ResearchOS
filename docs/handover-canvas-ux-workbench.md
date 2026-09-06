# Knowledge Canvas UX：Inspector + 右侧 Workbench

交互契约（Peng 已定方向）。本文件是画布选中 / 提问 / Brief·设备卡跳转的单一约定，供 #14 / #15 与后续交接对齐。

## 目标

点节点仍是提问入口，但预览与操作不再堵在画布中央。

| 动作 | 结果 |
|------|------|
| **单击** | 选中 + 轻量 **Inspector**。画布中心不被挡住。 |
| **双击 / Space / Inspector「问这节点」** | 打开固定 **右侧 Workbench**（不是居中 modal）。画布保持可见。 |
| Brief / 设备卡跳转 | `focus + select + Inspector`。若 `ask: true` 再开 Workbench。 |

非目标：不改 Openness / M1 导出管线；不开启自动 SCL 反写；不多选对比（二期）。

## 信息架构

```
[历史] [主对话] [画布 + 左上 Inspector | 右侧 Workbench]
```

- Inspector 贴在画布 **左上**，不占中心，**没有聊天框**。
- Workbench 是画布列内部的右侧固定栏，压缩画布宽度，不盖住图。
- 旧 `.kg-pop`（`role="dialog"` + 密集快捷操作）已降级移除；SCL / 反写只出现在 Workbench「怎么调」折叠区。

## Inspector

展示：

- 短名、类型、导出状态、一行职责、最多 3 条关键 I/O

仅三个动作：

| 动作 | 行为 |
|------|------|
| `问这节点` | 打开 Workbench，默认「怎么跑」，输入框聚焦当前节点 |
| `看引用源` | 打开 Workbench「怎么跑」，渲染 `block · locator · snippet` |
| `标记人注` | 打开 Workbench「是什么」，聚焦人注 |

节点 chrome：类型缩写 + 短名 + 状态点。密集预览不得再进节点 popover / `title`。

## Workbench（工程师三问）

| Tab | 内容 |
|-----|------|
| **是什么** | 含义、人注、状态 |
| **怎么跑** | 带引用的运行逻辑问答 |
| **怎么调** | HITL 调整建议；**SCL 优化 / 反写默认折叠** |

约束：

- 底部输入框 **始终** 以当前选中节点为上下文。
- 工作台打开时换节点：更新上下文，并闪一下 **「已切换节点 · {name}」**。
- 人注先写本机 `localStorage`（`researchos.canvas.humanNotes.v1`）。不自动反写；#15 批注 API 落地后可替换存储。
- 「确认反写」仍走现有 HITL 门闩（`writebackHintForBlock`），无 changeset 则禁用。

多选对比：二期。UI 不提供入口。

## 跳转契约（Brief / 设备卡）

前端唯一入口：

```ts
import type { CanvasJumpIntent } from "../plc/canvas";
// usePlcWorkspace().jumpToCanvasNode(intent)
```

```ts
type CanvasJumpIntent = {
  nodeId?: string;
  blockName?: string;
  symbol?: string; // 标签 / 传感器
  ask?: boolean;   // true → 再开 Workbench
};
```

| 来源 | 推荐调用 |
|------|----------|
| Brief 顶层调用 / 缺口 chip | `jumpToCanvasNode({ blockName })` → Inspector |
| Brief「问这节点」/ 工程师三问需要钉节点 | `jumpToCanvasNode({ blockName, ask: true })` |
| 设备卡 `used_by[].block` | `jumpToCanvasNode({ blockName: used_by.block })` |
| 传感器符号 | `jumpToCanvasNode({ symbol })` |
| 主对话 evidence chip | 已接 `onFocusNode` → 同上（inspect-only） |

`CanvasFocusRequest` 增加 `ask?: boolean`。#14 / #15 不要另写居中 modal。

## 引用形状

Workbench 与 Inspector「看引用源」接受 M3 形状，缺字段时占位：

```ts
{ block?: string; locator?: string; snippet?: string; source_status?: string }
```

兼容旧字段：`network` / `line` → locator；`evidence` → snippet。

## 模块边界（additive）

```
frontend/src/plc/canvas/
  jump.ts            # CanvasJumpIntent
  inspectModel.ts    # 职责 / I/O / 导出状态 / 引用归一
  humanNotes.ts      # 本机人注
  NodeInspector.tsx
  NodeWorkbench.tsx
  CitationSourceList.tsx
  demoFixture.ts     # ?canvasDemo=1 本地演示，不碰导出管线
```

复用既有 `POST /api/v1/chat/turns`（`onDeepDive` / `sendTurn`）。不新增节点聊天 API。

## 键盘

| 键 | 条件 | 行为 |
|----|------|------|
| Space | 已选中节点，焦点不在输入框 | 打开 Workbench |
| Escape | Workbench 打开 | 关 Workbench，保留选中 + Inspector |
| Escape | 仅 Inspector | 不抢 Settings；关 Inspector 用面板「关闭」 |

## 验证（本 PR 点过什么）

本地：`cd frontend && npm run dev`，打开 `http://localhost:5173/?canvasDemo=1`。

1. 单击 `FB_Motor` → 左上 Inspector：名称 / FB / 已导出 / 一行职责 / 最多 3 条 I/O；画布中心仍可见。
2. 确认 Inspector **没有** 聊天框，只有「问这节点 · 看引用源 · 标记人注」。
3. 双击同一节点（或 Space，或点「问这节点」）→ 右侧 Workbench 打开，画布仍在。
4. 切到「怎么跑」：演示引用 `FB_Motor · Network 1 / line 2 · snippet`。
5. 「怎么调」：SCL 优化 / 反写默认折叠；展开后「确认反写」在无 changeset 时禁用。
6. 工作台开着时单击 `Main` → 出现「已切换节点 · Main」，输入框上下文变成 Main。
7. 「标记人注」→ 「是什么」textarea 聚焦；刷新后人注仍在。
8. 节点只显示缩写 + 短名 + 状态点，不再弹出大段预览。

## 与并行 PR 的 rebase 风险

| PR | 热点 | 怎么合 |
|----|------|--------|
| **#13** M1 | `canvasModel.ts`、`KnowledgeCanvas.tsx`、`ResearchWorkspace.tsx`、`api.ts` | 保留本 PR 的 Inspector/Workbench；把 `export_status` 真值接到已有节点字段与状态点。不要恢复 `.kg-pop`。 |
| **#14** M2/M3 | `ResearchWorkspace.tsx`（`brief` tab）、`ChatMessages.tsx`、`api.ts` `PlcCitation`、`usePlcWorkspace.ts` | Tab union 做成 `"canvas" \| "brief" \| …`。Brief chip 改走 `jumpToCanvasNode`。`PlcCitation.locator` 已预留。 |
| **#15** Q1 | `ResearchWorkspace.tsx`（`sensors` tab）、`KnowledgeCanvas.tsx`、`api.ts` | 传感器 tab 与 Workbench 并列，不要把设备卡嵌回画布中央。`used_by` / 符号点击走 `jumpToCanvasNode`。人注可随后接到 annotation API。 |

建议合入顺序：**#13 → 本 PR → #15 → #14**（或本 PR 与 #13 可互换，只要 `export_status` 字段名不变）。

最高冲突面：`ResearchWorkspace.tsx` 的 tab 集合与 canvas body 布局；`usePlcWorkspace.ts` 的 focus/scope；`styles.css` 画布区块。
