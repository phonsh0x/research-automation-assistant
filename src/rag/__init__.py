"""
RAG 检索引擎 — 基于向量数据库的文献检索增强生成。

职责：
  - 文档分块与向量嵌入生成
  - 向量相似度检索（ChromaDB）
  - 查询改写（LLM 辅助）
  - 重排序（Cross-encoder / 时间衰减）
  - 上下文组装与引用标注
  - 与 DeepSeek-V4-Pro 集成生成回答

参考 literature-rag-assistant skill 规范。
"""

from src.rag.chunker import MarkdownChunk, MarkdownChunker
from src.rag.engine import RAGEngine

__all__ = ["MarkdownChunk", "MarkdownChunker", "RAGEngine"]
