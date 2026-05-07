# 下一步任务清单

> 按优先级排序。P0 必须在新功能前完成，P1 为优化，P2 为下一阶段功能。
> 每条任务含验收标准和建议 commit message。

---

## P0: UI 重构（阻断后续开发）

### P0-1 确认工作区干净

- [ ] `git status` 确认只有 `ui/app.py` 有修改
- [ ] `python run.py test` 确认 110 测试全部通过
- [ ] 如 `ui/app.py` 有未提交改动，先 `git add ui/app.py && git commit -m "chore: snapshot ui/app.py before refactor"`
- **验收**: `git status --porcelain` 输出为空或仅含计划内文件

### P0-2 新建 UI 重构分支

```bash
git checkout -b feature/ui-refactor
```

- **验收**: `git branch --show-current` 输出 `feature/ui-refactor`
- **commit**: N/A（空分支）

### P0-3 修复 DuplicateElementId 风险

- [ ] 给 `ui/app.py` 中所有未显式 `key=` 的 widget 补充唯一 key
- [ ] 特别检查：`st.radio`（`search_mode`）、`st.text_area`（`rag_question`、`writing_input`）、`st.selectbox`（`writing_type`）
- [ ] 检查所有页面的 `st.button` 是否 each 有唯一 key
- **不允许改**: 任何业务逻辑、后端代码、session_state 键名
- **验收**: 启动 `streamlit run ui/app.py`，遍历所有 9 个页面，确认无 `StreamlitDuplicateElementId` 异常
- **验收**: `python run.py test` 继续通过
- **测试**: 手动点击每个页面按钮至少一次
- **commit**: `fix(ui): add explicit keys to all Streamlit widgets to prevent DuplicateElementId`

### P0-4 抽出 state.py / constants.py / styles.py

- [ ] `ui/state.py`: 搬入 `init_session_state()` + 所有 30+ 个 session_state key 常量定义
- [ ] `ui/constants.py`: 搬入 `page_options` 列表（9 个页面名）、药物化学关键词模板字典、期刊监控默认值、版本号
- [ ] `ui/styles.py`: 搬入 `st.set_page_config()` 调用、自定义 CSS（如果有）
- [ ] 修改 `ui/app.py`：`from ui.state import init_session_state`、`from ui.constants import PAGE_OPTIONS, KEYWORD_TEMPLATES` 等
- **不允许改**: 任何页面渲染逻辑、业务函数
- **验收**: `python run.py test` 通过
- **验收**: `streamlit run ui/app.py` 启动无 import 错误，所有页面功能正常
- **commit**: `refactor(ui): extract state/constants/styles into separate modules`

### P0-5 拆出 ui/components/

- [ ] 识别 `ui/app.py` 中的可复用组件，至少拆出：
  - `ui/components/stats_cards.py` — 首页统计卡片（4 列 metric）
  - `ui/components/search_result_table.py` — `_display_search_results()` 中的表格渲染
  - `ui/components/pending_papers_table.py` — 全文获取页面的待下载列表
  - `ui/components/page_message.py` — `show_page_message()` 跨页面消息组件
- [ ] 每个组件是一个接收参数（不直接读 `st.session_state`）的函数
- [ ] 在 `ui/app.py` 中 import 并调用这些组件
- **不允许改**: 任何 session_state 读写逻辑、后端调用
- **验收**: 所有页面渲染结果与拆分前完全一致
- **验收**: `python run.py test` 通过
- **commit**: `refactor(ui): extract reusable components into ui/components/`

### P0-6 拆出 ui/services/

- [ ] 将后端调用封装从页面代码中提取到 `ui/services/`：
  - `ui/services/search_service.py` — `_execute_search()` 核心逻辑
  - `ui/services/fulltext_service.py` — `resolve()` / `download()` / `batch_download()` 调用封装
  - `ui/services/library_service.py` — 文献库搜索逻辑
- [ ] 每个 service 函数不直接操作 `st.session_state`，而是返回结果
- [ ] 页面回调中调用 service，然后将返回结果写入 session_state
- **不允许改**: session_state 键名、业务逻辑的语义
- **验收**: 所有页面功能与拆分前一致
- **验收**: `python run.py test` 通过
- **commit**: `refactor(ui): extract backend service calls into ui/services/`

### P0-7 拆出 ui/pages/

- [ ] 将 9 个页面的渲染逻辑从 `ui/app.py` 的 `if/elif` 链中拆出：
  - `ui/pages/home.py`
  - `ui/pages/paper_search.py`
  - `ui/pages/library.py`
  - `ui/pages/fulltext.py`
  - `ui/pages/pdf_convert.py`
  - `ui/pages/rag.py`
  - `ui/pages/group_profile.py`
  - `ui/pages/writing.py`
  - `ui/pages/settings.py`
- [ ] 每个页面文件导出一个 `render()` 函数
- [ ] `ui/app.py` 变为轻量路由：`pages[page_key].render()`
- **不允许改**: 任何 session_state 键名、组件的外观
- **验收**: 所有 9 个页面切换正常，功能与拆分前完全一致
- **验收**: `python run.py test` 通过
- **commit**: `refactor(ui): split monolithic app.py into per-page modules under ui/pages/`

---

## P1: 页面优化

### P1-1 优化文献检索页

- [ ] 检索结果支持分页（而非一次显示全部）
- [ ] 检索历史下拉选择（从 `search_runs` 表读取）
- [ ] "恢复最近检索"按钮改为精确恢复（按 `search_runs.run_id` 匹配）
- [ ] 期刊监控页面的结果支持导出
- **验收**: 手动检索关键词，翻页查看结果
- **验收**: 从检索历史中选择上一次查询，重新执行
- **测试**: `python run.py test`
- **commit**: `feat(ui): add pagination and search history to search page`

### P1-2 优化全文获取/PDF下载页

- [ ] 批量下载支持进度条（`st.progress`）
- [ ] 已下载 PDF 列表独立 tab
- [ ] 下载失败的论文显示重试按钮
- [ ] 人工上传支持拖拽
- **验收**: 手动批量下载 5 篇（如果有待获取论文），观察进度条
- **验收**: 切换 tab 查看已下载列表
- **测试**: `python run.py test`
- **commit**: `feat(ui): add progress bar and tabs to fulltext page`

### P1-3 完整前端手动验收

- [ ] 遍历所有 9 个页面
- [ ] 确认无 JavaScript 控制台错误
- [ ] 确认页面切换后状态不丢失
- [ ] 确认所有按钮都能点击且不报错
- **验收**: 手动遍历清单全部通过
- **commit**: `test(ui): complete manual acceptance pass`

---

## P2: Phase 2.3–2.5（新功能）

### P2-1 PDF 转 Markdown

详见 `docs/phase2_3_plan.md`。需在 UI 重构完成后执行。

- **预计范围**: `src/pdf_converter/` + `ui/pages/pdf_convert.py` + FastAPI `/api/v1/convert`
- **commit prefix**: `feat(phase2.3): ...`

### P2-2 Markdown 分块与 ChromaDB 向量化

- [ ] 实现 `src/rag/chunker.py`（paragraph/sentence/fixed 策略）
- [ ] 实现 `src/rag/embedder.py`（bge-large-zh-v1.5 / text-embedding-3-small）
- [ ] 实现 ChromaDB 连接管理 `src/rag/vector_store.py`
- [ ] 批量向量化 CLI 命令：`python run.py embed`
- **commit prefix**: `feat(phase2.4): ...`

### P2-3 RAG 问答

- [ ] 实现混合检索（向量 + BM25/FTS5）
- [ ] 实现重排序（Cross-Encoder 或 LLM rerank）
- [ ] 实现 LLM 生成（DeepSeek API）
- [ ] 来源追踪和回答证据标注
- [ ] 前端 RAG 页面接入真实后端
- [ ] FastAPI `/api/v1/rag/query` 真实实现
- **commit prefix**: `feat(phase2.5): ...`

---

## 分支策略

```
master ─────────────────────────────────────────────
  │
  ├── feature/ui-refactor (P0-2 到 P0-7)
  │     └── 合并回 master 后再继续
  │
  ├── feature/phase2.3-pdf-convert
  ├── feature/phase2.4-embedding
  └── feature/phase2.5-rag
```
