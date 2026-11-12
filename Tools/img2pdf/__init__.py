# Code By @V_Sbotmaker (on Telegram)
"""
Public API for the new img2pdf pipeline.
Replaces the old img2pdf.py file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List
import functools
import random
from loguru import logger

from .config import AppConfig
from .resource_manager import ResourceManager
from .pipeline import ImageToPDFPipeline
from .exceptions import ImageDownloadError, PipelineError

# We still need get_headers for compatibility
try:
    from Webs.scraper import UA_POOL
except ImportError:
    UA_POOL = [{"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}]

@functools.lru_cache(maxsize=32)
def _get_header_template(base_url: str) -> dict:
    if "manhuaplus.com" in base_url:
        return {
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://manhuaplus.com/",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }
    elif "mangakatana.com" in base_url:
        return {
            "accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "accept-language": "en-GB,en;q=0.8",
            "connection": "keep-alive",
            "referer": "https://mangakatana.com/",
            "sec-fetch-storage-access": "none",
            "sec-gpc": "1",
        }
    elif "mangakakalot.gg" in base_url:
        return {
            "accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": "https://www.manganato.gg/",
            "sec-fetch-dest": "image",
            "sec-fetch-mode": "no-cors",
            "sec-fetch-site": "cross-site",
        }
    elif "comick" in base_url:
        return {
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": "https://comick.live/",
            "Origin": "https://comick.live",
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site",
        }
    else:
        return {
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Connection": "keep-alive",
            "Referer": base_url,
            "Origin": base_url,
            "sec-fetch-dest": "image",
            "sec-fetch-mode": "no-cors",
            "sec-fetch-site": "cross-site",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }

def get_headers(base_url: str) -> dict:
    """Fresh headers on every call — template is cached, UA is not."""
    template = dict(_get_header_template(base_url))
    u  = random.choice(UA_POOL) if UA_POOL else {}
    ua = u.get(
        "ua",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    )

    if "mangakakalot.gg" in base_url:
        template["user-agent"] = (
            "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"
        )
    elif "mangakatana.com" in base_url:
        template["user-agent"] = ua
    else:
        template["User-Agent"] = ua

    return template

# Global pipeline instance for compatibility with old API
_pipeline: Optional[ImageToPDFPipeline] = None
_rm: Optional[ResourceManager] = None

def _get_pipeline() -> ImageToPDFPipeline:
    global _pipeline, _rm
    if _pipeline is None:
        config = AppConfig()
        _rm = ResourceManager(config)
        _pipeline = ImageToPDFPipeline(config, _rm)
    return _pipeline

async def download_and_convert_images(
    images: list,
    download_dir: str,
    base_url: str,
    cs: bool = False,
    headers: Optional[dict] = None,
) -> list:
    pipeline = _get_pipeline()
    headers = headers or get_headers(base_url)
    try:
        paths = await pipeline.download_images(
            urls=images,
            download_dir=Path(download_dir),
            headers=headers,
            use_cs=cs
        )
        return [str(p) for p in paths]
    except PipelineError as e:
        raise ImageDownloadError(str(e))

async def convert_images_to_pdf_async(
    image_files: list,
    pdf_output_path: str,
    compressed_dir: str,
    password: Optional[str] = None,
    compression_quality: int = 80,
    hyperLink: Optional[str] = None,
    banner1: Optional[str] = None,
    banner2: Optional[str] = None,
) -> Optional[str]:
    pipeline = _get_pipeline()
    try:
        await pipeline.convert_to_pdf(
            image_files=[Path(f) for f in image_files],
            pdf_output_path=Path(pdf_output_path),
            compressed_dir=Path(compressed_dir),
            password=password,
            compression_quality=compression_quality,
            hyperLink=hyperLink,
            banner1=Path(banner1) if banner1 else None,
            banner2=Path(banner2) if banner2 else None
        )
        return None
    except PipelineError as e:
        return str(e)

async def thumbnali_images(
    image_url: str,
    download_dir: str,
    base_url: Optional[str] = None,
    quality: int = 80,
    file_name: str = "thumb.jpg",
    sb: bool = False
) -> Optional[str]:
    pipeline = _get_pipeline()
    res = await pipeline.create_thumbnail(
        image_url,
        Path(download_dir),
        base_url,
        quality,
        file_name,
        sb
    )
    return str(res) if res else None

async def download_images_sb(
    images: list,
    download_dir: str,
    concurrency: int = 4,
) -> list:
    pipeline = _get_pipeline()
    try:
        paths = await pipeline.download_images(
            urls=images,
            download_dir=Path(download_dir),
            headers=None,
            use_cs=True
        )
        return [str(p) for p in paths]
    except PipelineError as e:
        logger.warning(f"sb download failed: {e}")
        return []

# Old sync API is mostly unused or wrapped in async calls, we omit it for brevity,
# but we need to alias the exception for compatibility
class ImageDownloadError(Exception):
    pass

__all__ = [
    "download_and_convert_images",
    "convert_images_to_pdf_async",
    "download_images_sb",
    "thumbnali_images",
    "get_headers",
    "ImageDownloadError",
]
