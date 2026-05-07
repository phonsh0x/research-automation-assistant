# Phase 1 Baseline — 项目骨架版

日期：2026-05-07

---

## 1. 项目概述

**课题组科研自动化助手** 是一个面向学术课题组内部的文献管理与科研辅助系统，覆盖"文献检索 -> 全文获取 -> 格式转换 -> 入库 -> RAG 问答 -> 方向画像 -> 写作辅助"全链路。Phase 1 阶段完成了完整的项目骨架搭建，包括目录结构、数据库 schema、FastAPI 后端框架、Streamlit 前端框架和核心模块占位。

---

## 2. 目录结构

```
research-automation-assistant/
|-- config/
|   |-- default.yaml              # 默认系统配置（YAML）
|   |-- .env.template             # 环境变量模板
|   |-- api_keys.template.json    # API 密钥模板
|-- src/
|   |-- __init__.py
|   |-- config.py                 # 配置管理（YAML + 环境变量）
|   |-- database/
|   |   |-- __init__.py
|   |   |-- connection.py         # DatabaseManager 单例 + DDL
|   |   |-- migrations.py         # 迁移引擎
|   |-- paper_search/
|   |   |-- __init__.py
|   |   |-- models.py             # PaperMetadata 数据模型
|   |   |-- searcher.py           # PaperSearcher 检索框架
|   |-- pdf_converter/
|   |   |-- __init__.py
|   |   |-- converter.py          # PDFConverter 转换管道
|   |-- storage/
|   |   |-- __init__.py
|   |   |-- repository.py         # PaperRepository CRUD
|   |-- rag/
|   |   |-- __init__.py
|   |   |-- engine.py             # RAGEngine 检索-重排-生成
|   |-- group_profile/
|   |   |-- __init__.py
|   |   |-- profiler.py           # GroupProfiler 方向抽取
|   |-- writing_assist/
|   |   |-- __init__.py
|   |   |-- assistant.py          # WritingAssistant 综述/润色
|   |-- utils/
|       |-- __init__.py
|       |-- logger.py             # 统一日志系统
|-- api/
|   |-- main.py                   # FastAPI 入口（7 端点 + CORS）
|-- ui/
|   |-- app.py                    # Streamlit 入口（8 页导航）
|-- data/                         # 运行时数据（gitignore 排除）
|   |-- pdf/                      #   已下载 PDF
|   |-- markdown/                 #   转换后的 Markdown
|   |-- vector_db/                #   ChromaDB 向量库
|   |-- paper.db                  #   SQLite 数据库
|   |-- profiles/                 #   课题组画像报告
|   |-- search_results/           #   检索结果导出
|   |-- logs/                     #   日志文件
|-- tests/
|   |-- __init__.py
|   |-- test_database.py          # 数据库单元测试（5 项）
|-- migrations/
|   |-- v01_initial_schema.sql    # 初始 schema 版本记录
|-- docs/
|   |-- phase1_baseline.md        # 本文档
|-- requirements.txt              # Python 依赖（分段标注）
|-- run.py                        # 统一启动脚本
|-- README.md                     # 项目说明
|-- CHANGELOG.md                  # 变更日志
|-- .gitignore                    # Git 排除规则
```

---

## 3. 核心模块职责

| 模块 | 子包/文件 | 关键类 | 职责 | Phase 1 状态 |
|------|----------|--------|------|-------------|
| 配置管理 | `src/config.py` | `load_config`, `get_config` | YAML + 环境变量三级优先级加载 | **已实现** |
| 数据库 | `src/database/connection.py` | `DatabaseManager` | SQLite 连接管理、建表 DDL、幂等初始化 | **已实现** |
| 数据库迁移 | `src/database/migrations.py` | `apply_pending_migrations` | 按版本号顺序执行 SQL 迁移 | **已实现** |
| 统一日志 | `src/utils/logger.py` | `init_logging`, `get_logger` | 按模块 + 日期分文件轮转 | **已实现** |
| 文献检索 | `src/paper_search/searcher.py` | `PaperSearcher` | 多 API 检索、去重、排序框架 | 占位 |
| 数据模型 | `src/paper_search/models.py` | `PaperMetadata` | 论文元数据 dataclass | 占位 |
| PDF 转换 | `src/pdf_converter/converter.py` | `PDFConverter` | PDF → Markdown 转换管道框架 | 占位 |
| 数据入库 | `src/storage/repository.py` | `PaperRepository` | CRUD、DOI 去重、BibTeX 导出框架 | 占位 |
| RAG 引擎 | `src/rag/engine.py` | `RAGEngine` | 检索-重排-生成管道框架 | 占位 |
| 课题组画像 | `src/group_profile/profiler.py` | `GroupProfiler` | 方向抽取、合作网络框架 | 占位 |
| 写作辅助 | `src/writing_assist/assistant.py` | `WritingAssistant` | 综述/润色框架 | 占位 |

---

## 4. 数据库 Schema

### 用户表（10 张）

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| `schema_version` | Schema 版本追踪 | version, applied_at, description |
| `papers` | 论文主表 | paper_id, title, doi, arxiv_id, pmid, pdf_path, md_path |
| `authors` | 作者表 | author_id, name, orcid, affiliation |
| `paper_authors` | 论文-作者关联 | paper_id, author_id, author_order, is_corresponding |
| `keywords` | 关键词表 | keyword_id, keyword, language |
| `paper_keywords` | 论文-关键词关联 | paper_id, keyword_id, is_author_kw |
| `full_texts` | 全文 Markdown | paper_id, content, section_count, figure_count |
| `citations` | 引用关系 | citing_paper_id, cited_doi, cited_title, citation_context |
| `group_profile` | 课题组论文画像 | paper_id, research_area, method_tags, domain_tags |
| `embeddings` | 向量嵌入元数据 | paper_id, chunk_index, chunk_text, chroma_id, embed_model |

### 视图（3 个）

| 视图名 | 用途 |
|--------|------|
| `v_paper_full` | 论文完整信息（含作者聚合、关键词聚合） |
| `v_group_papers` | 课题组论文子集 |
| `v_fulltext_available` | 有全文 Markdown 的论文 |

### 索引（10 个）

`papers` 表：doi, year, journal, oa_status, is_group_paper, title(全文搜索)
`authors` 表：name
`keywords` 表：keyword
`embeddings` 表：paper_id
`full_texts` 表：content(全文搜索)

### 关键属性

- WAL 模式开启
- 外键约束开启（ON DELETE CASCADE）
- UNIQUE 约束：doi, arxiv_id, pmid, pmcid, orcid, keyword
- 幂等初始化：`CREATE TABLE IF NOT EXISTS`

---

## 5. API 端点

| 方法 | 路径 | 用途 | 状态 |
|------|------|------|------|
| GET | `/api/v1/health` | 服务健康检查 | 已实现 |
| GET | `/api/v1/stats` | 系统统计信息 | 框架就绪 |
| POST | `/api/v1/search` | 文献检索 | 占位 |
| POST | `/api/v1/rag/query` | RAG 问答 | 占位 |
| POST | `/api/v1/convert` | PDF 转 Markdown | 占位 |
| GET | `/api/v1/profile/report` | 课题组画像报告 | 占位 |
| GET | `/api/v1/export/bibtex` | BibTeX 导出 | 占位 |

附加功能：
- CORS 中间件（允许所有来源）
- Swagger 文档 (`/docs`)
- ReDoc 文档 (`/redoc`)
- lifespan 生命周期（启动时初始化数据库）

---

## 6. Streamlit 页面

| 页面名称 | 导航标签 | 功能 |
|---------|---------|------|
| 首页 — 系统概览 | `首页 — 系统概览` | 系统介绍、状态概览卡片 |
| 文献检索 | `文献检索` | 关键词输入、数据源选择、年份过滤（占位） |
| 我的文献库 | `我的文献库` | 论文列表、BibTeX/CSV 导入导出（占位） |
| PDF 转换 | `PDF 转换` | PDF 上传和格式选择（占位） |
| RAG 智能问答 | `RAG 智能问答` | 文献问答输入（占位） |
| 课题组画像 | `课题组画像` | 研究方向分析（占位） |
| 写作辅助 | `写作辅助` | 综述/润色/基金申请书（占位） |
| 系统设置 | `系统设置` | API 配置、系统参数、关于信息 |

---

## 7. 已实现功能 vs 占位功能

| 已实现（Phase 1） | 占位（Phase 2-3） |
|-------------------|-------------------|
| 项目目录结构（19 个目录/文件） | 多 API 文献检索具体逻辑 |
| SQLite 数据库 Schema（11 表 + 3 视图 + 10 索引） | PDF 下载器实现 |
| DatabaseManager 单例 + 幂等初始化 | PDF → Markdown 转换（marker/pymupdf） |
| Schema 迁移引擎（版本号驱动） | 文献元数据入库（CRUD） |
| 配置系统（YAML + 环境变量 + 类型转换） | DOI 去重逻辑 |
| 统一日志系统（模块 + 日期轮转） | BibTeX 导出具体实现 |
| PaperSearcher 检索框架类 | ChromaDB 向量化与索引 |
| PaperMetadata 数据模型 | RAG 检索-重排-生成 |
| PDFConverter 转换管道框架 | 课题组方向自动抽取 |
| PaperRepository CRUD 框架 | 合作网络分析 |
| RAGEngine 管道框架 | 写作辅助（综述/润色） |
| GroupProfiler 方向抽取框架 | LLM 集成（DeepSeek API） |
| WritingAssistant 综述/润色框架 | 关键词云可视化 |
| FastAPI 7 个 REST 端点 + CORS + lifespan | |
| Streamlit 8 页导航 + 路由 | |
| .gitignore 排除敏感/运行时文件 | |
| 5 项数据库单元测试（全通过） | |
| 版本冲突锁定（streamlit/starlette/fastapi） | |

---

## 8. Phase 2 开发计划

以下功能为 Phase 2 需要实现的核心模块：

1. **文献检索实现**
   - 实现 PaperSearcher 的具体检索逻辑
   - 接入 OpenAlex、Crossref、PubMed、arXiv、Semantic Scholar API
   - 结果去重（DOI/arXiv ID 匹配）、排序
   - 分页与渐进式加载

2. **PDF 下载与转换**
   - 实现 Unpaywall OA 状态查询
   - 合法 PDF 下载器（断点续传）
   - PDFConverter 完整转换管道（marker + pymupdf）
   - 转换质量验证

3. **数据入库实现**
   - PaperRepository 完整 CRUD
   - DOI 去重检查
   - BibTeX 导出
   - 批量导入支持

4. **RAG 问答（Phase 2 核心）**
   - ChromaDB 向量化入库
   - 嵌入模型集成（bge-large-zh-v1.5）
   - 混合检索（向量 + BM25/FTS5）
   - 重排序 + LLM 生成（DeepSeek API）
   - 引用溯源标注

5. **单元测试扩展**
   - 检索模块测试（mock API）
   - 下载模块测试
   - 转换模块测试
   - 入库模块测试
   - RAG 引擎测试

---

## 9. 锁定依赖版本

为解决 Streamlit / Starlette / FastAPI 三方版本冲突，Phase 1 锁定以下核心依赖版本范围：

| 包名 | 版本范围 | 锁定原因 |
|------|---------|---------|
| `streamlit` | >=1.28.0, <1.40.0 | streamlit 1.40+ 依赖 starlette>=0.40 |
| `fastapi` | >=0.110.0, <0.115.0 | fastapi 0.115+ 依赖 starlette>=1.0 |
| `starlette` | >=0.37.2, <0.39.0 | 三者在 starlette 0.38 形成兼容交集 |
| `uvicorn` | >=0.24.0 | ASGI 服务器，无冲突风险 |

兼容交集说明：streamlit<1.40 和 fastapi<0.115 都需要 starlette<0.39/0.40，锁定 starlette 0.38 系列确保两者同时可用。

完整依赖清单请参见 `requirements.txt`。
