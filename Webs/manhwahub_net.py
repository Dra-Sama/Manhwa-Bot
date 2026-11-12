# Code By @V_Sbotmaker (on Telegram)

import json
import re
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin

from .scraper import Scraper
from .utitls import DEAULT_MSG_FORMAT

BASE_URL = "https://manhwahub.net"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": BASE_URL + "/",
}
SUGGEST_HEADERS = {
    **HEADERS,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

scraper = Scraper(headers=HEADERS)

class ManhwaHubSource:
    sf = "mh.n"
    url = BASE_URL

    # ---------------- SEARCH ---------------- #
    @classmethod
    async def search(cls, query):
        q = quote(query)
        api_url = f"{BASE_URL}/suggest?name={q}"

        api_scraper = Scraper(headers=SUGGEST_HEADERS)
        raw = await api_scraper.get(api_url, timeout=60)
        if not raw:
            return []
        
        try:
            payload = json.loads(raw)
        except Exception:
            m = re.search(r"(\{.*\})", raw, flags=re.S)
            payload = json.loads(m.group(1)) if m else {}

        html = payload.get("data") or None
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")

        results = []
        for card in soup.select(".page-item-detail"):
            a = card.select_one("a[href]")
            if not a:
                continue

            url = a.get("href", None)
            if not url:
                continue
            
            url = str(url)
            if url.startswith("/"):
                url = urljoin(BASE_URL, url)

            title = a.get("title") or a.get_text(" ", strip=True)

            if title and url:
                results.append(
                    {
                        "title": str(title).strip(),
                        "url": url.strip(),
                    }
                )

        return results

    # ---------------- INFO ---------------- #
    @classmethod
    async def get_chapters(cls, data, page: int = 1):
        html = await scraper.get(data['url'], timeout=60)
        if not html:
            return data

        results = data.copy()
        soup = BeautifulSoup(html, "html.parser")

        # Cover
        cover = None
        og = soup.select_one("meta[property='og:image']")
        if og and og.get("content"):
            cover = og.get("content").strip()
        
        if not cover:
            img = soup.select_one(".summary_image img")
            if img and img.get("src"):
                cover = str(img.get("src")).strip()
                
                if cover.startswith("/"):
                    cover = urljoin(BASE_URL, cover)
        if cover:
            results['poster'] = cover

        # Summary
        summary = "N/A"
        
        sum_div = soup.select_one("div.description-summary div.summary__content")
        if sum_div:
            ps = [p.get_text(" ", strip=True) for p in sum_div.select("p")]
            summary = "\n".join([t for t in ps if t]).strip() or None
        
        if not summary:
            meta_desc = soup.select_one("meta[name='description']")
            if meta_desc and meta_desc.get("content"):
                summary = meta_desc.get("content").strip()

        # Status
        status = "N/A"
        for item in soup.select(".post-content_item"):
            h5 = item.select_one(".summary-heading h5")
            val = item.select_one(".summary-content")
            if not h5 or not val:
                continue
            key = h5.get_text(strip=True).lower()
            if key == "status":
                status = val.get_text(" ", strip=True)
                break

        # Genres
        genres = []
        genres_div = soup.select_one(".genres-content")
        if genres_div:
            for a in genres_div.select("a"):
                g = a.get_text(strip=True)
                if g and g not in genres:
                    genres.append(g)
        
        genres = ", ".join(genres)

        results['msg'] = DEAULT_MSG_FORMAT.format(
            title=results['title'],
            summary=summary,
            genres=genres,
            status=status,
            url=results['url']
        )
        
        chapters = []
        for a in soup.select("ul.main.version-chap li a[href]"):
            ch_title = a.get_text(strip=True)
            ch_url = a.get("href")
            
            if ch_url and str(ch_url).startswith("/"):
                ch_url = urljoin(BASE_URL, str(ch_url))
            
            if ch_title and ch_url:
                chapters.append((ch_title, ch_url))

        if not chapters:
            for a in soup.select("li.wp-manga-chapter a[href]"):
                ch_title = a.get_text(strip=True)
                ch_url = a.get("href")
                
                if ch_url and str(ch_url).startswith("/"):
                    ch_url = urljoin(BASE_URL, str(ch_url))
                
                if ch_title and ch_url:
                    chapters.append((ch_title, ch_url))

        results['chapters'] = chapters

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
        reader = soup.select_one("div.reading-content") or soup.select_one(".reading-content")
        if not reader:
            return images

        for img in reader.select("img"):
            src = img.get("data-src") or img.get("data-lazy-src") or img.get("src")
            if not src:
                continue
            
            src = str(src).strip()
            if src.startswith("//"):
                src = "https:" + src
                
            elif src.startswith("/"):
                src = urljoin(BASE_URL, src)
                
            if src.startswith("http"):
                images.append(src)

        return images
