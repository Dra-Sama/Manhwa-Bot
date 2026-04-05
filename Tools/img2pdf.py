"""
This module provides functions to download, convert, and compress images, and then convert them into a PDF file.

Modified:- Dra-Sama
"""
from typing import Optional

from urllib.parse import quote
from PIL import Image, ImageFile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from loguru import logger
import os

import pillow_avif  # This registers AVIF format support with Pillow
import pillow_heif

from curl_cffi import requests

import shutil

from cloudscraper import create_scraper
import asyncio

import PyPDF2
import gc
from time import sleep


from Webs.scraper import Scraper


ImageFile.LOAD_TRUNCATED_IMAGES = False

tor_proxies = {
    "http": "socks5h://127.0.0.1:9050",
    "https": "socks5h://127.0.0.1:9050",
}

class ImageDownloadError(Exception):
    pass


def get_headers(base_url: str):
    if "manhuaplus.com" in base_url:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://manhuaplus.com/",
            #"Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }

    elif "mangakatana.com" in base_url:
        headers = {
            "accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            #"accept-encoding": "gzip, deflate, br, zstd"
            "accept-language": "en-GB,en;q=0.8",
            "connection": "keep-alive",
            #host: i.supernova22.click
            "referer": "https://mangakatana.com/",
            "sec-fetch-storage-access": "none",
            "sec-gpc": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
        }
    elif "mangakakalot.gg" in base_url:
        headers = {
            "authority": "imgs-2.2xstorage.com",
            "method": "GET",
            "scheme": "https",
            "accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": "https://www.manganato.gg/",
            "sec-ch-ua": '"Chromium";v="137", "Not(A)Brand";v="24"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "image",
            "sec-fetch-mode": "no-cors",
            "sec-fetch-site": "cross-site",
            "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"
        }
    else:
        headers = {
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": base_url,
        }

    return headers


async def thumbnali_images(image_url, download_dir, base_url = None, quality=80, file_name="thumb.jpg"):
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    headers = get_headers(base_url) if base_url else {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
    try:
        return await asyncio.to_thread(download_image, file_name, image_url, download_dir, cs=True, headers=headers)
    except Exception:
        return None



_scraper = create_scraper()
_session = requests.Session()
        
def download_image(
    idx: str, image_url:str, download_dir: str, 
    headers: Optional[dict] = None, cs: bool = False, 
):
    idx = idx.zfill(5)
    img_path = os.path.join(download_dir, f"{idx}.jpg")
    
    session = _session if not cs else _scraper
    
    args = (image_url,) 
    kwargs = {
        'stream': True,
        'headers': headers,
        'timeout': 50,
    }
    
    for retries in range(5):
        try:
            if retries > 3: # if more than 3 retries, use tor
                kwargs['proxies'] = tor_proxies
            
            with session.get(*args, **kwargs) as image_response:
                if "Attention Required! | Cloudflare" in str(image_response.text):
                    raise Exception("Cloudflare protection triggered")

                if image_response.status_code != 200:
                    raise Exception(" Not 200 Request Status ")
                
               
                if os.path.exists(download_dir):
                    with open(img_path, 'wb') as img_file:
                        for chunk in image_response.iter_content(1024 * 64):
                            if chunk:
                                img_file.write(chunk)
                else:
                    raise Exception("Tasks cancelled")

            return str(img_path)


        except Exception:
            sleep(3 * (retries + 1))
            #logger.warning(f"Download :- {retries} :- {image_url}")

    if os.path.exists(img_path):
        try:
            os.remove(img_path)
        except Exception:
            pass

    raise Exception("Failed to download image after 3 attempts")



async def download_and_convert_images(
    images, 
    download_dir,
    base_url: str,
    quality: int = 70,
    cs: bool = False,
    headers: dict = {},
    pw: bool = False
):
    async def with_semaphore(*args, **kwargs):
        async with asyncio.Semaphore(5):
            return await asyncio.to_thread(download_image, *args, **kwargs)

    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    headers = get_headers(base_url) if not headers else headers
    
    
    image_files = [
        with_semaphore(
            str(idx), image_url, 
            download_dir, headers=headers, 
            cs=cs
        )
        for idx, image_url in enumerate(images, 1)
    ]


    process_list = await asyncio.gather(*image_files, return_exceptions=True)
    for result in process_list:
        if isinstance(result, Exception):
            raise ImageDownloadError(result)

    picturesList = [ str(file) for file in process_list if isinstance(file, str) ]
    picturesList.sort()

    gc.collect()

    return picturesList


def get_min_width_generator(image_files):
    min_width = float('inf')

    for image_file in image_files:
        try:
            with Image.open(image_file) as img:
                width = img.width

                if width < min_width:
                    min_width = width

        except Exception:
            continue

    gc.collect()
    return min_width if min_width != float('inf') else None



def compress_image(image_path, output_path, quality=90, target_width=None):
    """Compress the image by resizing and reducing its quality."""
    try:
        img = Image.open(image_path).convert("RGB")
        img_width, img_height = img.size

        if target_width:
            new_height = int((target_width / img_width) * img_height)
            img = img.resize((target_width, new_height), Image.LANCZOS)

        img.save(output_path, "JPEG", quality=quality, progressive=True)

        return output_path, img_width, img_height
    except Exception:
        #logger.warning(f"Error compressing image {image_path}: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)

        return image_path, 0, 0


def convert_images_to_pdf(
    image_files, pdf_output_path, 
    compressed_dir, password=None, 
    compression_quality=10, hyperLink=None,
    banner1=None, banner2=None,
):
    if not image_files:
        logger.warning("No images provided for PDF conversion.")
        return "No images provided for PDF conversion."

    os.makedirs(compressed_dir, exist_ok=True)
    temp_pdf_path = str(pdf_output_path).replace(".pdf", "_temp.pdf")

    c = canvas.Canvas(str(temp_pdf_path), pagesize=letter)

    # Set the target width (e.g., the width of the smallest image)
    target_width = get_min_width_generator(image_files)

    def draw_image(f, w, h, hl=None):
        try:
            if target_width and w > 0:
                nh = int(target_width * h / w)
                c.setPageSize((target_width, nh))
                c.drawImage(str(f), 0, 0, width=target_width, height=nh)
                if hl:
                    c.linkURL(url=hl, rect=(0, 0, target_width, nh), relative=0, thickness=0)

            c.showPage()
        except Exception:
            pass
            #logger.error(f"Draw error {f}: {e}")
    if banner1:
        draw_image(banner1, 1, 1, hyperLink) if hyperLink else draw_image(banner1, 1, 1)

    for f in image_files:
        cf = f"{compressed_dir}/{os.path.basename(f)}"
        res, w, h = compress_image(f, cf, quality=compression_quality, target_width=target_width)

        draw_image(res, w, h)

        if res == cf and os.path.exists(res):
            os.remove(res)

    if banner2:
        draw_image(banner2, 1, 1, hyperLink) if hyperLink else draw_image(banner2, 1, 1)

    c.save()

    if password:
        encrypt_pdf(temp_pdf_path, str(pdf_output_path), password)
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)  # Remove the temporary unprotected PDF
    else:
        os.rename(temp_pdf_path, str(pdf_output_path))

    shutil.rmtree(compressed_dir, ignore_errors=True)

    #logger.info(f"Compressed PDF created at {pdf_output_path}")

    gc.collect()

    return None


def encrypt_pdf(input_path, output_path, password):
    """Encrypt a PDF with a password using PyPDF2"""
    try:
        with open(input_path, 'rb') as input_file:
            reader = PyPDF2.PdfReader(input_file)
            writer = PyPDF2.PdfWriter()

            for page in reader.pages:
                writer.add_page(page)

            writer.encrypt(user_password=password, owner_password=None, 
                          use_128bit=True)

            with open(output_path, 'wb') as output_file:
                writer.write(output_file)

    except Exception as e:
        logger.error(f"Failed to encrypt PDF: {e}")
