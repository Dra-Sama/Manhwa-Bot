# Code By @V_Sbotmaker (on Telegram)
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin

from Webs.utitls import DEAULT_MSG_FORMAT

from .scraper import Scraper


BASE_URL = "https://mangadass.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Referer": BASE_URL + "/",
    "Origin": BASE_URL,
}

_PAGE_CLASS_RE = re.compile(r"^p(\d+)$", re.I)
_ALLOWED_PATH_RE = re.compile(r"/(uploads|chapters)/", re.I)
_IMG_EXT_RE = re.compile(r"\.(jpg|jpeg|png|webp)(?:\?|$)", re.I)

class MangaDassWebs:
    sf = "md-s"
    url = BASE_URL

    @staticmethod
    def _abs_url(href: str) -> str:
        if not href:
            return href
        return urljoin(BASE_URL, href)

    @staticmethod
    def _clean_text(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "")).strip()

    @classmethod
    async def search(cls, query: str):
        search_url = f"{BASE_URL}/s"
        payload = {"search_query": query}
        
        data = await Scraper( headers={
            **HEADERS, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        } ).post(
            search_url, timeout=60, data=payload,
        )

        results = []
        if isinstance(data, list):
            for it in data:
                name = (it.get("name") or "").strip()
                slug = (it.get("slug") or "").strip()

                if not slug and not name:
                    continue
                
                manga_url = f"{BASE_URL}/manga/{slug}" if slug else None

                results.append(
                    {
                        "title": name,
                        "url": manga_url
                    }
                )

        return results

    @classmethod
    async def get_chapters(cls, data: dict, page: int = 1):
        results = data.copy()
        
        html = await Scraper(headers=HEADERS).get(data["url"])
        if not html:
            return results
        
        soup = BeautifulSoup(html, "html.parser")

        # Title
        title = None
        h1 = soup.select_one(".post-title h1")
        if h1:
            title = cls._clean_text(h1.get_text(" ", strip=True))
        if not title:
            bc_active = soup.select_one("ol.breadcrumb a.active")
            if bc_active:
                title = cls._clean_text(bc_active.get_text(" ", strip=True))
        if not title:
            ogt = soup.select_one('meta[property="og:title"]')
            if ogt:
                title = cls._clean_text(ogt.get("content"))
        if not title:
            tt = soup.select_one("title")
            if tt:
                title = cls._clean_text(tt.get_text(strip=True))
        
        if title:
            results['title'] = title

        # Cover
        cover = None
        ogi = soup.select_one('meta[property="og:image"]')
        if ogi:
            cover = str(ogi.get("content"))
        
        if cover:
            if cover.startswith("//"):
                cover = "https:" + cover
            elif cover.startswith("/"):
                cover = cls._abs_url(cover)
            
            results['poster'] = cover

        # Summary
        summary = "N/A"
        ss = soup.select_one(".panel-story-description .ss-manga")
        if ss:
            summary = cls._clean_text(ss.get_text(" ", strip=True))
        else:
            desc = soup.select_one('meta[name="description"]')
            if desc:
                summary = cls._clean_text(str(desc.get("content")))

        # Genres
        genres = []
        for a in soup.select(".genres-content a"):
            g = cls._clean_text(a.get_text(" ", strip=True))
            if g:
                genres.append(g)
        genres = ", ".join(genres)

        # Status
        status = "N/A"
        for item in soup.select(".post_status .post-content_item"):
            h5 = item.select_one(".summary-heading h5")
            if not h5:
                continue
            if cls._clean_text(h5.get_text(" ", strip=True)).lower() == "status":
                val = item.select_one(".summary-content")
                if val:
                    status = cls._clean_text(val.get_text(" ", strip=True))
                break
        
        results['msg'] = DEAULT_MSG_FORMAT.format(
            title=results['title'], 
            summary=summary, genres=genres, status=status, 
            url=results['url']
        )
        
        results['chapters'] = []
        seen = set()
        for a in soup.select(".panel-manga-chapter ul.row-content-chapter a.chapter-name[href]"):
            href = a.get("href")
            if not href:
                continue
            ch_url = cls._abs_url(str(href))
            ch_title = cls._clean_text(a.get_text(" ", strip=True))
            if ch_url in seen:
                continue
            
            seen.add(ch_url)
            results['chapters'] .append((ch_title, ch_url))
        
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
    
    @classmethod
    async def get_pictures(cls, chapter_url: str, data: dict = {}):
        
        html = await Scraper(headers=HEADERS).get(chapter_url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
    
        pages = []
        seen = set()
    
        for img in soup.select("div.read-content.wleft img"):
            src = str(img.get("data-src")) or str(img.get("src"))
            if not src:
                continue
    
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = cls._abs_url(src)
    
            if not src.startswith("http"):
                continue
            
            if not _IMG_EXT_RE.search(src):
                continue
            if not _ALLOWED_PATH_RE.search(src):
                continue
    
            page_no = None
            for c in (img.get("class") or []):
                m = _PAGE_CLASS_RE.match(c)
                if m:
                    page_no = int(m.group(1))
                    break
    
            if src in seen:
                continue
            
            seen.add(src)
    
            pages.append((page_no if page_no is not None else 10**9, src))
    
        pages.sort(key=lambda x: x[0])
        
        return [u for _, u in pages]


    @classmethod
    def chapter_url(cls, slug: str, chapter_slug: str) -> str:
        return f"{BASE_URL}/manga/{slug.strip('/')}/{chapter_slug.strip('/')}"
