"""
文献数据仓库 — 提供论文元数据和全文的 CRUD 操作。

封装 SQLite 操作，为上层模块提供简洁的数据访问接口。
所有数据库操作都通过 DatabaseManager 获取连接。
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional

from src.database.connection import get_db
from src.paper_search.models import PaperMetadata
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PaperRepository:
    """
    文献数据仓库。

    提供论文元数据的增、查、改操作，以及全文/作者/关键词的关联管理。

    Usage:
        repo = PaperRepository()
        repo.upsert_paper(metadata)  # 插入或更新论文元数据
        papers = repo.search_by_keyword("deep learning", limit=20)
    """

    def __init__(self):
        """初始化数据仓库，确保数据库已初始化。"""
        self.db = get_db()
        self.db.initialize()
        logger.info("PaperRepository 已初始化。")

    # ==========================================================================
    # 论文元数据 CRUD
    # ==========================================================================

    def upsert_paper(self, paper: PaperMetadata) -> tuple:
        """
        插入或更新论文元数据（按 DOI 去重 / title+year 弱去重）。

        去重策略：
          - 有 DOI → 按 DOI 去重
          - 无 DOI 但有 title+year → 按 (title, year) 弱去重
          - 既无 DOI 也无 title → 直接插入（不做去重）

        Args:
            paper: 论文元数据对象

        Returns:
            (paper_id, action) 元组
            - action: 'inserted'（新增）、'updated'（更新）、'duplicate'（完全重复跳过）
        """
        title_short = (paper.title or "无标题")[:60]
        logger.info(f"入库论文: {title_short}...")

        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()

            # 第一阶段：按 DOI 去重
            existing_id = None
            if paper.doi:
                cursor.execute("SELECT paper_id FROM papers WHERE doi = ?", (paper.doi,))
                row = cursor.fetchone()
                if row:
                    existing_id = row[0]

            # 第二阶段：DOI 缺失时按 title + year 弱去重
            if existing_id is None and paper.title:
                import re
                title_norm = re.sub(r"[^\w\s]", "", paper.title.lower())
                title_norm = re.sub(r"\s+", " ", title_norm).strip()
                cursor.execute(
                    "SELECT paper_id FROM papers WHERE LOWER(REPLACE(REPLACE(REPLACE(title, '.', ''), ',', ''), '  ', ' ')) = ? AND year = ? AND doi IS NULL",
                    (title_norm, paper.year),
                )
                row = cursor.fetchone()
                if row:
                    existing_id = row[0]
                    logger.debug(f"按 title+year 弱去重命中: paper_id={existing_id}, title='{title_short}'")

            if existing_id:
                # 更新已有记录（仅更新非空字段）
                updated = self._update_paper(cursor, existing_id, paper)
                conn.commit()
                if updated:
                    logger.debug(f"已更新论文: paper_id={existing_id}, title='{title_short}'")
                    return (existing_id, "updated")
                else:
                    logger.debug(f"论文重复，无字段更新: paper_id={existing_id}, title='{title_short}'")
                    return (existing_id, "duplicate")
            else:
                # 插入新记录
                paper_dict = paper.to_dict()
                # 过滤掉不存在于 papers 表中的字段
                valid_columns = self._get_papers_columns(conn)
                filtered = {k: v for k, v in paper_dict.items() if k in valid_columns}
                columns = ", ".join(filtered.keys())
                placeholders = ", ".join(["?"] * len(filtered))
                values = list(filtered.values())

                cursor.execute(
                    f"INSERT INTO papers ({columns}) VALUES ({placeholders})",
                    values,
                )
                conn.commit()
                new_id = cursor.lastrowid
                logger.info(f"已插入论文: paper_id={new_id}, title='{title_short}'")

                # 插入作者和关键词关联
                self._insert_authors(conn, new_id, paper.authors)
                self._insert_keywords(conn, new_id, paper.keywords)
                conn.commit()

                return (new_id, "inserted")

        except sqlite3.IntegrityError as e:
            logger.warning(f"完整性约束失败（可能 DOI/title 重复）: title='{title_short}', doi={paper.doi}, 原因={e}")
            conn.rollback()
            # 尝试再次按 DOI 查找
            if paper.doi:
                try:
                    cursor.execute("SELECT paper_id FROM papers WHERE doi = ?", (paper.doi,))
                    row = cursor.fetchone()
                    if row:
                        return (row[0], "duplicate")
                except Exception:
                    pass
            raise
        except Exception as e:
            logger.error(f"入库论文失败: title='{title_short}', doi={paper.doi}, 原因={e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def _update_paper(self, cursor, paper_id: int, paper: PaperMetadata) -> bool:
        """更新已有论文的非空字段。返回是否有字段被更新。"""
        paper_dict = paper.to_dict()
        updated = False
        for field, value in paper_dict.items():
            if value is not None and value != "" and value != 0:
                cursor.execute(
                    f"UPDATE papers SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE paper_id = ?",
                    (value, paper_id),
                )
                updated = True
        return updated

    def _insert_authors(self, conn, paper_id: int, authors: list[str]) -> None:
        """插入作者并创建论文-作者关联。"""
        cursor = conn.cursor()
        for order, author_name in enumerate(authors, start=1):
            # 插入或忽略作者
            cursor.execute(
                "INSERT OR IGNORE INTO authors (name) VALUES (?)",
                (author_name,),
            )
            # 获取 author_id
            cursor.execute("SELECT author_id FROM authors WHERE name = ?", (author_name,))
            row = cursor.fetchone()
            if row:
                author_id = row[0]
                # 创建关联
                cursor.execute(
                    "INSERT OR IGNORE INTO paper_authors (paper_id, author_id, author_order) VALUES (?, ?, ?)",
                    (paper_id, author_id, order),
                )

    def _insert_keywords(self, conn, paper_id: int, keywords: list[str]) -> None:
        """插入关键词并创建论文-关键词关联。"""
        cursor = conn.cursor()
        for keyword in keywords:
            if not keyword or len(keyword) > 200:
                continue
            cursor.execute(
                "INSERT OR IGNORE INTO keywords (keyword) VALUES (?)",
                (keyword,),
            )
            cursor.execute("SELECT keyword_id FROM keywords WHERE keyword = ?", (keyword,))
            row = cursor.fetchone()
            if row:
                keyword_id = row[0]
                cursor.execute(
                    "INSERT OR IGNORE INTO paper_keywords (paper_id, keyword_id) VALUES (?, ?)",
                    (paper_id, keyword_id),
                )

    @staticmethod
    def _get_papers_columns(conn) -> set:
        """获取 papers 表的所有列名。"""
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(papers)")
        return {row[1] for row in cursor.fetchall()}

    # ==========================================================================
    # 作者管理
    # ==========================================================================

    def insert_author(self, name: str, orcid: Optional[str] = None, affiliation: Optional[str] = None) -> int:
        """
        插入作者记录。

        Args:
            name: 作者姓名
            orcid: ORCID 标识符
            affiliation: 所属机构

        Returns:
            author_id
        """
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO authors (name, orcid, affiliation) VALUES (?, ?, ?)",
                (name, orcid, affiliation),
            )
            conn.commit()
            cursor.execute("SELECT author_id FROM authors WHERE name = ?", (name,))
            row = cursor.fetchone()
            return row[0] if row else -1
        except Exception as e:
            logger.error(f"插入作者失败: {e}")
            return -1
        finally:
            conn.close()

    def link_paper_author(self, paper_id: int, author_id: int, author_order: int = 1) -> bool:
        """
        关联论文和作者。

        Args:
            paper_id: 论文 ID
            author_id: 作者 ID
            author_order: 作者排序（1 为第一作者）

        Returns:
            是否关联成功
        """
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO paper_authors (paper_id, author_id, author_order) VALUES (?, ?, ?)",
                (paper_id, author_id, author_order),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"关联论文-作者失败: {e}")
            return False
        finally:
            conn.close()

    # ==========================================================================
    # 检索运行记录
    # ==========================================================================

    def record_search_run(
        self,
        run_type: str,
        sources: list[str],
        keywords: str,
        total_found: int = 0,
        new_added: int = 0,
        updated_count: int = 0,
        duplicate_count: int = 0,
        failed_count: int = 0,
        errors: Optional[list[str]] = None,
    ) -> int:
        """
        记录检索运行。

        Args:
            run_type: 检索类型（daily_watch / backfill）
            sources: 使用的检索源列表
            keywords: 检索关键词
            total_found: 总命中数
            new_added: 新增入库数
            updated_count: 更新数
            duplicate_count: 重复数
            failed_count: 失败数
            errors: 错误信息列表

        Returns:
            run_id
        """
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            sources_str = ",".join(sources)
            errors_str = json.dumps(errors, ensure_ascii=False) if errors else None

            cursor.execute(
                "INSERT INTO search_runs "
                "(run_type, sources_used, query_keywords, total_found, new_added, "
                "updated_count, duplicate_count, failed_count, errors, finished_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (run_type, sources_str, keywords, total_found, new_added,
                 updated_count, duplicate_count, failed_count, errors_str),
            )
            conn.commit()
            run_id = cursor.lastrowid
            logger.info(
                f"已记录检索运行: run_id={run_id}, type={run_type}, "
                f"found={total_found}, new={new_added}, updated={updated_count}, "
                f"dup={duplicate_count}, failed={failed_count}"
            )
            return run_id
        except Exception as e:
            logger.error(f"记录检索运行失败: {e}")
            return -1
        finally:
            conn.close()

    # ==========================================================================
    # 查询操作
    # ==========================================================================

    def get_paper_by_id(self, paper_id: int) -> Optional[dict]:
        """
        按 ID 查询论文。

        Args:
            paper_id: 论文 ID

        Returns:
            论文数据字典，未找到返回 None
        """
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM papers WHERE paper_id = ?", (paper_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"查询论文失败: {e}")
            return None
        finally:
            conn.close()

    def get_paper_by_doi(self, doi: str) -> Optional[dict]:
        """
        按 DOI 查询论文。

        Args:
            doi: 论文 DOI

        Returns:
            论文数据字典，未找到返回 None
        """
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM papers WHERE doi = ?", (doi,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"DOI 查询失败: {e}")
            return None
        finally:
            conn.close()

    def search_by_keyword(
        self,
        keyword: str,
        limit: int = 50,
        offset: int = 0,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
    ) -> list[dict]:
        """
        按关键词检索本地论文库（标题和摘要 LIKE 匹配）。

        Args:
            keyword: 检索关键词
            limit: 返回数量上限
            offset: 偏移量
            year_from: 起始年份
            year_to: 结束年份

        Returns:
            匹配的论文列表
        """
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()

            query = """
                SELECT * FROM papers
                WHERE (title LIKE ? OR abstract LIKE ?)
            """
            params: list = [f"%{keyword}%", f"%{keyword}%"]

            if year_from:
                query += " AND year >= ?"
                params.append(year_from)
            if year_to:
                query += " AND year <= ?"
                params.append(year_to)

            query += " ORDER BY year DESC, citation_count DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"本地检索失败: {e}")
            return []
        finally:
            conn.close()

    def search_papers(
        self,
        keyword: str = "",
        limit: int = 20,
        offset: int = 0,
        source: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
    ) -> list[dict]:
        """
        多条件检索本地论文库，支持关键词、来源、年份范围过滤，返回含作者聚合的完整记录。

        - keyword 为空时返回最近入库论文（按 created_at DESC）
        - keyword 不为空时模糊匹配 title、abstract、journal（LIKE %keyword%）
        - 支持 source 过滤（source_api = ?）
        - 支持年份范围过滤
        - 使用 JOIN 聚合作者列表（GROUP_CONCAT）
        - 所有参数使用参数化查询（占位符 ?）

        Args:
            keyword: 检索关键词，为空则返回最近入库论文
            limit: 返回数量上限
            offset: 偏移量
            source: 数据源过滤（如 "openalex"）
            year_from: 起始年份（含）
            year_to: 结束年份（含）

        Returns:
            匹配的论文字典列表，每项包含:
            id, title, doi, year, journal, authors, abstract,
            source, source_url, pdf_path, md_path, oa_status,
            citation_count, created_at
        """
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()

            query = """
                SELECT
                    p.paper_id AS id, p.title, p.doi, p.year, p.journal,
                    GROUP_CONCAT(DISTINCT a.name ORDER BY pa.author_order) AS authors,
                    p.abstract, p.source_api AS source, p.source_id AS source_url,
                    p.pdf_path, p.md_path, p.oa_status, p.citation_count, p.created_at
                FROM papers p
                LEFT JOIN paper_authors pa ON p.paper_id = pa.paper_id
                LEFT JOIN authors a ON pa.author_id = a.author_id
                WHERE 1=1
            """
            params: list = []

            if keyword:
                query += " AND (p.title LIKE ? OR p.abstract LIKE ? OR p.journal LIKE ?)"
                like_keyword = f"%{keyword}%"
                params.extend([like_keyword, like_keyword, like_keyword])

            if source:
                query += " AND p.source_api = ?"
                params.append(source)

            if year_from is not None:
                query += " AND p.year >= ?"
                params.append(year_from)

            if year_to is not None:
                query += " AND p.year <= ?"
                params.append(year_to)

            query += " GROUP BY p.paper_id"

            if keyword:
                query += " ORDER BY p.year DESC, p.citation_count DESC"
            else:
                query += " ORDER BY p.created_at DESC"

            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"search_papers 查询失败: {e}")
            return []
        finally:
            conn.close()

    # ==========================================================================
    # 全文 & 统计 & 导出
    # ==========================================================================

    def save_full_text(self, paper_id: int, content: str, stats: Optional[dict] = None) -> bool:
        """
        保存论文全文 Markdown 内容。

        Args:
            paper_id: 论文 ID
            content: Markdown 全文内容
            stats: 统计信息（章节数、图表数等）

        Returns:
            是否保存成功
        """
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            section_count = stats.get("section_count", 0) if stats else 0
            figure_count = stats.get("figure_count", 0) if stats else 0
            table_count = stats.get("table_count", 0) if stats else 0
            equation_count = stats.get("equation_count", 0) if stats else 0
            ref_count = stats.get("ref_count", 0) if stats else 0
            char_count = len(content)

            cursor.execute(
                "INSERT OR REPLACE INTO full_texts (paper_id, content, section_count, figure_count, "
                "table_count, equation_count, ref_count, char_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (paper_id, content, section_count, figure_count, table_count, equation_count, ref_count, char_count),
            )
            conn.commit()
            logger.info(f"已保存全文: paper_id={paper_id}, 字符数={char_count}")
            return True
        except Exception as e:
            logger.error(f"保存全文失败: {e}")
            return False
        finally:
            conn.close()

    def get_statistics(self) -> dict:
        """
        获取数据库统计信息。

        Returns:
            统计字典，包含论文总数、OA 分布、年份分布等
        """
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()

            # 总论文数
            cursor.execute("SELECT COUNT(*) FROM papers")
            total_papers = cursor.fetchone()[0]

            # 总作者数
            cursor.execute("SELECT COUNT(*) FROM authors")
            total_authors = cursor.fetchone()[0]

            # OA 分布
            cursor.execute("SELECT oa_status, COUNT(*) FROM papers GROUP BY oa_status")
            oa_distribution = {row[0]: row[1] for row in cursor.fetchall()}

            # 年份分布
            cursor.execute("SELECT year, COUNT(*) FROM papers WHERE year IS NOT NULL GROUP BY year ORDER BY year")
            year_distribution = {str(row[0]): row[1] for row in cursor.fetchall()}

            # 全文数
            cursor.execute("SELECT COUNT(*) FROM full_texts")
            total_full_texts = cursor.fetchone()[0]

            return {
                "total_papers": total_papers,
                "total_authors": total_authors,
                "oa_distribution": oa_distribution,
                "year_distribution": year_distribution,
                "total_full_texts": total_full_texts,
            }
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            return {
                "total_papers": 0,
                "total_authors": 0,
                "oa_distribution": {},
                "year_distribution": {},
                "total_full_texts": 0,
            }
        finally:
            conn.close()

    def export_bibtex(self, paper_ids: Optional[list[int]] = None, output_path: Optional[Path] = None) -> str:
        """
        导出论文为 BibTeX 格式。

        Args:
            paper_ids: 要导出的论文 ID 列表，None 表示全部
            output_path: 输出文件路径，None 表示仅返回字符串

        Returns:
            BibTeX 格式字符串
        """
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()

            if paper_ids:
                placeholders = ",".join(["?"] * len(paper_ids))
                cursor.execute(f"SELECT * FROM papers WHERE paper_id IN ({placeholders})", paper_ids)
            else:
                cursor.execute("SELECT * FROM papers ORDER BY year DESC, title")

            rows = cursor.fetchall()
            bibtex_entries = []

            for row in rows:
                row_dict = dict(row)
                # 生成 BibTeX key
                doi = row_dict.get("doi") or ""
                key = doi.replace("/", "_").replace(".", "_") if doi else f"paper_{row_dict['paper_id']}"

                entry_type = "article"
                title = row_dict.get("title", "")
                year = row_dict.get("year", "")
                journal = row_dict.get("journal", "")
                volume = row_dict.get("volume", "")
                pages = row_dict.get("pages", "")

                entry = f"""@{entry_type}{{{key},
  title = {{{title}}},
  year = {{{year}}},
  journal = {{{journal}}},
  volume = {{{volume}}},
  pages = {{{pages}}},
  doi = {{{doi}}}
}}"""
                bibtex_entries.append(entry)

            bibtex_str = "\n\n".join(bibtex_entries)

            if output_path:
                output_path.write_text(bibtex_str, encoding="utf-8")
                logger.info(f"BibTeX 已导出到: {output_path}")

            return bibtex_str
        except Exception as e:
            logger.error(f"导出 BibTeX 失败: {e}")
            return ""
        finally:
            conn.close()
