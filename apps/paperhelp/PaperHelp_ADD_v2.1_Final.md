# PaperHelp v2.1
# Architecture Design Document (ADD)
# 最终开发蓝图

Version: 2.1
Status: Final Draft
Product: PaperHelp
Architecture: Figure-first Scientific Writing Platform

---

# 1. Architecture Goal

PaperHelp 目标：

构建：

Figure-first 科研写作工作台。

核心：

- 小白零学习
- 专业Figure体验
- 本地离线
- 高保真导出
- 可持续扩展AI

---

# 2. 系统总体架构

```text
+----------------------------------------------------+
|                    UI Layer                         |
| React + Tailwind + Shadcn                          |
+----------------------------------------------------+
|                  Interaction Layer                  |
| Tiptap Editor + Konva Figure Studio                |
+----------------------------------------------------+
|                   Domain Layer                      |
| Document Engine                                    |
| Figure Engine                                      |
| Citation Engine                                    |
| Journal Engine                                     |
| AI Engine                                          |
+----------------------------------------------------+
|                 Persistence Layer                   |
| SQLite + Asset Manager + History                   |
+----------------------------------------------------+
|                  Export Layer                       |
| PDF / DOCX / ZIP                                   |
+----------------------------------------------------+
|                 Desktop Runtime                     |
| Tauri + Rust                                       |
+----------------------------------------------------+
```

---

# 3. 技术选型最终版

| 模块 | 技术 |
|---|---|
| Desktop | Tauri |
| Frontend | React |
| Build | Vite |
| UI | Tailwind + shadcn |
| Editor | Tiptap |
| Figure | Konva |
| State | Zustand |
| DB | SQLite |
| ORM | Drizzle |
| Export | Puppeteer |
| Packaging | JSZip |
| Image | Sharp |
| AI | OpenAI compatible |

原则：

- Web技术栈
- Rust负责系统能力
- React负责交互

---

# 4. Monorepo结构

推荐：

```text
paperhelp/

apps/
    desktop/

packages/
    ui/
    editor/
    figure/
    db/
    export/
    ai/
    shared/

assets/
docs/
```

优势：

- 可维护
- 模块解耦
- 便于多人协作

---

# 5. 编辑器架构

核心：

Hybrid Editor

双视图：

```text
Infinite Scroll
A4 Pagination
```

共享：

同一Document。

---

Editor：

Tiptap。

支持：

- Heading
- Paragraph
- Table
- FigureBlock
- CitationBlock

---

Tiptap Node：

```ts
FigureNode
CitationNode
JournalNode
```

Figure：

独立Node。

不是图片。

---

# 6. Figure Studio架构

核心壁垒。

采用：

Konva。

结构：

```text
Figure Studio

Stage
 ├── Layer
 ├── Image
 ├── Label
 ├── Annotation
 └── ScaleBar
```

---

Figure对象：

```ts
interface Figure {

id:string
title:string

assets:Asset[]

layout:Layout

annotations:Annotation[]

scaleBar?:ScaleBar

style:FigureStyle

}
```

---

Figure Engine：

职责：

- 自动排布
- 标签
- 吸附
- 对齐
- 图层

---

# 7. Figure自动排版算法

输入：

```text
n images
```

输出：

Layout。

规则：

1：

数量判断。

```text
1
2
3
4
6
9
```

2：

优先：

- 对称
- 等边距
- 期刊友好

示例：

6图：

默认：

2×3。

---

算法：

```text
Detect
↓
Suggest
↓
Preview
↓
Apply
```

支持：

实时预览。

---

# 8. Figure交互流

用户：

拖入图像。

系统：

```text
Import
↓
Asset Manager
↓
Thumbnail
↓
Auto Layout
↓
Figure Object
↓
Render
```

用户无需理解图层。

---

# 9. Asset Manager

必须独立。

职责：

- 素材索引
- Hash
- 去重
- Cache

Asset：

```ts
Asset{

id
path
hash
width
height
mime

}
```

Hash：

SHA256。

避免重复。

---

# 10. .paper规范

最终：

SQLite Container。

结构：

```text
paper.paper

db.sqlite

assets/

preview/
```

---

保存：

ZIP。

内部：

SQLite。

流程：

```text
Save
↓
Flush DB
↓
Copy Assets
↓
Zip
```

---

优势：

- PSD式
- 稳定
- 快

---

# 11. SQLite ER设计

核心表：

---

documents

```sql
id
title
created_at
updated_at
```

---

blocks

```sql
id
document_id
type
content
position
```

---

figures

```sql
id
document_id
layout
metadata
```

---

assets

```sql
id
path
hash
width
height
```

---

citations

```sql
id
doi
title
authors
journal
```

---

history

```sql
id
action
payload
created_at
```

---

# 12. Zustand Store

Store拆分：

```text
editorStore
figureStore
assetStore
exportStore
uiStore
```

---

editorStore

负责：

- 当前文档
- undo
- redo

---

figureStore

负责：

- 选中状态
- Konva对象

---

uiStore

负责：

- Dialog
- Theme
- View

---

原则：

UI状态 ≠ 数据状态。

---

# 13. Undo/Redo

Command Pattern。

不是：

快照。

命令：

```ts
execute()

undo()
```

记录：

history。

支持：

- 撤销
- 重做
- 时间旅行

---

# 14. Autosave

自动保存：

30秒。

机制：

Debounce。

流程：

```text
Edit
↓
Dirty
↓
Timer
↓
Save
```

---

崩溃恢复：

启动：

```text
Crash Detect
↓
Recover
```

---

# 15. Citation Engine

兼容：

- DOI
- BibTex
- RIS

未来：

Zotero。

流程：

```text
Import
↓
Parse
↓
Normalize
↓
Insert
```

Citation：

对象。

不是文本。

---

# 16. Journal Engine

期刊模式。

模板：

```text
Nature
Plant Physiology
Crop Journal
```

模板：

JSON。

例如：

```json
{
  "margin":"20mm",
  "font":"Times New Roman"
}
```

动态：

切换。

无需重排。

---

# 17. Export Engine

独立。

避免污染Editor。

---

PDF：

Puppeteer。

流程：

```text
HTML
↓
Print CSS
↓
PDF
```

---

DOCX：

Phase2。

支持：

纯文本。

---

ZIP：

投稿包。

包括：

- PDF
- Figure
- Metadata

---

# 18. AI Architecture

后期。

先预留。

AI：

服务层。

不是UI层。

---

AI Engine：

```text
Caption AI
Figure AI
Style AI
```

接口：

统一：

```ts
generate()
```

Provider：

可替换。

---

支持：

- OpenAI
- OpenRouter
- 本地模型

---

# 19. UI Design System

目标：

科研版Canva。

原则：

1：

极简。

2：

上下文操作。

3：

零工具栏。

---

组件：

```text
BubbleMenu
CommandPalette
FigureToolbar
Sidebar
```

---

设计：

shadcn。

---

# 20. 首版UI

首页：

```text
新建论文

导入Figure

模板中心
```

编辑：

左右：

```text
Outline
Editor
```

Figure：

右侧：

属性栏。

---

# 21. 第一开发Sprint

Sprint1：

目标：

Editor MVP。

周期：

1周。

任务：

- Tauri
- React
- Tailwind
- Tiptap
- A4

完成：

可编辑。

---

Sprint2：

Figure。

周期：

2周。

任务：

- Konva
- 导图
- 标签
- Auto Layout

完成：

Figure MVP。

---

Sprint3：

文件。

周期：

1周。

任务：

- SQLite
- Save
- Load

---

Sprint4：

导出。

周期：

1周。

完成：

PDF。

---

# 22. 开发原则

必须：

先：

能跑。

再：

优雅。

禁止：

过早AI。

禁止：

过早云同步。

禁止：

架构洁癖。

原则：

> Working software first.

---

# 23. Alpha里程碑

成功：

用户：

30分钟。

完成：

- 导图
- 组图
- 写作
- 导PDF

即：

验证成功。

---

# 24. 启动命令

创建：

```bash
npm create tauri-app
```

安装：

```bash
npm install
```

运行：

```bash
npm run tauri dev
```

---

# 25. 开发起点

立即：

从：

Editor MVP。

不是AI。

不是期刊。

不是协作。

先：

让用户写。

然后：

让用户组图。

最后：

让用户投稿。

