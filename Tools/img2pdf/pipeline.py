# Code By @V_Sbotmaker (on Telegram)
"""
Pipeline orchestrator for img2pdf.
Coordinates downloader and converter with backpressure and throttled progress reporting.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

from loguru import logger

from .models import ProgressEvent, DownloadReport, DownloadPolicy
from .exceptions import PipelineError
from .config import AppConfig
from .resource_manager import ResourceManager
from .downloader import ResilientDownloader
from .converter import PDFConverterFactory
from .image_processor import compress_image

class ImageToPDFPipeline:
    def __init__(self, config: AppConfig, resource_manager: ResourceManager):
        self.config = config
        self.rm = resource_manager

        self.downloader = ResilientDownloader(
            config=self.config,
            dl_executor=self.rm.get_dl_executor(),
            dl_sem=asyncio.Semaphore(self.config.img_dl_workers)
        )
        self.converter = PDFConverterFactory.get_converter(
            self.config,
            self.rm.get_pdf_compress_executor()
        )

    def _throttle_progress(self, callback: Callable[[ProgressEvent], None]) -> Callable[[ProgressEvent], None]:
        last_time = 0.0
        last_pct = 0.0

        def throttled_callback(event: ProgressEvent):
            nonlocal last_time, last_pct
            now = time.time()
            if event.percentage >= 100.0 or (now - last_time >= 3.0) or (event.percentage - last_pct >= 5.0):
                last_time = now
                last_pct = event.percentage
                try:
                    callback(event)
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")

        return throttled_callback

    async def download_images(
        self,
        urls: List[str],
        download_dir: Path,
        headers: Optional[Dict[str, str]] = None,
        use_cs: bool = False,
        chapter_id: str = "unknown",
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None
    ) -> List[Path]:
        """Download images with optional progress tracking."""
        throttled_cb = self._throttle_progress(progress_callback) if progress_callback else None

        if throttled_cb:
            throttled_cb(ProgressEvent("download_start", 0, len(urls), 0.0, chapter_id))

        report = await self.downloader.download_batch(urls, download_dir, headers, use_cs, chapter_id)

        if throttled_cb:
            throttled_cb(ProgressEvent("download_complete", len(report.successful_downloads), len(urls), 100.0, chapter_id, elapsed_time=report.elapsed_time))

        return [Path(p) for p in report.successful_downloads]

    async def convert_to_pdf(
        self,
        image_files: List[Path],
        pdf_output_path: Path,
        compressed_dir: Path,
        password: Optional[str] = None,
        compression_quality: int = 80,
        hyperLink: Optional[str] = None,
        banner1: Optional[Path] = None,
        banner2: Optional[Path] = None,
    ) -> None:
        """Convert images to PDF using the global semaphore for backpressure."""
        async with self.rm.get_pdf_semaphore():
            await asyncio.get_running_loop().run_in_executor(
                None,  # Use default executor for orchestrating the ThreadPoolExecutor map
                lambda: self.converter.convert(
                    image_files, pdf_output_path, compressed_dir,
                    password, compression_quality, hyperLink, banner1, banner2
                )
            )

    async def create_thumbnail(
        self,
        image_url: str,
        download_dir: Path,
        base_url: Optional[str] = None,
        quality: int = 80,
        file_name: str = "thumb.jpg",
        sb: bool = False
    ) -> Optional[Path]:
        download_dir.mkdir(parents=True, exist_ok=True)
        img_path = download_dir / file_name

        headers = None
        if base_url:
            from .__init__ import get_headers # Will be imported below or inject
            headers = get_headers(base_url)
        else:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        try:
            if sb:
                # We mock this up, original used sb.download_file
                res = await self.downloader.download_image(image_url, img_path, headers, True)
                if not res:
                    return None
            else:
                res = await asyncio.get_running_loop().run_in_executor(
                    self.rm.get_thumb_executor(),
                    self.downloader._sync_download,
                    image_url, img_path, img_path.with_suffix('.tmp'), headers, True
                )
                if not res:
                    return None

            tmp_thumb = img_path.with_suffix('.compressed.tmp')

            res_path, w, h = await asyncio.get_running_loop().run_in_executor(
                self.rm.get_thumb_executor(),
                compress_image,
                img_path, tmp_thumb, quality, None
            )

            if res_path == tmp_thumb and tmp_thumb.exists():
                tmp_thumb.replace(img_path)
            elif tmp_thumb.exists():
                tmp_thumb.unlink(missing_ok=True)

            return img_path
        except asyncio.CancelledError:
            logger.warning("Thumbnail download cancelled")
            return None
        except Exception as e:
            logger.warning(f"Thumbnail error: {e}")
            return None

__all__ = ["ImageToPDFPipeline"]
