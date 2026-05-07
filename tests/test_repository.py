"""
PaperRepository 单元测试 — 覆盖 search_papers() 及其他仓库方法。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from src.database.connection import DatabaseManager
from src.storage.repository import PaperRepository
from src.utils.logger import init_logging

init_logging()


# ============================================================================
# 测试辅助函数
# ============================================================================

def _insert_test_paper(conn, paper_id=None, title="测试论文", doi=None, year=2024,
                        journal="测试期刊", abstract="测试摘要", source_api="test",
                        source_id="test_001", citation_count=0, oa_status="unknown",
                        created_at=None):
    """直接用 SQL 插入测试论文，返回 paper_id。"""
    cursor = conn.cursor()
    if created_at:
        cursor.execute(
            "INSERT INTO papers (paper_id, title, doi, year, journal, abstract, "
            "source_api, source_id, citation_count, oa_status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (paper_id, title, doi, year, journal, abstract,
             source_api, source_id, citation_count, oa_status, created_at),
        )
    else:
        cursor.execute(
            "INSERT INTO papers (paper_id, title, doi, year, journal, abstract, "
            "source_api, source_id, citation_count, oa_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (paper_id, title, doi, year, journal, abstract,
             source_api, source_id, citation_count, oa_status),
        )
    conn.commit()
    return cursor.lastrowid


def _insert_test_author(conn, name, author_id=None):
    """插入测试作者，返回 author_id。"""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO authors (author_id, name) VALUES (?, ?)",
        (author_id, name),
    )
    conn.commit()
    return cursor.lastrowid


def _link_paper_author(conn, paper_id, author_id, author_order=1):
    """关联论文和作者。"""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO paper_authors (paper_id, author_id, author_order) "
        "VALUES (?, ?, ?)",
        (paper_id, author_id, author_order),
    )
    conn.commit()


# ============================================================================
# 测试夹具
# ============================================================================

@pytest.fixture
def repo(tmp_path):
    """创建基于临时数据库的 PaperRepository 实例。"""
    db_path = tmp_path / "test_search.db"
    db = DatabaseManager(db_path)
    db.initialize()
    repo = PaperRepository()
    repo.db = db
    return repo


# ============================================================================
# search_papers() 测试套件
# ============================================================================

class TestSearchPapers:
    """验证 search_papers() 方法的各项功能。"""

    def test_search_empty_keyword(self, repo):
        """空关键词查询返回最近入库论文，按 created_at DESC 排序。"""
        conn = repo.db.get_connection()
        try:
            # 插入 3 篇论文，显式设置不同的 created_at
            _insert_test_paper(conn, paper_id=1, title="论文C", doi="10.0/c.1", year=2023,
                               created_at="2025-01-01 10:00:00")
            _insert_test_paper(conn, paper_id=2, title="论文A", doi="10.0/a.1", year=2025,
                               created_at="2025-06-01 10:00:00")
            _insert_test_paper(conn, paper_id=3, title="论文B", doi="10.0/b.1", year=2024,
                               created_at="2025-03-01 10:00:00")
            # 添加作者
            _insert_test_author(conn, "张三", author_id=1)
            _insert_test_author(conn, "李四", author_id=2)
            _link_paper_author(conn, 1, 1, 1)
            _link_paper_author(conn, 2, 2, 1)
            _link_paper_author(conn, 3, 1, 1)
        finally:
            conn.close()

        papers = repo.search_papers("", limit=10)
        assert len(papers) == 3

        # 验证按 created_at DESC 排序：论文A(2025-06) → 论文B(2025-03) → 论文C(2025-01)
        titles = [p["title"] for p in papers]
        assert titles == ["论文A", "论文B", "论文C"]

        # 验证字段完整性
        p = papers[0]
        assert p["id"] == 2
        assert p["title"] == "论文A"
        assert p["doi"] == "10.0/a.1"
        assert p["year"] == 2025
        assert "authors" in p
        assert "source" in p
        assert "source_url" in p
        assert "oa_status" in p
        assert "citation_count" in p
        assert "created_at" in p

    def test_search_by_keyword(self, repo):
        """关键词查询匹配 title/abstract/journal。"""
        conn = repo.db.get_connection()
        try:
            # 论文1：标题匹配 "machine learning"
            _insert_test_paper(conn, paper_id=1, title="Machine Learning Basics",
                               abstract="An introduction.", journal="AI Journal",
                               year=2023, doi="10.0/ml.1")
            # 论文2：摘要匹配 "drug"
            _insert_test_paper(conn, paper_id=2, title="Organic Chemistry",
                               abstract="This paper discusses drug discovery.",
                               journal="Chem Journal", year=2024, doi="10.0/drug.1")
            # 论文3：期刊匹配 "Nature"
            _insert_test_paper(conn, paper_id=3, title="Biology Study",
                               abstract="Cell biology.", journal="Nature",
                               year=2025, doi="10.0/nature.1")
            # 论文4：完全不匹配
            _insert_test_paper(conn, paper_id=4, title="Physics Overview",
                               abstract="Quantum mechanics.", journal="Physics Rev",
                               year=2022, doi="10.0/phys.1")
        finally:
            conn.close()

        # 关键词查询 "drug"
        papers = repo.search_papers("drug", limit=10)
        assert len(papers) == 1
        assert papers[0]["title"] == "Organic Chemistry"
        assert papers[0]["doi"] == "10.0/drug.1"

        # 关键词查询 "nature" (大小写不敏感由 LIKE 处理)
        papers = repo.search_papers("Nature", limit=10)
        assert len(papers) == 1
        assert papers[0]["journal"] == "Nature"

        # 关键词查询 "learning"
        papers = repo.search_papers("learning", limit=10)
        assert len(papers) == 1  # 只有论文1标题包含 "Learning"
        assert papers[0]["title"] == "Machine Learning Basics"

    def test_search_source_filter(self, repo):
        """source 过滤只返回指定源的论文。"""
        conn = repo.db.get_connection()
        try:
            _insert_test_paper(conn, paper_id=1, title="OA Paper", doi="10.0/oa.1",
                               source_api="openalex", year=2023)
            _insert_test_paper(conn, paper_id=2, title="CR Paper", doi="10.0/cr.1",
                               source_api="crossref", year=2024)
            _insert_test_paper(conn, paper_id=3, title="PM Paper", doi="10.0/pm.1",
                               source_api="pubmed", year=2025)
        finally:
            conn.close()

        papers = repo.search_papers("", limit=10, source="openalex")
        assert len(papers) == 1
        assert papers[0]["title"] == "OA Paper"
        assert papers[0]["source"] == "openalex"

        papers = repo.search_papers("", limit=10, source="crossref")
        assert len(papers) == 1
        assert papers[0]["source"] == "crossref"

        # 不存在的 source
        papers = repo.search_papers("", limit=10, source="arxiv")
        assert len(papers) == 0

    def test_search_year_filter(self, repo):
        """年份过滤正确。"""
        conn = repo.db.get_connection()
        try:
            _insert_test_paper(conn, paper_id=1, title="Paper 2022", doi="10.0/y.22",
                               year=2022)
            _insert_test_paper(conn, paper_id=2, title="Paper 2023", doi="10.0/y.23",
                               year=2023)
            _insert_test_paper(conn, paper_id=3, title="Paper 2024", doi="10.0/y.24",
                               year=2024)
            _insert_test_paper(conn, paper_id=4, title="Paper 2025", doi="10.0/y.25",
                               year=2025)
        finally:
            conn.close()

        # year_from only
        papers = repo.search_papers("", limit=10, year_from=2024)
        assert len(papers) == 2
        years = {p["year"] for p in papers}
        assert years == {2024, 2025}

        # year_to only
        papers = repo.search_papers("", limit=10, year_to=2023)
        assert len(papers) == 2
        years = {p["year"] for p in papers}
        assert years == {2022, 2023}

        # year_from + year_to
        papers = repo.search_papers("", limit=10, year_from=2023, year_to=2024)
        assert len(papers) == 2
        years = {p["year"] for p in papers}
        assert years == {2023, 2024}

        # 无结果范围
        papers = repo.search_papers("", limit=10, year_from=2030)
        assert len(papers) == 0

    def test_search_limit(self, repo):
        """limit 参数生效。"""
        conn = repo.db.get_connection()
        try:
            for i in range(10):
                _insert_test_paper(
                    conn, paper_id=i + 1, title=f"Paper {i + 1}",
                    doi=f"10.0/limit.{i + 1}", year=2020 + i,
                    created_at=f"2025-01-{(i + 1):02d} 10:00:00",
                )
        finally:
            conn.close()

        papers = repo.search_papers("", limit=3, offset=0)
        assert len(papers) == 3  # 应该只返回 3 条

        # 验证 offset
        papers_all = repo.search_papers("", limit=10, offset=0)
        papers_offset = repo.search_papers("", limit=3, offset=3)
        assert len(papers_offset) == 3
        # 前 3 条和后 3 条不应重叠
        first_ids = {p["id"] for p in papers_all[:3]}
        offset_ids = {p["id"] for p in papers_offset}
        assert first_ids.isdisjoint(offset_ids)

    def test_search_no_results(self, repo):
        """无匹配时返回空列表。"""
        conn = repo.db.get_connection()
        try:
            _insert_test_paper(conn, paper_id=1, title="A Paper", doi="10.0/no.1",
                               abstract="Some abstract.", year=2023)
        finally:
            conn.close()

        # 不可能匹配的关键词
        papers = repo.search_papers("xyznonexistentkeyword999", limit=10)
        assert isinstance(papers, list)
        assert len(papers) == 0

        # 不存在的 source 过滤
        papers = repo.search_papers("", limit=10, source="nonexistent_source")
        assert len(papers) == 0

    def test_search_with_authors(self, repo):
        """验证作者列表通过 GROUP_CONCAT 正确聚合。"""
        conn = repo.db.get_connection()
        try:
            _insert_test_paper(conn, paper_id=1, title="Multi-Author Paper",
                               doi="10.0/auth.1", year=2024,
                               created_at="2025-01-01 10:00:00")
            _insert_test_author(conn, "Alice", author_id=1)
            _insert_test_author(conn, "Bob", author_id=2)
            _insert_test_author(conn, "Charlie", author_id=3)
            _link_paper_author(conn, 1, 1, 1)  # Alice 第一作者
            _link_paper_author(conn, 1, 2, 2)  # Bob 第二作者
            _link_paper_author(conn, 1, 3, 3)  # Charlie 第三作者
        finally:
            conn.close()

        papers = repo.search_papers("", limit=10)
        assert len(papers) == 1
        assert papers[0]["authors"] == "Alice,Bob,Charlie"

    def test_search_without_authors(self, repo):
        """没有作者的论文 authors 字段为 None 或空字符串。"""
        conn = repo.db.get_connection()
        try:
            _insert_test_paper(conn, paper_id=1, title="No Author Paper",
                               doi="10.0/noauth.1", year=2024,
                               created_at="2025-01-01 10:00:00")
        finally:
            conn.close()

        papers = repo.search_papers("", limit=10)
        assert len(papers) == 1
        # 没有作者时 GROUP_CONCAT 返回 None（在 dict(row) 中为 None）
        assert papers[0]["authors"] is None

    def test_search_combined_filters(self, repo):
        """组合过滤：关键词 + source + 年份范围。"""
        conn = repo.db.get_connection()
        try:
            _insert_test_paper(conn, paper_id=1, title="Drug Discovery AI",
                               abstract="Using AI for drug discovery.",
                               journal="Nature Drug", year=2023,
                               source_api="openalex", doi="10.0/comb.1",
                               created_at="2025-01-01")
            _insert_test_paper(conn, paper_id=2, title="Drug Discovery ML",
                               abstract="Machine learning in drug discovery.",
                               journal="Science Drug", year=2024,
                               source_api="crossref", doi="10.0/comb.2",
                               created_at="2025-01-02")
            _insert_test_paper(conn, paper_id=3, title="Drug Synthesis",
                               abstract="Chemical synthesis of drugs.",
                               journal="JACS", year=2023,
                               source_api="openalex", doi="10.0/comb.3",
                               created_at="2025-01-03")
            _insert_test_paper(conn, paper_id=4, title="AI in Chemistry",
                               abstract="AI applications.",
                               journal="Chem Rev", year=2025,
                               source_api="openalex", doi="10.0/comb.4",
                               created_at="2025-01-04")
        finally:
            conn.close()

        # 组合：keyword="drug" + source="openalex"
        papers = repo.search_papers("drug", limit=10, source="openalex")
        assert len(papers) == 2
        titles = {p["title"] for p in papers}
        assert titles == {"Drug Discovery AI", "Drug Synthesis"}

        # 组合：keyword="drug" + year_from=2024
        papers = repo.search_papers("drug", limit=10, year_from=2024)
        assert len(papers) == 1
        assert papers[0]["title"] == "Drug Discovery ML"

        # 三条件组合：keyword="drug" + source="openalex" + year=2023
        # 匹配论文1 (Drug Discovery AI) 和论文3 (Drug Synthesis)
        papers = repo.search_papers("drug", limit=10, source="openalex",
                                     year_from=2023, year_to=2023)
        assert len(papers) == 2
        titles = {p["title"] for p in papers}
        assert titles == {"Drug Discovery AI", "Drug Synthesis"}
