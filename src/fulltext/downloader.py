"""
PDF 下载工具函数 — URL 校验、文件清理、哈希计算、带重试的下载。
"""

import hashlib
import re
import os
import time
from pathlib import Path
from typing import Optional

import requests

from src.utils.logger import get_logger

logger = get_logger(__name__)

# 允许的 URL scheme
ALLOWED_SCHEMES = {"http", "https"}

# 最大文件大小：100 MB
MAX_FILE_SIZE = 100 * 1024 * 1024

# PDF 文件魔术字节
PDF_MAGIC = b"%PDF"

# 非法文件名字符
_ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def validate_url(url: str) -> bool:
    """验证 URL 合法性 — 检查 http/https 协议及域名黑名单。"""
    if not url:
        return False
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_SCHEMES:
            return False

        hostname = (parsed.hostname or "").lower()
        blocked_domains = [
            "sci-hub.ru", "sci-hub.se", "sci-hub.st", "sci-hub.do",
            "sci-hub.tw", "sci-hub.ee", "sci-hub.ren", "sci-hub.is",
            "sci-hub.love", "sci-hub.mk", "sci-hub.wf",
            "sci-hub.hk", "sci-hub.la",
            "libgen.is", "libgen.rs", "libgen.st", "libgen.li",
        ]
        for blocked in blocked_domains:
            if hostname == blocked or hostname.endswith("." + blocked):
                return False

        return True
    except Exception:
        return False


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符。"""
    name = _ILLEGAL_FILENAME_CHARS.sub("_", name)
    name = re.sub(r"_+", "_", name)
    name = re.sub(r"\s+", " ", name)
    if len(name) > 200:
        name = name[:200]
    return name.strip()


def build_pdf_filename(paper: dict) -> str:
    """
    按规则生成 PDF 文件名：年份_期刊简写_标题前80字符_DOI哈希.pdf
    """
    year = str(paper.get("year") or "0000")
    journal = (paper.get("journal") or "unknown")[:20]
    journal_short = sanitize_filename(journal.lower().replace(" ", "_"))

    title = (paper.get("title") or "untitled")[:80]
    title_clean = sanitize_filename(title.lower().replace(" ", "_"))

    doi = paper.get("doi") or ""
    if doi:
        doi_hash = hashlib.md5(doi.encode("utf-8")).hexdigest()[:8]
    else:
        doi_hash = "nodoi"

    filename = f"{year}_{journal_short}_{title_clean}_{doi_hash}.pdf"
    return sanitize_filename(filename)


def validate_pdf_file(file_path: Path) -> bool:
    """检查文件是否为有效 PDF（%PDF 文件头）。"""
    if not file_path.exists():
        return False
    try:
        with open(file_path, "rb") as f:
            header = f.read(4)
        return header == PDF_MAGIC
    except Exception as e:
        logger.warning(f"验证 PDF 文件头失败: {file_path}, 原因={e}")
        return False


def compute_sha256(file_path: Path) -> str:
    """计算文件 SHA256。"""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        logger.error(f"计算 SHA256 失败: {file_path}, 原因={e}")
        return ""


def download_pdf(
    url: str,
    save_dir: Path,
    paper: dict,
    timeout: int = 30,
    max_retries: int = 3,
) -> dict:
    """
    下载 PDF 并返回结果字典。

    Returns:
        {pdf_path, file_size, content_type, checksum_sha256, error_message}
    """
    # URL 校验
    if not validate_url(url):
        return {
            "pdf_path": None,
            "file_size": 0,
            "content_type": None,
            "checksum_sha256": None,
            "error_message": f"非法的 URL scheme，仅允许 http/https: {url[:100]}",
        }

    # 创建目录
    save_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名
    filename = build_pdf_filename(paper)
    file_path = save_dir / filename

    # 如果文件已存在且有效，跳过
    if file_path.exists() and validate_pdf_file(file_path):
        file_size = file_path.stat().st_size
        checksum = compute_sha256(file_path)
        logger.info(f"PDF 已存在，跳过下载: {file_path}")
        return {
            "pdf_path": str(file_path),
            "file_size": file_size,
            "content_type": "application/pdf",
            "checksum_sha256": checksum,
            "error_message": None,
        }

    headers = {
        "User-Agent": "ResearchAutomationAssistant/0.2 (mailto:research-assist@example.com)",
        "Accept": "application/pdf, */*",
    }

    # HEAD 请求检查 Content-Type
    content_type = None
    try:
        head_resp = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        content_type = head_resp.headers.get("Content-Type", "")
        content_length = head_resp.headers.get("Content-Length")
        if content_length:
            try:
                cl = int(content_length)
                if cl > MAX_FILE_SIZE:
                    return {
                        "pdf_path": None,
                        "file_size": 0,
                        "content_type": content_type,
                        "checksum_sha256": None,
                        "error_message": f"文件过大 ({cl} 字节)，超出限制 {MAX_FILE_SIZE}",
                    }
            except ValueError:
                pass
    except Exception as e:
        logger.warning(f"HEAD 请求失败，继续尝试 GET 下载: {e}")

    # GET 下载（带重试 + 指数退避）
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"下载 PDF (第 {attempt}/{max_retries} 次): {url[:100]}...")
            resp = requests.get(
                url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
                stream=True,
            )
            resp.raise_for_status()

            resp_content_type = resp.headers.get("Content-Type", "")
            if "text/html" in resp_content_type.lower():
                logger.warning(f"收到 HTML 内容而非 PDF: Content-Type={resp_content_type}")
                last_error = "服务器返回 HTML 内容，可能为登录页面或错误页面"
                continue

            # 写入临时文件
            temp_path = file_path.with_suffix(".tmp")
            downloaded_size = 0
            with open(temp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_size += len(chunk)
                        if downloaded_size > MAX_FILE_SIZE:
                            f.close()
                            temp_path.unlink(missing_ok=True)
                            return {
                                "pdf_path": None,
                                "file_size": 0,
                                "content_type": resp_content_type,
                                "checksum_sha256": None,
                                "error_message": f"下载过程中文件超过限制 {MAX_FILE_SIZE}",
                            }
                        f.write(chunk)

            # 验证 PDF 文件头
            if not validate_pdf_file(temp_path):
                temp_path.unlink(missing_ok=True)
                last_error = "文件头不是 %PDF，下载内容可能不是有效的 PDF"
                logger.warning(f"PDF 验证失败: {url[:100]}")
                continue

            # 检查文件大小（< 10KB 标记为无效）
            file_size = temp_path.stat().st_size
            if file_size < 10240:
                temp_path.unlink(missing_ok=True)
                last_error = f"PDF 文件过小 ({file_size} 字节)，可能已损坏"
                logger.warning(f"PDF 文件过小: {url[:100]}, 大小={file_size}")
                continue

            # 重命名为正式文件
            temp_path.replace(file_path)

            # 计算 SHA256
            checksum = compute_sha256(file_path)

            logger.info(f"PDF 下载成功: {file_path}, 大小={file_size}, SHA256={checksum[:16]}...")
            return {
                "pdf_path": str(file_path),
                "file_size": file_size,
                "content_type": resp_content_type,
                "checksum_sha256": checksum,
                "error_message": None,
            }

        except requests.exceptions.HTTPError as e:
            status_code = getattr(e.response, "status_code", 0)
            if status_code == 429:
                retry_after = e.response.headers.get("Retry-After", "5")
                try:
                    wait_seconds = int(retry_after)
                except ValueError:
                    wait_seconds = 5
                logger.warning(f"HTTP 429，等待 {wait_seconds} 秒后重试...")
                time.sleep(wait_seconds)
                last_error = f"HTTP 429 (第 {attempt} 次尝试)"
            else:
                last_error = f"HTTP {status_code}: {e}"
            if attempt < max_retries:
                time.sleep(2 ** (attempt - 1))
        except requests.exceptions.Timeout:
            last_error = f"请求超时 ({timeout}s)"
            if attempt < max_retries:
                time.sleep(2 ** (attempt - 1))
        except requests.exceptions.RequestException as e:
            last_error = f"网络错误: {e}"
            if attempt < max_retries:
                time.sleep(2 ** (attempt - 1))

    # 清理临时文件
    temp_path = file_path.with_suffix(".tmp")
    temp_path.unlink(missing_ok=True)

    logger.error(f"PDF 下载最终失败 ({max_retries} 次重试后): {url[:100]}")
    return {
        "pdf_path": None,
        "file_size": 0,
        "content_type": content_type,
        "checksum_sha256": None,
        "error_message": last_error or "下载失败（未知原因）",
    }
