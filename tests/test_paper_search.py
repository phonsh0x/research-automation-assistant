"""
文献检索模块单元测试 — Phase 2.1 多源检索架构。

测试覆盖：
  - 抽象基类接口
  - 各检索源 API 调用和结果转换（使用 mock 模拟网络请求）
  - 去重逻辑（DOI 去重 + title/year 弱去重）
  - 多源聚合器
  - 期刊监控清单管理
  - 检索运行记录
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from unittest import mock
from unittest.mock import patch, MagicMock

from src.paper_search.models import PaperMetadata, SearchQuery
from src.paper_search.base import BaseSearcher
from src.paper_search.openalex import OpenAlexSearcher
from src.paper_search.crossref import CrossrefSearcher
from src.paper_search.pubmed import PubMedSearcher
from src.paper_search.europe_pmc import EuropePMCSearcher
from src.paper_search.aggregator import SearchAggregator
from src.paper_search.searcher import SearchResult, PaperSearcher
from src.paper_search.journal_watchlist import JournalWatchlist
from src.utils.logger import init_logging

# 初始化日志
init_logging()

# ============================================================================
# 测试数据工厂
# ============================================================================

def make_paper(
    title="测试论文标题",
    doi="10.1234/test.001",
    year=2023,
    authors=None,
    source_api="test",
    abstract="__default__",
    journal="测试期刊",
    keywords=None,
    oa_status="unknown",
) -> PaperMetadata:
    """创建测试用的 PaperMetadata 实例。"""
    if abstract == "__default__":
        abstract = "这是一篇测试论文的摘要。"
    return PaperMetadata(
        title=title,
        authors=authors or ["张三", "李四"],
        doi=doi,
        year=year,
        journal=journal,
        abstract=abstract,
        keywords=keywords or [],
        source_api=source_api,
        source_id="test_001",
        oa_status=oa_status,
    )


# ============================================================================
# 1. 抽象基类接口测试
# ============================================================================

class TestBaseSearcher:
    """验证 BaseSearcher 抽象基类接口。"""

    def test_cannot_instantiate_base(self):
        """BaseSearcher 不能直接实例化。"""
        with pytest.raises(TypeError):
            BaseSearcher()

    def test_concrete_implementation(self):
        """具体实现类必须实现所有抽象方法。"""

        class TestSearcher(BaseSearcher):
            @property
            def source_name(self):
                return "test"

            def search(self, query):
                return []

            def get_recent(self, journal_name, days=7):
                return []

        searcher = TestSearcher()
        assert searcher.source_name == "test"
        assert searcher.search(SearchQuery(keywords="test")) == []
        assert searcher.get_recent("Nature") == []

    def test_resolve_doi_optional(self):
        """resolve_doi 有默认实现。"""

        class TestSearcher(BaseSearcher):
            @property
            def source_name(self):
                return "test"

            def search(self, query):
                return []

            def get_recent(self, journal_name, days=7):
                return []

        searcher = TestSearcher()
        assert searcher.resolve_doi("10.1234/test") is None


# ============================================================================
# 2. OpenAlex 检索源测试
# ============================================================================

class TestOpenAlexSearcher:
    """验证 OpenAlex API 调用和结果转换。"""

    @patch("src.paper_search.openalex.requests.get")
    def test_search_success(self, mock_get):
        """测试 OpenAlex search 成功返回结果。"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "https://openalex.org/W123",
                    "doi": "https://doi.org/10.1234/oa.001",
                    "title": "OpenAlex 测试论文",
                    "publication_year": 2023,
                    "cited_by_count": 42,
                    "primary_location": {
                        "source": {"display_name": "Nature"}
                    },
                    "authorships": [
                        {
                            "author": {"display_name": "第一作者"},
                        },
                        {
                            "author": {"display_name": "第二作者"},
                        },
                    ],
                    "abstract_inverted_index": {
                        "This": [0], "is": [1], "abstract": [2]
                    },
                    "concepts": [
                        {"display_name": "测试概念", "level": 0},
                    ],
                    "open_access": {
                        "oa_status": "gold",
                        "oa_url": "https://example.com/oa.pdf",
                    },
                    "biblio": {
                        "volume": "10",
                        "issue": "2",
                        "first_page": "100",
                        "last_page": "120",
                    },
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        searcher = OpenAlexSearcher()
        query = SearchQuery(keywords="test", max_results=10)
        papers = searcher.search(query)

        assert len(papers) == 1
        assert papers[0].title == "OpenAlex 测试论文"
        assert papers[0].doi == "10.1234/oa.001"
        assert papers[0].year == 2023
        assert papers[0].citation_count == 42
        assert papers[0].source_api == "openalex"
        assert papers[0].oa_status == "gold"
        assert len(papers[0].authors) == 2
        assert papers[0].journal == "Nature"

    @patch("src.paper_search.openalex.requests.get")
    def test_search_timeout_retry(self, mock_get):
        """测试 OpenAlex 超时重试逻辑。"""
        Timeout = __import__("requests").exceptions.Timeout
        mock_get.side_effect = [
            Timeout("timeout"),
            Timeout("timeout"),
            Timeout("timeout"),
        ]

        searcher = OpenAlexSearcher()
        query = SearchQuery(keywords="test", max_results=10)
        papers = searcher.search(query)

        # 3 次全部超时后返回空
        assert papers == []
        assert mock_get.call_count == 3

    @patch("src.paper_search.openalex.requests.get")
    def test_get_recent(self, mock_get):
        """测试 OpenAlex get_recent 期刊检索。"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        searcher = OpenAlexSearcher()
        papers = searcher.get_recent("Nature", days=7)

        assert papers == []

    @patch("src.paper_search.openalex.requests.get")
    def test_resolve_doi(self, mock_get):
        """测试 OpenAlex DOI 解析。"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "https://openalex.org/W456",
            "doi": "https://doi.org/10.1234/resolve.001",
            "title": "DOI 查询测试",
            "publication_year": 2024,
            "cited_by_count": 10,
            "primary_location": {"source": {"display_name": "Science"}},
            "authorships": [],
            "concepts": [],
            "open_access": {"oa_status": "closed"},
            "biblio": {},
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        searcher = OpenAlexSearcher()
        paper = searcher.resolve_doi("10.1234/resolve.001")

        assert paper is not None
        assert paper.doi == "10.1234/resolve.001"
        assert paper.title == "DOI 查询测试"


# ============================================================================
# 3. Crossref 检索源测试
# ============================================================================

class TestCrossrefSearcher:
    """验证 Crossref API 调用和结果转换。"""

    @patch("src.paper_search.crossref.requests.get")
    def test_search_success(self, mock_get):
        """测试 Crossref search 成功返回结果。"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "items": [
                    {
                        "DOI": "10.1234/cr.001",
                        "title": ["Crossref 测试论文"],
                        "author": [
                            {"given": "John", "family": "Doe"},
                        ],
                        "created": {"date-parts": [[2023, 5, 10]]},
                        "container-title": ["Test Journal"],
                        "abstract": "Abstract text",
                        "subject": ["keyword1", "keyword2"],
                        "is-referenced-by-count": 5,
                        "publisher": "Test Publisher",
                        "volume": "1",
                        "page": "10-20",
                    }
                ]
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        searcher = CrossrefSearcher()
        query = SearchQuery(keywords="test", max_results=10)
        papers = searcher.search(query)

        assert len(papers) == 1
        assert papers[0].title == "Crossref 测试论文"
        assert papers[0].doi == "10.1234/cr.001"
        assert papers[0].source_api == "crossref"
        assert len(papers[0].authors) == 1
        assert papers[0].authors[0] == "John Doe"

    @patch("src.paper_search.crossref.requests.get")
    def test_resolve_doi(self, mock_get):
        """测试 Crossref DOI 解析。"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "DOI": "10.1234/cr.resolve.001",
                "title": ["DOI 查询"],
                "author": [],
                "created": {"date-parts": [[2024]]},
                "container-title": ["Journal A"],
                "is-referenced-by-count": 0,
                "abstract": "Test abstract",
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        searcher = CrossrefSearcher()
        paper = searcher.resolve_doi("10.1234/cr.resolve.001")

        assert paper is not None
        assert paper.doi == "10.1234/cr.resolve.001"


# ============================================================================
# 4. PubMed 检索源测试
# ============================================================================

class TestPubMedSearcher:
    """验证 PubMed API 调用和结果转换。"""

    @patch("src.paper_search.pubmed.requests.get")
    def test_search_success(self, mock_get):
        """测试 PubMed 两步流程（esearch + efetch）。"""
        # esearch 响应
        esearch_response = MagicMock()
        esearch_response.json.return_value = {
            "esearchresult": {"idlist": ["12345", "67890"]}
        }
        esearch_response.raise_for_status.return_value = None

        # efetch 响应（简化 XML）
        efetch_response = MagicMock()
        efetch_response.text = """<?xml version="1.0"?>
        <PubmedArticleSet>
            <PubmedArticle>
                <MedlineCitation Status="MEDLINE">
                    <PMID>12345</PMID>
                    <Article>
                        <ArticleTitle>PubMed 测试论文</ArticleTitle>
                        <Abstract>
                            <AbstractText>测试摘要内容。</AbstractText>
                        </Abstract>
                        <AuthorList>
                            <Author>
                                <LastName>王</LastName>
                                <ForeName>小明</ForeName>
                            </Author>
                        </AuthorList>
                        <Journal>
                            <Title>Nature Medicine</Title>
                            <JournalIssue>
                                <Volume>30</Volume>
                                <Issue>1</Issue>
                                <PubDate><Year>2023</Year></PubDate>
                            </JournalIssue>
                        </Journal>
                        <Pagination><MedlinePgn>1-10</MedlinePgn></Pagination>
                    </Article>
                </MedlineCitation>
            </PubmedArticle>
        </PubmedArticleSet>"""
        efetch_response.raise_for_status.return_value = None

        mock_get.side_effect = [esearch_response, efetch_response]

        searcher = PubMedSearcher()
        query = SearchQuery(keywords="test", max_results=10)
        papers = searcher.search(query)

        assert len(papers) == 1
        assert papers[0].title == "PubMed 测试论文"
        assert papers[0].source_api == "pubmed"
        assert papers[0].pmid == "12345"
        assert papers[0].journal == "Nature Medicine"
        assert papers[0].year == 2023

    @patch("src.paper_search.pubmed.requests.get")
    def test_search_empty(self, mock_get):
        """测试 PubMed esearch 返回空结果。"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"esearchresult": {"idlist": []}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        searcher = PubMedSearcher()
        query = SearchQuery(keywords="unfindable_query", max_results=10)
        papers = searcher.search(query)

        assert papers == []


# ============================================================================
# 5. Europe PMC 检索源测试
# ============================================================================

class TestEuropePMCSearcher:
    """验证 Europe PMC API 调用和结果转换。"""

    @patch("src.paper_search.europe_pmc.requests.get")
    def test_search_success(self, mock_get):
        """测试 Europe PMC search 成功返回结果。"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "resultList": {
                "result": [
                    {
                        "id": "PMC12345",
                        "source": "MED",
                        "pmid": "12345",
                        "pmcid": "PMC12345",
                        "doi": "10.1234/epmc.001",
                        "title": "Europe PMC 测试论文",
                        "authorString": "Zhang San, Li Si",
                        "pubYear": "2024",
                        "journalTitle": "Nature",
                        "journalInfo": {
                            "volume": "10",
                            "issue": "2",
                            "pages": "50-60",
                        },
                        "abstractText": "This is the abstract.",
                        "citedByCount": 15,
                        "isOpenAccess": "Y",
                    }
                ]
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        searcher = EuropePMCSearcher()
        query = SearchQuery(keywords="test", max_results=10)
        papers = searcher.search(query)

        assert len(papers) == 1
        assert papers[0].title == "Europe PMC 测试论文"
        assert papers[0].source_api == "europe_pmc"
        assert papers[0].doi == "10.1234/epmc.001"
        assert papers[0].pmid == "12345"
        assert papers[0].pmcid == "PMC12345"
        assert papers[0].year == 2024
        assert papers[0].oa_status == "gold"


# ============================================================================
# 6. 去重逻辑测试
# ============================================================================

class TestDeduplication:
    """验证 DOI 去重和 title+year 弱去重。"""

    def test_deduplication_doi(self):
        """按 DOI 去重：相同 DOI 的论文合并为一条。"""
        p1 = make_paper(doi="10.1234/dup.001", title="论文A", year=2023, source_api="openalex")
        p2 = make_paper(doi="10.1234/dup.001", title="论文A (不同来源)", year=2023, source_api="crossref")

        agg = SearchAggregator(searchers=[])
        result = agg.deduplicate([p1, p2])

        assert len(result) == 1
        assert result[0].doi == "10.1234/dup.001"

    def test_deduplication_doi_merge_fields(self):
        """去重合并时，缺失字段从另一篇补充。"""
        p1 = make_paper(doi="10.1234/merge.001", title="合并测试", abstract=None, oa_status="unknown")
        p2 = make_paper(doi="10.1234/merge.001", title="合并测试", abstract="补充摘要", oa_status="gold")

        agg = SearchAggregator(searchers=[])
        result = agg.deduplicate([p1, p2])

        assert len(result) == 1
        assert result[0].abstract == "补充摘要"
        assert result[0].oa_status == "gold"

    def test_deduplication_title_year(self):
        """无 DOI 时按 title+year 弱去重。"""
        p1 = make_paper(doi=None, title="机器学习综述", year=2023)
        p2 = make_paper(doi=None, title="机器学习综述", year=2023)

        agg = SearchAggregator(searchers=[])
        result = agg.deduplicate([p1, p2])

        assert len(result) == 1

    def test_deduplication_different_year(self):
        """同名但不同年份的论文不合并。"""
        p1 = make_paper(doi=None, title="年度报告", year=2022)
        p2 = make_paper(doi=None, title="年度报告", year=2023)

        agg = SearchAggregator(searchers=[])
        result = agg.deduplicate([p1, p2])

        assert len(result) == 2

    def test_deduplication_mixed(self):
        """混合 DOI 和无 DOI 的论文去重。"""
        p1 = make_paper(doi="10.1234/has.001", title="论文A", year=2023)
        p2 = make_paper(doi=None, title="论文B", year=2023)
        p3 = make_paper(doi="10.1234/has.001", title="论文A", year=2023)  # DOI 重复
        p4 = make_paper(doi=None, title="论文B", year=2023)  # title+year 重复

        agg = SearchAggregator(searchers=[])
        result = agg.deduplicate([p1, p2, p3, p4])

        assert len(result) == 2


# ============================================================================
# 7. 多源聚合器测试
# ============================================================================

class TestSearchAggregator:
    """验证多源聚合检索。"""

    def test_aggregator_multi_source(self):
        """多源聚合：从多个检索源获取结果并去重。"""
        # 模拟两个检索源
        mock_searcher1 = MagicMock(spec=BaseSearcher)
        mock_searcher1.source_name = "openalex"
        mock_searcher1.search.return_value = [
            make_paper(doi="10.1234/agg.001", title="来源1", source_api="openalex"),
            make_paper(doi="10.1234/agg.002", title="来源1-共享", source_api="openalex"),
        ]

        mock_searcher2 = MagicMock(spec=BaseSearcher)
        mock_searcher2.source_name = "crossref"
        mock_searcher2.search.return_value = [
            make_paper(doi="10.1234/agg.002", title="来源2-共享", source_api="crossref"),
            make_paper(doi="10.1234/agg.003", title="来源2独有", source_api="crossref"),
        ]

        agg = SearchAggregator(searchers=[mock_searcher1, mock_searcher2])
        query = SearchQuery(keywords="test", max_results=10, sources=["openalex", "crossref"])
        result = agg.search(query)

        # 去重后应有 3 条（agg.002 被合并）
        assert len(result.papers) == 3

    def test_aggregator_single_source_failure(self):
        """单个源失败不影响其他源。"""
        mock_searcher1 = MagicMock(spec=BaseSearcher)
        mock_searcher1.source_name = "openalex"
        mock_searcher1.search.side_effect = Exception("API 不可用")

        mock_searcher2 = MagicMock(spec=BaseSearcher)
        mock_searcher2.source_name = "crossref"
        mock_searcher2.search.return_value = [
            make_paper(doi="10.1234/failover.001", title="备用源结果", source_api="crossref"),
        ]

        agg = SearchAggregator(searchers=[mock_searcher1, mock_searcher2])
        query = SearchQuery(keywords="test", max_results=10, sources=["openalex", "crossref"])
        result = agg.search(query)

        assert len(result.papers) == 1
        assert len(result.errors) == 1
        assert "API 不可用" in result.errors[0]

    def test_aggregator_empty(self):
        """空检索源列表。"""
        agg = SearchAggregator(searchers=[])
        query = SearchQuery(keywords="test")
        result = agg.search(query)

        assert result.papers == []
        assert result.total_count == 0


# ============================================================================
# 8. SearchResult 和 PaperSearcher 测试
# ============================================================================

class TestSearchResult:
    """验证 SearchResult 容器。"""

    def test_search_result_defaults(self):
        """SearchResult 默认值正确。"""
        query = SearchQuery(keywords="test")
        result = SearchResult(query=query)

        assert result.papers == []
        assert result.total_count == 0
        assert result.page == 1
        assert result.errors == []

    def test_search_result_with_papers(self):
        """SearchResult 包含论文时正确。"""
        query = SearchQuery(keywords="test")
        papers = [make_paper()]
        result = SearchResult(query=query, papers=papers, total_count=1)

        assert len(result.papers) == 1
        assert result.total_count == 1


# ============================================================================
# 9. 期刊监控清单测试
# ============================================================================

class TestJournalWatchlist:
    """验证期刊监控清单管理。"""

    def test_default_journals(self):
        """默认期刊清单包含预期期刊。"""
        wl = JournalWatchlist()
        journals = wl.get_journals()

        assert len(journals) > 0
        names = {j["name"] for j in journals}
        assert "Nature" in names
        assert "Science" in names
        assert "Cell" in names
        assert "PNAS" in names

    def test_add_journal(self, tmp_path):
        """测试添加期刊。"""
        db_path = tmp_path / "test_journals.db"
        from src.database.connection import DatabaseManager
        db = DatabaseManager(db_path)
        db.initialize()

        wl = JournalWatchlist(db_manager=db)
        initial_count = len(wl.get_journals())

        result = wl.add_journal("Test Journal", issn="1234-5678", rss_url="https://example.com/rss")
        assert result is True

        journals = wl.get_journals()
        assert len(journals) == initial_count + 1

    def test_remove_journal(self, tmp_path):
        """测试删除期刊。"""
        db_path = tmp_path / "test_journals2.db"
        from src.database.connection import DatabaseManager
        db = DatabaseManager(db_path)
        db.initialize()

        wl = JournalWatchlist(db_manager=db)
        wl.add_journal("To Remove", issn="0000-0000")

        result = wl.remove_journal("To Remove")
        assert result is True

    def test_set_active(self, tmp_path):
        """测试启用/停用期刊。"""
        db_path = tmp_path / "test_journals3.db"
        from src.database.connection import DatabaseManager
        db = DatabaseManager(db_path)
        db.initialize()

        wl = JournalWatchlist(db_manager=db)
        wl.add_journal("Status Test", issn="1111-2222")

        wl.set_active("Status Test", active=False)
        active_journals = wl.get_journals(active_only=True)
        names = {j["name"] for j in active_journals}
        assert "Status Test" not in names

        wl.set_active("Status Test", active=True)
        active_journals = wl.get_journals(active_only=True)
        names = {j["name"] for j in active_journals}
        assert "Status Test" in names

    def test_get_rss_urls(self):
        """测试获取 RSS URL 列表。"""
        wl = JournalWatchlist()
        urls = wl.get_rss_urls()

        assert len(urls) > 0
        assert any("nature.com" in u for u in urls)
        assert any("science.org" in u for u in urls)

    def test_get_statistics(self):
        """测试获取统计信息。"""
        wl = JournalWatchlist()
        stats = wl.get_statistics()

        assert "total_journals" in stats
        assert "active_journals" in stats
        assert "journals_with_rss" in stats
        assert stats["total_journals"] > 0


# ============================================================================
# 10. 检索运行记录测试
# ============================================================================

class TestSearchRuns:
    """验证检索运行记录功能。"""

    def test_record_search_run(self, tmp_path):
        """测试记录检索运行（含完整统计字段）。"""
        db_path = tmp_path / "test_runs.db"
        from src.database.connection import DatabaseManager
        db = DatabaseManager(db_path)
        db.initialize()

        from src.storage.repository import PaperRepository
        repo = PaperRepository()
        repo.db = db

        run_id = repo.record_search_run(
            run_type="backfill",
            sources=["openalex", "crossref"],
            keywords="test keywords",
            total_found=42,
            new_added=10,
            updated_count=5,
            duplicate_count=20,
            failed_count=7,
            errors=["error1"],
        )

        assert run_id > 0

        # 验证记录
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM search_runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        d = dict(row)
        assert d["run_type"] == "backfill"
        assert d["total_found"] == 42
        assert d["new_added"] == 10
        assert d["updated_count"] == 5
        assert d["duplicate_count"] == 20
        assert d["failed_count"] == 7

    def test_record_search_run_without_errors(self, tmp_path):
        """测试记录无错误的检索运行。"""
        db_path = tmp_path / "test_runs2.db"
        from src.database.connection import DatabaseManager
        db = DatabaseManager(db_path)
        db.initialize()

        from src.storage.repository import PaperRepository
        repo = PaperRepository()
        repo.db = db

        run_id = repo.record_search_run(
            run_type="daily_watch",
            sources=["rss"],
            keywords="journal watch",
            total_found=5,
            new_added=3,
        )

        assert run_id > 0


# ============================================================================
# 11. 数据流端到端测试 — 检索 → 入库 → papers 表
# ============================================================================

class TestEndToEndSaveFlow:
    """验证检索结果完整入库流程。"""

    def test_upsert_inserts_into_papers(self, tmp_path):
        """PaperMetadata 通过 upsert_paper 成功写入 papers 表。"""
        db_path = tmp_path / "test_e2e.db"
        from src.database.connection import DatabaseManager
        db = DatabaseManager(db_path)
        db.initialize()

        from src.storage.repository import PaperRepository
        repo = PaperRepository()
        repo.db = db

        paper = make_paper(
            title="端到端测试论文",
            doi="10.9999/e2e.001",
            year=2025,
        )

        paper_id, action = repo.upsert_paper(paper)
        assert paper_id > 0
        assert action == "inserted"

        # 验证 papers 表 count 增加
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM papers")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1

    def test_upsert_updates_existing(self, tmp_path):
        """重复 DOI 的论文触发更新而非重复插入。"""
        db_path = tmp_path / "test_e2e_update.db"
        from src.database.connection import DatabaseManager
        db = DatabaseManager(db_path)
        db.initialize()

        from src.storage.repository import PaperRepository
        repo = PaperRepository()
        repo.db = db

        p1 = make_paper(title="原始论文", doi="10.9999/e2e.002", year=2024, abstract=None)
        p2 = make_paper(
            title="原始论文",
            doi="10.9999/e2e.002",
            year=2024,
            abstract="新摘要内容",
        )

        id1, act1 = repo.upsert_paper(p1)
        id2, act2 = repo.upsert_paper(p2)

        assert id1 == id2  # 同一 paper_id
        assert act1 == "inserted"
        assert act2 in ("updated", "duplicate")

        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM papers")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1  # 只有一条记录

    def test_save_results_return_stats(self, tmp_path):
        """save_results 返回正确的统计字典。"""
        db_path = tmp_path / "test_e2e_stats.db"
        from src.database.connection import DatabaseManager
        db = DatabaseManager(db_path)
        db.initialize()

        from src.storage.repository import PaperRepository
        repo = PaperRepository()
        repo.db = db

        from src.paper_search.aggregator import SearchAggregator
        agg = SearchAggregator(searchers=[], repository=repo)

        papers = [
            make_paper(title="论文A", doi="10.9999/save.001", year=2024),
            make_paper(title="论文B", doi="10.9999/save.002", year=2025),
        ]
        stats = agg.save_results(papers)

        assert stats["new_count"] == 2
        assert stats["failed_count"] == 0

    def test_save_results_handles_failures(self, tmp_path):
        """入库失败时统计 failed_count 并记录失败详情。"""
        db_path = tmp_path / "test_e2e_fail.db"
        from src.database.connection import DatabaseManager
        db = DatabaseManager(db_path)
        db.initialize()

        from src.storage.repository import PaperRepository
        repo = PaperRepository()
        repo.db = db

        from src.paper_search.aggregator import SearchAggregator
        agg = SearchAggregator(searchers=[], repository=repo)

        # 构造一个会触发完整性错误的重复
        papers = [
            make_paper(title="正常论文", doi="10.9999/fail.001", year=2024),
            make_paper(title="正常论文2", doi="10.9999/fail.001", year=2024),  # 同 DOI
        ]
        stats = agg.save_results(papers)

        # 至少有一篇入库成功
        assert stats["new_count"] + stats["updated_count"] + stats["duplicate_count"] >= 1
        assert stats["failed_count"] <= 1  # 第二篇可能因 DOI 重复而触发 IntegrityError


# ============================================================================
# 12. PaperMetadata 序列化测试
# ============================================================================

class TestPaperMetadata:
    """验证 PaperMetadata 数据模型。"""

    def test_to_dict(self):
        """to_dict 方法正确序列化。"""
        paper = make_paper()
        d = paper.to_dict()

        assert d["title"] == "测试论文标题"
        assert d["doi"] == "10.1234/test.001"
        assert d["year"] == 2023
        assert d["source_api"] == "test"

    def test_str_representation(self):
        """__str__ 方法正确。"""
        paper = make_paper()
        s = str(paper)

        assert "PaperMetadata" in s
        assert "测试论文标题" in s

    def test_default_values(self):
        """默认值正确。"""
        paper = PaperMetadata(title="测试")
        assert paper.authors == []
        assert paper.keywords == []
        assert paper.doi is None
        assert paper.year is None
        assert paper.oa_status == "unknown"
        assert paper.citation_count == 0
