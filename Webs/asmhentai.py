# Code By @V_Sbotmaker (on Telegram)

from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus
import re
from .scraper import Scraper

from .utitls import DEAULT_MSG_FORMAT
from loguru import logger

BASE_URL = "https://asmhentai.com"
IMAGE_BASE = "https://images.asmhentai.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "Referer": BASE_URL
}

scraper = Scraper(HEADERS)

class AsmHentaiWebs:
    sf = "amhi"
    url = BASE_URL

    # ---------------- SEARCH ---------------- #

    @classmethod
    async def search(cls, query, page=1):
        search_url = (
            f"{BASE_URL}/search/?q={quote_plus(query)}"
            f"{'&page=' + str(page) if page > 1 else ''}"
        )

        html = await scraper.get(search_url, timeout=60)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")

        results = []

        for item in soup.select(".preview_item"):
            a = item.select_one(".image a")
            img = item.select_one("img")
            title = item.select_one(".caption")

            if not (a and img and title):
                continue

            url = urljoin(BASE_URL, a["href"])
            title_text = title.get_text(strip=True)

            results.append({
                "title": title_text,
                "url": url,
                "poster": img
            })

        return results

    # ---------------- INFO ---------------- #

    @classmethod
    async def get_chapters(cls, data: dict):
        results = data.copy()
        
        html = await scraper.get(results['url'], timeout=60)
        if not html:
            return results
        
        soup = BeautifulSoup(html, "html.parser")

        # Title
        title = soup.select_one("h1")
        title = title.get_text(strip=True) if title else None

        # Tags
        tags = []
        for block in soup.select(".tag_list a"):
            tag = block.get_text(strip=True)
            if tag:
                tags.append(tag)
        
        tags = ", ".join(tags) if tags else "N/A"

        # Pages
        pages = 0
        pages_el = soup.find("h3", string=re.compile(r"Pages:"))
        if pages_el:
            pages = int(re.search(r"\d+", pages_el.text).group())

        # Gallery ID
        gallery_id = soup.find("input", {"id": "gallery_id"})
        gallery_id = gallery_id.get("value", None) if gallery_id else None

        # Dir
        load_dir = soup.find("input", {"id": "load_dir"})
        dir_id = load_dir.get("value", None) if load_dir else None
        
        results.update({
            "pages": pages,
            "gallery_id": gallery_id,
            "dir": dir_id,
        })
        
        results["poster"] = f"{IMAGE_BASE}/{dir_id}/{gallery_id}/1.jpg"
        # CSRF token
        #token = soup.find("meta", {"name": "csrf-token"})
        #token = token["content"] if token else None

        results['msg'] = DEAULT_MSG_FORMAT.format(
            title=title,
            status="N/A",
            genres=tags,
            summary="N/A",
            url=results['url']
        )
        return results

    @classmethod
    def iter_chapters(cls, data, page: int=1):
        return [{
            "title": "Chapter 1",
            "url": data['url'],
            "poster": data['poster'] if "poster" in data else "",
            "manga_title": data['title'] if "title" in data else ""
        }] if page == 1 else []
    
    # ---------------- IMAGES ---------------- #

    @classmethod
    async def get_pictures(cls, manga_url: str, data: dict = {}):
        try:
            if "pages" not in data:
                data = await cls.get_chapters(data)
            
            gallery_id = data["gallery_id"]
            dir_id = data["dir"]
            total_pages = data["pages"]
            
            return [
                f"{IMAGE_BASE}/{dir_id}/{gallery_id}/{page}.jpg"
                for page in range(1, total_pages + 1)
            ]
        except Exception as er:
            logger.exception(er)
            return []
