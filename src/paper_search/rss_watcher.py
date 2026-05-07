"""
RSS 监控器 — 解析期刊 RSS Feed 并提取最新论文元数据。

支持期刊：Nature、Science、Cell、PNAS 等主流期刊的 RSS feed。
"""

import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from src.paper_search.models import PaperMetadata
from src.utils.logger import get_logger

logger = get_logger(__name__)

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
FEEDPARSER_AVAILABLE = False

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    logger.warning("feedparser 未安装，RSS 功能将使用简易 XML 解析。RSS 解析精度有限。")


# ============================================================================
# RSS Feed 解析
# ============================================================================

def fetch_rss_papers(rss_url: str, days: int = 7, journal_name: str = "") -> list[PaperMetadata]:
    """
    从 RSS Feed 获取最近 N 天的新论文。

    Args:
        rss_url: RSS feed URL
        days: 最近天数
        journal_name: 期刊名称（可选，用于标注）

    Returns:
        标准化 PaperMetadata 列表
    """
    logger.info(f"RSS 抓取: url='{rss_url}', days={days}")

    if FEEDPARSER_AVAILABLE:
        return _fetch_with_feedparser(rss_url, days, journal_name)
    else:
        return _fetch_with_regex(rss_url, days, journal_name)


def _fetch_with_feedparser(rss_url: str, days: int, journal_name: str) -> list[PaperMetadata]:
    """使用 feedparser 库解析 RSS feed。"""
    papers = []

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            feed = feedparser.parse(rss_url)
            if feed.bozo and not feed.entries:
                logger.warning(f"RSS 解析异常 (尝试 {attempt}): {feed.bozo_exception}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return []

            since_date = datetime.now(timezone.utc) - timedelta(days=days)

            for entry in feed.entries:
                paper = _parse_feedparser_entry(entry, since_date, journal_name)
                if paper:
                    papers.append(paper)

            logger.info(f"RSS 抓取完成: 获取 {len(papers)} 篇论文")
            return papers

        except Exception as e:
            logger.warning(f"RSS feedparser 异常 (尝试 {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"RSS 抓取失败: {e}")
                return []

    return papers


def _parse_feedparser_entry(entry, since_date: datetime, journal_name: str) -> Optional[PaperMetadata]:
    """将 feedparser entry 转换为 PaperMetadata。"""
    try:
        # 检查发表日期
        pub_date = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

        if pub_date and pub_date < since_date:
            return None

        # 标题
        title = entry.get("title", "未知标题")
        # 清理 HTML 标记
        title = re.sub(r"<[^>]+>", "", title).strip()

        # 作者
        authors = []
        if hasattr(entry, "authors"):
            for author in entry.authors:
                name = author.get("name", "")
                if name:
                    authors.append(name)

        # 摘要
        summary = entry.get("summary", "")
        summary = re.sub(r"<[^>]+>", "", summary).strip()[:2000] if summary else None

        # DOI
        doi = None
        link = entry.get("link", "")
        # 尝试从 link 或 id 提取 DOI
        id_val = entry.get("id", "")
        doi_match = re.search(r"(10\.\d{4,}/[^\s\"'<>]+)", id_val + " " + link)
        if doi_match:
            doi = doi_match.group(1).rstrip(".")

        # 年份
        year = pub_date.year if pub_date else None

        # 期刊
        journal = journal_name or entry.get("source", {}).get("title", "")

        return PaperMetadata(
            title=title,
            authors=authors,
            doi=doi,
            year=year,
            journal=journal,
            abstract=summary,
            source_api="rss",
            source_id=doi,
            oa_status="unknown",
        )
    except Exception as e:
        logger.error(f"解析 RSS entry 失败: {e}")
        return None


def _fetch_with_regex(rss_url: str, days: int, journal_name: str) -> list[PaperMetadata]:
    """使用正则表达式简易解析 RSS feed（feedparser 不可用时的后备方案）。"""
    papers = []

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                rss_url,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "ResearchAutomationAssistant/0.1.0"},
            )
            response.raise_for_status()
            xml_text = response.text

            # 简易正则解析 <item> 元素
            item_pattern = re.compile(r"<item>(.*?)</item>", re.DOTALL)
            items = item_pattern.findall(xml_text)

            if not items:
                # 尝试 Atom feed 格式 <entry>
                entry_pattern = re.compile(r"<entry>(.*?)</entry>", re.DOTALL)
                items = entry_pattern.findall(xml_text)

            since_date = datetime.now(timezone.utc) - timedelta(days=days)

            for item_xml in items:
                paper = _parse_regex_entry(item_xml, since_date, journal_name)
                if paper:
                    papers.append(paper)

            logger.info(f"RSS 正则解析完成: 获取 {len(papers)} 篇论文")
            return papers

        except requests.exceptions.RequestException as e:
            logger.warning(f"RSS 请求异常 (尝试 {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"RSS 抓取失败: {e}")
                return []

    return papers


def _parse_regex_entry(item_xml: str, since_date: datetime, journal_name: str) -> Optional[PaperMetadata]:
    """使用正则解析单个 RSS item XML 片段。"""
    try:
        # 标题
        title_match = re.search(r"<title[^>]*>(.*?)</title>", item_xml, re.DOTALL)
        if title_match:
            title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()
        else:
            return None

        # DOI
        doi = None
        doi_match = re.search(r"(10\.\d{4,}/[^\s\"'<>]+)", item_xml)
        if doi_match:
            doi = doi_match.group(1).rstrip(".")

        # 摘要
        desc_match = re.search(r"<description[^>]*>(.*?)</description>", item_xml, re.DOTALL)
        abstract = None
        if desc_match:
            abstract = re.sub(r"<[^>]+>", "", desc_match.group(1)).strip()[:2000]

        # 日期
        year = None
        date_match = re.search(r"<dc:date>(.*?)</dc:date>", item_xml)
        if not date_match:
            date_match = re.search(r"<pubDate>(.*?)</pubDate>", item_xml)
        if date_match:
            try:
                date_str = date_match.group(1).strip()
                for fmt in ["%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%SZ"]:
                    try:
                        pub_date = datetime.strptime(date_str, fmt)
                        if pub_date.tzinfo is None:
                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                        if pub_date < since_date:
                            return None
                        year = pub_date.year
                        break
                    except ValueError:
                        continue
            except Exception:
                pass

        return PaperMetadata(
            title=title,
            authors=[],
            doi=doi,
            year=year,
            journal=journal_name,
            abstract=abstract,
            source_api="rss",
            source_id=doi,
            oa_status="unknown",
        )
    except Exception as e:
        logger.error(f"正则解析 RSS entry 失败: {e}")
        return None


# ============================================================================
# RSS 监控调度
# ============================================================================

def run_rss_watch(
    rss_urls: list[str],
    journal_names: list[str] | None = None,
    days: int = 7,
) -> list[PaperMetadata]:
    """
    批量监控多个 RSS feed 源。

    Args:
        rss_urls: RSS feed URL 列表
        journal_names: 对应的期刊名称列表（可选）
        days: 最近天数

    Returns:
        所有 RSS feed 中获取的 PaperMetadata 列表
    """
    if journal_names is None:
        journal_names = [f"Journal_{i + 1}" for i in range(len(rss_urls))]

    all_papers = []
    for i, url in enumerate(rss_urls):
        try:
            jname = journal_names[i] if i < len(journal_names) else f"Journal_{i + 1}"
            papers = fetch_rss_papers(url, days=days, journal_name=jname)
            all_papers.extend(papers)
            logger.info(f"RSS {jname}: 获取 {len(papers)} 篇")
        except Exception as e:
            logger.error(f"RSS feed 抓取异常 ({journal_names[i] if i < len(journal_names) else url}): {e}")

        # 礼貌延迟
        time.sleep(0.5)

    logger.info(f"RSS 批量监控完成: 共 {len(all_papers)} 篇论文")
    return all_papers
