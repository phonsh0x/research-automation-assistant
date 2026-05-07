# 架构决策记录 (ADRs)

---

## ADR-001: paper_search 只负责元数据检索

**日期**: 2026-05-07
**状态**: 已确认

### 决策

paper_search 模块只负责从外部 API 获取论文元数据（标题、作者、DOI、摘要等），不负责全文下载。

### 理由

- 检索和全文获取是不同的数据源和协议：检索用 REST API（OpenAlex、Crossref），全文获取需要处理文件下载、OA 状态查询、机构认证
- 分离后各模块可独立测试：检索模块 mock API JSON 响应，全文模块 mock PDF 文件
- 符合单一职责原则：Searcher 关心"有哪些论文"，FullText 关心"论文能拿到吗"

### 边界

- paper_search: 调用 API → 返回 PaperMetadata → 写入 papers 表 → 记录 search_runs
- fulltext: 从 papers 表取待获取论文 → 调用各 resolver → 下载 PDF → 更新 pdf_path/download_status → 写入 fulltext_access

---

## ADR-002: fulltext 单独作为合法全文获取层

**日期**: 2026-05-07
**状态**: 已确认

### 决策

全文获取独立为 `src/fulltext/` 模块，包含 6 个 Resolver 和 1 个编排 Service。

### 理由

- 全文获取涉及法律合规（合法 OA / 机构订阅 / 版权确认），与检索的纯技术问题不同
- 每个 Resolver 的处理逻辑截然不同（API 查询 vs 直接 URL 构造 vs 用户上传 vs 阻拦），但对外接口统一（`source_name` + `resolve(paper) → FullTextResult`）
- 编排逻辑（按优先级尝试、失败降级）独立于具体渠道实现
- 法律审计需要独立表（`fulltext_access`），与论文元数据表分离

### 架构

```
FullTextAcquisitionService (编排层)
  ├── UnpaywallResolver       (OA 元数据查询)
  ├── PMCResolver             (PMC OA 子集)
  ├── ArxivResolver           (预印本)
  ├── PublisherOAResolver     (Gold/Hybrid OA)
  └── InstitutionAccessResolver (机构订阅)
  
RestrictedSourceResolver    (拦截层，不参与下载)
ManualUploadResolver        (带外上传)
```

---

## ADR-003: pdf_converter 单独负责 PDF 转 Markdown

**日期**: 2026-05-07
**状态**: 已确认

### 决策

PDF 转 Markdown 独立为 `src/pdf_converter/`，不混入 fulltext 或 rag 模块。

### 理由

- PDF 转换是计算密集型操作（marker 需要 GPU/CPU 推理），与全文下载（网络 I/O）和 RAG（向量检索）的资源特征不同
- 支持多种转换引擎（marker/pymupdf/nougat），需要在文件级别做缓存判断（"已转换过且未修改 → 跳过"）
- 转换质量检测（字符数、行数、公式保留率）是独立的质量维度
- 输出（Markdown 文件路径 + full_texts 表内容）是 RAG 和写作辅助的输入

### 数据流位置

```
PDF (data/pdf/) ──→ pdf_converter ──→ Markdown (data/markdown/)
                                          │
                                          ├── full_texts 表
                                          └── 向量化输入
```

---

## ADR-004: RAG 不直接读取 PDF，而读取 Markdown 和向量库

**日期**: 2026-05-07
**状态**: 已确认

### 决策

RAG 问答模块的检索源是 Markdown 文本块和 ChromaDB 向量库，不直接从 PDF 中提取。

### 理由

- PDF 格式复杂（多栏、图表、公式），每次问答时实时解析 PDF 延迟不可接受
- Markdown 已结构化（标题层级、段落边界），分块质量更好
- 向量检索是 RAG 的核心性能路径，需要预计算的 embedding（放在 ChromaDB 中）
- 分离后可以独立升级转换引擎而不影响问答效果

### 数据流

```
data/markdown/ ──→ Chunker ──→ Embedder ──→ ChromaDB (向量)
                                                │
                              data/markdown/ ──┤ (混合检索)
                                                │
                              Query ────────────┼──→ LLM ──→ Answer
```

---

## ADR-005: Streamlit 前端拆成 pages/components/services/state/styles

**日期**: 2026-05-07
**状态**: 已确认，待实施

### 决策

将当前 1268 行的 `ui/app.py` 拆分为：

```
ui/
  app.py              # 入口 + 轻量路由（~50行）
  state.py             # 所有 session_state 键和初始化
  constants.py         # 页面列表、模板、版本号等常量
  styles.py            # st.set_page_config + 自定义 CSS
  components/          # 可复用组件（统计卡片、结果表格等）
  services/            # 后端调用封装（检索、下载、文献库）
  pages/               # 每个页面一个文件，导出 render()
```

### 理由

- 当前单文件 1268 行，全部 9 个页面混在 `if/elif` 链中，新增页面导致线性膨胀
- 存在 StreamlitDuplicateElementId 风险：widget key 在全局命名空间不唯一时 Streamlit 抛异常
- 拆分为独立文件后，每个页面修改不触碰其他页面
- `ui/services/` 层封装后端调用后，组件可以不经由 session_state 直接测试

### 原则

- 所有 Streamlit widget 必须有显式 `key=`
- 每个页面文件只导出一个 `render()` 函数
- 组件不直接读 `st.session_state`，通过参数接收数据
- service 不直接写 `st.session_state`，返回结果由调用方写入

---

## ADR-006: 禁止 Sci-Hub / LibGen / 绕过付费墙

**日期**: 2026-05-07
**状态**: 已确认，已实现双重拦截

### 决策

系统在任何情况下不实现、不调用、不引导用户使用 Sci-Hub、Library Genesis、Z-Library 或任何绕过期刊付费墙的手段。

### 理由

- 法律合规：Sci-Hub 和 LibGen 在多数司法管辖区属于侵权服务
- 学术伦理：课题组作为正规学术机构，应以合法途径获取文献
- 系统安全：盗版网站常伴随恶意广告和钓鱼风险
- 机构合规：避免课题组因使用盗版资源面临学校或出版社的法律行动

### 实现方式

1. **URL 验证层**（`src/fulltext/downloader.py:validate_url()`）：拒绝 `sci-hub.*`、`libgen.*`、`z-lib.*` 域名的 URL
2. **Resolver 拦截层**（`src/fulltext/restricted_sources.py:RestrictedSourceResolver`）：`resolve()` 直接返回 `unsupported_source`，不尝试任何下载
3. **域名黑名单**（`_BLOCKED_DOMAINS`）：23 个已知盗版域名变体
4. **UI 声明**：全文获取页面底部法律声明，列出合法和非法来源

---

## ADR-007: 机构网络访问需用户确认且不保存凭证

**日期**: 2026-05-07
**状态**: 已确认，已实现

### 决策

校园网/VPN 授权访问功能：
- 必须在 UI 中由用户明确勾选"确认我已连接机构网络"后才能触发
- **不保存任何机构账号、密码、VPN 配置、Cookie、Token**
- 每次下载单独请求，不保持会话持久化

### 理由

- 权限边界：系统不知道自己是否在机构网络内，由用户确认是最可靠的方式
- 安全最小化：不保存凭证意味着即使数据库被泄露，攻击者也无法获取机构授权
- 合规要求：学校通常禁止第三方工具存储校园网密码
- 法律清晰：每次下载都是用户主动确认后的一次性操作，有明确的审计记录（`institution_access` 标记在 `fulltext_access` 表中）

### 实现

- `institution_access.py` 的 `download()` 方法要求 `user_confirmed_authorization=True` 参数
- UI 中 `institution_access_confirmed` checkbox 绑定到 session_state
- API 端点 `/api/v1/fulltext/institution/download/{paper_id}` 要求请求体包含 `user_confirmed_authorization: true`
- 每次下载前检测 HTTP 状态码（401/403/429/451），不重试认证失败
