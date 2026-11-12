# Code By @V_Sbotmaker (on Telegram)
"""
Configuration for the img2pdf pipeline.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings
from pydantic import Field
try:
    import psutil
except Exception:
    psutil = None

def _auto_pdf_concurrency() -> int:
    if psutil is None:
        return 2
    try:
        avail_mb = psutil.virtual_memory().available / (1024 * 1024)
        return max(1, min(4, int(avail_mb // 150)))
    except Exception:
        return 2

from pydantic_settings import SettingsConfigDict

class AppConfig(BaseSettings):
    img_dl_workers: int = Field(default=5, json_schema_extra={"env": "IMG_DL_WORKERS"})
    img_thumb_workers: int = Field(default=5, json_schema_extra={"env": "IMG_THUMB_WORKERS"})
    img_width_scan_workers: int = Field(default=5, json_schema_extra={"env": "IMG_WIDTH_SCAN_WORKERS"})
    pdf_compress_workers: int = Field(default=5, json_schema_extra={"env": "PDF_COMPRESS_WORKERS"})
    pdf_chunk_size: int = Field(default=5, json_schema_extra={"env": "PDF_CHUNK_SIZE"})
    img_strict_download: bool = Field(default=False, json_schema_extra={"env": "IMG_STRICT_DOWNLOAD"})
    pdf_concurrent_chapters: int = Field(default_factory=_auto_pdf_concurrency, json_schema_extra={"env": "PDF_CONCURRENT_CHAPTERS"})
    download_retries: int = Field(default=3, json_schema_extra={"env": "DOWNLOAD_RETRIES"})
    timeout_seconds: int = Field(default=30, json_schema_extra={"env": "DOWNLOAD_TIMEOUT"})

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

__all__ = ["AppConfig"]
