# Phase 2.3: PDF 转 Markdown 计划

> **重要: 本计划在 UI 重构完成后执行。**
> 前置条件: `feature/ui-refactor` 分支已合并回 master
> 状态: 占位 → 待实现

---

## 一、目标

将 `data/pdf/` 中的已下载学术 PDF 转换为结构化 Markdown，输出到 `data/markdown/`，并将内容存储到 `full_texts` 表。

---

## 二、模块位置

- 核心代码: `src/pdf_converter/converter.py`（已有占位，需重写）
- 配置: `config/default.yaml` → `pdf_conversion` 段（已配置参数）
- 数据库: `full_texts` 表（已建表）

---

## 三、转换引擎

### 首选: PyMuPDF (pymupdf)

```python
import fitz  # pymupdf
doc = fitz.open(pdf_path)
markdown_text = ""
for page in doc:
    markdown_text += page.get_text("markdown")
```

- **优点**: 轻量、快速、纯 Python、保留标题层级
- **缺点**: 图表说明可能丢失、复杂公式效果一般

### 备选: marker-pdf

```python
from marker.converters.pdf import PdfConverter
converter = PdfConverter()
rendered = converter(pdf_path)
markdown_text = rendered.markdown
```

- **优点**: 高精度、图表说明提取、格式保留好
- **缺点**: 依赖较重的 ML 模型、需要 GPU 加速

### 预留扩展: MinerU

- **优点**: 公式识别 (LaTeX)、表格结构化
- **缺点**: 依赖 CUDA、安装复杂
- 预留接口: `_convert_with_mineru(pdf_path) -> str`

### 引擎选择逻辑

```python
# config/default.yaml
pdf_conversion:
  default_tool: "pymupdf"   # pymupdf | marker | nougat

# 转换器内部
def convert(pdf_path, engine=None):
    engine = engine or get_config("pdf_conversion.default_tool", "pymupdf")
    if engine == "pymupdf":
        return self._convert_with_pymupdf(pdf_path)
    elif engine == "marker":
        return self._convert_with_marker(pdf_path)
    elif engine == "mineru":
        return self._convert_with_mineru(pdf_path)
```

---

## 四、输入和输出

### 输入

- `data/pdf/{paper}.pdf` — 已下载的 PDF 文件
- 从 `papers` 表取 `pdf_path IS NOT NULL AND md_path IS NULL` 的论文

### 输出

- `data/markdown/{paper}.md` — 转换后的 Markdown 文件
- `full_texts` 表写入：
  ```sql
  INSERT INTO full_texts (paper_id, content, section_count, figure_count,
      table_count, equation_count, ref_count, char_count)
  VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  ```
- `papers.md_path` 更新为 Markdown 文件路径

---

## 五、核心类和函数

```python
# src/pdf_converter/converter.py

class PDFConverter:
    def __init__(self, engine="pymupdf"):
        ...

    def convert(self, pdf_path: Path, output_dir: Path) -> ConvertResult:
        """单文件转换"""
        ...

    def batch_convert(self, paper_ids: list[int]) -> list[ConvertResult]:
        """批量转换：从 papers 表取 PDF 路径，逐一转换"""
        ...

    def detect_quality(self, markdown_text: str) -> QualityReport:
        """质量检测：字符数、行数、公式/图表标注保留率"""
        ...
```

### ConvertResult

```python
@dataclass
class ConvertResult:
    paper_id: int
    pdf_path: str
    md_path: str | None
    success: bool
    char_count: int
    section_count: int
    figure_count: int
    table_count: int
    equation_count: int
    ref_count: int
    quality_score: int         # 0-100
    needs_review: bool         # quality_score < threshold
    error_message: str | None
```

### QualityReport

```python
@dataclass
class QualityReport:
    char_count: int
    line_count: int
    chars_per_page: float
    section_count: int
    figure_count: int
    table_count: int
    equation_count: int
    ref_count: int
    quality_score: int
    needs_review: bool
    warnings: list[str]
```

### 质量检测规则

- `char_count < 500` → 警告（可能转换失败）
- `chars_per_page < 200` → 警告（PDF 可能是扫描版）
- `section_count < 2` → 可能是非结构化输出
- `quality_score < quality_threshold (默认 60)` → 标记为 `needs_review`

---

## 六、数据库更新

### full_texts 表写入

```python
def _save_to_db(self, paper_id: int, result: ConvertResult):
    conn = self.db.get_connection()
    try:
        conn.execute("""
            INSERT INTO full_texts (paper_id, content, section_count,
                figure_count, table_count, equation_count, ref_count, char_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(paper_id) DO UPDATE SET
                content = excluded.content,
                section_count = excluded.section_count,
                ...
        """, (...))
        conn.commit()
    finally:
        conn.close()
```

### papers 表更新

```python
conn.execute("""
    UPDATE papers SET md_path = ?, updated_at = CURRENT_TIMESTAMP
    WHERE paper_id = ?
""", (str(md_path), paper_id))
```

---

## 七、Streamlit 页面接入

在 UI 重构完成后，只需创建 `ui/pages/pdf_convert.py`：

```python
# ui/pages/pdf_convert.py

def render():
    st.title("PDF 转 Markdown")
    st.markdown("将学术 PDF 论文转换为结构化 Markdown。")

    # 统计已有 Markdown 数量
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("已下载 PDF", ...)
    with col2: st.metric("已转换 MD", ...)
    with col3: st.metric("待转换", ...)

    # 单篇转换
    with st.form("convert_single"):
        paper_id = st.number_input("论文 ID")
        engine = st.selectbox("转换引擎", ["pymupdf", "marker"])
        if st.form_submit_button("转换"):
            converter = PDFConverter(engine=engine)
            result = converter.convert(...)
            st.json(result.to_dict())

    # 批量转换
    if st.button("批量转换所有待转换论文"):
        converter = PDFConverter()
        results = converter.batch_convert()
        for r in results:
            st.write(f"#{r.paper_id}: {'OK' if r.success else 'FAIL'}")

    # 质量报告
    if results:
        st.dataframe([...])
```

---

## 八、FastAPI 接口接入

将 `api/main.py` 中的占位 `/api/v1/convert` 改为真实实现：

```python
@app.post("/api/v1/convert")
async def convert_pdf(request: dict):
    pdf_path = request.get("pdf_path", "")
    engine = request.get("tool", "pymupdf")

    if not Path(pdf_path).exists():
        return {"success": False, "error": "PDF 文件不存在"}

    converter = PDFConverter(engine=engine)
    result = converter.convert(Path(pdf_path))

    return result.to_dict()
```

---

## 九、CLI 命令

```bash
# 在 run.py 中添加
python run.py convert --paper-id 5          # 单篇转换
python run.py convert --all                  # 批量转换所有待转换
python run.py convert --engine marker        # 指定引擎
```

---

## 十、测试计划

### 单元测试（不依赖真实 PDF）

```python
# tests/test_pdf_converter.py

def test_convert_result_defaults():
    r = ConvertResult(paper_id=1)
    assert r.success is False

def test_quality_report():
    report = QualityReport(char_count=1000, line_count=50, ...)
    assert report.char_count == 1000

def test_detect_quality_good():
    converter = PDFConverter()
    text = "# Title\n\n" + "Content. " * 500
    report = converter.detect_quality(text)
    assert report.quality_score > 60

def test_detect_quality_poor():
    converter = PDFConverter()
    text = "short"
    report = converter.detect_quality(text)
    assert report.quality_score < 60
    assert report.needs_review is True

def test_engine_selection():
    converter = PDFConverter(engine="pymupdf")
    assert converter.engine == "pymupdf"
```

### 集成测试（使用测试 PDF）

```python
def test_convert_real_pdf(tmp_path):
    """使用最小合法 PDF 测试转换流程"""
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n...\n%%EOF")
    converter = PDFConverter()
    result = converter.convert(pdf, tmp_path / "output")
    assert result.success is True  # 或其他预期状态
```

### 测试验证命令

```bash
python run.py test  # 必须全部通过（包括新增测试）
```

---

## 十一、文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/pdf_converter/converter.py` | **重写** | 当前占位 → 真实实现 |
| `src/pdf_converter/__init__.py` | 更新 | 导出 PDFConverter, ConvertResult, QualityReport |
| `ui/pages/pdf_convert.py` | **新建** | Streamlit 页面（UI 重构后） |
| `api/main.py` | 修改 | `/api/v1/convert` 占位 → 真实实现 |
| `run.py` | 修改 | 添加 `convert` 命令 |
| `tests/test_pdf_converter.py` | **新建** | 单元测试和集成测试 |

---

## 十二、依赖安装

```bash
# pymupdf (首选)
pip install pymupdf

# marker (备选，按需安装)
pip install marker-pdf

# 如果使用 marker，还需要 torch
# pip install torch
```

---

## 十三、commit 建议

```
git checkout -b feature/phase2.3-pdf-convert

# 分步提交:
git commit -m "feat(phase2.3): implement PDF to Markdown converter with pymupdf"
git commit -m "feat(phase2.3): add quality detection and full_texts table update"
git commit -m "feat(phase2.3): add batch convert and CLI command"
git commit -m "feat(phase2.3): connect UI page and API endpoint"
git commit -m "test(phase2.3): add converter unit and integration tests"
```
