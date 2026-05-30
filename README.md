# PaperHelp

**仓库**: [Roarpeng/PaperHelp](https://github.com/Roarpeng/PaperHelp)

Figure-first 本地离线科研写作桌面应用（Alpha MVP）。

## 项目概述

PaperHelp 面向科研写作者，以 **Figure Studio** 为核心：导入图片 → 自动排版 → 嵌入正文 → 导出 PDF 与投稿包。Alpha 阶段支持 Tiptap 混合编辑器（Scroll / A4 分页）、`.paper` 本地持久化、Word 文档导入，以及高保真 PDF 导出。

## 技术栈

| 层级 | 技术 |
|------|------|
| 桌面壳 | Tauri 2 + Rust |
| 前端 | React 19 · Vite 7 · React Router |
| 样式 | Tailwind CSS v4 · shadcn/ui |
| 编辑器 | Tiptap 3（StarterKit · Table · 自定义 Figure/Citation Node） |
| Figure | Konva · react-konva |
| 状态 | Zustand |
| 持久化 | SQLite（Tauri SQL 插件）· ZIP `.paper` 容器 |
| 导出 | Puppeteer / 系统 Chrome · JSZip 投稿包 |
| 文档导入 | mammoth（docx → HTML + 图片提取）· @tiptap/html |
| 构建 | pnpm workspaces · Turborepo |

## Alpha 功能清单

- **编辑器**：Heading（H1–H3）、段落、粗体/斜体、表格；Scroll / A4 双视图；Outline 同步
- **Figure Studio**：多图导入、自动 2×N 排版、标签 a–f、比例尺、FigureBlock 嵌入与 reopen
- **持久化**：`.paper` 保存/打开、30s 自动保存、崩溃恢复、Command Pattern 撤销/重做
- **导出**：PDF（系统 Chrome 或 Puppeteer Chromium）、投稿 ZIP（manuscript.pdf + figures/ + metadata.json）
- **文档导入**：Word `.docx` → 文字进编辑器、图片进资源库（SHA256 去重）

## 环境要求

| 工具 | 版本 |
|------|------|
| Node.js | ≥ 20 |
| pnpm | ≥ 10 |
| Rust | stable（Tauri 2 必需） |
| Windows | WebView2（Win10/11 通常已预装） |

## 安装与运行

### 一键安装

```powershell
cd C:\Users\Lidou\Desktop\Project\Code\PaperHelp
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

脚本会：检查 node/pnpm/rust → 将 `%USERPROFILE%\.cargo\bin` 写入用户 PATH → `pnpm install` → 检测/下载 PDF 浏览器 → `pnpm build` → `cargo check`。

### 开发运行

```powershell
# 推荐：仓库根目录（自动注入 cargo PATH）
pnpm dev:desktop
```

`dev:desktop` / `build:desktop` 通过 `scripts/with-cargo-path.mjs` 包装，新终端未加载 Rust PATH 时也能找到 `cargo`。

若仍找不到 `cargo`：

```powershell
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
```

### 生产打包

```powershell
pnpm build:desktop
```

安装包：`apps/desktop/src-tauri/target/release/bundle/`（MSI / NSIS）。

## 测试清单（约 30 分钟）

1. **新建论文** → 空白编辑器
2. **导入文档**（.docx）→ 文字进编辑器、图片进资源库 → 跳转编辑器
3. 写 **Heading + 段落** → 左侧 Outline 更新
4. **导入 Figure**（6 张图）→ 自动 2×3 排版
5. 编辑 **a–f 标签**、**比例尺**
6. **插入 Figure** 到正文 → FigureBlock 预览
7. 切换 **Scroll / A4** 视图
8. **Ctrl+S** 保存 `.paper` → 关闭重开 → **打开** 验证
9. **导出 PDF**
10. **导出投稿包** → ZIP 含 `manuscript.pdf`、`figures/`、`metadata.json`

### 快捷操作

- **Cmd/Ctrl+K**：命令面板
- **双击** FigureBlock → 重新打开 Figure Studio
- 底部状态栏：**已保存 / 保存中 / 未保存**（30s 自动保存）

## 架构简述

```text
apps/desktop/       Tauri 壳、页面路由、autosave / export hooks
packages/editor/    Tiptap、Hybrid 视图、docx 导入
packages/figure/    Konva Figure Studio、Layout 算法
packages/db/        SQLite schema、.paper ZIP I/O
packages/export/    HTML 渲染、Puppeteer PDF、投稿 ZIP
packages/shared/    Zustand stores、Command Pattern
packages/ui/        shadcn 组件
```

数据流：UI stores ↔ `.paper`（SQLite + assets/）↔ Tauri 文件对话框 / 二进制 I/O。

详细 Sprint 记录与 GitHub 推送说明见 [docs/PROJECT_SUMMARY.md](docs/PROJECT_SUMMARY.md)。

## Sprint 完成情况

| Sprint | 状态 | 交付 |
|--------|------|------|
| Sprint 1 — Editor MVP | ✅ | Tiptap、Scroll/A4、Outline、Command Palette |
| Sprint 2 — Figure MVP | ✅ | Konva Studio、自动排版、FigureBlock |
| Sprint 3 — 持久化 | ✅ | `.paper`、autosave、recovery、undo/redo |
| Sprint 4 — 导出 | ✅ | PDF、投稿 ZIP |
| Alpha+ | ✅ | docx 导入、cargo PATH 包装、Chrome PDF 检测 |

当前分支：`feature/sprint3-4-alpha`

## 近期修复与工具说明

- **cargo PATH**：`scripts/with-cargo-path.mjs` + `setup.ps1` 自动写入用户 PATH；根 `package.json` 的 `dev:desktop` / `build:desktop` 已使用该包装
- **package.json BOM**：根 `package.json` 已去除 UTF-8 BOM，避免部分工具解析失败
- **PDF 导出**：`generatePdf.ts` 优先使用系统 Chrome，无需强制下载 Puppeteer Chromium
- **GitHub CLI**：推送需本机安装 [GitHub CLI](https://cli.github.com/) 并执行 `gh auth login`（见 PROJECT_SUMMARY.md）

## PDF 导出前置条件

- **推荐**：安装 [Google Chrome](https://www.google.com/chrome/)，项目自动检测 `chrome.exe`
- **备选**：`cd packages/export && pnpm exec puppeteer browsers install chrome@stable`
- 导出时 PATH 需有 **Node.js**（Tauri 调用 `apps/desktop/scripts/export-pdf.mjs`）
