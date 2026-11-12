# Code By @V_Sbotmaker (on Telegram)
"""
Data models for the img2pdf pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional
import time

class DownloadPolicy(Enum):
    STRICT = auto()
    PERMISSIVE = auto()

@dataclass
class ProgressEvent:
    stage: str
    current: int
    total: int
    percentage: float
    chapter_id: str
    filename: Optional[str] = None
    elapsed_time: float = 0.0

@dataclass
class DownloadReport:
    successful_downloads: List[str] = field(default_factory=list)
    failed_urls: List[str] = field(default_factory=list)
    retry_counts: dict[str, int] = field(default_factory=dict)
    failure_reasons: dict[str, str] = field(default_factory=dict)
    elapsed_time: float = 0.0

__all__ = [
    "DownloadPolicy",
    "ProgressEvent",
    "DownloadReport",
]
