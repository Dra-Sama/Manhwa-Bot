# Code By @V_Sbotmaker (on Telegram)
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import re
from .scraper import Scraper
from .utitls import DEAULT_MSG_FORMAT


BASE_URL = "https://w1.hotcomics.me/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"}

scraper = Scraper(headers=HEADERS)

class HotComicsWebs:
    sf = "htcs"
    url = BASE_URL

    @classmethod
    async def search(cls, query):
        search_url = f"https://w1.hotcomics.me/en/search?keyword={quote_plus(query)}"
        html = await scraper.get(search_url, timeout=60)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for item in soup.select("div.list-wrap ul.normal li"):
            a_tag = item.select_one("a")
            if not a_tag:
                continue
            
            manga_url = a_tag.get("href", "")
            img_tag = a_tag.find("img")
            
            thumbnail = img_tag.get("src") if img_tag else None
            title_tag = item.find("h4", class_="title")
            title = title_tag.get_text().strip() if title_tag else None
            
            results.append({
                "title": title,
                "url": manga_url,
                "poster": thumbnail
            })
        return results

    @classmethod
    async def get_chapters(cls, data, page: int = 1):
        results = data.copy()
        
        html = await scraper.get(results['url'], timeout=60)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        box = soup.find("div", class_="title_content")
        
        # Cover
        cover = None
        inner_ch_div = soup.find("div", class_="inner_ch")
        if inner_ch_div:
            style = inner_ch_div.get("style")
            if style:
                match = re.search(r"url\(['\"]([^'\"]+)['\"]\)", str(style))
                if match:
                    cover = match.group(1)
                    results['poster'] = cover
                


        # Genres
        genres = "N/A"
        type_box = box.find("p", class_="type_box")
        if type_box:
            type_span = type_box.find("span", class_="type")
            if type_span:
                genres_text = type_span.get_text()
                genres = ", ".join([g.strip() for g in genres_text.split(" / ") if g.strip()])

        # Status
        status = "N/A"
        if type_box:
            date_span = type_box.find("span", class_="date")
            if date_span:
                date_text = date_span.get_text(strip=True)
                if date_text == "End":
                    status = "Finished"

        # Summary
        summary = "N/A"
        desc_span = box.find("span", class_="desc-text")
        if desc_span:
            summary = desc_span.get_text(strip=True)

        results['msg'] = DEAULT_MSG_FORMAT.format(
            title=results['title'],
            summary=summary,
            genres=genres,
            status=status,
            url=results['url']
        )
        
        # Chapters
        results['chapters'] = []
        chapter_list = soup.find("ol", class_="list-ep")
        if chapter_list:
            for li in chapter_list.find_all("li"):
                a = li.find("a")
                if a:
                    num_span = li.find("span", class_="num")
                    num = num_span.get_text(strip=True) if num_span else ""
                    
                    ch_title = f"Episode {num}" if num else ""
                    onclick = a.get("onclick", "")
                    match = re.search(r"popupLogin\('([^']+)'", str(onclick))
                    
                    ch_url = match.group(1) if match else ""
                    if ch_title and ch_url:
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
        html = await scraper.get(chapter_url, timeout=60)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        
        images = []
        for img in soup.select('div.viewer-imgs div.lazy'):
            src = img.find("img").get("src") or img.find("img").get("data-src")
            if src:
                images.append(src)
        
        return images
