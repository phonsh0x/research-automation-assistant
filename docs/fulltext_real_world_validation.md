# 全文获取真实下载验收指南

> 目标：用真实学术 DOI 验证整个全文获取链路，而非测试 DOI。

---

## 一、为什么测试 DOI 无法下载

测试 DOI（如 `10.9999/xxx`）是虚构的：
- Unpaywall 无此记录 → 返回 `unavailable`
- PMC 无此记录 → 返回 `unavailable`
- 出版社无此 DOI → 返回 `unavailable`
- 所有 resolver 均未命中 → 最终状态 `unavailable`

这不是程序错误，而是输入的 DOI 不存在于任何数据库中。

---

## 二、选择真实验证样本的优先级

### Tier 1 — 已知有 PMCID 的 OA 论文

PMC ID 可直接用于 `PMCResolver` 下载全文。

示例 DOI（确认 OA 可获取）:
- `10.1371/journal.pone.0234567` 等 PLOS ONE 论文
- `10.7554/eLife.12345` 等 eLife 论文
- `10.1186/s12859-020-3456-7` 等 BMC 系列

验证方式：
1. 在 PubMed 搜索确认有 `PMCID: PMCxxxxxxx`
2. 将论文入库后进入全文获取页面
3. 点击「查询合法全文来源」→ 应显示 PMC 来源
4. 点击「下载合法 PDF」→ 应成功下载

### Tier 2 — arXiv 预印本

arXiv ID 可直接构造 PDF URL。

示例：
- `10.48550/arXiv.2301.12345`
- `10.48550/arXiv.2312.56789`

验证方式：
1. 搜索 arXiv 论文并入库存
2. 全文获取页面 → 查询来源 → 应显示 arXiv 来源
3. 下载 → 应成功获取 PDF

### Tier 3 — Unpaywall 已知 OA

使用 Unpaywall API 确认有 `best_oa_location.pdf_url` 的 DOI。

验证方式：
1. 访问 `https://api.unpaywall.org/v2/{DOI}?email=your@email`
2. 确认返回 `is_oa: true` 且有 `best_oa_location.pdf_url`
3. 入库后进入全文获取页面下载

---

## 三、不推荐的验证样本

| 类型 | 原因 |
|------|------|
| 测试 DOI（10.9999/xxx） | 不存在于任何数据库 |
| 付费墙期刊 DOI | 合法途径无法获取 |
| 仅有摘要无全文的 DOI | 本身不提供 PDF |
| 预印本但未开放全文 | arXiv 可能仅索引不托管 PDF |

---

## 四、校园网授权访问验证

1. 确认已连接学校 VPN / 校园网 / 图书馆代理
2. 进入全文获取页面，勾选「校园网授权确认」
3. 选择一篇已知机构订阅的论文
4. 点击「通过校园网授权访问下载」

注意事项：
- 系统不会保存账号密码
- 遇到 401 / 403 / 429 时自动停止
- 每次下载需要用户确认

---

## 五、验收检查表

- [ ] Unpaywall email 已配置
- [ ] 至少 1 篇 PMC OA 论文下载成功
- [ ] 至少 1 篇 arXiv 论文下载成功
- [ ] unavailable 结果不以失败（红叉）展示
- [ ] 测试 DOI 不会被误判为程序错误
- [ ] 批量下载统计清晰（已下载 / 未找到 / 失败）
