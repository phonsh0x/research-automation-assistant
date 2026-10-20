# 当前状态

> 最后更新: 2026-10-20
> 当前版本: 0.3.0（Phase 2.3 完成 + RAG 切片器）

---

## 一、版本与测试

| 项目 | 状态 |
|------|------|
| 当前版本 | 0.3.0 |
| 总测试数 | **299** |
| 通过 | **299**（100%） |
| 基线耗时 | 约 15–17 秒（Windows / Python 3.11.9） |
| 测试文件 | 10 个 |
| 运行命令 | `python run.py test` |

最近一次完整验证：2026-10-20，`299 passed`，工作区 clean。
同时在一个**全新 `git clone`（不含 `data/`）**中验证通过，说明测试不依赖本地运行数据，可用于 CI。

---

## 二、模块实现状态

图例：✅ 真实实现 ｜ 🔶 部分实现/能力受限 ｜ ⛔ 占位（未实现）

### 2.1 基础设施

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 配置系统 | `src/config.py` | ✅ | YAML + 环境变量两级覆盖，支持类型转换与缓存 |
| 日志系统 | `src/utils/logger.py` | ✅ | 按模块+日期分文件、滚动、控制台同步输出 |
| 数据库 | `src/database/connection.py` | ✅ | SQLite WAL，13 表 + 3 视图 + 17 索引，幂等初始化，15 本默认期刊种子数据 |
| 迁移引擎 | `src/database/migrations.py` | ✅ | 版本号驱动，逐文件提交 |
| 路径解析 | `src/files/path_resolver.py` | ✅ | 可移植路径、非法字符、重名规避、上传暂存路径 |
| CLI | `run.py` | ✅ | init / ui / api / test / help |

### 2.2 文献检索（Phase 2.1）

| 模块 | 状态 | 说明 |
|------|------|------|
| OpenAlex | ✅ | 关键词/年份/OA 过滤、分页参数、重试、429 Retry-After |
| Crossref | ✅ | 关键词检索 + DOI 解析 |
| PubMed | ✅ | ESearch + EFetch 流程 |
| Europe PMC | ✅ | 生命科学补充源 |
| 聚合器 | ✅ | 多源并发协调 → DOI/标题去重 → 入库 → search_runs 日志 |
| 期刊监控 | ✅ | 15 本默认期刊，增删/启停/优先级 |
| RSS 抓取 | ✅ | 多源抓取 + 0.5s 礼貌间隔 |
| `check_oa_status` | ⛔ | `PaperSearcher` 上的该方法返回 `unknown`（Unpaywall 能力已在 fulltext 中实现） |

### 2.3 合法全文获取（Phase 2.2）

| 模块 | 状态 | 说明 |
|------|------|------|
| Unpaywall | ✅ | OA 状态与 best OA location |
| PMC | 🔶 | 仅处理 PMCID 直链，未做下载前 URL 有效性校验 |
| arXiv | ✅ | ID 提取 + PDF URL 构造 |
| 出版社 OA | ✅ | Gold/Hybrid/Bronze 判定后下载 |
| 机构授权 | 🔶 | 需显式确认；未接入真实登录流程；`max_downloads_per_run` 等配置未生效 |
| 人工上传 | ✅ | 版权确认 gate + 审核记录 |
| 盗版源拦截 | ✅ | Sci-Hub/LibGen/Z-Library 域名黑名单，解析与下载双重校验 |
| 下载器 | 🔶 | magic bytes + SHA-256 + 大小限制 + 重试；无 `%%EOF` 校验 |

### 2.4 PDF 转 Markdown（Phase 2.3）

| 模块 | 状态 | 说明 |
|------|------|------|
| PyMuPDF 抽取 | ✅ | 元数据、标题层级、正文 → Markdown |
| 质量评分 | ✅ | 字符数/页、行数等启发式打分 |
| 图表计数 | ⛔ | 固定为 0 |
| 参考文献计数 | 🔶 | 基于文本启发式，精度有限 |
| 扫描件 OCR | ⛔ | 未实现 |
| UI 服务 | ✅ | 批量转换、状态标签、Markdown 预览与下载 |

### 2.5 RAG（Phase 2.4）

| 能力 | 状态 | 说明 |
|------|------|------|
| Markdown 切片 | ✅ | `src/rag/chunker.py`，按标题分段 + 超长二次切分 + overlap |
| Ingestion | ⛔ | 转换后未调用切片器，全文内容字段写入空串 |
| Embedding | ⛔ | 无 embedding 客户端 |
| 向量库 | ⛔ | `data/vector_db/` 与 `embeddings` 表已预留但未使用 |
| 混合检索 / 重排 | ⛔ | 无实现 |
| 引用回标 / 上下文组装 | ⛔ | 返回空列表 |
| LLM 调用 | ⛔ | 无客户端；API 返回固定占位文案 |

### 2.6 课题组画像 / 写作辅助（Phase 3）

| 模块 | 状态 |
|------|------|
| `src/group_profile/profiler.py` | ⛔ 全部方法返回空/占位 |
| `src/writing_assist/assistant.py` | ⛔ 全部方法返回空/占位 |
| 对应 UI 页面 | ⛔ 仅显示说明文字 |

---

## 三、API 状态（`api/main.py`，19 个端点）

| 端点 | 方法 | 状态 |
|------|------|------|
| `/api/v1/health` | GET | ✅ |
| `/api/v1/stats` | GET | ✅ |
| `/api/v1/search` | POST | ✅ |
| `/api/v1/fulltext/stats` | GET | ✅ |
| `/api/v1/fulltext/pending` | GET | ✅ |
| `/api/v1/fulltext/resolve/{id}` | POST | ✅ |
| `/api/v1/fulltext/download/{id}` | POST | ✅ |
| `/api/v1/fulltext/institution/download/{id}` | POST | ✅ |
| `/api/v1/fulltext/manual-review/{id}` | POST | ✅ |
| `/api/v1/fulltext/manual-upload/{id}` | POST | ✅（旧版兼容接口） |
| `/api/v1/convert/stats` | GET | ✅ |
| `/api/v1/convert/pending` | GET | ✅ |
| `/api/v1/convert/{id}` | POST | ✅ |
| `/api/v1/convert/batch` | POST | ⚠️ 被 `/{id}` 路由遮蔽，返回 422 |
| `/api/v1/convert/preview/{id}` | GET | ✅ |
| `/api/v1/convert` | POST | ✅ |
| `/api/v1/rag/query` | POST | ⛔ 占位 |
| `/api/v1/profile/report` | GET | ⛔ 占位 |
| `/api/v1/export/bibtex` | GET | ⛔ 占位（仓库层 `export_bibtex()` 已可用） |

---

## 四、Streamlit 前端

**架构**：`ui/app.py`（103 行入口）→ 侧边栏 + `PAGE_RENDERERS` 路由 → 9 个 `ui/views/` 页面。

```
ui/
├── app.py              — 入口、侧边栏、路由分发
├── state.py            — session_state 键常量、初始化、清理
├── constants.py        — 页面列表与选项常量
├── styles.py           — 页面配置与全局 CSS
├── views/              — 9 个页面（**注意：不是 pages**）
├── components/         — 8 个可复用组件
└── services/           — 5 个 UI 服务，封装后端调用
```

| 页面 | 状态 | 说明 |
|------|------|------|
| 首页/系统概览 | ✅ | 统计卡片、版本信息、合规声明 |
| 文献检索 | ✅ | 表单检索、12 个 MedChem chips、期刊监控、结果详情 |
| 我的文献库 | ✅ | 检索、筛选、BibTeX 导出 |
| 全文获取 / PDF 下载 | ✅ | 筛选→选择→详情→操作，机构授权与手动上传均有合规 gate |
| PDF 转换 | ✅ | 批量转换、状态标签、Markdown 预览与下载 |
| RAG 智能问答 | ⛔ | 占位说明 |
| 课题组画像 | ⛔ | 占位说明 |
| 写作辅助 | ⛔ | 占位说明 |
| 系统设置 | ✅ | API 配置、系统参数、技术栈信息 |

**Streamlit 1.39.1 兼容规则**：
- 交互控件必须显式 `key=`：button / text_input / number_input / selectbox / multiselect /
  checkbox / radio / text_area / file_uploader / download_button / form
- 布局 API 不得传 `key`：tabs / columns / container / expander / form_submit_button

---

## 五、已知问题

### 功能性

1. **DOI 未规范化**：`aggregator.py` 与 `repository.py` 直接比较原始 DOI，
   `https://doi.org/`、`http://dx.doi.org/`、大小写差异会被视为不同文献
2. **标题弱去重失效**：Python 侧剥离全部非单词字符，SQL 侧只移除 `.` `,` 和双空格，两侧键不一致

### 架构性

3. `api/main.py` 反向依赖 `ui/services/*`（API 进程会 import streamlit）
4. `ui/services/search_ui_service.py` 直接开 sqlite 连接写 SQL，绕过 repository
5. `ui/components/job_status.py` 在展示组件内创建 repository
6. `api` 端点均为 `async def`，内部却是同步 SQLite/HTTP/PDF 调用，高并发会阻塞事件循环
7. `PaperRepository` 已达 1000+ 行 / 25 个方法，承担论文、作者、关键词、统计、导出五类职责
8. 空结果与失败均返回 `[]` / `False` / `-1`，调用方无法区分

### 测试

9. `tests/test_fulltext.py`、`tests/test_pdf_converter.py` 会写入真实 `data/paper.db`
10. `ui/views/`、`ui/state.py` 仍无测试；`api/main.py` 仅有 3 个路由可达性测试
11. 部分 chunker / 后台任务测试断言过弱（不变量缺失）

### 已于 v0.3.0 修复

- OpenAlex 年份区间过滤（改为 `from_publication_date` / `to_publication_date`）
- Crossref 单边年份被静默忽略
- `/convert/batch` 被 `/{paper_id}` 路由遮蔽
- 三处版本号（UI / API / tag）不一致
- `.gitignore` 混合编码（UTF-8 + GBK）


---

## 六、下一步

| 优先级 | 任务 |
|--------|------|
| P1 | DOI 规范化统一（聚合与入库共用同一 `normalize_doi`）；标题弱去重 SQL/Python 对齐 |
| P1 | 扩充 API 测试（当前仅路由可达性）；把写真实数据库的测试改为 tmp_path 隔离 |
| P2 | RAG 落地：embedding → ChromaDB → 混合检索 → 重排 → 引用回标 |
| P2 | 抽 `src/services/` 消解 `api → ui` 反向依赖；按领域拆分 Repository |
| P3 | 课题组画像与写作辅助 |

详细分阶段审计与重构建议见 `docs/architecture_decisions.md` 与项目 issue 跟踪。
