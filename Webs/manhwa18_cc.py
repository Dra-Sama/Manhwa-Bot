# Code By @V_Sbotmaker (on Telegram)

from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus, quote
import re

from Webs.utitls import DEAULT_MSG_FORMAT

from .scraper import Scraper


BASE_URL = "https://manhwa18.cc"

HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    )
}

scraper = Scraper(headers=HEADERS)

class Manhwa18Source:
    sf = "m.c"
    url = BASE_URL

    # ---------------- SEARCH ---------------- #

    @classmethod
    async def search(cls, query):
        url = f"{BASE_URL}/search?q={quote_plus(query)}"
        html = await scraper.get(url, timeout=60)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")

        results = []
        container = soup.find("div", class_="manga-lists")
        if not container:
            return results

        for card in container.find_all("div", class_="manga-item"):
            a = card.find("a")
            img = card.find("img")
            
            if not a:
                continue

            results.append({
                "title": a.get("title"),
                "url": urljoin(BASE_URL, str(a.get("href"))),
                "poster": img.get("src") if img else None,
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

        # -------- COVER --------
        cover = None
        img = soup.select_one(".summary_image img")
        if img:
            cover = img.get("src")
            results['poster'] = cover

        # -------- SUMMARY --------
        summary = "N/A"
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            summary = str(og_desc["content"]).strip()

        if not summary:
            desc = soup.select_one(".description-summary")
            if desc:
                summary = desc.get_text(" ", strip=True)

        # -------- GENRES --------
        genres = "N/A"
        genres_div = soup.select_one(".genres-content")
        if genres_div:
            genres = ", ".join([
                a.get_text(strip=True)
                for a in genres_div.find_all("a")
            ])

        results['msg'] = DEAULT_MSG_FORMAT.format(
            title=results['title'],
            summary=summary,
            genres=genres,
            url=results['url'],
            status="N/A",
        )
        
        # -------- CHAPTERS --------
        results['chapters'] = []
        ul = soup.select_one("ul.row-content-chapter")
        if ul:
            for li in ul.find_all("li", class_="a-h"):
                a = li.find("a")
                if not a:
                    continue
                
                ch_title = a.get_text(strip=True)
                ch_url = urljoin(BASE_URL, str(a.get("href")))
                results['chapters'].append((ch_title, ch_url))

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
    
    # ---------------- CHAPTER IMAGES ---------------- #

    @classmethod
    async def get_pictures(cls, chapter_url, data: dict = {}):
        html = await scraper.get(chapter_url, timeout=60)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")

        images = []
        container = soup.find("div", class_="read-content wleft tcenter")
        if container:
            for img in container.find_all("img"):
                src = str(img.get("src"))
                if src:
                    images.append(quote(src, safe=":/%"))

        return images

