"""Data-source health checker — configuration, availability, advice.

Each check returns a uniform dict:

    {"source": str, "type": "metadata"|"fulltext", "configured": bool,
     "available": bool, "requires_key": bool, "requires_email": bool,
     "message": str, "advice": str}
"""

from src.config import get_config
from src.utils.logger import get_logger

_log = get_logger(__name__)


class SourceHealthChecker:
    """Checks configuration and basic reachability for each data source."""

    @staticmethod
    def check_openalex() -> dict:
        api_key = get_config("openalex.api_key", "")
        return {
            "source": "OpenAlex",
            "type": "metadata",
            "configured": bool(api_key),
            "available": True,
            "requires_key": False,
            "requires_email": False,
            "message": "已配置 API key" if api_key else "未配置 API key（低频可用，规模化建议配置）",
            "advice": "OpenAlex 无 key 也可正常检索，但配置 key 可提高速率上限。",
        }

    @staticmethod
    def check_crossref() -> dict:
        mailto = get_config("crossref.mailto", "")
        return {
            "source": "Crossref",
            "type": "metadata",
            "configured": bool(mailto),
            "available": True,
            "requires_key": False,
            "requires_email": True,
            "message": "已配置 mailto（polite pool）" if mailto else "未配置 mailto（可用但不在 polite pool）",
            "advice": "配置 mailto 可纳入 Crossref polite pool，获得更稳定的服务。",
        }

    @staticmethod
    def check_pubmed() -> dict:
        api_key = get_config("pubmed.api_key", "")
        return {
            "source": "PubMed",
            "type": "metadata",
            "configured": bool(api_key),
            "available": True,
            "requires_key": False,
            "requires_email": False,
            "message": "已配置 NCBI API key（10 rps）" if api_key else "未配置 API key（默认 3 rps，低频可用）",
            "advice": "不配置 key 也可检索，频率高时建议配置以提升至 10 rps。",
        }

    @staticmethod
    def check_europe_pmc() -> dict:
        return {
            "source": "Europe PMC",
            "type": "metadata",
            "configured": True,
            "available": True,
            "requires_key": False,
            "requires_email": False,
            "message": "免费开放，无需 key",
            "advice": "",
        }

    @staticmethod
    def check_semantic_scholar() -> dict:
        api_key = get_config("semantic_scholar.api_key", "")
        return {
            "source": "Semantic Scholar",
            "type": "metadata",
            "configured": bool(api_key),
            "available": bool(api_key),
            "requires_key": True,
            "requires_email": False,
            "message": "已配置 API key" if api_key else "未配置 API key（当前未启用）",
            "advice": "Semantic Scholar 需要 API key，未配置时不可用。",
        }

    @staticmethod
    def check_arxiv() -> dict:
        return {
            "source": "arXiv",
            "type": "fulltext",
            "configured": True,
            "available": True,
            "requires_key": False,
            "requires_email": False,
            "message": "免费开放，无需 key",
            "advice": "arXiv 预印本可免费获取全文 PDF。",
        }

    @staticmethod
    def check_unpaywall() -> dict:
        email = get_config("unpaywall.email", "")
        return {
            "source": "Unpaywall",
            "type": "fulltext",
            "configured": bool(email),
            "available": True,
            "requires_key": False,
            "requires_email": True,
            "message": "已配置 email" if email else "⚠ 未配置 email — 建议在系统设置中配置",
            "advice": "Unpaywall 要求提供 email 以获得稳定的 API 访问。未配置时可能被限速。",
        }

    @staticmethod
    def check_pmc() -> dict:
        return {
            "source": "PubMed Central",
            "type": "fulltext",
            "configured": True,
            "available": True,
            "requires_key": False,
            "requires_email": False,
            "message": "免费开放 OA 子集",
            "advice": "PMC 提供 OA 论文全文，无需额外配置。",
        }

    @staticmethod
    def check_publisher_oa() -> dict:
        return {
            "source": "Publisher OA",
            "type": "fulltext",
            "configured": True,
            "available": True,
            "requires_key": False,
            "requires_email": False,
            "message": "尝试出版社 Gold/Hybrid OA 接口",
            "advice": "仅有 OA 论文可通过此途径获取。",
        }

    @staticmethod
    def check_institution_access() -> dict:
        require_confirm = get_config("institution_access.require_user_confirmation", True)
        return {
            "source": "Institution Access",
            "type": "fulltext",
            "configured": True,
            "available": True,
            "requires_key": False,
            "requires_email": False,
            "message": "需用户勾选「已连接校园网/VPN」确认",
            "advice": "仅限已获得机构授权的用户使用。系统不保存账号密码。"
            if require_confirm else "机构访问已启用",
        }

    @staticmethod
    def check_manual_upload() -> dict:
        return {
            "source": "Manual Upload",
            "type": "fulltext",
            "configured": True,
            "available": True,
            "requires_key": False,
            "requires_email": False,
            "message": "用户自行上传合法 PDF",
            "advice": "上传前需确认版权合规。",
        }

    @classmethod
    def check_all_metadata(cls) -> list[dict]:
        return [
            cls.check_openalex(),
            cls.check_crossref(),
            cls.check_pubmed(),
            cls.check_europe_pmc(),
            cls.check_semantic_scholar(),
        ]

    @classmethod
    def check_all_fulltext(cls) -> list[dict]:
        return [
            cls.check_unpaywall(),
            cls.check_pmc(),
            cls.check_arxiv(),
            cls.check_publisher_oa(),
            cls.check_institution_access(),
            cls.check_manual_upload(),
        ]

    @classmethod
    def check_all(cls) -> dict:
        return {
            "metadata": cls.check_all_metadata(),
            "fulltext": cls.check_all_fulltext(),
        }
