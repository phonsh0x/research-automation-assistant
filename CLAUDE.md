# CLAUDE.md

## 项目信息

- **项目名称**: research-automation-assistant
- **项目定位**: 课题组科研自动化助手，覆盖文献检索、合法全文获取、PDF 转 Markdown、RAG 问答、课题组画像、写作辅助
- **技术栈**: Python 3.11、Streamlit 1.39.1、FastAPI 0.114.2、SQLite WAL、DeepSeek-V4-Pro

## 启动命令

```bash
python run.py init     # 初始化数据库（首次运行）
python run.py test     # 运行全部测试（必须通过）
python run.py ui       # 启动 Streamlit 前端 (http://localhost:8501)
python run.py api      # 启动 FastAPI 后端 (http://localhost:8000)
```

## 当前完成

- **Phase 1** — 项目骨架：配置系统、日志系统、数据库 Schema（11表+3视图）、FastAPI 框架、Streamlit 框架
- **Phase 2.1** — 多源文献检索：OpenAlex / Crossref / PubMed / Europe PMC，DOI去重 + title+year弱去重，search_runs 日志
- **Phase 2.2** — 合法全文获取：Unpaywall / PMC / arXiv / PublisherOA / InstitutionAccess / ManualUpload，Sci-Hub/LibGen 域名黑名单，fulltext_access 审计表

## 当前未完成

- **UI 重构** — ui/app.py 1268 行严重超载，存在 StreamlitDuplicateElementId 风险，需拆分为 pages/components/services/state/styles
- **Phase 2.3** — PDF 转 Markdown（src/pdf_converter/，当前占位）
- **Phase 2.4** — Markdown 分块与 ChromaDB 向量化
- **Phase 2.5** — RAG 检索增强生成问答
- **Phase 3** — 课题组画像和写作辅助

## 合规边界（严禁突破）

- **禁止实现**: Sci-Hub、LibGen、Z-Library 等盗版源的任何访问逻辑
- **禁止**: 绕过验证码、绕过付费墙、账号共享、批量规避访问限制
- **机构访问**: 仅用于用户已获得学校合法授权的资源，不保存校园网账号密码
- **人工上传**: 仅处理用户自己合法获得的 PDF，必须弹出 rights_confirmation 确认
- **域名黑名单**: `src/fulltext/restricted_sources.py` 中的 `_BLOCKED_DOMAINS` + `validate_url()` 双重拦截

## 开发规则

### 通用规则
- 每次开发前运行 `git status`，确认工作区状态
- 每个阶段先建分支（如 `feature/ui-refactor`、`feature/phase2.3-pdf-convert`）
- 小步提交，每个 commit 只做一件事
- 修改代码后必须运行 `python run.py test` 确认全部通过
- 禁止提交: `data/paper.db`、`data/pdf/`、`data/markdown/`、`data/vector_db/`、`data/logs/`、`.env`、真实 API Key

### Streamlit 前端规则
- **所有 Streamlit 控件必须显式 `key=`**，不允许依赖自动生成的 widget ID
- **新增 UI 功能必须拆到子模块**，不允许继续往 `ui/app.py` 塞大段代码：
  - `ui/pages/` — 页面级组件
  - `ui/components/` — 可复用小组件
  - `ui/services/` — 后端调用封装
- **session_state 键统一在 `ui/state.py` 中管理**
- **常量（页面列表、关键词模板等）集中到 `ui/constants.py`**
- **自定义 CSS 放到 `ui/styles.py`**

### 数据库规则
- **所有 SQL 必须参数化**（`?` 占位符），严禁字符串拼接
- **修改 schema 必须新增 migration 文件**（`migrations/vXX_description.sql`）
- **不破坏已有数据**: papers、authors、fulltext_access、search_runs 表不得丢失数据
- **新增字段**: 使用 `ALTER TABLE ADD COLUMN`，在 migration 中处理 SQLite 限制

### 测试规则
- 单元测试**不依赖真实外网**（mock API 响应）
- 真实下载只能作为手动验证（不在 CI 中运行）
- 运行 `python run.py test` 必须 100% 通过
- 新增功能必须同步新增测试

## 关键文件路径

- 配置: `config/default.yaml`
- 数据库: `src/database/connection.py` + `migrations/`
- 检索: `src/paper_search/searcher.py` (入口) → `aggregator.py` (聚合) → `openalex.py`/`crossref.py`/`pubmed.py`/`europe_pmc.py`
- 全文: `src/fulltext/service.py` (编排) → `unpaywall.py`/`pmc.py`/`arxiv.py`/`publisher_oa.py`/`institution_access.py`
- 黑名单: `src/fulltext/restricted_sources.py`
- 数据仓库: `src/storage/repository.py`
- API: `api/main.py`
- UI: `ui/app.py` (当前超载，待重构)
- 测试: `tests/test_*.py`

## 版本兼容约束

- streamlit==1.39.1（不能升到 1.40+，会与 fastapi 的 starlette 要求冲突）
- starlette==0.38.6（streamlit<1.40 和 fastapi<0.115 的兼容交集）
- fastapi==0.114.2（不能升到 0.115+，需要 starlette>=1.0）
- 升级任何一个前须同步验证三者的 starlette 依赖上限
