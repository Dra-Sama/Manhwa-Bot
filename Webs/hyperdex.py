# Code By @V_Sbotmaker (on Telegram)

from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, urlencode
import json

from Webs.utitls import DEAULT_MSG_FORMAT

from .scraper import Scraper

BASE_URL = "https://hiperdex.com"

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
}

API_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": BASE_URL,
    "Referer": BASE_URL,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "X-Requested-With": "XMLHttpRequest",
}

scraper = Scraper(headers=HEADERS)

class HiperDexSource:
    sf = "hdx"
    url = BASE_URL

    # ---------------- SEARCH ---------------- #

    @classmethod
    async def search(cls, query):
        api_url = f"{BASE_URL}/wp-admin/admin-ajax.php"
        params = {
            "action": "wp-manga-search-manga",
            "title": query
        }

        data = urlencode(params, quote_via=quote)
        headers = API_HEADERS.copy()
        headers["Content-Length"] = str(len(data))

        api_scraper = Scraper(headers=headers)
        res = await api_scraper.post(api_url, data=data, rjson=True)
        if not res:
            return []
        
        results = []
        for item in res.get("data", []) if res else []:
            results.append({
                "title": item.get("title"),
                "url": item.get("url"),
                "thumbnail": item.get("img"),
            })

        return results

    # ---------------- INFO ---------------- #

    @classmethod
    async def get_chapters(cls, data: dict):
        results = data.copy()
    
        html = await scraper.get(results['url'], cs=True, timeout=60)
        if not html:
            return results
        
        soup = BeautifulSoup(html, "html.parser")

        # Cover
        cover = None
        img = soup.select_one("div.summary_image img")
        if img:
            cover = img.get("src") or img.get("data-src")
            if cover and str(cover).startswith("/"):
                cover = urljoin(BASE_URL, str(cover))
                results['poster'] = cover

        # Summary
        summary = "N/A"
        desc = soup.select_one(".description-summary")
        if desc:
            summary = desc.get_text(" ", strip=True)

        # Genres
        genres = "N/A"
        genres_div = soup.select_one(".genres-content")
        if genres_div:
            genres = ", ".join([a.get_text(strip=True) for a in genres_div.find_all("a")])

        results['msg'] = DEAULT_MSG_FORMAT.format(
            title=results['title'],
            poster=results['poster'],
            summary=summary,
            genres=genres,
            status="N/a",
            url=results['url']
        )
        
        # Chapters (AJAX)
        results['chapters'] = []
        ajax_url = results['url'].rstrip("/") + "/ajax/chapters"
        
        headers = HEADERS.copy()
        headers["x-requested-with"] = "XMLHttpRequest"

        ajax_scraper = Scraper(headers=headers)
        ajax_html = await ajax_scraper.post(ajax_url)

        if not ajax_html:
            return results
        
        bs = BeautifulSoup(ajax_html, "html.parser")
        for a in bs.find_all("a"):
            try:
                href = a.get("href")
                title_txt = a.get_text(strip=True)
                if href and str(href).startswith(BASE_URL):
                    results['chapters'].append((title_txt, href))
            except Exception:
                continue
        
        return results
    
    @classmethod
    def iter_chapters(cls, data, page: int=1):
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
        for div in soup.find_all("div", class_="page-break no-gaps"):
            img = div.find("img")
            if not img:
                continue
            
            src = img.get("src")
            if src:
                images.append(src.strip())

        return images