# Code By @V_Sbotmaker (on Telegram)

from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import json

from .scraper import Scraper
from .utitls import DEAULT_MSG_FORMAT

BASE_URL = "https://manhwahentai.io"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"}

class ManhwaHentaiSource:
    sf = "mh.io"
    url = BASE_URL

    @classmethod
    async def search(cls, query):
        search_url = f"https://manhwahentai.io/search?keyword={quote_plus(query)}"
        html = await Scraper(headers=HEADERS).get(search_url,  timeout=60)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for item in soup.select("#all-items .item"):
            tag = item.select_one(".item-right a")
            if not tag:
                continue

            title = tag.get_text(strip=True)
            manga_u = tag.get("href", "")
            manga_url = f"https://manhwahentai.io{manga_u}"
            results.append({
                "title": title,
                "url": manga_url
            })
        return results

    @classmethod
    async def get_chapters(cls, data: dict, page: int = 1):
        html = await Scraper(headers=HEADERS).get(data['url'])
        if not html:
            return data

        results = data.copy()
        soup = BeautifulSoup(html, "html.parser")
        
        # Cover
        cover = None
        cover_tag = soup.find("div", class_="thumb-block")
        if cover_tag:
            img_tag = cover_tag.find("img")
            if img_tag:
                cover = img_tag.get("data-src") or img_tag.get("src")
                results['poster'] = cover


        # Status and Released
        status = "N/A"
        box = soup.find("div", class_="post-meta")
        if box:
            for div in box.find_all("div", class_="meta-item"):
                span = div.find("span")
                if not span:
                    continue

                label = div.get_text(separator=" ", strip=True).lower()
                value = span.get_text(strip=True)

                if "status" in label:
                    status = value

        # Summary
        summary = "N/A"
        desc_tag = soup.find("div", class_="desc-show2")
        if desc_tag:
            summary = desc_tag.get_text(strip=True).strip()

        results['msg'] = DEAULT_MSG_FORMAT.format(
            title=data['title'],
            status=status, genres="N/A",
            summary=summary,
            url=results['url']
        )
        
        # Chapters
        chapters = []
        chap_div = soup.find("div", class_="chapter-list")
        if chap_div:
            for li in chap_div.find_all("li"):
                try:
                    a = li.find("a")
                    if not a:
                        continue
                    
                    chu = str(a["href"]).strip()
                    ch_url = BASE_URL + chu
                    ch_tag = a.find("div", class_="chapter-name")
                    ch_title = ch_tag.get_text(strip=True)
                    
                    chapters.append((ch_title, ch_url)) 
                except Exception:
                    continue
            
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
    
    @classmethod
    async def get_pictures(cls, chapter_url, data: dict = {}):
        html = await Scraper(headers=HEADERS).get(chapter_url, timeout=60)
        if not html:
            return html
        
        soup = BeautifulSoup(html, "html.parser")
        images = []
        for script in soup.find_all("script"):
            if not script:
                continue
            
            if script.string and "read_image_list" in script.string:
                js = script.string
                
                start = js.find("[")
                end = js.find("]") + 1
                
                images = json.loads(js[start:end])
        
        return images