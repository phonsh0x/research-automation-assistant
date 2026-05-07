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
