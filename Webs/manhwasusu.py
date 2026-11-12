# Code By @V_Sbotmaker (on Telegram)
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re

from .scraper import Scraper
from .utitls import DEAULT_MSG_FORMAT

BASE_URL = "https://manhwasusu.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.8",
    "Connection": "keep-alive",
}

def _abs(url: str) -> str:
    if not url:
        return url
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(BASE_URL, url)
    return url

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def _extract_chapters_from_chapter_list(soup: BeautifulSoup):
    chapter_h1 = None
    for h1 in soup.find_all("h1"):
        txt = h1.get_text(" ", strip=True).lower()
        if "chapter" in txt and "list" in txt:
            chapter_h1 = h1
            break
    if not chapter_h1:
        return []

    list_div = chapter_h1.find_next(
        "div",
        class_=lambda c: c and "overflow-y-auto" in c
    )
    if not list_div:
        return []

    out = []
    seen = set()

    for a in list_div.find_all("a", href=True):
        href = (a.get("href") or "").strip()

        if not re.search(r"^/read/[^/]+/chapter-[^/]+/?$", href, re.I):
            continue

        url = _abs(href)
        if url in seen:
            continue
        seen.add(url)

        title_p = a.select_one("div > p")
        title = _clean(title_p.get_text(" ", strip=True) if title_p else "")

        if not title:
            slug = href.rstrip("/").split("/")[-1]
            title = _clean(slug.replace("-", " ").title())

        out.append((title, url))

    return out

class ManhwaSusuSource:
    sf = "su.c"
    url = BASE_URL

    @classmethod
    async def search(cls, query: str):
        q = quote(query.strip())
        search_url = f"{BASE_URL}/search/{q}/"
    
        html = await Scraper(headers=HEADERS).get(search_url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        results = []
    
        for card in soup.select('div.overflow-hidden.rounded-lg'):
            a = card.select_one('h2 a[href^="/read/"]') or card.select_one('a[href^="/read/"]')
            if not a:
                continue
    
            href = (a.get("href") or "").strip()
            if not href.startswith("/read/"):
                continue
    
            url = _abs(href)
    
            if re.search(r"/read/[^/]+/chapter", url, re.I):
                continue
    
            title = _clean(a.get_text(" ", strip=True))
    
            if not title:
                img = card.select_one("img[alt]")
                if img and img.get("alt"):
                    title = _clean(str(img["alt"]))
    
            if not title:
                continue
    
            results.append({"title": title, "url": url})
    
        uniq = {}
        for r in results:
            uniq[r["url"]] = r
        
        return list(uniq.values())

    @classmethod
    async def get_chapters(cls, data: dict, page: int = 1):
        html = await Scraper(headers=HEADERS).get(data['url'])
        if not html:
            return data

        results = data.copy()
        soup = BeautifulSoup(html, "html.parser")

        summary = ""
        for div in soup.select("div.mt-4.w-full"):
            if div.find("p"):
                parent_text = " ".join((div.parent.get("class") or []))
                if "chapter" in parent_text.lower():
                    continue
                summary = _clean(div.get_text(" ", strip=True))
                if summary:
                    break

        cover = None
        mi = soup.select_one('meta[property="og:image"]')
        if mi and mi.get("content"):
            cover = _abs(mi["content"].strip())

        status = None
        status_div = soup.select_one("div.bg-green-800")
        if status_div:
            status = status_div.get_text(" ", strip=True).lower()
        if status == "end":
            status = "Finished"
        elif status == "on-going":
            status = "On-Going"
    
        genres = []

        for ga in soup.select('a[href*="/genre/"], a[href*="/genres/"]'):
            g = _clean(ga.get_text(" ", strip=True))
            if g and g.lower() not in {"genre", "genres"}:
                genres.append(g)
            
        genres = list(dict.fromkeys(genres))
        
        genres = ", ".join(genres)
        results['msg'] = DEAULT_MSG_FORMAT.format(
            title=data['title'],
            summary=summary,
            cover=cover,
            status=status,
            genres=genres,
            url=data['url']
        )
        
        results['chapters'] = _extract_chapters_from_chapter_list(soup)
        
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
    
    @classmethod
    async def get_pictures(cls, chapter_url: str, data: dict = {}):
        html = await Scraper(headers=HEADERS).get(chapter_url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
    
        images = []
        wrap = soup.find("div", class_=lambda c: c and "mx-auto" in c and "min-h-screen" in c)
        if not wrap:
            return []
    
        for img in wrap.select("img[data-src]"):
            src = (img.get("data-src") or "").strip()
            if not src:
                continue
            if "readerarea.svg" in src or src.endswith(".svg"):
                continue
            images.append(_abs(src))
    
        out, seen = [], set()
        for u in images:
            if u not in seen:
                seen.add(u)
                out.append(u)
                
        return out
