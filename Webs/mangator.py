# Code By @V_Sbotmaker (on Telegram)

from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import re

from .scraper import Scraper
from .utitls import DEAULT_MSG_FORMAT


BASE_URL = "https://mangator.com/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive"
    }

class MangatorSource:
    sf = "m-tr"
    url = BASE_URL

    @classmethod
    async def search(cls, query):
        search_url = f"{BASE_URL}?s={quote_plus(query)}&post_type=wp-manga"
        html = await Scraper(headers=HEADERS).get(search_url,  timeout=60)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for item in soup.select("div.page-content-listing.item-big_thumbnail div.page-listing-item"):
            a_tag = item.select_one("a")
            if not a_tag:
                continue
            
            manga_url = a_tag.get("href", "")
            
            title_tag = item.find("h3", class_="h5")
            title = title_tag.get_text().strip() if title_tag else None
            
            results.append({ "title": title, "url": manga_url })
            
        return results

    @classmethod
    async def get_chapters(cls, results, page: int = 1):
        html = await Scraper(headers=HEADERS).get(results['url'], timeout=60)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Cover
        cover = None
        cover_tag = soup.find("div", class_="summary_image")
        if cover_tag:
            img_tag = cover_tag.find("img")
            if img_tag:
                cover = img_tag.get("data-src") or img_tag.get("src")
                results['poster'] = cover


        # Genres
        genres = []
        tbox = soup.find("div", class_="genres-content")
        if tbox:
            for a in tbox.find_all("a"):
                genres.append(a.get_text(strip=True))
        
        genres = ", ".join(genres)

        # Status
        status = ""
        status_box = soup.find("div", class_="post-status")
        if status_box:
            for div in status_box.find_all("div", class_="post-content_item"):
                
                 div_lable = div.find("div", class_="summary-heading")
                 lable = div_lable.get_text(strip=True).lower() if div_lable else ""
                 
                 if "status" in lable:
                    status_tag = div.find("div", class_="summary-content")
                    status = status_tag.get_text(strip=True) if status_tag else ""
                     

        # Summary
        summary = "N/A"
        desc_tag = soup.find("div", class_="summary__content")
        desc_p = desc_tag.find_all("p")
        summary = ""
        for p in desc_p:
            summary += p.get_text(strip=True) + "\n"
        
        summary = summary.strip()
        results['msg'] = DEAULT_MSG_FORMAT.format(
            title=results['title'],
            summary=summary[:300],
            genres=genres,
            status=status,
            url=results['url']
        )
        
        # Chapters
        results['chapters'] = []
        
        series_path = results['url'].replace(BASE_URL, "").strip("/")
        ajax_url = f"{BASE_URL}{series_path}/ajax/chapters/?t=1"
        
        ajax_html = await Scraper(headers=HEADERS).post(ajax_url, data={}, timeout=60)
        if not ajax_html:
            return results
        
        ajax_soup = BeautifulSoup(ajax_html, "html.parser")
        
        for li in ajax_soup.select("li.wp-manga-chapter"):
            a = li.find("a")
            if not a:
                continue
        
            ch_title = a.get_text(strip=True)
            ch_url = str(a["href"]).strip()
            
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
        for img in soup.select('div.reading-content div.page-break'):
            src = img.find("img").get("src") or img.find("img").get("data-src")
            if src:
                images.append(src)
        
        return images
