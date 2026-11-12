# Code By @V_Sbotmaker (on Telegram)
import random
import base64
import json
import re
from bs4 import BeautifulSoup
from html import unescape
from urllib.parse import urljoin

from Webs.scraper import Scraper
from Webs.utitls import DEAULT_MSG_FORMAT

BASE_URL = "https://manhwaread.com"
AJAX_URL = f"{BASE_URL}/wp-admin/admin-ajax.php"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "Referer": BASE_URL
}

def _b64decode_fix(data: str) -> bytes:
    data = data.strip()
    missing = len(data) % 4
    if missing:
        data += "=" * (4 - missing)
    return base64.b64decode(data)

def get_proxy() -> str:
    return random.choice([
        "https://bpass-sophia-02.sanalphanzo.workers.dev/proxy?url=",
    ])


class ManhwaReadSource:
    sf = "mr.d"
    url = BASE_URL

    # -------------------------------------------------
    # SEARCH
    # -------------------------------------------------
    @classmethod
    async def search(cls, query):
        payload = {
            "action": "quick_search",
            "keyword": query,
        }

        search_url = get_proxy() + AJAX_URL
        data = await Scraper(headers=HEADERS).post(
            search_url, rjson=True, data=payload,
        )
        if not data or not isinstance(data, dict):
            return []

        html = data.get("data", {}).get("searchMangaResults")
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []

        for item in soup.select(".manga-item"):
            a = item.select_one("h3 a[href]")
            img = item.select_one("img")

            if not a:
                continue

            title = unescape(a.get_text(strip=True))
            url = a.get("href")

            cover = None
            if img:
                cover = img.get("src")

            results.append({
                "title": title,
                "url": url,
                "poster": cover,
            })

        return results

    # -------------------------------------------------
    # MANGA INFO
    # -------------------------------------------------
    @classmethod
    async def get_chapters(cls, data: dict, page: int = 1):
        request_url = get_proxy() + data['url']
        
        html = await Scraper(headers=HEADERS).get(request_url)
        if not html:
            return data
        
        results = data.copy()
        soup = BeautifulSoup(html, "html.parser")


        # -----------------------------
        # SUMMARY
        # -----------------------------
        summary = "N/A"
        summary_block = soup.select_one(
            "#mangaSummary .summary-content p, "
            "#mangaSummary p"
        )
        if summary_block:
            summary = unescape(summary_block.get_text(" ", strip=True))

        if not summary:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                summary = unescape(meta_desc.get("content", "")).strip()

        # -----------------------------
        # COVER
        # -----------------------------
        cover = None
        img = soup.select_one("#mangaSummary img")
        if img:
            cover = img.get("src")

        if not cover:
            og = soup.find("meta", property="og:image")
            if og:
                cover = og.get("content")
                results['poster'] = cover

        # -----------------------------
        # STATUS + RELEASED
        # -----------------------------
        status = "N/A"

        status_block = soup.select_one(".manga-status")
        if status_block:
            label = status_block.select_one(".manga-status__label")
            if label:
                text = label.get_text(" ", strip=True)

                if re.search(r"\bcompleted\b", text, re.I):
                    status = "Completed"
                elif re.search(r"\bongoing\b", text, re.I):
                    status = "Ongoing"

            if not status:
                ds = status_block.get("data-status")
                if ds:
                    status = ds.capitalize()

        # -----------------------------
        # TAGS
        # -----------------------------
        tags = []
        for block in soup.select("div.flex-col"):
            title_div = block.select_one(".text-primary")
            if title_div and title_div.get_text(strip=True) == "Tags:":
                for a in block.select("a[rel='tag'] span.text-gray-100"):
                    tag = a.get_text(strip=True)
                    if tag not in tags:
                        tags.append(tag)
                break
        
        tags = ", ".join(tags) if tags else "N/A"
        results['msg'] = DEAULT_MSG_FORMAT.format(
            title=results['title'],
            url=results['url'],
            poster=results['poster'],
            summary=summary,
            status=status,
            genres=tags
        )

        # -----------------------------
        # CHAPTERS
        # -----------------------------
        chapters = []
        container = soup.select_one("#chaptersList")
        if container:
            for a in container.select("a.chapter-item"):
                name = a.select_one(".chapter-item__name")
                if not name:
                    continue

                chapters.append((
                     name.get_text(strip=True),
                     urljoin(BASE_URL, str(a.get("href")))
                ))
        
        results['chapters'] = list(reversed(chapters))

        return results
    
    def iter_chapters(self, data, page: int=1):
        chapters_list = []

        if 'chapters' in data:
          chapters_list = [
            {
              "title": card[0],
              "url": card[1],
              "manga_title": data['title'],
              "poster": data['poster'] if 'poster' in data else None
            }
            for card in data['chapters']
          ]

        return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list
    
    # -------------------------------------------------
    # CHAPTER IMAGES
    # -------------------------------------------------
    @classmethod
    async def get_pictures(cls, chapter_url, data: dict = {}):
        request_url = get_proxy() + chapter_url
        html = await Scraper(headers=HEADERS).get(request_url)
        if not html:
            return []
    
        match = re.search(
            r'var\s+chapterData\s*=\s*(\{.*?\});',
            html,
            re.DOTALL
        )
        if not match:
            return []
    
        data_obj = json.loads(match.group(1))
    
        encoded = data_obj.get("data")
        base = data_obj.get("base")
    
        if not encoded or not base:
            return []
    
        decoded = _b64decode_fix(encoded).decode("utf-8")
    
        pages = json.loads(decoded)
    
        images = []
        for page in pages:
            src = page.get("src")
            if not src:
                continue
            
            images.append(f"{base}/{src}")
    
        return images
