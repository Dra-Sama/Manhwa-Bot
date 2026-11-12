# Code By @V_Sbotmaker (on Telegram)

import re
import json
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin

from .scraper import Scraper
from .utitls import DEAULT_MSG_FORMAT

BASE_URL = "https://hentalk.pw"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "Referer": BASE_URL,
}

scraper = Scraper(HEADERS)

DEFAULT_PRESET_HASH = "5cfead81"


class HentalkSource:
    sf = "h.k"
    url = BASE_URL

    # ---------------- SEARCH ---------------- #

    @classmethod
    async def search(cls, query, page=1):
        params = f"?q={quote_plus(query)}"
        if page > 1:
            params += f"&page={page}"

        html = await scraper.get(BASE_URL + "/" + params, timeout=60)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")

        results = []

        for card in soup.select("a[href^='/g/']"):
            href = card.get("href")
            if not href:
                continue

            url = urljoin(BASE_URL, str(href).split("?")[0])

            img = card.select_one("img")
            title = img.get("alt") if img else None
            thumb = img.get("src") if img else None

            if not (title and thumb):
                continue
            
            results.append({
                "title": str(title).replace(" cover", "").strip("' "),
                "url": url,
                "poster": urljoin(BASE_URL, str(thumb)),
            })

        return results

    # ---------------- INFO ---------------- #

    @classmethod
    async def get_chapters(cls, data: dict, page: int = 1):
        results = data.copy()
        
        html = await scraper.get(results['url'], timeout=60)
        if not html:
            return results
        
        soup = BeautifulSoup(html, "html.parser")

        # -------- ID -------- #
        m = re.search(r"/g/(\d+)", results['url'])
        gallery_id = m.group(1) if m else None

        # -------- TITLE -------- #
        title_el = soup.select_one("meta[property='og:title']")
        title = str(title_el["content"]).replace(" - faccina", "") if title_el else ""

        # -------- DESCRIPTION -------- #
        desc_el = soup.select_one("meta[property='og:description']")
        description = desc_el["content"] if desc_el else ""

        # -------- COVER -------- #
        cover = None
        cover_img = soup.select_one("img[src*='/image/'][src*='type=cover']")
        if cover_img:
            cover = urljoin(BASE_URL, str(cover_img["src"]))
            results['poster'] = cover

        # -------- TAGS -------- #
        fields = {
            #"Artists": "N/A",
            #"Circles": "N/A",
            #"Publishers": "N/A",
            #"Parodies": "N/A",
            "Tags": "N/A",
        }

        for section in soup.select("p.uppercase"):
            label = section.get_text(strip=True)
            container = section.find_next_sibling("div")
            if not container:
                continue
            try:
                values = ", ".join([
                    a.get_text(strip=True)
                    for a in container.select("a")
                ])
                
                if label in fields:
                    fields[label] = values
            except Exception:
                continue

        pages = None
        page_badge = soup.select_one("div.text-xs.font-bold")
        if page_badge:
            pages = int(page_badge.get_text(strip=True).replace("P", ""))
        
        results['msg'] = DEAULT_MSG_FORMAT.format(
          title=results['title'],
          status="N/A",
          genres=fields.get("Tags"),
          summary=description[:400],
          url=results['url']
        )
        
        results.update({
            "pages": pages,
        })
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
    async def get_pictures(cls, manga_url, data: dict = {}):
        m = re.search(r"/g/(\d+)", manga_url)
        if not m:
            return []
    
        gid = m.group(1)
        reader_url = f"{BASE_URL}/g/{gid}/read/1"
    
        html = await scraper.get(reader_url, timeout=60)
        if not html:
            return []
        
        preset_match = re.search(
            r'defaultPreset\s*:\s*\{[^}]*?hash\s*:\s*"([a-f0-9]+)"',
            html
        )
    
        gallery_hash_match = re.search(
            r"gallery\s*:\s*\{[^}]*?hash\s*:\s*\"([a-f0-9]+)\"",
            html
        )
    
        pages_match = re.search(
            r"gallery\s*:\s*\{[^}]*?pages\s*:\s*(\d+)",
            html
        )
    
        if not (preset_match and gallery_hash_match and pages_match):
            return []
    
        preset_hash = preset_match.group(1)
        gallery_hash = gallery_hash_match.group(1)
        total_pages = int(pages_match.group(1))
    
        return [
            f"{BASE_URL}/image/{gallery_hash}/{page}?type={preset_hash}"
            for page in range(1, total_pages + 1)
        ]
