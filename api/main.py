"""
FastAPI 后端服务 — 提供 RESTful API 接口。

启动方式：
  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

API 路由：
  GET  /api/v1/health              — 健康检查
  GET  /api/v1/stats               — 数据库统计信息
  POST /api/v1/search              — 文献检索
  POST /api/v1/rag/query           — RAG 问答
  POST /api/v1/convert             — PDF 转 Markdown
  GET  /api/v1/profile/report      — 课题组画像报告
"""

import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.utils.logger import init_logging, get_logger

# 初始化日志系统
init_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    logger.info("=" * 60)
    logger.info("科研自动化助手 API 服务启动中...")
    logger.info(f"项目根目录: {PROJECT_ROOT}")

    # 启动时初始化数据库
    try:
        from src.database.connection import get_db
        db = get_db()
        db.initialize()
        logger.info("数据库已就绪。")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")

    logger.info("API 服务已启动，等待请求...")
    logger.info("=" * 60)

    yield

    logger.info("API 服务正在关闭...")


# 创建 FastAPI 应用实例
app = FastAPI(
    title="科研自动化助手 API",
    description="课题组文献管理与科研辅助系统 — 提供检索、RAG 问答、PDF 转换、画像分析等接口",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 中间件（允许 Streamlit 前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发阶段允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# 健康检查
# ============================================================================

@app.get("/api/v1/health")
async def health_check():
    """服务健康检查接口。"""
    return {
        "status": "ok",
        "version": "0.1.0",
        "service": "科研自动化助手",
        "database": "connected" if _check_db() else "disconnected",
    }


def _check_db() -> bool:
    """检查数据库连接是否正常。"""
    try:
        from src.database.connection import get_db
        conn = get_db().get_connection()
        conn.execute("SELECT 1")
        conn.close()
        return True
    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")
        return False


# ============================================================================
# 数据库统计
# ============================================================================

@app.get("/api/v1/stats")
async def get_stats():
    """获取系统总体统计信息。"""
    stats = {
        "app": "科研自动化助手",
        "version": "0.1.0",
        "phase": "Phase 1 — 基础（检索 + 下载 + 入库）",
    }

    try:
        from src.storage.repository import PaperRepository
        repo = PaperRepository()
        db_stats = repo.get_statistics()
        stats["database"] = db_stats
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        stats["database"] = {"error": str(e)}

    return stats


# ============================================================================
# 文献检索
# ============================================================================

@app.post("/api/v1/search")
async def search_papers(request: dict):
    """
    文献检索接口。

    请求体示例：
    {
        "keywords": "deep learning medical imaging",
        "max_results": 20,
        "year_from": 2020,
        "year_to": 2025
    }
    """
    keywords = request.get("keywords", "")
    if not keywords:
        return {"error": "keywords 参数为必填项"}

    logger.info(f"API 检索请求: {keywords}")

    # Phase 1 占位
    return {
        "query": keywords,
        "total": 0,
        "papers": [],
        "message": "检索接口框架已就绪，具体检索逻辑将在 Phase 1 中实现。",
    }


# ============================================================================
# RAG 问答
# ============================================================================

@app.post("/api/v1/rag/query")
async def rag_query(request: dict):
    """
    RAG 问答接口。

    请求体示例：
    {
        "question": "U-Net 在医学图像分割中的应用有哪些？",
        "top_k": 20,
        "min_similarity": 0.5
    }
    """
    question = request.get("question", "")
    if not question:
        return {"error": "question 参数为必填项"}

    logger.info(f"API RAG 查询: {question[:80]}...")

    # Phase 2 占位
    return {
        "question": question,
        "answer": "RAG 问答功能将在 Phase 2 中实现。",
        "sources": [],
        "message": "RAG 接口框架已就绪。",
    }


# ============================================================================
# PDF 转换
# ============================================================================

@app.post("/api/v1/convert")
async def convert_pdf(request: dict):
    """
    PDF 转 Markdown 接口。

    请求体示例：
    {
        "pdf_path": "data/pdf/paper.pdf",
        "tool": "marker"
    }
    """
    pdf_path = request.get("pdf_path", "")
    if not pdf_path:
        return {"error": "pdf_path 参数为必填项"}

    logger.info(f"API PDF 转换请求: {pdf_path}")

    # Phase 2 占位
    return {
        "pdf_path": pdf_path,
        "success": False,
        "message": "PDF 转换接口框架已就绪，转换逻辑将在 Phase 2 中实现。",
    }


# ============================================================================
# 课题组画像
# ============================================================================

@app.get("/api/v1/profile/report")
async def get_profile_report():
    """获取课题组画像报告。"""
    logger.info("API 画像报告请求")

    # Phase 3 占位
    return {
        "message": "课题组画像报告功能将在 Phase 3 中实现。",
        "report": None,
    }


# ============================================================================
# 导出
# ============================================================================

@app.get("/api/v1/export/bibtex")
async def export_bibtex():
    """导出全部论文为 BibTeX。"""
    logger.info("API BibTeX 导出请求")
    return {
        "message": "BibTeX 导出功能将在 Phase 1 中实现。",
        "bibtex": "",
    }


# ============================================================================
# 入口
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
