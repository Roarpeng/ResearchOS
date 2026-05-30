# PaperHelp

Figure-first 本地离线科研写作桌面应用（Alpha MVP）。

## 环境要求

| 工具 | 版本 |
|------|------|
| Node.js | ≥ 20 |
| pnpm | ≥ 10 |
| Rust | stable（Tauri 2 必需） |
| Windows | WebView2（Win10/11 通常已预装） |

## 一键安装

```powershell
cd C:\Users\Lidou\Desktop\Project\Code\PaperHelp
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

脚本会：检查 node/pnpm/rust → `pnpm install` → 下载 Puppeteer Chromium → `pnpm build` → `cargo check`。

## 开发运行

```powershell
# 推荐：仓库根目录
pnpm dev:desktop

# 或
cd apps/desktop
pnpm tauri dev
```

若新终端找不到 `cargo`：

```powershell
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
```

## 生产打包

```powershell
pnpm build:desktop
```

安装包输出目录：

```text
apps/desktop/src-tauri/target/release/bundle/
  msi/PaperHelp_0.1.0_x64_en-US.msi
  nsis/PaperHelp_0.1.0_x64-setup.exe
```

可执行文件：`apps/desktop/src-tauri/target/release/desktop.exe`

## PDF 导出前置条件

PDF 与投稿包导出依赖 **Puppeteer + Chromium**：

```powershell
cd packages/export
pnpm exec puppeteer browsers install chrome
```

首次约下载 150MB。若 `pnpm install` 提示忽略 build scripts，确保根目录 `.npmrc` 含 `allow-build=puppeteer,esbuild`。

导出时系统 PATH 需有 **Node.js**（Tauri 通过 `node` 调用 `apps/desktop/scripts/export-pdf.mjs`）。

## Alpha 测试清单（约 30 分钟）

1. **新建论文** → 空白编辑器  
2. 写 **Heading + 段落** → 左侧 Outline 更新  
3. **导入 Figure**（6 张图）→ 自动 2×3 排版  
4. 编辑 **a–f 标签**、**比例尺**  
5. **插入 Figure** 到正文 → FigureBlock 预览  
6. 切换 **Scroll / A4** 视图  
7. **Ctrl+S** 保存 `.paper` → 关闭重开 → **打开** 验证  
8. **导出 PDF**  
9. **导出投稿包** → ZIP 含 `manuscript.pdf`、`figures/`、`metadata.json`

### 快捷操作

- **Cmd/Ctrl+K**：命令面板（插入 Figure、切换视图等）
- **双击** FigureBlock → 重新打开 Figure Studio
- 底部状态栏：**已保存 / 保存中 / 未保存**（30s 自动保存）

## Monorepo 结构

```text
apps/desktop/     Tauri 桌面应用
packages/editor/  Tiptap 编辑器
packages/figure/  Konva Figure Studio
packages/db/      SQLite + .paper 持久化
packages/export/  PDF + 投稿 ZIP
packages/shared/  Zustand stores
packages/ui/      shadcn 组件
```

## 当前分支

Alpha MVP：`feature/sprint3-4-alpha`
