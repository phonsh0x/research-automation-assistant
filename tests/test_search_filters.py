"""检索过滤器回归测试（年份区间）。

覆盖两个已修复的缺陷：

1. **OpenAlex**：原实现把年份区间拼成两个 ``publication_year`` 过滤条件。
   OpenAlex 的 ``filter`` 参数以逗号分隔且语义为 **AND**，因此
   ``publication_year:2020,publication_year:2025`` 表示"2020 且 2025"，恒为空结果。
   正确做法是使用 ``from_publication_date`` / ``to_publication_date``。

2. **Crossref**：原实现只在起止年份**同时**给出时才添加过滤器，
   只填一边的年份条件会被静默忽略。

这些测试全部离线运行（HTTP 层被打桩）。
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.paper_search.crossref import CrossrefSearcher  # noqa: E402
from src.paper_search.models import SearchQuery  # noqa: E402
from src.paper_search.openalex import OpenAlexSearcher  # noqa: E402


class _FakeResponse:
    """最小化的 requests.Response 替身。"""

    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.headers = {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class TestOpenAlexYearFilter:
    def test_no_bounds_returns_empty(self):
        assert OpenAlexSearcher._build_year_filter(None, None) == ""

    def test_lower_bound_only(self):
        result = OpenAlexSearcher._build_year_filter(2020, None)
        assert result == "from_publication_date:2020-01-01"

    def test_upper_bound_only(self):
        result = OpenAlexSearcher._build_year_filter(None, 2025)
        assert result == "to_publication_date:2025-12-31"

    def test_range_uses_from_and_to_filters(self):
        result = OpenAlexSearcher._build_year_filter(2020, 2025)
        assert result == "from_publication_date:2020-01-01,to_publication_date:2025-12-31"

    def test_range_never_repeats_publication_year(self):
        """关键回归：重复的 publication_year 会被 AND 成空结果。"""
        result = OpenAlexSearcher._build_year_filter(2020, 2025)
        assert result.count("publication_year:") == 0

    def test_filter_is_sent_to_the_api(self, monkeypatch):
        captured = {}

        def fake_get(url, params=None, **kwargs):
            captured["params"] = params
            return _FakeResponse({"results": []})

        import src.paper_search.openalex as openalex_module

        monkeypatch.setattr(openalex_module.requests, "get", fake_get)

        OpenAlexSearcher().search(SearchQuery(keywords="cancer", year_from=2020, year_to=2025))

        assert captured["params"]["filter"] == (
            "from_publication_date:2020-01-01,to_publication_date:2025-12-31"
        )

    def test_oa_filter_combines_with_year_filter(self, monkeypatch):
        captured = {}

        def fake_get(url, params=None, **kwargs):
            captured["params"] = params
            return _FakeResponse({"results": []})

        import src.paper_search.openalex as openalex_module

        monkeypatch.setattr(openalex_module.requests, "get", fake_get)

        OpenAlexSearcher().search(
            SearchQuery(keywords="cancer", year_from=2020, filter_oa_only=True)
        )

        filter_value = captured["params"]["filter"]
        assert "from_publication_date:2020-01-01" in filter_value
        assert "is_oa:true" in filter_value


class TestCrossrefYearFilter:
    def _run(self, monkeypatch, **query_kwargs):
        captured = {}

        def fake_get(url, params=None, **kwargs):
            captured["params"] = params
            return _FakeResponse({"message": {"items": []}})

        import src.paper_search.crossref as crossref_module

        monkeypatch.setattr(crossref_module.requests, "get", fake_get)
        CrossrefSearcher().search(SearchQuery(keywords="cancer", **query_kwargs))
        return captured["params"]

    def test_no_bounds_has_no_filter(self, monkeypatch):
        params = self._run(monkeypatch)
        assert "filter" not in params

    def test_both_bounds(self, monkeypatch):
        params = self._run(monkeypatch, year_from=2020, year_to=2025)
        assert params["filter"] == "from-pub-date:2020,until-pub-date:2025"

    def test_lower_bound_only_is_not_dropped(self, monkeypatch):
        params = self._run(monkeypatch, year_from=2020)
        assert params["filter"] == "from-pub-date:2020"

    def test_upper_bound_only_is_not_dropped(self, monkeypatch):
        params = self._run(monkeypatch, year_to=2025)
        assert params["filter"] == "until-pub-date:2025"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
