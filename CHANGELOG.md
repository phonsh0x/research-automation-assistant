# 变更日志

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
