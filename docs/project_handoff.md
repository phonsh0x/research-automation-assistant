# 项目交接文档

> 最后更新: 2026-05-07
> 交接版本: 0.2.0 (Phase 2)

---

## 一、项目目标

课题组科研自动化助手 — 面向学术课题组的文献管理与科研辅助系统。

**全链路**: 文献检索 → 合法全文获取 → PDF 转 Markdown → 向量化 → RAG 问答 → 课题组画像 → 写作辅助

---

## 二、当前目录结构

```
research-automation-assistant/
├── CLAUDE.md                    # 项目级规则（新会话自动加载）
├── README.md                    # 项目说明
├── CHANGELOG.md                 # 变更日志
├── requirements.txt             # Python 依赖（分段标注）
├── run.py                       # 统一启动脚本
├── .gitignore                   # Git 排除规则
│
├── config/
│   ├── default.yaml             # 默认配置（15 个配置段）
│   ├── .env.template            # 环境变量模板
│   └── api_keys.template.json   # API 密钥模板
│
├── api/
│   ├── __init__.py
│   └── main.py                  # FastAPI 后端（18 个端点）
│
├── ui/
│   └── app.py                   # Streamlit 前端（9 页，1268 行，待重构）
│
├── src/
│   ├── __init__.py
│   ├── config.py                # 配置管理（YAML + 环境变量）
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py        # DatabaseManager 单例（11 表 + 3 视图）
│   │   └── migrations.py        # Schema 迁移引擎
│   ├── paper_search/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseSearcher ABC
│   │   ├── models.py            # SearchQuery / SearchResult / PaperMetadata
│   │   ├── searcher.py          # PaperSearcher 入口
│   │   ├── aggregator.py        # 多源聚合 + DOI 去重 + 入库
│   │   ├── openalex.py          # OpenAlex API 检索源
│   │   ├── crossref.py          # Crossref API 检索源
│   │   ├── pubmed.py            # PubMed Entrez 检索源
│   │   ├── europe_pmc.py        # Europe PMC 检索源
│   │   ├── journal_watchlist.py # 期刊监控清单
│   │   └── rss_watcher.py       # RSS 抓取器
│   ├── fulltext/
│   │   ├── __init__.py
│   │   ├── base.py              # FullTextResult + FullTextResolver ABC
│   │   ├── downloader.py        # 下载工具 + URL 黑名单验证
│   │   ├── unpaywall.py         # Unpaywall OA 查询
│   │   ├── pmc.py               # PubMed Central OA
│   │   ├── arxiv.py             # arXiv 预印本
│   │   ├── publisher_oa.py      # 出版社 OA 接口
│   │   ├── institution_access.py# 机构网络授权
│   │   ├── manual_upload.py     # 人工 PDF 上传
│   │   ├── restricted_sources.py# 非法来源域名黑名单
│   │   └── service.py           # 全文获取编排
│   ├── storage/
│   │   ├── __init__.py
│   │   └── repository.py        # PaperRepository CRUD + 统计 + 导出
│   ├── pdf_converter/
│   │   ├── __init__.py
│   │   └── converter.py         # PDF 转 Markdown（占位）
│   ├── rag/
│   │   ├── __init__.py
│   │   └── engine.py            # RAG 检索引擎（占位）
│   ├── group_profile/
│   │   ├── __init__.py
│   │   └── profiler.py          # 课题组画像（占位）
│   ├── writing_assist/
│   │   ├── __init__.py
│   │   └── assistant.py         # 写作辅助（占位）
│   └── utils/
│       ├── __init__.py
│       └── logger.py            # 统一日志系统
│
├── tests/
│   ├── __init__.py
│   ├── test_database.py         # 数据库 DDL / 迁移测试
│   ├── test_paper_search.py     # 文献检索全链路测试（51 个）
│   ├── test_fulltext.py         # 全文获取模块测试（27 个）
│   └── test_repository.py       # 数据仓库测试（27 个）
│
├── migrations/
│   ├── v01_initial_schema.sql   # 初始 schema
│   └── v02_fulltext_access.sql  # 全文获取审计表 + papers 字段补列
│
├── docs/
│   ├── phase1_baseline.md       # Phase 1 基线文档
│   ├── project_handoff.md       # 本文档
│   ├── current_status.md        # 当前状态
│   ├── next_tasks.md            # 下一步任务
│   ├── architecture_decisions.md# 架构决策记录
│   ├── ui_refactor_plan.md      # UI 重构计划
│   └── phase2_3_plan.md         # Phase 2.3 PDF 转换计划
│
├── data/                        # 运行时数据（gitignore 排除）
│   ├── pdf/                     #   已下载 PDF
│   ├── markdown/                #   转换后的 Markdown
│   ├── vector_db/               #   ChromaDB 向量库
│   ├── paper.db                 #   SQLite 数据库
│   ├── profiles/                #   课题组画像报告
│   ├── search_results/          #   检索结果导出
│   └── logs/                    #   日志文件
│
└── .claude/
    ├── agents/                  # Claude Code 自定义 agent（空）
    └── skills/                  # Claude Code 自定义 skill（空）
```

---

## 三、核心模块说明

| 模块 | 入口文件 | 核心类 | 职责 |
|------|---------|--------|------|
| 配置 | `src/config.py` | `get_config(path)` | YAML + 环境变量三级优先级加载 |
| 数据库 | `src/database/connection.py` | `DatabaseManager` | SQLite WAL 连接、建表 DDL、迁移 |
| 检索 | `src/paper_search/searcher.py` | `PaperSearcher` → `SearchAggregator` | 多 API 检索、去重、入库 |
| 全文 | `src/fulltext/service.py` | `FullTextAcquisitionService` | 按优先级串联 6 个 Resolver |
| 存储 | `src/storage/repository.py` | `PaperRepository` | 论文 CRUD、搜索、统计、导出 |
| API | `api/main.py` | `FastAPI app` | 18 个 REST 端点 + CORS |
| UI | `ui/app.py` | Streamlit | 9 页交互界面（待重构） |
| 日志 | `src/utils/logger.py` | `init_logging` / `get_logger` | 按模块+日期分文件 |

---

## 四、数据流

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 文献检索                                                         │
│   用户输入关键词 → PaperSearcher.search(query)                       │
│   → OpenAlex / Crossref / PubMed / Europe PMC API 调用              │
│   → SearchAggregator 按 DOI/(title+year) 去重                       │
│   → papers 表入库 → search_runs 表记录日志                           │
│   → 用户看到检索结果列表                                              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. 合法全文获取                                                      │
│   从 papers 表取 download_status=pending 的论文                       │
│   → FullTextAcquisitionService.resolve(paper_id)                    │
│   → 按优先级尝试: Unpaywall → PMC → arXiv → PublisherOA → Institution│
│   → 下载 PDF → 保存到 data/pdf/ → 计算 SHA256                        │
│   → 更新 papers.download_status/pdf_path                            │
│   → 写入 fulltext_access 审计表                                      │
│   → RestrictedSourceResolver 拦截 Sci-Hub/LibGen                    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. PDF 转 Markdown (待实现 — Phase 2.3)                              │
│   PDFConverter.convert(pdf_path)                                    │
│   → marker / pymupdf 引擎                                           │
│   → 输出到 data/markdown/                                           │
│   → 更新 papers.md_path → full_texts 表写入内容                      │
│   → 质量检测（字符数、行数）                                          │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. Markdown 分块与向量化 (待实现 — Phase 2.4)                        │
│   Chunker → 按 paragraph/sentence/fixed 策略分块                     │
│   → Embedder (bge-large-zh-v1.5) 向量化                              │
│   → ChromaDB 持久化 → embeddings 表记录映射                           │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. RAG 问答 (待实现 — Phase 2.5)                                     │
│   用户提问 → 混合检索（向量 + BM25/FTS5）→ 重排序                     │
│   → 组装上下文 → DeepSeek-V4-Pro 生成回答                             │
│   → 返回答案 + 引用来源                                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 6. 课题组画像 + 写作辅助 (待实现 — Phase 3)                           │
│   GroupProfiler: 研究方向抽取、合作网络、关键词聚类                    │
│   WritingAssistant: 综述/基金申请书/论文引言                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 五、已完成 vs 未完成

### 已完成（有真实实现，非占位）

- **Phase 1**: 项目骨架（配置、日志、数据库 Schema、FastAPI 框架、Streamlit 框架）
- **Phase 2.1**: 多源文献检索（4 个 API 检索源 + 聚合去重 + 入库 + search_runs 日志）
- **Phase 2.2**: 合法全文获取（6 个获取渠道 + 域名黑名单 + fulltext_access 审计 + API 14 个端点中 10 个为真实实现）

### 未完成（占位或未开始）

- **UI 重构**: `ui/app.py` 1268 行需要拆分为 pages/components/services/state/styles
- **Phase 2.3**: PDF 转 Markdown（`src/pdf_converter/converter.py` 为占位，API `/api/v1/convert` 为占位）
- **Phase 2.4**: Markdown 分块与向量化
- **Phase 2.5**: RAG 问答（`src/rag/engine.py` 为占位，API `/api/v1/rag/query` 为占位）
- **Phase 3**: 课题组画像 + 写作辅助（`src/group_profile/profiler.py` 和 `src/writing_assist/assistant.py` 为占位）

---

## 六、当前最优先任务

**UI 重构** — 阻塞所有后续 UI 开发。

详细计划见 `docs/ui_refactor_plan.md`。核心步骤：
1. 补充 widget key → 2. 拆 state/constants/styles → 3. 拆 components → 4. 拆 services → 5. 拆 pages

---

## 七、Git 分支和提交建议

```
当前分支: master
当前状态: 仅 ui/app.py 有未提交修改

建议:
  1. git add ui/app.py && git commit -m "chore: snapshot ui/app.py before refactor"
  2. git checkout -b feature/ui-refactor
  3. 按 docs/ui_refactor_plan.md 逐步提交
  4. 合并回 master 后再创建 feature/phase2.3-pdf-convert
```

---

## 八、新会话如何继续

### 第 1 步: 确认环境

```bash
cd /path/to/research-automation-assistant
git status
python run.py test  # 当前基线：299 passed
```

### 第 2 步: 阅读关键文档

按优先级：
1. `CLAUDE.md` — 项目规则和规则
2. `docs/current_status.md` — 当前真实状态
3. `docs/next_tasks.md` — 下一步任务清单
4. `docs/ui_refactor_plan.md` — UI 重构详细计划

### 第 3 步: 开始 UI 重构

```bash
git checkout -b feature/ui-refactor
# 按 docs/ui_refactor_plan.md Step 1 开始
```

### 关键约束

- **每次修改后运行 `python run.py test`** — 必须 299 passed
- **不要往 `ui/app.py` 塞新代码** — 优先拆分
- **不要实现 Sci-Hub/LibGen** — 合规红线
- **不要破坏已有 schema** — 新增用 migration
- **所有 widget 必须显式 `key=`**
