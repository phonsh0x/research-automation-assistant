# 人工上传自动归档设计方案

> 状态：设计阶段，待 Phase 2.4 实现

---

## 一、当前限制

人工上传 PDF 需要用户手动输入 `paper_id`，原因：
1. 系统无法从 PDF 自动提取元数据（DOI、标题等）
2. 无法自动匹配到数据库中的 papers 记录
3. 无法自动创建新记录

## 二、目标流程

```
用户选择 PDF 文件
→ 系统计算 SHA256
→ 从 PDF 前几页提取 DOI / 标题 / 年份
→ DOI 精确匹配 papers 表
  ├── 匹配成功 → 关联到已有 paper，更新 pdf_path
  └── 匹配失败 → 标题相似度匹配
       ├── 高相似度 → 自动合并（低风险）
       ├── 中相似度 → 提示用户确认
       └── 低相似度 → 新建 papers 记录
→ 写入 fulltext_access 审计记录
→ 不要求用户输入 paper_id
```

## 三、新增 uploaded_files 表

```sql
CREATE TABLE uploaded_files (
    upload_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id     INTEGER REFERENCES papers(paper_id),
    filename     TEXT NOT NULL,
    file_size    INTEGER,
    checksum     TEXT NOT NULL,
    pdf_path     TEXT NOT NULL,
    doi_extracted TEXT,
    title_extracted TEXT,
    year_extracted INTEGER,
    match_method TEXT,       -- doi / title_similarity / manual / new
    match_confidence REAL,   -- 0.0-1.0
    uploaded_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 四、PDF 元数据提取

使用 PyMuPDF 从前 3 页提取：
- DOI：正则 `10.\d{4,}/[^\s]+`
- 标题：第一页前几行大字文本
- 年份：正则 `(19|20)\d{2}`

## 五、匹配策略

| 匹配方式 | 条件 | 操作 |
|---------|------|------|
| DOI 精确匹配 | papers.doi == extracted_doi | 自动关联 |
| 标题高相似度 | similarity > 0.9 | 自动合并 |
| 标题中相似度 | 0.6 < similarity < 0.9 | 提示用户确认 |
| 无匹配 | similarity < 0.6 | 新建 papers 记录 |

相似度计算：使用 `difflib.SequenceMatcher` 或简单的 token 重叠比。

## 六、合规要求（保持不变）

- 上传前必须确认版权合规（checkbox）
- 写入 fulltext_access 审计记录
- 不保存校园网账号密码
- 禁止 Sci-Hub / LibGen / 盗版源
