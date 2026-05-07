"""
校园网授权访问解析器 — 通过机构网络授权获取 PDF。
Phase 2.2 仅实现 network_authorized 模式。
"""

import time
from pathlib import Path
from typing import Optional

import requests

from src.config import get_config
from src.fulltext.base import FullTextResult, FullTextResolver
from src.fulltext.downloader import validate_url, validate_pdf_file, build_pdf_filename
from src.utils.logger import get_logger

logger = get_logger(__name__)


class InstitutionAccessResolver(FullTextResolver):
    """
    校园网 / 学校图书馆授权访问解析器。

    支持模式:
      - network_authorized (Phase 2.2): 依赖用户已连接的校园网/VPN 直接下载
      - browser_session (未来): 通过浏览器会话访问

    约束（严禁）:
      - 不得保存账号密码
      - 不得自动登录
      - 不得绕过验证码
      - 不得批量规避速率限制

    network_authorized 模式流程:
      1. 检查 download_status
      2. URL scheme 校验
      3. HEAD 请求检查 Content-Type
      4. GET 下载（带超时+重试）
      5. 检查文件头 %PDF
      6. 403/401/429 → failed
      7. HTML 登录页 → manual_review
      8. 成功 → institution_access
    """

    def __init__(self):
        self.enabled = get_config("institution_access.enabled", True)
        self.mode = get_config("institution_access.mode", "network_authorized")
        self.max_downloads = get_config("institution_access.max_downloads_per_run", 10)
        self.request_interval = get_config("institution_access.request_interval_seconds", 8)
        self.timeout = get_config("institution_access.timeout_seconds", 30)
        self.max_file_size = get_config("institution_access.max_file_size_mb", 100) * 1024 * 1024
        self.stop_on_403 = get_config("institution_access.stop_on_403", True)
        self.stop_on_429 = get_config("institution_access.stop_on_429", True)
        self.user_agent = get_config(
            "institution_access.user_agent",
            "ResearchAutomationAssistant/0.2 institutional access",
        )
        self.require_confirmation = get_config("institution_access.require_user_confirmation", True)

    @property
    def source_name(self) -> str:
        return "institution_access"

    def resolve(self, paper: dict) -> FullTextResult:
        paper_id = paper.get("paper_id", paper.get("id", 0))
        doi = paper.get("doi")
        title = paper.get("title")
        pdf_url = paper.get("pdf_url")
        download_status = paper.get("download_status", "")

        if not self.enabled:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="unavailable", legal_status="unknown",
                error_message="机构访问功能已禁用",
            )

        if download_status == "downloaded" and paper.get("pdf_path"):
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="institution_access",
                legal_status="institution_authorized",
                pdf_path=paper.get("pdf_path"), pdf_url=pdf_url,
                risk_level="low",
            )

        if not pdf_url:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="unavailable", legal_status="unknown",
                error_message="论文无可用 PDF URL，无法通过机构访问获取",
            )

        if not validate_url(pdf_url):
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="unavailable", legal_status="unknown",
                error_message=f"机构访问 URL 校验失败: {pdf_url[:100]}",
            )

        logger.info(f"机构访问来源就绪: paper_id={paper_id}")
        return FullTextResult(
            paper_id=paper_id, doi=doi, title=title,
            source=self.source_name,
            access_status="institution_access",
            legal_status="institution_authorized",
            pdf_url=pdf_url,
            landing_page_url=paper.get("landing_page_url"),
            risk_level="low",
        )

    def download(
        self,
        paper: dict,
        save_dir,
        user_confirmed_authorization: bool = False,
    ) -> FullTextResult:
        """通过机构网络授权下载 PDF。要求 user_confirmed_authorization=True。"""
        paper_id = paper.get("paper_id", paper.get("id", 0))
        doi = paper.get("doi")
        title = paper.get("title")
        pdf_url = paper.get("pdf_url")

        if self.require_confirmation and not user_confirmed_authorization:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="failed", legal_status="unknown",
                error_message="需要用户确认已具备机构授权 (user_confirmed_authorization=True)",
            )

        if not self.enabled:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="unavailable", legal_status="unknown",
                error_message="机构访问功能已禁用",
            )

        if not pdf_url or not validate_url(pdf_url):
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="failed", legal_status="unknown",
                error_message="无可用 PDF URL 或 URL 校验失败",
            )

        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/pdf, */*",
        }

        logger.info(f"机构访问下载: paper_id={paper_id}")

        try:
            # HEAD 请求
            head_resp = requests.head(pdf_url, headers=headers, timeout=self.timeout, allow_redirects=True)
            status_code = head_resp.status_code

            if status_code in (401, 403):
                return FullTextResult(
                    paper_id=paper_id, doi=doi, title=title,
                    source=self.source_name,
                    access_status="failed", legal_status="unknown",
                    pdf_url=pdf_url, risk_level="medium",
                    risk_note=f"HTTP {status_code} — 机构可能未订阅该期刊",
                    error_message=f"HTTP {status_code}: 访问被拒绝",
                )
            elif status_code == 429:
                return FullTextResult(
                    paper_id=paper_id, doi=doi, title=title,
                    source=self.source_name,
                    access_status="failed", legal_status="unknown",
                    pdf_url=pdf_url, risk_level="medium",
                    risk_note="HTTP 429 — 请求频率过高",
                    error_message="HTTP 429: 请求频率过高",
                )
            elif status_code == 451:
                return FullTextResult(
                    paper_id=paper_id, doi=doi, title=title,
                    source=self.source_name,
                    access_status="failed", legal_status="unknown",
                    pdf_url=pdf_url, risk_level="high",
                    risk_note="HTTP 451 — 因法律原因不可用",
                    error_message="HTTP 451: 因法律原因不可用",
                )

            content_type = head_resp.headers.get("Content-Type", "")
            if "text/html" in content_type.lower():
                return FullTextResult(
                    paper_id=paper_id, doi=doi, title=title,
                    source=self.source_name,
                    access_status="manual_review", legal_status="unknown",
                    pdf_url=pdf_url, risk_level="medium",
                    risk_note="服务器返回 HTML 登录页面",
                    error_message="服务器返回 HTML，可能是登录页面",
                )

            head_resp.raise_for_status()

            # GET 下载
            filename = build_pdf_filename(paper)
            file_path = save_dir / filename
            temp_path = file_path.with_suffix(".tmp")

            resp = requests.get(pdf_url, headers=headers, timeout=self.timeout, allow_redirects=True, stream=True)
            resp.raise_for_status()

            resp_ct = resp.headers.get("Content-Type", "")
            if "text/html" in resp_ct.lower():
                return FullTextResult(
                    paper_id=paper_id, doi=doi, title=title,
                    source=self.source_name,
                    access_status="manual_review", legal_status="unknown",
                    pdf_url=pdf_url, risk_level="medium",
                    risk_note="下载内容为 HTML，可能是登录页面",
                    error_message="下载内容为 HTML 而非 PDF",
                )

            downloaded_size = 0
            with open(temp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_size += len(chunk)
                        if downloaded_size > self.max_file_size:
                            temp_path.unlink(missing_ok=True)
                            return FullTextResult(
                                paper_id=paper_id, doi=doi, title=title,
                                source=self.source_name,
                                access_status="failed", legal_status="unknown",
                                pdf_url=pdf_url,
                                error_message=f"文件超过大小限制 ({self.max_file_size} 字节)",
                            )
                        f.write(chunk)

            if not validate_pdf_file(temp_path):
                temp_path.unlink(missing_ok=True)
                return FullTextResult(
                    paper_id=paper_id, doi=doi, title=title,
                    source=self.source_name,
                    access_status="failed", legal_status="unknown",
                    pdf_url=pdf_url,
                    error_message="下载内容不是有效的 PDF",
                )

            file_size = temp_path.stat().st_size
            if file_size < 10240:
                temp_path.unlink(missing_ok=True)
                return FullTextResult(
                    paper_id=paper_id, doi=doi, title=title,
                    source=self.source_name,
                    access_status="failed", legal_status="unknown",
                    pdf_url=pdf_url,
                    error_message=f"PDF 文件过小 ({file_size} 字节)",
                )

            temp_path.replace(file_path)

            from src.fulltext.downloader import compute_sha256
            checksum = compute_sha256(file_path)

            logger.info(f"机构访问下载成功: paper_id={paper_id}, path={file_path}, size={file_size}")
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="institution_access",
                legal_status="institution_authorized",
                pdf_url=pdf_url, pdf_path=str(file_path),
                file_size=file_size, content_type=resp_ct,
                checksum_sha256=checksum, risk_level="low",
            )

        except requests.exceptions.HTTPError as e:
            sc = getattr(e.response, "status_code", 0)
            if sc in (401, 403):
                return FullTextResult(
                    paper_id=paper_id, doi=doi, title=title,
                    source=self.source_name,
                    access_status="failed", legal_status="unknown",
                    pdf_url=pdf_url,
                    risk_note=f"HTTP {sc} — 机构可能未订阅该期刊",
                    error_message=f"HTTP {sc}: 访问被拒绝",
                )
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="failed", legal_status="unknown",
                pdf_url=pdf_url,
                error_message=f"HTTP {sc}: {e}",
            )
        except requests.exceptions.Timeout:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="failed", legal_status="unknown",
                pdf_url=pdf_url,
                error_message="机构访问请求超时",
            )
        except Exception as e:
            logger.error(f"机构访问下载异常: paper_id={paper_id}, 原因={e}")
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="failed", legal_status="unknown",
                pdf_url=pdf_url,
                error_message=f"下载异常: {e}",
            )
