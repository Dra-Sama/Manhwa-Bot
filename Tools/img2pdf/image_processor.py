# Code By @V_Sbotmaker (on Telegram)
"""
Image processing utilities for the img2pdf pipeline.
Handles compression, resizing, and dimension scanning.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = False

def pil_image(path: Path) -> Tuple[int, int]:
    try:
        with Image.open(path) as img:
            return img.width, img.height
    except Exception:
        return 0, 0

def get_min_width(image_files: List[Path], executor: ThreadPoolExecutor) -> Optional[int]:
    """
    Return the minimum pixel width across all image files.
    """
    valid = []

    def get_width(p: Path) -> int:
        w, _ = pil_image(p)
        return w

    results = executor.map(get_width, image_files)
    for w in results:
        if w > 0:
            valid.append(w)

    return min(valid) if valid else None

def compress_image(
    image_path: Path,
    output_path: Path,
    quality: int = 90,
    target_width: Optional[int] = None,
) -> Tuple[Path, int, int]:
    """
    Compress/resize a single image to JPEG.
    """
    orig_width, orig_height = None, None

    try:
        with Image.open(image_path) as img:
            img_width, img_height = img.size
            orig_width, orig_height = img_width, img_height

            if img.mode != "RGB":
                img = img.convert("RGB")

            if target_width and img_width != target_width:
                new_height = int((target_width / img_width) * img_height)
                img = img.resize((target_width, new_height), Image.LANCZOS)
                img_width, img_height = target_width, new_height

            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "JPEG", quality=quality, progressive=True)

        return output_path, img_width, img_height

    except Exception as e:
        logger.warning(f"Compress failed {image_path}: {e}")
        output_path.unlink(missing_ok=True)

    if orig_width is None or orig_height is None:
        orig_width, orig_height = pil_image(image_path)

    return image_path, orig_width, orig_height

def _compress_worker(args: Tuple[int, Path, Path, int, Optional[int]]) -> Tuple[int, Path, int, int]:
    idx, image_path, output_dir, quality, target_width = args
    if not image_path.exists():
        return idx, image_path, 0, 0

    out_path = output_dir / f"{idx:010d}_comp.jpg"
    res_path, w, h = compress_image(image_path, out_path, quality, target_width)
    return idx, res_path, w, h

__all__ = ["pil_image", "get_min_width", "compress_image", "_compress_worker"]
