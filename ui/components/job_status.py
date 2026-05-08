"""Background job status display component."""

import streamlit as st

from src.tasks.repository import JobRepository


def render_job_status(limit: int = 10):
    """Show recent background jobs in an expander."""
    repo = JobRepository()
    jobs = repo.list_jobs(limit=limit)

    if not jobs:
        return

    with st.expander(f"后台任务 ({len(jobs)})", expanded=False):
        for j in jobs:
            status = j.get("status", "?")
            emoji = {"success": "✅", "failed": "❌", "running": "🔄", "pending": "⏳",
                     "cancelled": "🚫", "partial": "⚠️"}.get(status, "❓")
            created = (j.get("created_at") or "")[:19]
            st.caption(
                f"{emoji} [{j.get('job_type', '?')}] {j.get('title', '')} "
                f"— {status} — {created}"
            )
