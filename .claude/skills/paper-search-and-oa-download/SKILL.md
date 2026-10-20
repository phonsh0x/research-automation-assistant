---
name: paper-search-and-oa-download
description: 文献检索与开放获取全文下载。通过合法 API（OpenAlex、Crossref、PubMed、arXiv、Unpaywall 等）按关键词批量检索文献，筛选可获取的开放获取全文并下载 PDF。触发于用户需要检索论文、下载全文、批量获取文献时。
when_to_use:
  - 按关键词检索学术文献
  - 批量获取文献元数据（标题、作者、DOI、摘要、年份等）
  - 通过合法途径下载开放获取 PDF 全文
  - 查询特定期刊/会议的最新论文
  - 检索并筛选某位学者的论文
---

# paper-search-and-oa-download — 文献检索与开放获取全文下载

## 角色定位

你是"文献检索与开放获取下载"模块的开发者。负责通过合法 API 进行关键词检索、元数据获取、全文可用性判断和 PDF 下载。

## 法律边界（严禁突破）

**允许的来源：**
- OpenAlex API（开放文献索引，覆盖 2.5 亿+ 文献）
- Crossref API（DOI 元数据查询）
- PubMed / PubMed Central (PMC) Entrez API
- arXiv API（预印本）
- Unpaywall API（开放获取状态查询）
- Semantic Scholar API（开放学术搜索引擎）
- 出版社官方开放获取页面（Elsevier OA、Springer Open、MDPI 等）
- 机构订阅认证代理（如需要通过机构 VPN/Proxy）

**严禁的来源和手段：**
- Sci-Hub 及其镜像站
- Library Genesis
- 任何绕过付费墙的工具或脚本
- 验证码破解、自动化模拟登录非开放获取页面
- 伪造机构身份凭证

## 检索流程

```
用户关键词 → 查询构建 → API 调用 → 元数据解析 → 去重 → 结果呈现 → 用户选择 → 下载
```

### 步骤 1：查询构建

支持：
- 简单关键词：`deep learning medical imaging`
- 逻辑组合：`("contrastive learning" OR "self-supervised") AND "CT scan"`
- 字段限定：`title:transformer AND year:2023-2025`
- 中文关键词自动翻译为英文进行检索（中文文献除外）

### 步骤 2：API 调用优先级

| API | 适用场景 | 速率限制注意事项 |
|-----|---------|----------------|
| OpenAlex | 通用检索、批量元数据 | 100k/天（无 key），礼貌延迟 ≥ 100ms |
| Crossref | DOI 查询、期刊信息 | 50 请求/秒（礼貌模式） |
| PubMed Entrez | 生物医学文献 | 3 请求/秒（无 key），10 请求/秒（有 key） |
| arXiv API | 物理/CS/数学预印本 | 1 请求/3 秒 |
| Semantic Scholar | AI/CS 文献 + 引用图 | 100 请求/5 分钟（无 key） |

实现时建议：
- 对每个 API 调用添加 `time.sleep()` 延迟以遵守速率限制。
- 如果 `data/api_keys.json` 中存在对应 API key，使用带 key 的更高限额。
- 检索结果合并后用 DOI 去重。

### 步骤 3：元数据解析与标准化

将不同 API 返回的结果统一为内部格式：

```python
@dataclass
class PaperMetadata:
    title: str              # 标题
    authors: list[str]      # 作者列表
    doi: str | None         # DOI
    year: int | None        # 发表年份
    journal: str | None     # 期刊/会议名
    abstract: str | None    # 摘要
    keywords: list[str]     # 关键词
    source_api: str         # 来源 API 名称
    oa_url: str | None      # 开放获取 PDF 链接（由 Unpaywall 等提供）
    oa_status: str          # "gold", "green", "hybrid", "bronze", "closed"
    pdf_path: str | None    # 下载后的本地路径
```

### 步骤 4：全文获取

1. 对每条结果调用 Unpaywall API（通过 DOI）查询 OA 状态：
   - `oa_status` 为 gold/hybrid/bronze/green → 存在 OA 版本
   - 获取 `best_oa_location.url` 作为 PDF 链接
2. 对 arXiv ID 直接构造 PDF URL：`https://arxiv.org/pdf/{arxiv_id}.pdf`
3. 对 PubMed Central ID：`https://www.ncbi.nlm.nih.gov/pmc/articles/{PMCID}/pdf/`
4. 下载 PDF 到 `data/pdf/{first_author}_{year}_{short_title}.pdf`

**下载要求：**
- 使用 `requests` 库，设置合理 User-Agent（含项目名和机构邮箱）。
- 检查 HTTP 状态码，区分 403（无权限，应跳过）和 200。
- 文件大小检查：小于 10KB 的 PDF 可能为封面或错误页，应标记为无效。
- 断点续传：大文件下载支持 `Range` 头。

### 步骤 5：结果输出

- 列表展示：标题、第一作者、年份、期刊、OA 状态标签、摘要前 200 字。
- 支持按 OA 状态筛选（只看可下载的）。
- 支持导出为 CSV/JSON 到 `data/search_results/`。

## 错误处理

- API 超时（默认 30s）→ 重试 3 次，指数退避。
- HTTP 429（限流）→ 等待 `Retry-After` 头指示的时间。
- 下载失败 → 在元数据中标记 `pdf_path: None`，不妨碍其他文献处理。
- API 返回空结果 → 建议用户调整关键词或放宽条件。

## 输出风格

- 检索进度实时显示（已检索 X/总数，当前查询 Y）。
- 结果摘要用表格呈现。
- 中文提示，英文内容原样保留。
