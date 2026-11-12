# Code By @V_Sbotmaker (on Telegram)

from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus
import re

from .scraper import Scraper

from .utitls import DEAULT_MSG_FORMAT
from loguru import logger



BASE_URL = "https://doujins.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    )
}

scraper = Scraper(HEADERS)


class DoujinsSource:
    sf = "dou"
    url = BASE_URL

    # ---------------- SEARCH ---------------- #

    @classmethod
    async def search(cls, query):
        search_url = f"{BASE_URL}/searches?words={quote_plus(query)}"
        html = await scraper.get(search_url, timeout=60)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")

        results = []
        cards = soup.find_all(
            "div",
            class_="col-6 col-sm-4 col-md-3 col-lg-2 px-1"
        )[:25]

        for card in cards:
            try:
                if not card:
                    continue
                
                a = card.find("a")
                img = card.find("img")
                title_div = card.find("div", class_="text")
                
                url = urljoin(BASE_URL, a.get("href"))
                title = title_div.get_text(strip=True)
                thumbnail = img.get("src")
                
                results.append({
                    "title": title, "url": url,
                    "poster": thumbnail
                })
            except Exception:
                continue

        return results

    # ---------------- CHAPTERS ---------------- #

    @classmethod
    async def get_chapters(cls, data: dict):
        results = data.copy()
        
        html = await scraper.get(results['url'], timeout=60)
        if not html:
            return results
        
        soup = BeautifulSoup(html, "html.parser")

        # Title
        title = None
        title_div = soup.find("div", class_="folder-title")
        if title_div:
            a_tags = title_div.find_all("a")
            if len(a_tags) >= 2:
                title = a_tags[1].get_text(strip=True)
        results['title'] = title

        # Summary
        summary = "N/A"

        # Genres / Tags
        genres = "N/A"
        tag_li = soup.find("li", class_="tag-area")
        if tag_li:
            genres = ", ".join([
                a.get_text(strip=True)
                for a in tag_li.find_all("a")
                if a.get_text(strip=True)
            ])
        
        img = soup.find("img", class_="doujin")
        thumb2 = None
        if img:
            thumb2 = img.get("data-thumb2")
            if thumb2:
                thumb2 = thumb2.split()[0]
        if thumb2:
            results['poster'] = thumb2

        results['msg'] = DEAULT_MSG_FORMAT.format(
            title=title, summary=summary,
            genres=genres, status="N/A",
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

    # ---------------- CHAPTER IMAGES ---------------- #

    @classmethod
    async def get_pictures(cls, chapter_url, data: dict = {}):
        html = await scraper.get(chapter_url, timeout=60)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")

        images = []
        for div in soup.find_all("div", class_="swiper-zoom-container"):
            img = div.find("img")
            if not img:
                continue
            
            src = img.get("data-src") or img.get("src")
            if src:
                images.append(src.strip())

        return images

