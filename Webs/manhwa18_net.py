# Code By @V_Sbotmaker (on Telegram)

from bs4 import BeautifulSoup
from urllib.parse import quote_plus, quote
import re
import json

from loguru import logger
from .scraper import Scraper
from .utitls import DEAULT_MSG_FORMAT


BASE_URL = "https://manhwa18.net"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "referer": BASE_URL + "/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "x-requested-with": "XMLHttpRequest",
}

scraper = Scraper(headers=HEADERS)

class Manhwa18NetSource:
    sf = "m.nt"
    url = BASE_URL

    # ---------------- SEARCH ---------------- #

    @classmethod
    async def search(cls, query):
        url = f"{BASE_URL}/action/search?q={quote_plus(query)}"
        data = await scraper.get(url, rjson=True, timeout=60)
        if not data:
            return []
        
        results = []
        for item in data.get("data", []) if data else []:
            
            item['title'] = item.pop("name")
            item['poster'] = item.pop("cover_url")
            item['url'] = BASE_URL + "/manga/" + item.pop("slug")
            results.append(item)

        return results

    # ---------------- INFO ---------------- #

    @classmethod
    async def get_chapters(cls, data, page: int = 1) -> dict:
        headers = HEADERS.copy()
        headers["referer"] = data['url']
        
        html = await Scraper(headers=headers).get(data['url'], timeout=60)
        if not html:
            return []
        
        results = data.copy()
        soup = BeautifulSoup(html, "html.parser")
        
        div_element = soup.find('div', id='app')
        if not div_element:
            return results
        
        data_page = div_element.get('data-page')
        if not data_page:
            return results

        c_data = json.loads(data_page)
        
        manga_info = c_data['props']['manga']
        
        results['title'] = manga_info['name']
        results['poster'] = manga_info['cover_url']

        summary = manga_info.get("pilot", "N/A")
        genres = manga_info.get("genres", [])
        genres = ", ".join([genre['name'] for genre in genres]) if genres else "N/A"
        status = manga_info.get("status_id", "N/A")
        results['msg'] = DEAULT_MSG_FORMAT.format(
            title=results['title'],
            url=results['url'],
            summary=summary,
            genres=genres,
            status=status,
        )
        
        chapters = c_data['props']['chapters']
        results['chapters'] = []
        for i in chapters:
            results['chapters'].append((
                i['name'], 
                results['url'] + "/" + i['slug']
            ))
        
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
        headers = HEADERS.copy()
        headers["referer"] = chapter_url

        html = await Scraper(headers=headers).get(chapter_url, cs=True)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")

        div_element = soup.find('div', id='app')
        if not div_element:
            return []

        data_page = div_element.get('data-page')
        if not data_page:
            return []

        c_data = json.loads(data_page)
        
        chapterContent = c_data['props']['chapterContent']
        
        image_urls = re.findall(r'src="(https?://[^"]+\.jpe?g)"', str(chapterContent), re.IGNORECASE)

        return [img.strip() for img in image_urls]