# 当前状态

> 最后更新: 2026-05-07
> 当前版本: 0.2.2 (v0.2.2-ui-refactor)

---

## 一、版本和测试

| 项目 | 状态 |
|------|------|
| 当前版本 | 0.2.2 (Phase 2, UI 重构完成) |
| 总测试数 | **110** |
| 通过 | **110** (100%) |
| 测试文件 | 4 个 (test_database.py, test_paper_search.py, test_fulltext.py, test_repository.py) |
| 运行命令 | `python run.py test` |

---

## 二、已完成模块（有真实实现，非占位）

### 2.1 基础设施

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 配置系统 | `src/config.py` | ✅ | YAML + 环境变量三级优先级，类型转换，缓存 |
| 日志系统 | `src/utils/logger.py` | ✅ | 按模块+日期分文件，自动轮转，同时输出控制台 |
| 数据库管理 | `src/database/connection.py` | ✅ | SQLite WAL 模式，11表+3视图，幂等初始化，种子数据（15个默认期刊） |
| 迁移引擎 | `src/database/migrations.py` | ✅ | 版本号驱动迁移 |
| CLI 入口 | `run.py` | ✅ | 4 命令：api/ui/init/test |

### 2.2 多源文献检索（Phase 2.1）

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 检索器入口 | `src/paper_search/searcher.py` | ✅ | PaperSearcher 包装 SearchAggregator |
| 聚合器 | `src/paper_search/aggregator.py` | ✅ | 多源协调、DOI去重、入库、search_runs 日志 |
| OpenAlex | `src/paper_search/openalex.py` | ✅ | 免费 API，按关键词/年份/OA过滤 |
| Crossref | `src/paper_search/crossref.py` | ✅ | DOI解析 + 关键词检索 |
| PubMed | `src/paper_search/pubmed.py` | ✅ | ESearch + EFetch 流程 |
| Europe PMC | `src/paper_search/europe_pmc.py` | ✅ | 生命科学补充源 |
| 数据模型 | `src/paper_search/models.py` | ✅ | SearchQuery / SearchResult / PaperMetadata |
| 期刊监控 | `src/paper_search/journal_watchlist.py` | ✅ | 15个默认期刊，增删/启用停用 |
| RSS抓取 | `src/paper_search/rss_watcher.py` | ✅ | 多源并发抓取 |
| 检索源基类 | `src/paper_search/base.py` | ✅ | BaseSearcher ABC |

### 2.3 合法全文获取（Phase 2.2）

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 核心模型 | `src/fulltext/base.py` | ✅ | FullTextResult dataclass, FullTextResolver ABC |
| 下载工具 | `src/fulltext/downloader.py` | ✅ | URL验证(含黑名单)、文件名生成、SHA256、PDF头部校验、下载 |
| 编排服务 | `src/fulltext/service.py` | ✅ | FullTextAcquisitionService 按优先级串联所有 resolver |
| Unpaywall | `src/fulltext/unpaywall.py` | ✅ | api.unpaywall.org/v2/{doi}，OA状态查询 |
| PMC | `src/fulltext/pmc.py` | ✅ | PubMed Central OA 子集 |
| arXiv | `src/fulltext/arxiv.py` | ✅ | arXiv ID 提取 + 直接 PDF URL 构造 |
| 出版社OA | `src/fulltext/publisher_oa.py` | ✅ | Gold/Hybrid/Bronze OA 论文 PDF 下载 |
| 机构访问 | `src/fulltext/institution_access.py` | ✅ | 校园网/VPN 授权下载，需用户确认 |
| 人工上传 | `src/fulltext/manual_upload.py` | ✅ | 用户手动上传合法 PDF，版权确认 |
| 受限来源 | `src/fulltext/restricted_sources.py` | ✅ | Sci-Hub/LibGen/Z-Library 黑名单 + 拦截 |
| 模块导出 | `src/fulltext/__init__.py` | ✅ | 导出所有 resolver 和工具函数 |

### 2.4 数据仓库

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 论文仓库 | `src/storage/repository.py` | ✅ | CRUD、多条件搜索、PDF状态更新、全文审计记录、统计、BibTeX导出 |

### 2.5 API

| 端点 | 方法 | 状态 |
|------|------|------|
| `/api/v1/health` | GET | ✅ 真实实现 |
| `/api/v1/stats` | GET | ✅ 真实实现 |
| `/api/v1/search` | POST | ✅ 真实实现 (PaperSearcher) |
| `/api/v1/fulltext/stats` | GET | ✅ 真实实现 |
| `/api/v1/fulltext/pending` | GET | ✅ 真实实现 |
| `/api/v1/fulltext/resolve/{id}` | POST | ✅ 真实实现 |
| `/api/v1/fulltext/download/{id}` | POST | ✅ 真实实现 |
| `/api/v1/fulltext/institution/download/{id}` | POST | ✅ 真实实现 |
| `/api/v1/fulltext/manual-review/{id}` | POST | ✅ 真实实现 |
| `/api/v1/fulltext/manual-upload/{id}` | POST | ✅ 真实实现 |
| `/api/v1/rag/query` | POST | 🔶 占位 |
| `/api/v1/convert` | POST | 🔶 占位 |
| `/api/v1/profile/report` | GET | 🔶 占位 |
| `/api/v1/export/bibtex` | GET | 🔶 占位 |

### 2.6 Streamlit 前端（UI 重构已完成 — v0.2.2）

**架构**：`ui/app.py` (103 行) → 侧边栏 + PAGE_RENDERERS 路由 → 9 个页面模块。

```
ui/
├── app.py              (103 行 — 入口、侧边栏、路由分发)
├── state.py            (213 行 — 50+ key 常量、init、clear helpers)
├── constants.py        (161 行 — 页面列表、12 个 MedChem chips、全部选项)
├── styles.py           ( 56 行 — set_page_config + 自定义 CSS)
├── pages/              (9 页面 + __init__)
│   ├── dashboard.py         — 首页统计
│   ├── literature_search.py — 关键词检索 + 期刊监控 + 12 chips + st.form
│   ├── library.py           — 文献库搜索/筛选/导出
│   ├── fulltext_download.py — 全文获取工作流（选择→详情→操作）
│   ├── pdf_convert.py       — 占位 (Phase 2.3)
│   ├── rag_chat.py          — 占位 (Phase 2.5)
│   ├── group_profile.py     — 占位 (Phase 3)
│   ├── writing_assistant.py — 占位 (Phase 3)
│   └── settings.py          — API 配置、系统参数、关于
├── components/         (7 文件 — layout, metric_cards, paper_table, filters, messages, actions)
└── services/           (5 文件 — repository, search, fulltext, export)
```

| 页面 | 功能 | 状态 |
|------|------|------|
| 首页/系统概览 | 统计卡片、版本信息、法律声明 | ✅ |
| 文献检索 | st.form 表单 + 12 MedChem chips + 期刊监控 + 论文选择详情 | ✅ |
| 我的文献库 | 搜索/筛选/导出 | ✅ |
| 全文获取/PDF下载 | 筛选→选择→详情→操作工作流，校园网授权 gate，手动上传 gate | ✅ |
| PDF 转换 | 上传界面 | 🔶 占位 |
| RAG 智能问答 | 输入界面 | 🔶 占位 |
| 课题组画像 | 说明文字 | 🔶 占位 |
| 写作辅助 | 输入界面 | 🔶 占位 |
| 系统设置 | API配置、系统参数、技术栈信息 | ✅ |

**兼容性规则**（streamlit==1.39.1）：
- 交互控件必须有显式 `key=`：`st.button`, `st.text_input`, `st.number_input`, `st.selectbox`, `st.multiselect`, `st.checkbox`, `st.radio`, `st.text_area`, `st.file_uploader`, `st.download_button`, `st.form`
- 布局 API 不得传 `key`：`st.tabs`, `st.columns`, `st.container`, `st.expander`, `st.form_submit_button`

---

## 三、当前已知问题

### 轻微问题

1. **`_restore_last_search()` 恢复的是"最近入库论文"而非"最近检索结果"** — 按钮名称与实际行为不完全一致
2. **UI 层缺少自动化测试** — 后端 110 测试全部通过，前端 0 测试覆盖
3. **`JournalWatchlist` 仍在页面层直接导入** — `literature_search.py` 中有一处 `# TODO: move to service`

### 已修复问题

- ~~`ui/app.py` 超载（1268 行）~~ → 已拆分为 pages/components/services/state/constants/styles
- ~~StreamlitDuplicateElementId 风险~~ → 所有交互控件显式 key，布局 API 不传 key
- ~~session_state 管理分散~~ → 集中在 `ui/state.py`，50+ key 常量
- ~~文献检索失败时 search_results 未清除~~ → 已修复
- ~~数据库连接泄漏~~ → 已修复
- ~~st.form_submit_button 不支持 key~~ → 已移除
- ~~st.tabs 不支持 key~~ → 已移除
- ~~全文获取页 selectbox 返回 None 崩溃~~ → 已加固

---

## 四、下一步：Phase 2.3 PDF 转 Markdown

**当前阻塞**：无。UI 重构已完成，可以安全地新增 `ui/pages/pdf_convert.py` 和 `src/pdf_converter/` 实现。

**详细计划**：见 `docs/phase2_3_plan.md`

**建议分支**：`feature/phase2.3-pdf-convert`
