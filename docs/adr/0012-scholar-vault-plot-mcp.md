# ADR-0012: Scholar / Vault / Plot MCP Tools(论文域工具层)

Status: Draft(待并入 ResearchOS 后正式化)
Date: 2026-09-06
编号说明:承 ADR-0010(ResearchOS ADR 已编至 0009)。
关联:[ADR-0010](./0010-scientific-manuscript-domain.md)

## 背景

论文域需要三类 ResearchOS 尚未具备的 MCP 工具,且都必须满足既有约束:
MCP-Native、可审计、工具 ACL、密钥不进 Prompt(见既有 ADR-0002/0007)。

## 决策

1. **mcp-scholar(文献查表与检索,只读)**:
   - 能力:DOI/标题/作者解析 → 规范化元数据;行内引用完整性扫描(幽灵引用检测);
     期刊文献检索(Crossref / OpenAlex / Semantic Scholar 优先级可配置);
   - 纪律:**只查表,不生成**;结果写 citation 缓存库(PostgreSQL/Redis),带 verified_at;
   - 输出:citation 记录(doi, title, authors, journal, year)与来源;供 CitationNode/Writer/Reviewer 消费;
   - 限流与 ACL:出站域名白名单、每任务预算。
2. **mcp-vault(研究文件夹摄取入口)**:
   - 能力:watch 指定文件夹(PDF/docx/md/txt/csv/xlsx/图片/聊天导出)增量入库;
     哈希去重;解析失败分类(no-text 等);触发既有 knowledge ETL(Docling/MarkItDown/Unstructured);
   - 设计:文件夹即知识入口,零摩擦捕获;图片首期仅元数据+缩略图,OCR 为后续增强;
   - 中文检索:依赖既有 Hybrid(向量+BM25),BM25 需 CJK 分词配置(预分词或 n-gram)。
3. **mcp-plot(数据→可复现图,沙箱)**:
   - 能力:CSV/XLSX → 生成 matplotlib/R 代码 → **沙箱执行** → 渲染图+脚本归档;
     输出对接 Figure Studio(前端)与 knowledge 回流;
   - 纪律:代码是产物、图是渲染结果;脚本随图可复现;默认只读执行沙箱、无网络;
   - 领域默认:作物学图规范(dpi≥300、字号、双栏宽),样式映射到期刊模板。
4. 三个 MCP 均遵循:task_id 贯穿日志、调用可审计、密钥/凭据仅存环境与 Secret。

## Consequences

- Reviewer 的"引用必须可解析"由 mcp-scholar 提供机器核验通道(幽灵引用=0 放行的工程实现);
- mcp-vault 取代 PaperHelp v3.0 原计划的 Node sidecar 自研解析(不再重复造轮子);
- mcp-plot 是 R3「数据→图」闭环的服务端承载;
- 工具注册到 ResearchOS 既有 MCP 客户端(runtime/researchos_runtime/mcp_client.py)与工具目录 `tools/`。
