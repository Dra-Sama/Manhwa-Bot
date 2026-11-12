# Code By @V_Sbotmaker (on Telegram)
"""
PDF Converter protocol and implementations for the img2pdf pipeline.
"""

from __future__ import annotations

import gc
import os
from pathlib import Path
from typing import List, Optional, Protocol, Tuple
from concurrent.futures import ThreadPoolExecutor

from loguru import logger
from fpdf import FPDF

from .exceptions import ConversionError
from .config import AppConfig
from .image_processor import pil_image, get_min_width, _compress_worker

def unicode_to_latin1(text: str) -> str:
    return text.encode('latin-1', 'replace').decode('latin-1')

def _try_hybrid_import() -> Tuple[Any, Any]:
    try:
        import img2pdf as _i2p
        import pikepdf as _pkpdf
        return _i2p, _pkpdf
    except ImportError:
        return None, None

def _convert_chunk_lossless(images: List[Path], img2pdf_mod) -> Optional[bytes]:
    try:
        a4_width = img2pdf_mod.in_to_pt(8.27)
        def layout_fun(imgwidthpx, imgheightpx, ndpi):
            imgwidthpdf = img2pdf_mod.px_to_pt(imgwidthpx, ndpi[0])
            imgheightpdf = img2pdf_mod.px_to_pt(imgheightpx, ndpi[1])
            scale = a4_width / imgwidthpdf
            imgwidthpdf = a4_width
            imgheightpdf *= scale
            pagewidth = imgwidthpdf
            pageheight = imgheightpdf
            if pageheight < 3: pageheight = 3
            elif pageheight > 14400: pageheight = 14400
            if pagewidth < 3: pagewidth = 3
            elif pagewidth > 14400: pagewidth = 14400
            return pagewidth, pageheight, imgwidthpdf, imgheightpdf

        return img2pdf_mod.convert(
            [str(p) for p in images],
            layout_fun=layout_fun
        )
    except Exception as e:
        logger.warning(f"img2pdf chunk error: {e}")
        return None

def _merge_pdfs_pikepdf(chunk_pdfs: List[bytes], output_path: Path, pikepdf_mod, password: Optional[str] = None) -> bool:
    import io
    try:
        merged = pikepdf_mod.Pdf.new()

        for pdf_bytes in chunk_pdfs:
            with pikepdf_mod.Pdf.open(io.BytesIO(pdf_bytes)) as chunk:
                merged.pages.extend(chunk.pages)

        if password:
            try:
                encryption = pikepdf_mod.Encryption(owner=password, user=password, R=4)
                merged.save(str(output_path), encryption=encryption)
            except Exception:
                merged.save(str(output_path))
        else:
            merged.save(str(output_path))
        return True
    except Exception as e:
        logger.error(f"pikepdf merge failed: {e}")
        return False

class PDFConverter(Protocol):
    def convert(
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
        ...

class FPDF2Converter:
    def __init__(self, config: AppConfig, executor: ThreadPoolExecutor):
        self.config = config
        self.executor = executor

    def convert(
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
        compressed_dir.mkdir(parents=True, exist_ok=True)
        target_width = get_min_width(image_files, self.executor)
        chunk_size = max(1, self.config.pdf_chunk_size)

        all_results = []

        try:
            for chunk_start in range(0, len(image_files), chunk_size):
                chunk = image_files[chunk_start : chunk_start + chunk_size]

                tasks = [
                    (i, f, compressed_dir, compression_quality, target_width)
                    for i, f in enumerate(chunk, chunk_start)
                ]

                try:
                    chunk_results = list(self.executor.map(_compress_worker, tasks))
                    all_results.extend(chunk_results)
                except Exception as e:
                    logger.warning(f"fpdf2 chunk compression error: {e}")
                    for i, f in enumerate(chunk, chunk_start):
                        w, h = pil_image(f)
                        all_results.append((i, f, w, h))

                gc.collect()

            all_results.sort(key=lambda x: x[0])

            pdf = FPDF('P', 'pt')

            # Render banner1
            if banner1 and banner1.exists():
                w, h = pil_image(banner1)
                if w and h:
                    pdf.add_page(format=(w, h))
                    pdf.image(str(banner1), x=0, y=0, w=w, h=h, link=hyperLink)

            # Render pages
            for idx, res_path, w, h in all_results:
                if not w or not h:
                    continue
                pdf.add_page(format=(w, h))
                pdf.image(str(res_path), x=0, y=0, w=w, h=h, link=hyperLink)

            # Render banner2
            if banner2 and banner2.exists():
                w, h = pil_image(banner2)
                if w and h:
                    pdf.add_page(format=(w, h))
                    pdf.image(str(banner2), x=0, y=0, w=w, h=h, link=hyperLink)

            if password:
                pdf.set_encryption(password)

            pdf.output(str(pdf_output_path))
        finally:
            import shutil
            shutil.rmtree(compressed_dir, ignore_errors=True)
            gc.collect()

class LosslessHybridConverter:
    def __init__(self, config: AppConfig, executor: ThreadPoolExecutor, fpdf_fallback: FPDF2Converter):
        self.config = config
        self.executor = executor
        self.fpdf_fallback = fpdf_fallback
        self.img2pdf_mod, self.pikepdf_mod = _try_hybrid_import()

    def convert(
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
        can_use_hybrid = (
            self.img2pdf_mod is not None and
            self.pikepdf_mod is not None
        )

        if not can_use_hybrid:
            return self.fpdf_fallback.convert(
                image_files, pdf_output_path, compressed_dir,
                password, compression_quality, hyperLink, banner1, banner2
            )

        # Include banner1 & banner2 into hybrid image order
        full_image_files: List[Path] = []
        if banner1 and banner1.exists():
            full_image_files.append(banner1)
        full_image_files.extend(image_files)
        if banner2 and banner2.exists():
            full_image_files.append(banner2)

        target_width = get_min_width(full_image_files, self.executor)
        chunk_size = max(1, self.config.pdf_chunk_size)
        skip_recompress = (compression_quality >= 95)

        chunk_pdfs = []

        try:
            for chunk_start in range(0, len(full_image_files), chunk_size):
                chunk = full_image_files[chunk_start : chunk_start + chunk_size]

                compressed_chunk = []
                if skip_recompress:
                    compressed_chunk = chunk
                else:
                    tasks = [
                        (i, f, compressed_dir, compression_quality, target_width)
                        for i, f in enumerate(chunk, chunk_start)
                    ]
                    try:
                        raw_results = list(self.executor.map(_compress_worker, tasks))
                        raw_results.sort(key=lambda x: x[0])
                        for idx, res_path, w, h in raw_results:
                            if w and h:
                                compressed_chunk.append(res_path)
                            else:
                                orig = full_image_files[idx]
                                if orig.exists():
                                    compressed_chunk.append(orig)
                                logger.warning(f"Skipping unreadable image: {full_image_files[idx]}")
                    except Exception as e:
                        logger.warning(f"Chunk compression error (chunk start={chunk_start}): {e}")
                        compressed_chunk = [f for f in chunk if f.exists()]

                if compressed_chunk:
                    pdf_bytes = _convert_chunk_lossless(compressed_chunk, self.img2pdf_mod)
                    if pdf_bytes:
                        chunk_pdfs.append(pdf_bytes)
                    else:
                        logger.warning(f"img2pdf failed for chunk {chunk_start}, falling back to fpdf2")
                        import shutil
                        shutil.rmtree(compressed_dir, ignore_errors=True)
                        gc.collect()
                        return self.fpdf_fallback.convert(
                            image_files, pdf_output_path, compressed_dir.with_name(compressed_dir.name + "_fp2"),
                            password, compression_quality, hyperLink, banner1, banner2
                        )

                if not skip_recompress:
                    for idx, res_path, w, h in raw_results:
                        if res_path not in full_image_files and res_path.exists():
                            res_path.unlink(missing_ok=True)

                del compressed_chunk
                gc.collect()

            if not chunk_pdfs:
                raise ConversionError("No PDF chunks produced.")

            success = _merge_pdfs_pikepdf(chunk_pdfs, pdf_output_path, self.pikepdf_mod, password=password)
            if not success:
                logger.warning("pikepdf merge failed, falling back to fpdf2")
                import shutil
                shutil.rmtree(compressed_dir, ignore_errors=True)
                gc.collect()
                return self.fpdf_fallback.convert(
                    image_files, pdf_output_path, compressed_dir.with_name(compressed_dir.name + "_fp2"),
                    password, compression_quality, hyperLink, banner1, banner2
                )

        except Exception as e:
            logger.exception(f"Hybrid PDF conversion failed: {e}")
            raise ConversionError(str(e))
        finally:
            import shutil
            shutil.rmtree(compressed_dir, ignore_errors=True)
            gc.collect()

class PDFConverterFactory:
    @staticmethod
    def get_converter(config: AppConfig, executor: ThreadPoolExecutor) -> PDFConverter:
        fpdf = FPDF2Converter(config, executor)
        return LosslessHybridConverter(config, executor, fpdf)

__all__ = ["PDFConverter", "PDFConverterFactory", "FPDF2Converter", "LosslessHybridConverter"]
