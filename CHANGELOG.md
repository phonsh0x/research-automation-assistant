# 变更日志

## [v0.2.2-ui-refactor] — 2026-05-07 UI 重构

### 架构重构
- `ui/app.py` 从 1297 行简化为 103 行入口路由
- 拆分 9 个页面至 `ui/pages/`，每个页面导出 `render()`
- 抽离 7 个可复用组件至 `ui/components/`（layout / metric_cards / paper_table / filters / messages / actions）
- 抽离 5 个 service 至 `ui/services/`（repository / search / fulltext / export），封装全部后端调用
- 抽离 `ui/state.py`（50+ key 常量 + session_state 集中管理）
- 抽离 `ui/constants.py`（页面列表、12 MedChem chips、全部选项）
- 抽离 `ui/styles.py`（set_page_config + 自定义 CSS）

### 交互优化
- 文献检索页：st.form 批量提交 + 12 个药物化学快捷 chips + 论文选择详情
- 全文获取页：筛选→选择→详情→操作工作流；手动 paper_id 降级至折叠调试区
- 校园网授权访问和手动上传均设合规确认 gate

### 兼容性修复
- 所有交互控件显式 `key=`（72 处），消除 StreamlitDuplicateElementId
- 适配 streamlit==1.39.1：st.form_submit_button / st.tabs / st.columns / st.expander 不传 key
- 加固空状态处理：selectbox None 检查、dict.get 替代裸 key 访问、label_to_id 映射

### 测试
- 110 passed, 0 failed
- src/ / api/ / tests/ / migrations/ 零修改

---

## [Phase 2.3.2] — 2026-05-11 PDF 转 Markdown UI 验收

### 已转换 Markdown 展示 (A)
- `fbe58a3` feat: show converted markdown files in pdf conversion UI
- PDF 转 Markdown 页面新增"已转换 Markdown"区域
- 支持已转换 Markdown 文件展示、预览、下载
- 下载文件名使用安全文件名生成逻辑
- 批量选择、批量转换、刷新状态、下载功能已通过人工验收

### 异常状态与边界情况 (B)
- `9f10b12` fix: improve pdf markdown edge status labels
- `ui/services/pdf_convert_ui_service.py` 新增 `_pdf_label()` helper
- `_md_label()` 改用 `markdown_status()`，保留 Markdown 缺失显示为"未转换"的 UI 语义
- `get_pending_papers()` / `get_converted_papers()` 复用状态 helper，减少重复判断逻辑
- PDF 状态支持：路径缺失 / 文件不存在 / 不是文件 / 文件为空 / 格式异常 / 已存在
- Markdown 状态支持：未转换 / 不是文件 / 文件为空 / 格式异常 / 已转换
- `tests/test_pdf_converter.py` 新增 10 个边界情况测试

### 测试
- Phase 2.3.2-A 合并后：245 passed in 14.15s
- Phase 2.3.2-B 分支提交后：255 passed in 14.20s
- Phase 2.3.2-B 合并 master 后：255 passed in 14.60s
- 当前 master 工作区 clean

---

## [Phase 2.3.1] — 2026-05-09 后台任务加固 & 路径统一

### 后台任务系统 (B0-A)
- `9d56b62` feat: add background jobs and automatic pdf upload ingestion
- `f7db54d` feat: harden background job recovery
- TaskManager + ThreadPoolExecutor + stale running job 恢复
- JobRepository 便捷方法（mark_job_running/success/failed/interrupted）
- JobStatus 新增 INTERRUPTED 状态
- 测试隔离：tmp_path 临时数据库 + uuid checksum

### 路径统一 (B1-B6)
- `5f9bfec` feat: add centralized file path resolver — `src/files/path_resolver.py`
- `8a18066` fix: use centralized path resolver for upload ingestion
- `77bfd5f` refactor: use path resolver in pdf conversion ui service
- `197a918` refactor: use path resolver for pdf conversion outputs
- `bc3c121` feat: add storage path normalization for legacy db paths
- `d7d72e5` fix: normalize stored paths before file-existence checks in pdf conversion

### 当前路径策略
- **写入 DB**: `to_portable_path()` → 保存 `data/xxx/yyy` 格式，正斜杠
- **读取 DB**: `normalize_storage_path()` → 兼容旧 Windows 绝对路径、反斜杠、缺少/重复 data/ 前缀
- **文件检查**: `normalize_storage_path()` → `resolve_project_path()` → `is_file()`
- 不再依赖 CWD，不再硬编码 `Path("data/pdf")`

### UI 修复
- `14121be` fix: remove user-facing paper id remnants — 普通界面不显示内部 ID
- `f7db54d` fix: remove empty streamlit widget labels — 3 处 `st.checkbox("")` 修复

### 测试
- **245 passed**, 0 failed
- 新增 `tests/test_path_resolver.py` (71 tests)
- 新增 `tests/test_background_jobs.py` (31 tests, 完整隔离)

---

## [Phase 1] — 2026-05-07 项目骨架版

### 已完成
- 项目目录结构搭建（config/、src/、api/、ui/、data/、tests/、docs/、migrations/）
- 数据库模块：SQLite 11 表 + 3 视图 + 10 索引，WAL 模式，幂等初始化，迁移引擎
- 配置系统：YAML + 环境变量三级优先级
- 统一日志系统：按模块 + 日期分文件轮转
- 文献检索模块：PaperSearcher 框架 + PaperMetadata 数据模型（占位）
- PDF 转换模块：PDFConverter 管道框架（占位）
- 数据入库模块：PaperRepository CRUD + DOI 去重 + BibTeX 导出（占位）
- RAG 模块：RAGEngine 检索-重排-生成管道框架（占位）
- 课题组画像模块：GroupProfiler 方向抽取框架（占位）
- 写作辅助模块：WritingAssistant 综述/润色框架（占位）
- FastAPI 后端：7 个 REST 端点 + Swagger/ReDoc 文档 + CORS + lifespan 生命周期
- Streamlit 前端：8 页侧边栏导航界面
- 单元测试：5 项数据库测试全部通过
- 安全措施：无硬编码密钥、无绝对路径、.gitignore 正确排除敏感文件

### 版本冲突修复
- **Streamlit / Starlette / FastAPI 版本冲突**：streamlit>=1.40 依赖 starlette>=0.40，fastapi<0.115 依赖 starlette<0.39，两者无交集
- **解决方案**：降级 streamlit 至 1.39.1，锁定三者在 starlette 0.38 兼容交集
- **锁定版本**：
  - streamlit==1.39.1
  - starlette==0.38.6
  - fastapi==0.114.2
  - uvicorn==0.34.0
