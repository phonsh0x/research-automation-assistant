"""
期刊监控清单管理 — 管理重点期刊监控清单的增删改查。

支持：
  - 加载默认期刊清单
  - 从 SQLite 读写期刊配置
  - 添加/删除/激活/停用期刊
  - 获取活跃期刊的 RSS URL 列表
"""

from typing import Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


class JournalWatchlist:
    """
    管理重点期刊监控清单。

    期刊列表持久化在 SQLite 表 journal_watchlist 中。

    Usage:
        wl = JournalWatchlist()
        journals = wl.get_journals()
        urls = wl.get_rss_urls()
        wl.add_journal("New Journal", "1234-5678", "https://example.com/rss")
    """

    # 默认期刊清单（用于首次初始化，与数据库 seed 数据保持一致）
    DEFAULT_JOURNALS = [
        {"name": "Nature", "issn": "0028-0836", "eissn": "1476-4687",
         "rss_url": "https://www.nature.com/nature.rss", "category": "综合科学", "priority": 10},
        {"name": "Science", "issn": "0036-8075", "eissn": "1095-9203",
         "rss_url": "https://www.science.org/rss/express.xml", "category": "综合科学", "priority": 10},
        {"name": "Cell", "issn": "0092-8674", "eissn": "1097-4172",
         "rss_url": "https://www.cell.com/cell/inpress.rss", "category": "生命科学", "priority": 10},
        {"name": "PNAS", "issn": "0027-8424", "eissn": "1091-6490",
         "rss_url": "https://www.pnas.org/action/showFeed?type=etoc&feed=rss", "category": "综合科学", "priority": 9},
        {"name": "Journal of Medicinal Chemistry", "issn": "0022-2623", "eissn": "1520-4804",
         "rss_url": "https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jmcmar", "category": "药物化学", "priority": 9},
        {"name": "ACS Medicinal Chemistry Letters", "issn": "1948-5875", "eissn": "1948-5875",
         "rss_url": "https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=amclct", "category": "药物化学", "priority": 8},
        {"name": "JACS", "issn": "0002-7863", "eissn": "1520-5126",
         "rss_url": "https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=jacsat", "category": "化学", "priority": 8},
        {"name": "Organic Letters", "issn": "1523-7060", "eissn": "1523-7052",
         "rss_url": "https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=orlef7", "category": "有机化学", "priority": 8},
        {"name": "The Journal of Organic Chemistry", "issn": "0022-3263", "eissn": "1520-6904",
         "rss_url": "https://pubs.acs.org/action/showFeed?type=etoc&feed=rss&jc=joceah", "category": "有机化学", "priority": 8},
        {"name": "Acta Pharmaceutica Sinica B", "issn": "2211-3835", "eissn": "2211-3843",
         "rss_url": "https://www.sciencedirect.com/science/journal/22113835", "category": "药物化学", "priority": 8},
        {"name": "European Journal of Medicinal Chemistry", "issn": "0223-5234", "eissn": "1768-3254",
         "rss_url": "https://www.sciencedirect.com/science/journal/02235234", "category": "药物化学", "priority": 8},
        {"name": "Cell Chemical Biology", "issn": "2451-9456", "eissn": "2451-9448",
         "rss_url": "https://www.cell.com/cell-chemical-biology/inpress.rss", "category": "化学生物学", "priority": 8},
        {"name": "Nature Chemical Biology", "issn": "1552-4450", "eissn": "1552-4469",
         "rss_url": "https://www.nature.com/nchembio.rss", "category": "化学生物学", "priority": 8},
        {"name": "Nature Chemistry", "issn": "1755-4330", "eissn": "1755-4349",
         "rss_url": "https://www.nature.com/nchem.rss", "category": "化学", "priority": 8},
        {"name": "Science Translational Medicine", "issn": "1946-6234", "eissn": "1946-6242",
         "rss_url": "https://www.science.org/rss/stm_express.xml", "category": "转化医学", "priority": 7},
        {"name": "Science Advances", "issn": "2375-2548", "eissn": "2375-2548",
         "rss_url": "https://www.science.org/rss/sciadv_express.xml", "category": "综合科学", "priority": 8},
    ]

    def __init__(self, db_manager=None):
        """
        初始化期刊清单管理器。

        Args:
            db_manager: DatabaseManager 实例，默认使用全局单例
        """
        if db_manager is None:
            from src.database.connection import get_db
            self._db = get_db()
        else:
            self._db = db_manager
        self._db.initialize()
        logger.info("JournalWatchlist 已初始化。")

    def get_journals(self, active_only: bool = True) -> list[dict]:
        """
        获取监控期刊列表。

        Args:
            active_only: 是否仅返回活跃期刊

        Returns:
            期刊信息字典列表
        """
        conn = self._db.get_connection()
        try:
            cursor = conn.cursor()
            if active_only:
                cursor.execute(
                    "SELECT journal_id, name, issn, eissn, rss_url, category, priority, is_active "
                    "FROM journal_watchlist WHERE is_active = 1 ORDER BY priority DESC, name"
                )
            else:
                cursor.execute(
                    "SELECT journal_id, name, issn, eissn, rss_url, category, priority, is_active "
                    "FROM journal_watchlist ORDER BY priority DESC, name"
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取期刊列表失败: {e}")
            # 回退到默认内存列表
            return self.DEFAULT_JOURNALS
        finally:
            conn.close()

    def get_rss_urls(self, active_only: bool = True) -> list[str]:
        """
        获取所有期刊的 RSS URL 列表。

        Args:
            active_only: 是否仅返回活跃期刊的 URL

        Returns:
            RSS URL 字符串列表
        """
        journals = self.get_journals(active_only=active_only)
        return [j["rss_url"] for j in journals if j.get("rss_url")]

    def get_journal_names(self, active_only: bool = True) -> list[str]:
        """
        获取所有期刊名称列表。

        Args:
            active_only: 是否仅返回活跃期刊

        Returns:
            期刊名称字符串列表
        """
        journals = self.get_journals(active_only=active_only)
        return [j["name"] for j in journals]

    def add_journal(
        self,
        name: str,
        issn: Optional[str] = None,
        eissn: Optional[str] = None,
        rss_url: Optional[str] = None,
        category: Optional[str] = None,
        priority: int = 5,
    ) -> bool:
        """
        添加监控期刊。

        Args:
            name: 期刊名称
            issn: ISSN 号
            eissn: EISSN 号
            rss_url: RSS feed URL
            category: 期刊分类
            priority: 优先级（1-10，默认 5）

        Returns:
            是否添加成功
        """
        conn = self._db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO journal_watchlist (name, issn, eissn, rss_url, category, priority) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, issn, eissn, rss_url, category, priority),
            )
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"已添加期刊: {name}")
                return True
            else:
                logger.warning(f"期刊已存在，跳过: {name}")
                return False
        except Exception as e:
            logger.error(f"添加期刊失败: {e}")
            return False
        finally:
            conn.close()

    def remove_journal(self, name: str) -> bool:
        """
        删除监控期刊。

        Args:
            name: 期刊名称

        Returns:
            是否删除成功
        """
        conn = self._db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM journal_watchlist WHERE name = ?", (name,))
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"已删除期刊: {name}")
                return True
            else:
                logger.warning(f"未找到期刊: {name}")
                return False
        except Exception as e:
            logger.error(f"删除期刊失败: {e}")
            return False
        finally:
            conn.close()

    def set_active(self, name: str, active: bool = True) -> bool:
        """
        设置期刊的启用/停用状态。

        Args:
            name: 期刊名称
            active: True 启用，False 停用

        Returns:
            是否设置成功
        """
        conn = self._db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE journal_watchlist SET is_active = ? WHERE name = ?",
                (1 if active else 0, name),
            )
            conn.commit()
            if cursor.rowcount > 0:
                status = "启用" if active else "停用"
                logger.info(f"已{status}期刊: {name}")
                return True
            else:
                logger.warning(f"未找到期刊: {name}")
                return False
        except Exception as e:
            logger.error(f"设置期刊状态失败: {e}")
            return False
        finally:
            conn.close()

    def set_priority(self, name: str, priority: int) -> bool:
        """
        设置期刊优先级。

        Args:
            name: 期刊名称
            priority: 优先级（1-10）

        Returns:
            是否设置成功
        """
        conn = self._db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE journal_watchlist SET priority = ? WHERE name = ?",
                (priority, name),
            )
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"已设置期刊优先级: {name} -> {priority}")
                return True
            else:
                logger.warning(f"未找到期刊: {name}")
                return False
        except Exception as e:
            logger.error(f"设置期刊优先级失败: {e}")
            return False
        finally:
            conn.close()

    def get_journals_by_category(self, category: str) -> list[dict]:
        """
        按分类获取期刊列表。

        Args:
            category: 期刊分类名称

        Returns:
            匹配的期刊列表
        """
        conn = self._db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT journal_id, name, issn, eissn, rss_url, category, priority, is_active "
                "FROM journal_watchlist WHERE category = ? AND is_active = 1 ORDER BY priority DESC",
                (category,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"按分类获取期刊失败: {e}")
            return []
        finally:
            conn.close()

    def get_statistics(self) -> dict:
        """
        获取期刊清单统计信息。

        Returns:
            统计字典
        """
        conn = self._db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM journal_watchlist")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM journal_watchlist WHERE is_active = 1")
            active = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM journal_watchlist WHERE rss_url IS NOT NULL AND rss_url != ''")
            with_rss = cursor.fetchone()[0]
            return {
                "total_journals": total,
                "active_journals": active,
                "journals_with_rss": with_rss,
            }
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            return {"total_journals": 0, "active_journals": 0, "journals_with_rss": 0}
        finally:
            conn.close()
