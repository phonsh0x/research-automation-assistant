"""Reusable UI components for the research automation assistant.

Each module exports render functions that accept data via parameters
and call Streamlit widget APIs.  Components do not create service
instances (PaperRepository, PaperSearcher, etc.) — they only render.
"""

from ui.components.layout import (
    render_page_header,
    render_section,
    render_empty_state,
    render_divider,
)
from ui.components.metric_cards import (
    render_metric_cards,
    render_database_stats,
    render_fulltext_stats,
)
from ui.components.paper_table import (
    render_paper_table,
    render_paper_detail,
    render_fulltext_status_badge,
)
from ui.components.filters import (
    render_text_filter,
    render_year_range_filter,
    render_source_filter,
    render_limit_select,
)
from ui.components.messages import (
    render_page_message,
    render_error_box,
    render_success_box,
    render_warning_box,
    render_info_box,
)
from ui.components.actions import (
    render_primary_button,
    render_secondary_button,
    render_reset_button,
)

__all__ = [
    # layout
    "render_page_header",
    "render_section",
    "render_empty_state",
    "render_divider",
    # metric_cards
    "render_metric_cards",
    "render_database_stats",
    "render_fulltext_stats",
    # paper_table
    "render_paper_table",
    "render_paper_detail",
    "render_fulltext_status_badge",
    # filters
    "render_text_filter",
    "render_year_range_filter",
    "render_source_filter",
    "render_limit_select",
    # messages
    "render_page_message",
    "render_error_box",
    "render_success_box",
    "render_warning_box",
    "render_info_box",
    # actions
    "render_primary_button",
    "render_secondary_button",
    "render_reset_button",
]
