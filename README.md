# 课题组科研自动化助手

当前版本为 **Phase 1 项目骨架版** — 完整的目录结构、数据库、API/UI 框架已就绪，具体业务逻辑待后续阶段实现。

基于 DeepSeek-V4-Pro 的课题组科研自动化工具，覆盖"文献检索 -> 全文获取 -> 格式转换 -> 入库 -> RAG问答 -> 方向画像 -> 写作辅助"全链路。

## 技术栈

- **后端**: Python + FastAPI
- **前端**: Streamlit
- **数据库**: SQLite
- **向量库**: ChromaDB
- **LLM**: DeepSeek-V4-Pro（通过 API）
- **文献检索**: OpenAlex, Crossref, PubMed, arXiv, Semantic Scholar, Unpaywall

## 项目结构

```
research-automation-assistant/
|-- config/                  # 配置文件
|   |-- default.yaml         #   默认系统配置
|   |-- .env.template        #   环境变量模板
|   |-- api_keys.template.json  # API 密钥模板
|-- src/                     # 源代码
|   |-- database/            #   数据库管理（Schema, 连接, 迁移）
|   |-- paper_search/        #   文献检索模块
|   |-- pdf_converter/       #   PDF 转 Markdown 模块
|   |-- storage/             #   数据入库模块
|   |-- rag/                 #   RAG 检索引擎
|   |-- group_profile/       #   课题组画像模块
|   |-- writing_assist/      #   写作辅助模块
|   |-- utils/               #   工具（日志）
|   |-- config.py            #   配置管理
|   |-- __init__.py
|-- api/                     # FastAPI 后端
|   |-- main.py              #   API 主入口
|-- ui/                      # Streamlit 前端
|   |-- app.py               #   交互界面
|-- data/                    # 运行时数据
|   |-- pdf/                 #   已下载 PDF
|   |-- markdown/            #   转换后的 Markdown
|   |-- vector_db/           #   ChromaDB 向量库
|   |-- paper.db             #   SQLite 文献数据库
|   |-- profiles/            #   课题组画像报告
|   |-- search_results/      #   检索结果导出
|   |-- logs/                #   日志文件
|-- tests/                   # 测试
|-- migrations/              # 数据库迁移脚本
|-- requirements.txt         # Python 依赖
|-- run.py                   # 统一启动脚本
|-- README.md
```

## 快速开始

### 1. 安装依赖

```bash
cd research-automation-assistant
pip install -r requirements.txt
```

### 2. 配置 API 密钥

```bash
# 复制环境变量模板
cp config/.env.template config/.env

# 编辑 config/.env 填入你的 API Key
# 至少需要配置:
#   PAPER_ASSIST_LLM_API_KEY=你的DeepSeek-API-Key
#   PAPER_ASSIST_CONTACT_EMAIL=你的邮箱
```

### 3. 启动方式

```
python run.py init     # 初始化数据库（首次运行）
python run.py test     # 运行单元测试
python run.py api      # 启动 FastAPI 后端 → http://localhost:8000/docs
python run.py ui       # 启动 Streamlit 前端 → http://localhost:8501
```

启动成功后：
- FastAPI 交互式文档（Swagger）：http://localhost:8000/docs
- FastAPI ReDoc 文档：http://localhost:8000/redoc
- Streamlit 前端界面：http://localhost:8501

## 开发路线

| 阶段 | 内容 | 状态 |
|------|------|------|
| Phase 1 | 检索 + 下载 + 入库（核心数据流） | 骨架就绪 |
| Phase 2 | PDF 转换 + RAG 智能问答 | 待开发 |
| Phase 3 | 课题组画像 + 写作辅助 + 完善 UI | 待开发 |

## 合法获取文献

所有文献获取均通过合法开放 API:
- OpenAlex、Crossref、PubMed、PubMed Central、arXiv
- Unpaywall（开放获取状态查询）
- 出版社官方开放获取页面

**严禁使用** Sci-Hub、Library Genesis 或任何绕过付费墙的手段。

## 许可证

课题组内部使用。
