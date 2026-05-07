"""
受限来源解析器 — 阻止对非法/受限来源的访问尝试。
不实现任何下载逻辑，直接返回 unsupported 状态。
"""

from src.config import get_config
from src.fulltext.base import FullTextResult, FullTextResolver
from src.utils.logger import get_logger

logger = get_logger(__name__)

_BLOCKED_DOMAINS = {
    "sci-hub.se", "sci-hub.st", "sci-hub.ru", "sci-hub.tw",
    "sci-hub.do", "sci-hub.ee", "sci-hub.is", "sci-hub.la",
    "sci-hub.mn", "sci-hub.wf",
    "libgen.is", "libgen.li", "libgen.gs", "libgen.lc",
    "library.lol", "libgen.rs", "libgen.fun", "libgen.ee",
    "libgen.pm", "libgen.st",
    "z-lib.org", "z-lib.id", "z-lib.is",
}


class RestrictedSourceResolver(FullTextResolver):
    """
    受限来源解析器。

    规则:
      - 不实现任何下载逻辑
      - resolve() 直接返回 access_status="unsupported_source"
      - 用于在 pipeline 中拦截受限来源
    严禁: Sci-Hub、LibGen 或任何盗版源。
    """

    @property
    def source_name(self) -> str:
        return "restricted_sources"

    def __init__(self):
        self.enabled = get_config("restricted_sources.enabled", False)
        self.block_scihub = get_config("restricted_sources.block_scihub", True)
        self.block_libgen = get_config("restricted_sources.block_libgen", True)
        self.block_paywall_bypass = get_config("restricted_sources.block_paywall_bypass", True)

    def resolve(self, paper: dict) -> FullTextResult:
        paper_id = paper.get("paper_id", paper.get("id", 0))
        doi = paper.get("doi")
        title = paper.get("title")
        logger.debug(f"受限来源拦截: paper_id={paper_id}")

        return FullTextResult(
            paper_id=paper_id, doi=doi, title=title,
            source=self.source_name,
            access_status="unsupported_source",
            legal_status="unsupported",
            risk_level="high",
            risk_note="该来源涉及版权与合规风险，系统不提供自动检索、镜像访问或下载功能。"
                     "请通过合法途径获取文献（Unpaywall / PubMed Central / arXiv / 机构订阅）。",
            error_message="不支持该来源的自动获取",
        )

    @staticmethod
    def is_blocked_domain(url: str) -> bool:
        if not url:
            return False
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = (parsed.hostname or "").lower()
            for blocked in _BLOCKED_DOMAINS:
                if domain == blocked or domain.endswith("." + blocked):
                    return True
            return False
        except Exception:
            return False


# 已知合法 OA 域名
_KNOWN_OA_DOMAINS = {
    "arxiv.org", "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov",
    "europepmc.org", "doi.org", "nature.com", "science.org",
    "pnas.org", "cell.com", "pubs.acs.org", "pubs.rsc.org",
    "wiley.com", "onlinelibrary.wiley.com", "springer.com",
    "link.springer.com", "elsevier.com", "sciencedirect.com",
    "tandfonline.com", "mdpi.com", "frontiersin.org",
    "plos.org", "biorxiv.org", "medrxiv.org", "chemrxiv.org",
    "researchgate.net", "semanticscholar.org", "openalex.org",
    "unpaywall.org", "crossref.org",
}


def is_restricted_domain(url: str) -> bool:
    """检查 URL 域名是否在受限列表中（Sci-Hub、LibGen 等）。"""
    if not url:
        return False
    try:
        from urllib.parse import urlparse
        hostname = (urlparse(url).hostname or "").lower()
        for domain in _BLOCKED_DOMAINS:
            if hostname == domain or hostname.endswith("." + domain):
                return True
        return False
    except Exception:
        return True


def is_known_oa_domain(url: str) -> bool:
    """检查 URL 是否属于已知合法 OA 来源。"""
    if not url:
        return False
    try:
        from urllib.parse import urlparse
        hostname = (urlparse(url).hostname or "").lower()
        for domain in _KNOWN_OA_DOMAINS:
            if hostname == domain or hostname.endswith("." + domain):
                return True
        return False
    except Exception:
        return False


def check_restricted(url: str) -> tuple[bool, str]:
    """综合检查 URL 合法性。返回 (is_safe, risk_level)。"""
    if is_restricted_domain(url):
        return (False, "high")
    if is_known_oa_domain(url):
        return (True, "low")
    return (True, "medium")
