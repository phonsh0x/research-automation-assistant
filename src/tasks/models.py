"""Data models for background jobs."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"
    INTERRUPTED = "interrupted"


@dataclass
class BackgroundJob:
    job_id: int | None = None
    job_type: str = ""
    status: str = JobStatus.PENDING.value
    title: str = ""
    payload_json: str = ""
    result_json: str = ""
    progress_current: int = 0
    progress_total: int = 0
    message: str = ""
    error_message: str = ""
    created_at: str = ""
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status,
            "title": self.title,
            "progress_current": self.progress_current,
            "progress_total": self.progress_total,
            "message": self.message,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }
