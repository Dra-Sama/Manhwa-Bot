# Code By @V_Sbotmaker (on Telegram)

from Webs.utitls import DEAULT_MSG_FORMAT
from .scraper import Scraper
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, quote_plus

BASE_URL = "https://mangadistrict.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0"
}

class MangaDistrictSource:
    sf = "mdt"
    url = BASE_URL

    @classmethod
    async def search(cls, query):
        search_url = f"{BASE_URL}/?s={quote_plus(query)}&post_type=wp-manga"
        html = await Scraper(headers=HEADERS).get(search_url, timeout=60)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        results = []
        container = soup.find('div', {'class': 'tab-content-wrap'})
        
        cards = container.find_all("div", {"class": "auto-col badge-pos-2"}) if container else []
        
        for card in cards:
            try:
                a_tag = card.find("a")
                img_tag = card.find("img")
                title = a_tag.get("title") if a_tag else None
                url = a_tag.get("href") if a_tag else None
                thumbnail = img_tag.get("src") if img_tag else None
                
                results.append({
                    "title": title,
                    "url": url,
                    "poster": thumbnail
                })
            except Exception:
                continue
        
        return results

    @classmethod
    async def get_chapters(cls, data: dict, page: int = 1):
        html = await Scraper(headers=HEADERS).get(data['url'], timeout=60)
        if not html:
            return data

        results = data.copy()
        soup = BeautifulSoup(html, "html.parser")
        
        # Title
        title_tag = soup.select_one("div.post-title h1")
        title = title_tag.get_text(strip=True) if title_tag else None
        if title_tag:
            results['title'] = title
        
        # Cover
        cover_tag = soup.select_one('div.summary_image img')
        cover = str(cover_tag.get("src")) if cover_tag else None
        if cover and cover.startswith("/"):
            cover = urljoin(BASE_URL, cover)
            results['poster'] = cover

        
        # Summary
        desc_tag = soup.select_one("div.description-summary")
        summary = desc_tag.get_text(strip=True) if desc_tag else "N/A"
        
        # Genres
        genres_tag = soup.find(class_="genres-content")
        genres = "N/A"
        if genres_tag:
            genres = ", ".join([
                a.get_text(strip=True) for a in genres_tag.find_all("a")
            ])
        
        # Status
        status = "N/A"
        for post_item in soup.select('.post-content_item'):
            head = post_item.select_one('.summary-heading')
            if head and 'status' in head.get_text(strip=True).lower():
                cont = post_item.select_one('.summary-content')
                if cont:
                    status = cont.get_text(strip=True)
                    break

        results['msg'] = DEAULT_MSG_FORMAT.format(
            title=results['title'], summary=summary,
            genres=genres, status=status, url=results['url']
        )
        # Chapters
        results['chapters'] = []
        for li in soup.select("li.wp-manga-chapter"):
            a = li.find('a')
            if a:
                ch_title = a.get_text(strip=True)
                ch_url = a.get('href')
                results['chapters'].append((ch_title, ch_url))
            
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
    async def get_pictures(cls, chapter_url, data: dict = {}):
        html = await Scraper(headers=HEADERS).get(chapter_url, timeout=60)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        images = []
        content = soup.find(class_="reading-content")
        
        if content:
            for img in content.find_all("img"):
                src = str(img.get("src"))
                if src and src.startswith("http") and re.search(r'\.(jpg|jpeg|png|webp)$', src, re.I):
                    images.append(src)
        
        return images
