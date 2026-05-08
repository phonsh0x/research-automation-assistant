"""UI service layer for the research automation assistant.

Service functions encapsulate backend calls (PaperRepository, PaperSearcher,
FullTextAcquisitionService, etc.) so that page code only handles display.
"""

from ui.services.repository_service import (
    get_repository,
    get_db_stats,
    get_download_stats,
    search_library,
    get_pending_papers,
    get_paper_detail,
    clear_cached_stats,
)
from ui.services.search_ui_service import (
    execute_keyword_search,
    restore_last_search,
    execute_journal_watch,
)
from ui.services.fulltext_ui_service import (
    resolve_fulltext,
    download_fulltext,
    batch_download_pending,
    mark_manual_review,
    handle_manual_upload,
    friendly_source,
)
from ui.services.export_service import (
    export_bibtex,
    export_csv,
    export_json,
)

__all__ = [
    # repository
    "get_repository",
    "get_db_stats",
    "get_download_stats",
    "search_library",
    "get_pending_papers",
    "get_paper_detail",
    "clear_cached_stats",
    # search
    "execute_keyword_search",
    "restore_last_search",
    "execute_journal_watch",
    # fulltext
    "resolve_fulltext",
    "download_fulltext",
    "batch_download_pending",
    "mark_manual_review",
    "handle_manual_upload",
    "friendly_source",
    # export
    "export_bibtex",
    "export_csv",
    "export_json",
]
