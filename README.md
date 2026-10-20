# 课题组科研自动化助手 · Research Automation Assistant

> 面向学术课题组的本地优先科研工作流工具：**文献检索 → 合法全文获取 → PDF 转 Markdown → 结构化入库 → （规划中）RAG 问答 / 方向画像 / 写作辅助**。

[![CI](https://github.com/phonsh0x/research-automation-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/phonsh0x/research-automation-assistant/actions/workflows/ci.yml)

> 徽章指向 `phonsh0x/research-automation-assistant`；若仓库改名或转移，需同步更新此处与下方 clone 地址。

---

## 一、项目定位

一个运行在本地、面向单个课题组的**科研文献流水线**：
把「找文献、下全文、转格式、建库、查资料」这些重复劳动串成一条可复用、可审计的流水线，
而不是散落在一堆脚本、浏览器书签和临时 Excel 里。

它**不是**通用文献管理器的替代品（Zotero / EndNote 依然更适合日常阅读管理），
而是在它们之外补齐**批量检索 → 批量获取 → 批量结构化**这一段工程化缺口。

## 二、为什么开发它

科研工作中真正耗时的往往不是"读论文"，而是读之前的准备工作：

| 痛点 | 本项目的处理方式 |
|---|---|
| 同一关键词要在 5 个数据库里各搜一遍、手动去重 | 多源聚合检索 + DOI 去重 + 统一入库 |
| 找到 DOI 后还要逐个判断是否开放获取、能不能下 | 分级全文解析链（Unpaywall → PMC → arXiv → 出版社 OA → 机构授权） |
| PDF 无法全文检索、无法喂给模型 | PyMuPDF 结构化抽取，转成带标题层级的 Markdown |
| 下载记录、失败原因、访问合法性没有留痕 | `fulltext_access` 审计表记录每次获取的来源与风险级别 |
| 课题组新同学要重新踩一遍坑 | 统一 CLI、统一配置、统一日志、299 个自动化测试 |

**设计底线**：只走合法开放渠道。项目内置盗版站点黑名单并在下载前强制拦截
（`src/fulltext/restricted_sources.py`），机构授权下载必须由用户显式确认。

## 三、核心功能

### 已完成（可直接使用）

- **多源文献检索**：OpenAlex、Crossref、PubMed（E-utilities）、Europe PMC 四个数据源，
  统一 `SearchQuery` / `PaperMetadata` 模型，指数退避重试、429 响应尊重 `Retry-After`
- **多源聚合与去重**：DOI 去重 + 标题/年份弱去重，聚合结果一次性入库，检索运行写入 `search_runs`
- **期刊监控**：内置 15 本化学/生物医药方向期刊的 RSS 清单，支持增删、启停、优先级、并发抓取
- **合法全文获取**：Unpaywall → PMC → arXiv → 出版社 OA → 机构授权（需确认）→ 人工上传 五级链路，
  下载前做域名黑名单校验、magic bytes 校验、SHA-256 校验、大小限制、重试与指数退避
- **PDF 转 Markdown**：PyMuPDF 提取元数据 / 标题层级 / 正文，生成可检索 Markdown，
  并计算质量分数（`src/pdf_converter/quality.py`）
- **结构化文献库**：SQLite（WAL）13 张表 + 3 视图 + 17 索引，DOI/标题去重、CRUD、多条件检索、
  BibTeX 导出、下载统计、全文访问审计
- **后台任务**：`ThreadPoolExecutor` 任务管理器 + 任务表持久化，支持重启后把僵死任务标记为 `interrupted`；
  上传 PDF 自动归档入库走异步任务
- **Streamlit 前端**：9 个页面（首页 / 检索 / 文献库 / 全文获取 / PDF 转换 / RAG / 画像 / 写作 / 设置），
  UI 与业务逻辑之间有一层 `ui/services/`
- **FastAPI 后端**：19 个端点（健康检查、统计、检索、全文、PDF 转换、BibTeX 导出等），
  自带 Swagger(`/docs`) 与 ReDoc(`/redoc`)
- **统一路径解析**：`src/files/path_resolver.py` 统一处理相对/绝对路径、非法字符、重名覆盖，
  数据库中只存 `data/xxx` 形式的可移植路径
- **配置与日志**：YAML + `.env` 两级配置覆盖，按模块+日期分文件的滚动日志

### 部分完成（能用，但能力有限）

| 模块 | 现状 | 缺口 |
|---|---|---|
| PDF → Markdown | 可用（PyMuPDF 文本层抽取） | 仅识别英文常见章节标题；扫描版/图片型 PDF 无 OCR；图表计数固定为 0；参考文献计数不准确 |
| 数据入库 | 可用 | DOI 未做规范化（大小写、`dx.doi.org`、尾部斜杠）；标题弱去重键在 SQL 与 Python 两侧不一致 |
| 全文获取 | 可用 | 机构授权链路未接入真实登录流程；失败状态缺少重试次数与 `downloading` 中间态 |

### 规划中（尚未实现，代码中为显式占位）

| 模块 | 代码位置 | 说明 |
|---|---|---|
| RAG 问答引擎 | `src/rag/engine.py` | 4 个方法均返回占位值；**仅 `src/rag/chunker.py` 已实现**（Markdown 切片） |
| 向量化 / 向量库 | `embeddings` 表、`data/vector_db/` 目录已预留 | 无 embedding 客户端、无 ChromaDB 调用 |
| 课题组画像 | `src/group_profile/profiler.py` | 全部方法返回空/占位 |
| 写作辅助 | `src/writing_assist/assistant.py` | 全部方法返回空/占位 |
| RAG / 画像 / BibTeX API | `api/main.py` 对应端点 | 返回"将在后续阶段实现" |

> 说明：`api/main.py` 的 `/api/v1/export/bibtex` 目前是占位返回，
> 但仓库层 `PaperRepository.export_bibtex()` 已实现并被 Streamlit 文献库页面使用。

## 四、功能完成度

| 阶段 | 内容 | 状态 |
|---|---|---|
| Phase 1 | 项目骨架、数据库、配置、日志、CLI | ✅ 完成 |
| Phase 2.1 | 多源文献检索 + 聚合入库 + 期刊监控 | ✅ 完成 |
| Phase 2.2 | 合法全文获取（5 级链路 + 合规拦截） | ✅ 完成 |
| Phase 2.3 | PDF 转 Markdown + UI 验收 + 路径统一 + 后台任务 | ✅ 完成 |
| Phase 2.4 | RAG：切片 ✅ / 向量化 ⛔ / 检索 ⛔ / 生成 ⛔ | 🚧 进行中（约 15%） |
| Phase 3 | 课题组画像、写作辅助 | ⛔ 未开始（仅占位） |

## 五、系统架构

```
┌──────────────────────────────┐      ┌──────────────────────────────┐
│  Streamlit UI (ui/)          │      │  FastAPI (api/main.py)       │
│  views → services → src      │      │  19 个 REST 端点              │
└──────────────┬───────────────┘      └──────────────┬───────────────┘
               │                                     │
               └──────────────┬──────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 业务层 (src/)                                                        │
│  paper_search  fulltext  pdf_converter  rag  tasks  files           │
│  group_profile  writing_assist  config  utils                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 数据层                                                               │
│  storage/repository.py (论文/作者/关键词/统计/BibTeX)                 │
│  tasks/repository.py   (后台任务表)                                   │
│  database/connection.py + migrations.py (SQLite WAL, 13 表 3 视图)    │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
        data/paper.db   data/pdf/   data/markdown/   data/logs/
```

**分层约定**：`ui/views` 只做渲染；`ui/services` 负责编排；`src/` 不感知 UI；
数据库访问集中在 `repository`。已知的反向依赖见「已知问题」。

## 六、技术栈

| 类别 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.11 | 使用 `X | None` 等 3.10+ 语法 |
| 前端 | Streamlit 1.39.1 | 锁定版本以兼容 starlette |
| 后端 | FastAPI 0.114.2 + Starlette 0.38.6 + Uvicorn 0.34.0 | 三者版本存在冲突，已锁定于兼容区间 |
| 存储 | SQLite（WAL 模式） | 单文件、零部署、便于备份 |
| PDF | PyMuPDF 1.23+ | 文本层抽取 |
| 检索 | OpenAlex / Crossref / PubMed / Europe PMC / RSS | 全部为公开 API |
| 全文合法性 | Unpaywall + PMC OA + arXiv + 出版社 OA | 无盗版源 |
| 测试 | pytest 7.4+ | 299 个用例 |
| 规划中 | ChromaDB、DeepSeek API | 尚未接入 |

> 版本冲突说明：`streamlit>=1.40` 要求 `starlette>=0.40`，而 `fastapi<0.115` 要求 `starlette<0.39`，
> 两者无交集，因此锁定 `streamlit==1.39.1 / starlette==0.38.6 / fastapi==0.114.2`。
> 升级任一方前必须重新验证三者兼容性。

## 七、安装

```bash
git clone https://github.com/phonsh0x/research-automation-assistant.git
cd research-automation-assistant

# 建议使用虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

依赖说明：`requirements.txt` 只安装**当前代码实际导入**的包。
`chromadb`、`marker-pdf` 等向量/备选引擎依赖已注释，待对应模块实现后再启用，避免无谓拉取重型依赖。

## 八、配置

所有配置都有可用默认值，**只有 LLM 相关配置需要你自行填写**（且仅在未来启用 RAG 时才需要）。

```bash
# 1. 复制环境变量模板
cp config/.env.template config/.env

# 2. 按需填写（config/.env 已被 .gitignore 忽略，不会进入 Git）
```

主要配置项：

| 变量 | 必填 | 用途 |
|---|---|---|
| `PAPER_ASSIST_CONTACT_EMAIL` | 推荐 | 写入 User-Agent，Crossref/Unpaywall 的礼貌池要求 |
| `PAPER_ASSIST_CROSSREF_MAILTO` | 推荐 | Crossref polite pool，显著降低被限流概率 |
| `PAPER_ASSIST_UNPAYWALL_EMAIL` | 推荐 | Unpaywall 查询必需 |
| `PAPER_ASSIST_NCBI_API_KEY` | 可选 | PubMed 速率从 3 req/s 提升到 10 req/s |
| `PAPER_ASSIST_LLM_API_KEY` | 规划中 | DeepSeek API Key，RAG 实现后才使用 |

完整配置项见 `config/default.yaml`（含检索、下载、PDF 转换、RAG、日志等分段）。

> 环境变量覆盖规则：`PAPER_ASSIST_<SECTION>_<KEY>=value`，仅支持两级嵌套。
> 因此 `institution_access`、`pdf_conversion` 这类含下划线的 section 暂不支持用环境变量覆盖，
> 需直接修改 `config/default.yaml`。

## 九、使用

```bash
python run.py init     # 初始化数据库（首次运行，幂等）
python run.py ui       # 启动 Streamlit 前端 → http://localhost:8501
python run.py api      # 启动 FastAPI 后端 → http://localhost:8000/docs
python run.py test     # 运行全部测试
```

典型工作流：

1. `python run.py init` 建库（自动创建 13 张表、3 个视图，并写入 15 本默认期刊）
2. `python run.py ui` → **文献检索**页输入关键词/年份，勾选数据源，检索并入库
3. **全文获取**页筛选待下载文献 → 解析合法来源 → 下载（或手动上传你已有权限的 PDF）
4. **PDF 转换**页批量转成 Markdown，产出在 `data/markdown/`
5. **我的文献库**页检索、查看、导出 BibTeX

## 十、测试

```bash
python run.py test          # 等价于 pytest tests -v
python -m pytest tests -q   # 静默模式
```

当前基线：**299 passed**，覆盖数据库、仓库层、四个检索源、全文获取链路、
路径解析、PDF 转换、RAG 切片、后台任务。

测试不需要网络：所有外部 API 调用均被 mock，PDF 用例在运行时生成最小 PDF。

## 十一、数据与隐私

- **全部数据本地存储**：`data/paper.db`、`data/pdf/`、`data/markdown/`、`data/logs/`
- **`.gitignore` 已排除**：数据库、PDF、Markdown 产物、日志、向量库、`.env` 与 API Key
- **不会上传任何文献或元数据**；除检索/全文查询本身外，不产生第三方请求
- **密钥只从环境变量读取**，不写入代码、不写日志；`/api/v1/settings` 相关 UI 对 Key 做掩码显示
- **日志含检索关键词**（用于排查），介意可在 `config/default.yaml` 调整日志级别

## 十二、合法全文获取与版权边界

本项目**只提供开放获取（Open Access）与用户自身已获授权内容**的获取能力：

- ✅ 允许：Unpaywall 标记的 OA 版本、PubMed Central OA 子集、arXiv 预印本、
  出版社官方 OA 页面、校园网/VPN 授权范围内的下载、用户自行上传的合法副本
- ⛔ 明确禁止：Sci-Hub、Library Genesis、Z-Library 及任何绕过付费墙的服务。
  这些域名在 `src/fulltext/restricted_sources.py` 中硬编码拦截，
  `src/fulltext/downloader.py` 在发请求前再次校验，双重拦截
- ⚠️ 机构授权下载必须由用户在界面上显式勾选"我确认具备访问权限"，
  且每次访问都会写入 `fulltext_access` 审计表（来源、状态、合法性、风险级别）

**使用者责任**：请遵守所在机构订阅协议与当地著作权法。本项目不存储、不分发受版权保护的全文，
仅协助你在合法权限内自动化已有的获取流程。

## 十三、项目结构

```
research-automation-assistant/
├── run.py                      # 统一 CLI：init / ui / api / test
├── requirements.txt            # 运行依赖（仅实际导入的包）
├── pyproject.toml              # pytest / ruff 工具配置（非打包元数据）
├── LICENSE                     # MIT
├── README.md
├── CHANGELOG.md
├── config/
│   ├── default.yaml            # 默认配置（检索/下载/PDF/RAG/日志）
│   ├── .env.template           # 环境变量模板
│   └── api_keys.template.json  # API Key 结构模板
├── api/
│   └── main.py                 # FastAPI 应用（19 端点）
├── ui/
│   ├── app.py                  # Streamlit 入口（侧边栏路由）
│   ├── state.py                # session_state 集中管理
│   ├── constants.py            # 页面列表与选项常量
│   ├── styles.py               # 主题与 CSS
│   ├── views/                  # 9 个页面（注意：不是 ui/pages）
│   ├── components/             # 8 个可复用组件
│   └── services/               # 5 个 UI 服务（封装后端调用）
├── src/
│   ├── config.py               # YAML + env 配置加载
│   ├── database/               # 连接管理 + DDL + 迁移引擎
│   ├── storage/repository.py   # 论文/作者/关键词/统计/BibTeX
│   ├── paper_search/           # 4 个检索源 + 聚合 + 期刊监控 + RSS
│   ├── fulltext/               # 全文解析链 + 下载 + 合规拦截
│   ├── pdf_converter/          # PyMuPDF → Markdown + 质量评分
│   ├── rag/                    # chunker（已实现）+ engine（占位）
│   ├── tasks/                  # 后台任务管理器 + 任务表
│   ├── files/path_resolver.py  # 统一路径解析
│   ├── group_profile/          # 课题组画像（占位）
│   ├── writing_assist/         # 写作辅助（占位）
│   └── utils/logger.py         # 按模块+日期分文件日志
├── migrations/                 # v01–v04 SQL 迁移脚本
├── docs/                       # 架构决策、阶段计划、验收记录
├── tests/                      # 299 个测试
└── data/                       # 运行时数据（Git 忽略）
```

## 十四、Roadmap

| 优先级 | 内容 |
|---|---|
| P1 | DOI 规范化统一（去重/入库共用同一 `normalize_doi`）；修正 OpenAlex 年份区间过滤；修复 `/convert/batch` 路由被 `/{paper_id}` 遮蔽 |
| P1 | 扩充 API 测试（当前仅覆盖路由可达性）、chunker 语义测试、后台任务状态机测试 |
| P2 | RAG 落地：embedding 接入 → ChromaDB 持久化 → 混合检索（向量+BM25）→ 重排 → 引用回标 |
| P2 | PDF 转换质量：扫描件 OCR 兜底、图/表计数、参考文献解析、质量门槛拦截 |
| P2 | 架构解耦：`src/services/` 承载编排逻辑，消除 `api → ui` 反向依赖；Repository 按领域拆分 |
| P3 | 课题组画像（方向抽取、关键词云、合作网络）与写作辅助（综述生成、润色、引用推荐） |
| P3 | 可观测性（结构化日志、任务进度条、耗时指标）与大规模基准测试（万篇级） |

## 十五、已知问题（会在后续版本处理）

- **DOI 去重未做规范化**：大小写、`http://dx.doi.org/`、尾部斜杠等不同写法会被当作不同文献重复入库
- **标题弱去重键不一致**：Python 侧剥离全部非单词字符，SQL 侧只移除 `.` `,` 与双空格，两侧键难以命中
- FastAPI 端点均为 `async def` 但内部是同步 SQLite/HTTP 调用，高并发下会阻塞事件循环
- `ui/components/job_status.py`、`ui/services/search_ui_service.py` 存在越过 service 层直接访问数据库的情况
- `api/main.py` 反向依赖 `ui/services/*`，API 进程会连带加载 Streamlit
- 测试仍会写入真实 `data/paper.db`（非隔离临时库），影响并行与可重复性
- 扫描版 PDF 无 OCR 兜底，图表计数固定为 0

已在 v0.3.0 修复：OpenAlex/Crossref 年份区间过滤、`/convert/batch` 路由遮蔽、版本号不一致、
`.gitignore` 混合编码。

## 十六、贡献

欢迎 Issue / PR。提交前请确保：

```bash
python run.py test     # 299 passed 为基线
```

代码风格：4 空格缩进、类型注解优先、日志统一用 `src.utils.logger.get_logger(__name__)`。

## 十七、License

[MIT](LICENSE) © 2026 phonsh0x

第三方数据源（OpenAlex、Crossref、PubMed、Europe PMC、Unpaywall、arXiv）遵循各自的服务条款与许可，
本项目仅调用其公开 API，不声明对其数据的所有权。
