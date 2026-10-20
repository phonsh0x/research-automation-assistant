---
name: pdf-to-markdown-pipeline
description: PDF 转 Markdown 转换管道。将学术 PDF 论文转换为结构化 Markdown，保留标题层级、表格、公式、参考文献等元素。处理 OCR、多栏排版、图文混排等学术 PDF 特有挑战。触发于需要转换 PDF 为可检索文本、入库前的格式化处理。
when_to_use:
  - 将已下载的学术 PDF 转换为 Markdown 格式
  - 批量处理 data/pdf/ 目录下的 PDF 文件
  - 处理扫描版 PDF 的 OCR 需求
  - PDF 内容提取后的结构化整理（章节、图表、公式、参考文献）
  - 转换质量检查与报告
---

# pdf-to-markdown-pipeline — PDF 转 Markdown 管道

## 角色定位

你是"PDF→Markdown 转换管道"模块的开发者。负责将学术 PDF 论文高质量地转换为结构化 Markdown，支撑后续入库和 RAG 问答。

## 输入 / 输出

- **输入**：`data/pdf/` 目录下的学术 PDF 文件，或用户指定的 PDF 路径。
- **输出**：`data/markdown/` 目录下的 `.md` 文件，文件名与源 PDF 对应。

## 转换工具选择

| 工具 | 适用场景 | 优缺点 |
|------|---------|--------|
| `marker` (pdf2md) | 文字型 PDF、双栏排版 | 对学术论文优化好，支持公式转 LaTeX |
| `markitdown` | 通用文档 | Microsoft 出品，支持多种格式 |
| `PyMuPDF` (fitz) | 简单文字提取、元数据 | 轻量快速，但对复杂排版支持有限 |
| `pymupdf4llm` | 学术论文 LLM 预处理 | 专门为 RAG 优化的 PyMuPDF 封装 |
| `nougat` / `grobid` | 高精度学术论文解析 | 需 GPU，对公式和表格还原度最高 |

**建议策略：**
1. 默认使用 `marker` 进行批量转换（CPU 友好，对中英文论文均支持良好）。
2. 对公式密集的论文（数学、物理），使用 `nougat`（需 CUDA 环境）。
3. 对扫描版 PDF，先使用 `ocrmypdf` 或 `tesseract` 进行 OCR 预处理，再用 `marker` 转换。

## 转换管道

```
PDF 输入 → 工具选择 → 初转换 → 后处理 → 质量检查 → Markdown 输出
```

### 阶段 1：PDF 分类

```
1. 用 PyMuPDF 检测页数、是否有文字层。
   - 有文字层 → 直接转换
   - 无文字层 → OCR 预处理 → 转换
2. 判断是否为双栏排版（通过文本坐标分布）。
3. 统计公式/图表密度，决定转换工具。
```

### 阶段 2：转换执行

```
marker 命令行（推荐）：
  marker "data/pdf/paper.pdf" "data/markdown/" --output_format markdown

nougat 命令行（公式密集）：
  nougat "data/pdf/paper.pdf" -o "data/markdown/"
```

### 阶段 3：后处理

转换后的 Markdown 需要：

1. **标题层级修复** — 确保 `#` 层级连续（不跳级），识别 Abstract、Introduction、Methods、Results、Discussion、References 等典型章节。
2. **表格格式化** — 将提取的表格转为标准 Markdown 表格。
3. **公式包装** — LaTeX 公式统一用 `$$`（块级）或 `$`（行内）包裹。
4. **参考文献提取** — 识别 Reference/Bibliography 节，提取每条引用。
5. **页码/页眉/页脚去除** — 删除转换残留的页码、期刊名页眉、版权声明等噪声。
6. **图表引用标记** — 标记 `![figure_caption](path)` 和 `[Figure N]` 位置。
7. **中文后处理** — 中文 PDF 转换后去除多余空格、断行合并（中文排版无英文式单词间隔）。

### 阶段 4：质量检查

- 检查输出文件非空且行数 > 50（正文应有足够内容）。
- 检查是否包含 "Abstract" 或 "摘要" 关键词（标志性章节）。
- 与原文页数对比：输出内容量与页数应成比例（粗略估计 ≥ 200 字符/页）。
- 质量评分：0–100，低于 60 分标记为需人工复核。

## 批量处理

```python
# 批量处理 data/pdf/ 下所有 PDF
for pdf_path in Path("data/pdf").glob("*.pdf"):
    md_path = Path("data/markdown") / f"{pdf_path.stem}.md"
    if not md_path.exists():  # 跳过已转换的
        convert_pdf_to_markdown(pdf_path, md_path)
```

支持 `--force` 参数覆盖已转换文件。

## 错误处理

- 损坏的 PDF → 记录到 `data/logs/pdf_errors.log`，跳过继续处理其余文件。
- OCR 超时（扫描件 > 50 页）→ 标记为需 GPU 加速或人工处理。
- 转换后 Markdown 为空 → 回退到 PyMuPDF 做原始文本提取。

## 输出

- 每个 PDF 对应一个同主名的 `.md` 文件在 `data/markdown/`。
- 批量处理结束后生成转换报告：成功 X 个，失败 Y 个，需人工复核 Z 个。
- 报告保存到 `data/logs/conversion_report_{timestamp}.json`。

## 依赖安装参考

```bash
pip install marker-pdf pymupdf pymupdf4llm markitdown
# OCR 可选
pip install ocrmypdf pytesseract
# nougat 可选（需 PyTorch + CUDA）
pip install nougat-ocr
```
