# Code By @V_Sbotmaker (on Telegram)
"""
Downloader for the img2pdf pipeline.
Handles retries, exponential backoff, Tor fallback, Cloudflare detection.
"""

from __future__ import annotations

import asyncio
import os
import random
from pathlib import Path
from typing import Optional, List, Callable, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from loguru import logger
from cloudscraper import create_scraper

from .exceptions import DownloadError, SecurityError
from .models import DownloadPolicy, DownloadReport, ProgressEvent
from .config import AppConfig

# Assume these exist or we mock them if we don't have access to Webs.scraper
try:
    from Webs.scraper import is_tor_running, sb
except ImportError:
    # Dummy fallbacks for testability
    def is_tor_running(force: bool = False) -> bool:
        return False
    sb = None

_CHUNK = 8192
_HEAD_PEEK = 512
_CF_MARKER = b"cloudflare"

tor_proxies = {
    "http": "socks5h://127.0.0.1:9050",
    "https": "socks5h://127.0.0.1:9050",
}

class ResilientDownloader:
    def __init__(
        self,
        config: AppConfig,
        dl_executor: ThreadPoolExecutor,
        dl_sem: asyncio.Semaphore,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None
    ):
        self.config = config
        self.dl_executor = dl_executor
        self.dl_sem = dl_sem
        self.progress_callback = progress_callback

    def _get_session(self, use_cs: bool = False):
        if use_cs:
            try:
                return create_scraper(turbo_mode=True)
            except Exception:
                return create_scraper()
        else:
            # We use a simple import here instead of cloudscraper when not needed,
            # but curl_cffi requests is preferred by original
            from curl_cffi import requests
            return requests.Session()

    def _sync_download(
        self,
        url: str,
        img_path: Path,
        tmp_path: Path,
        headers: Optional[Dict[str, str]],
        use_cs: bool
    ) -> Optional[Path]:
        last_error = None
        for attempt in range(self.config.download_retries * 2): # original had 6
            resp = None
            try:
                cs = use_cs or attempt >= 2
                use_tor = is_tor_running(attempt >= 4)

                session = self._get_session(cs)
                kwargs: Dict[str, Any] = {
                    "headers": headers,
                    "timeout": self.config.timeout_seconds + attempt * 5,
                    "stream": True,
                }
                if use_tor:
                    kwargs["proxies"] = tor_proxies

                resp = session.get(url, **kwargs)

                if resp.status_code in (429, 503):
                    base_wait = min(2 * (2 ** attempt), 8)
                    import time
                    time.sleep(base_wait + random.uniform(0, base_wait * 0.5))
                    continue

                if resp.status_code != 200:
                    raise Exception(f"HTTP {resp.status_code}")

                size = 0
                head = b""

                iter_content = getattr(resp, "iter_content", None)
                with open(tmp_path, "wb") as f:
                    if callable(iter_content):
                        for chunk in iter_content(_CHUNK):
                            if chunk:
                                f.write(chunk)
                                size += len(chunk)
                                if len(head) < _HEAD_PEEK:
                                    head += chunk[: _HEAD_PEEK - len(head)]
                    else:
                        content = resp.content
                        head = content[:_HEAD_PEEK]
                        for i in range(0, len(content), _CHUNK):
                            chunk = content[i : i + _CHUNK]
                            if chunk:
                                f.write(chunk)
                                size += len(chunk)

                if size == 0:
                    tmp_path.unlink(missing_ok=True)
                    raise Exception("Empty response")

                if _CF_MARKER in head:
                    tmp_path.unlink(missing_ok=True)
                    raise Exception("Cloudflare block")

                tmp_path.replace(img_path)
                return img_path

            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed: {url} -> {e}")
                tmp_path.unlink(missing_ok=True)
                import time
                time.sleep(min(0.5 * (2 ** attempt), 8) + random.uniform(0, 0.5))
            finally:
                if resp is not None:
                    closer = getattr(resp, "close", None)
                    if callable(closer):
                        try:
                            closer()
                        except Exception:
                            pass

        for p in (img_path, tmp_path):
            p.unlink(missing_ok=True)
        logger.error(f"Giving up on {url} after {self.config.download_retries * 2} attempts: {last_error}")
        return None

    async def download_image(
        self,
        url: str,
        img_path: Path,
        headers: Optional[Dict[str, str]],
        use_cs: bool = False
    ) -> Optional[Path]:
        tmp_path = img_path.with_suffix(img_path.suffix + ".tmp")
        async with self.dl_sem:
            return await asyncio.get_running_loop().run_in_executor(
                self.dl_executor,
                self._sync_download,
                url, img_path, tmp_path, headers, use_cs
            )

    async def download_batch(
        self,
        urls: List[str],
        download_dir: Path,
        headers: Optional[Dict[str, str]] = None,
        use_cs: bool = False,
        chapter_id: str = "unknown"
    ) -> DownloadReport:
        download_dir.mkdir(parents=True, exist_ok=True)
        import time
        start_time = time.time()

        tasks = []
        expected_paths = []
        for idx, url in enumerate(urls, 1):
            img_path = download_dir / f"{str(idx).zfill(10)}.jpg"
            expected_paths.append((url, img_path))
            tasks.append(self.download_image(url, img_path, headers, use_cs))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        report = DownloadReport(elapsed_time=time.time() - start_time)
        fail_pairs = []

        for (url, img_path), res in zip(expected_paths, results):
            if isinstance(res, Exception) or res is None or not img_path.exists():
                fail_pairs.append((url, img_path))
                report.failed_urls.append(url)
                if isinstance(res, Exception):
                    report.failure_reasons[url] = str(res)
            else:
                report.successful_downloads.append(str(res))

        # Recovery phase
        if fail_pairs:
            logger.info(f"Attempting recovery for {len(fail_pairs)} failed downloads")
            recovery_tasks = [
                self.download_image(url, img_path, headers, use_cs)
                for url, img_path in fail_pairs
            ]
            recovery_results = await asyncio.gather(*recovery_tasks, return_exceptions=True)

            for (url, img_path), res in zip(fail_pairs, recovery_results):
                if isinstance(res, Exception) or res is None or not img_path.exists():
                    pass # already in failed list
                else:
                    report.successful_downloads.append(str(res))
                    report.failed_urls.remove(url)
                    if url in report.failure_reasons:
                        del report.failure_reasons[url]

        report.successful_downloads.sort(key=lambda p: Path(p).name)

        if report.failed_urls:
            if self.config.img_strict_download:
                import shutil
                shutil.rmtree(download_dir, ignore_errors=True)
                raise DownloadError(f"Download failed: {len(report.failed_urls)} images missing (Strict Mode)")
            else:
                logger.warning(
                    f"Partial download: {len(report.failed_urls)}/{len(urls)} images failed — "
                    "continuing with available pages"
                )

        if not report.successful_downloads:
            raise DownloadError("All images failed to download")

        return report

__all__ = ["ResilientDownloader"]
