"""
PDF 转 Markdown 转换管道 — 将学术 PDF 转换为结构化 Markdown。

职责：
  - PDF 文件分类（文字型/扫描型、单栏/双栏）
  - 使用 marker/pymupdf/nougat 进行转换
  - 后处理：标题修复、表格格式化、公式包装、噪声去除
  - 质量检查与评分
  - 批量转换管理

参考 pdf-to-markdown-pipeline skill 规范。
"""

from src.pdf_converter.converter import PDFConverter

__all__ = ["PDFConverter"]
