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
        "year_to": 2025,
        "sources": ["openalex", "crossref"]
    }
    """
    keywords = request.get("keywords", "")
    if not keywords:
        return {"error": "keywords 参数为必填项"}

    logger.info(f"API 检索请求: {keywords}")

    try:
        from src.paper_search.models import SearchQuery
        from src.paper_search.searcher import PaperSearcher

        query = SearchQuery(
            keywords=keywords,
            max_results=request.get("max_results", 20),
            year_from=request.get("year_from"),
            year_to=request.get("year_to"),
            sources=request.get("sources", ["openalex"]),
            sort_by=request.get("sort_by", "relevance"),
            filter_oa_only=request.get("filter_oa_only", False),
        )

        searcher = PaperSearcher()
        result = searcher.search(query)

        return {
            "query": keywords,
            "total": result.total_count,
            "papers": [
                {
                    "title": p.title,
                    "authors": p.authors,
                    "doi": p.doi,
                    "year": p.year,
                    "journal": p.journal,
                    "abstract": (p.abstract or "")[:500],
                    "oa_status": p.oa_status,
                    "citation_count": p.citation_count,
                    "source": p.source_api,
                }
                for p in result.papers
            ],
            "errors": result.errors,
        }
    except Exception as e:
        logger.error(f"检索失败: {e}")
        return {"error": str(e)}


# ============================================================================
# 全文获取
# ============================================================================

@app.get("/api/v1/fulltext/stats")
async def fulltext_stats():
    """获取全文下载统计信息。"""
    try:
        from src.storage.repository import PaperRepository
        repo = PaperRepository()
        return repo.get_download_statistics()
    except Exception as e:
        logger.error(f"获取全文统计失败: {e}")
        return {"error": str(e)}


@app.get("/api/v1/fulltext/pending")
async def fulltext_pending(limit: int = 20):
    """获取尚未下载 PDF 的论文列表。"""
    try:
        from src.storage.repository import PaperRepository
        repo = PaperRepository()
        papers = repo.get_papers_without_pdf(limit=limit)
        return {
            "count": len(papers),
            "papers": papers,
        }
    except Exception as e:
        logger.error(f"获取待下载论文失败: {e}")
        return {"error": str(e)}


@app.post("/api/v1/fulltext/resolve/{paper_id}")
async def fulltext_resolve(paper_id: int):
    """查询合法全文来源。"""
    try:
        from src.fulltext.service import FullTextAcquisitionService

        service = FullTextAcquisitionService()
        result = service.resolve(paper_id)
        return result.to_dict()
    except Exception as e:
        logger.error(f"全文解析失败: paper_id={paper_id}, 原因={e}")
        return {"error": str(e)}


@app.post("/api/v1/fulltext/download/{paper_id}")
async def fulltext_download(paper_id: int, request: dict = None):
    """尝试下载合法 PDF。"""
    try:
        from src.fulltext.service import FullTextAcquisitionService

        service = FullTextAcquisitionService()
        result = service.download(paper_id)
        return result.to_dict()
    except Exception as e:
        logger.error(f"全文下载失败: paper_id={paper_id}, 原因={e}")
        return {"error": str(e)}


@app.post("/api/v1/fulltext/institution/download/{paper_id}")
async def fulltext_institution_download(paper_id: int, request: dict):
    """通过校园网授权访问下载 PDF。要求 user_confirmed_authorization=true。"""
    if not request or not request.get("user_confirmed_authorization"):
        return {"success": False, "error": "需要确认已具备机构授权"}

    try:
        from src.fulltext.service import FullTextAcquisitionService

        service = FullTextAcquisitionService()
        result = service.download(paper_id, user_confirmed_institution=True)
        return result.to_dict()
    except Exception as e:
        logger.error(f"机构访问下载失败: paper_id={paper_id}, 原因={e}")
        return {"error": str(e)}


@app.post("/api/v1/fulltext/manual-review/{paper_id}")
async def fulltext_mark_manual_review(paper_id: int, request: dict = None):
    """标记为 manual_review。"""
    reason = request.get("reason", "") if request else ""
    try:
        from src.storage.repository import PaperRepository
        repo = PaperRepository()
        success = repo.mark_manual_review(paper_id, reason)
        return {
            "paper_id": paper_id,
            "success": success,
            "message": "已标记为人工审查" if success else "更新失败（论文不存在？）",
        }
    except Exception as e:
        logger.error(f"标记人工审查失败: paper_id={paper_id}, 原因={e}")
        return {"error": str(e)}


@app.post("/api/v1/fulltext/manual-upload/{paper_id}")
async def fulltext_manual_upload(paper_id: int, request: dict = None):
    """处理用户手动上传的 PDF 文件。"""
    pdf_path = request.get("pdf_path", "") if request else ""
    user_confirmed_rights = request.get("user_confirmed_rights", False) if request else False

    try:
        from src.fulltext.manual_upload import ManualUploadResolver
        from src.storage.repository import PaperRepository

        repo = PaperRepository()
        paper = repo.get_paper_by_id(paper_id)
        if not paper:
            return {"error": f"论文 ID {paper_id} 不存在"}

        if not pdf_path:
            return {"error": "pdf_path 参数为必填项"}

        resolver = ManualUploadResolver()
        result = resolver.upload(paper, pdf_path, user_confirmed_rights=user_confirmed_rights)

        if result.pdf_path:
            repo.update_paper_pdf_status(
                paper_id=paper_id,
                pdf_path=result.pdf_path,
                download_status="downloaded",
                access_source="manual_upload",
                legal_status=result.legal_status,
            )
            repo.record_fulltext_access(
                paper_id=paper_id,
                doi=paper.get("doi", ""),
                title=paper.get("title", ""),
                access_status="manual_upload",
                access_source="manual_upload",
                access_mode="manual",
                legal_status=result.legal_status,
                pdf_path=result.pdf_path,
                file_size=result.file_size,
                checksum_sha256=result.checksum_sha256,
                risk_level=result.risk_level,
                risk_note=result.risk_note,
            )

        return result.to_dict()
    except Exception as e:
        logger.error(f"人工上传处理失败: paper_id={paper_id}, 原因={e}")
        return {"error": str(e)}


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
