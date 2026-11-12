# Code By @V_Sbotmaker (on Telegram)
"""
Resource manager for the img2pdf pipeline.
Handles global resources like thread pools and limits concurrency.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator

from .config import AppConfig

class ResourceManager:
    def __init__(self, config: AppConfig):
        self.config = config
        self._pdf_sem: Optional[asyncio.Semaphore] = None
        self._thumb_executor: Optional[ThreadPoolExecutor] = None
        self._width_scan_executor: Optional[ThreadPoolExecutor] = None
        self._pdf_compress_executor: Optional[ThreadPoolExecutor] = None
        self._dl_executor: Optional[ThreadPoolExecutor] = None

    def get_pdf_semaphore(self) -> asyncio.Semaphore:
        if self._pdf_sem is None:
            self._pdf_sem = asyncio.Semaphore(self.config.pdf_concurrent_chapters)
        return self._pdf_sem

    def get_thumb_executor(self) -> ThreadPoolExecutor:
        if self._thumb_executor is None:
            self._thumb_executor = ThreadPoolExecutor(max_workers=self.config.img_thumb_workers)
        return self._thumb_executor

    def get_width_scan_executor(self) -> ThreadPoolExecutor:
        if self._width_scan_executor is None:
            self._width_scan_executor = ThreadPoolExecutor(max_workers=self.config.img_width_scan_workers)
        return self._width_scan_executor

    def get_pdf_compress_executor(self) -> ThreadPoolExecutor:
        if self._pdf_compress_executor is None:
            self._pdf_compress_executor = ThreadPoolExecutor(max_workers=self.config.pdf_compress_workers)
        return self._pdf_compress_executor

    def get_dl_executor(self) -> ThreadPoolExecutor:
        if self._dl_executor is None:
            self._dl_executor = ThreadPoolExecutor(max_workers=self.config.img_dl_workers)
        return self._dl_executor

    def close(self):
        if self._thumb_executor:
            self._thumb_executor.shutdown(wait=False)
        if self._width_scan_executor:
            self._width_scan_executor.shutdown(wait=False)
        if self._pdf_compress_executor:
            self._pdf_compress_executor.shutdown(wait=False)
        if self._dl_executor:
            self._dl_executor.shutdown(wait=False)

@asynccontextmanager
async def managed_resources(config: AppConfig) -> AsyncGenerator[ResourceManager, None]:
    """Provides a managed ResourceManager instance."""
    manager = ResourceManager(config)
    try:
        yield manager
    finally:
        manager.close()

__all__ = ["ResourceManager", "managed_resources"]
