# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus
import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT

class ManhuaFastWebs(Scraper):
    def __init__(self):
        super().__init__()
        self.url = "https://manhuafast.net/"
        self.bg = None
        self.sf = "mufa"
        self.headers = {
            "Connection": "keep-alive",
            "Host": "manhuafast.net",
            "Referer": "https://manhuafast.net/",
            "sec-ch-ua": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "Windows",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        }

    async def search(self, query: str = ""):
        url = f"https://manhuafast.net/?s={quote_plus(query)}&post_type=wp-manga&post_type=wp-manga"
        try:
            mangas = await self.get(url, headers=self.headers)
        except:
            try:
                mangas = await self.get(url, cs=True, headers=self.headers)
            except:
                return []

        bs = BeautifulSoup(mangas, "html.parser")
        con = bs.find(class_="tab-content-wrap")
        if not con:
            return []
        cards = con.find_all("div", class_="row c-tabs-item__content")
        results = []
        for card in cards:
            data = {}
            a_tag = card.find_next("a")
            if a_tag:
                data['url'] = a_tag.get('href', '').strip()
            
            img_tag = card.find_next("img")
            if img_tag:
                data['poster'] = img_tag.get('data-src', img_tag.get('src', '')).strip()
            
            h3_tag = card.find_next('h3')
            if h3_tag:
                data['title'] = h3_tag.text.strip()

            if data.get('url') and data.get('title'):
                results.append(data)
        
        return results

    async def get_chapters(self, data, page: int = 1):
        results = data
        try:
            content = await self.get(results['url'], headers=self.headers)
            if content:
                bs = BeautifulSoup(content, "html.parser")
                con = bs.find(class_="summary_content_wrap")
                
                if con:
                    generes = con.find_next(class_="genres-content")
                    generes = ", ".join([g.text.strip() for g in generes.find_all("a")]) if generes else "N/A"
                else:
                    generes = "N/A"
                
                des_tag = bs.find(class_="summary__content show-more")
                des = des_tag.text.strip() if des_tag else "N/A"
                
                results['msg'] = DEAULT_MSG_FORMAT.format(
                    title=results.get('title', 'N/A'),
                    status="N/A",
                    genres=generes,
                    summary=des[:200] if des else "N/A",
                    url=results['url']
                )
        except Exception as e:
            logger.warning(f"Error getting manga details: {e}")
            results['msg'] = DEAULT_MSG_FORMAT.format(
                title=results.get('title', 'N/A'),
                status="N/A",
                genres="N/A",
                summary="N/A",
                url=results['url']
            )
            
        try:
            ajax_url = f"{results['url']}ajax/chapters/"
            chapters = await self.post(ajax_url, headers=self.headers)
            if not chapters:
                chapters = await self.post(ajax_url, data={}, headers=self.headers)
        except Exception as e:
            logger.warning(f"First POST attempt failed: {e}")
            try:
                chapters = await self.post(f"{results['url']}ajax/chapters/", cs=True, headers=self.headers)
            except Exception as e2:
                logger.error(f"Second POST attempt failed: {e2}")
                chapters = None
        
        results['chapters'] = chapters if chapters else []

        return results

    def iter_chapters(self, data, page: int = 1):
        chapters_list = []
        
        if not data.get('chapters'):
            return chapters_list
            
        try:
            bs = BeautifulSoup(data['chapters'], "html.parser")
            cards = bs.find_all("a")
            for card in cards:
                link = card.get("href", "")
                if link and link.startswith("https://manhuafast.net/manga"):
                    chapters_list.append({
                        "title": card.text.strip(),
                        "url": link,
                        "manga_title": data.get('title', 'Unknown'),
                        "poster": data.get('poster'),
                    })
        except Exception as e:
            logger.error(f"Error parsing chapters: {e}")
        
        if page == 1:
            return chapters_list
        return chapters_list[(page - 1) * 60:page * 60]

    async def get_pictures(self, url, data=None):
        try:
            response = await self.get(url, headers=self.headers)
            if not response:
                return []
                
            bs = BeautifulSoup(response, "html.parser")

            div_tags = bs.find(class_="reading-content")
            if not div_tags:
                logger.warning(f"reading-content not found for {url}")
                div_tags = bs.find("div", class_=re.compile("reading-content|chapter-content"))
            
            if not div_tags:
                return []
                
            imgs_tags = div_tags.find_all(class_="page-break no-gaps")
            
            if not imgs_tags:
                imgs_tags = div_tags.find_all(class_="page-break")
            if not imgs_tags:
                imgs_tags = div_tags.find_all("img", class_=re.compile("wp-manga-chapter-img|chapter-img"))
            if not imgs_tags:
                imgs_tags = div_tags.find_all("img")
            
            image_links = []
            for img in imgs_tags:
                img_tag = img.find_next('img') if img.name != 'img' else img
                if img_tag:
                    image_url = img_tag.get('data-src') or img_tag.get('src') or img_tag.get('data-lazy-src')
                    if image_url:
                        image_url = image_url.strip()
                        image_url = image_url.replace('https:///', 'https://')
                        image_url = image_url.replace('http:///', 'http://')
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        image_links.append(image_url)
            
            return image_links
        except Exception as e:
            logger.error(f"Error getting pictures from {url}: {e}")
            return []

    async def get_updates(self, page: int = 1):
        output = []
        current_page = page
        while current_page < page + 4:  
            url = f"https://manhuafast.net/page/{current_page}/"
            try:
                results = await self.get(url, headers=self.headers)
                if not results:
                    current_page += 1
                    continue

                bs = BeautifulSoup(results, "html.parser")
                container = bs.find(class_="c-blog-listing c-page__content manga_content")
                
                if not container:
                    current_page += 1
                    continue
                    
                container = container.find(class_="c-blog__content")
                if not container:
                    current_page += 1
                    continue
                    
                mangas = container.find_all(class_="page-listing-item")
                if mangas:
                    for manga in mangas:
                        if manga:
                            cards = manga.find_all(class_="col-6 col-md-3 badge-pos-1")
                            if cards:
                                for card in cards:
                                    try:
                                        data = {}
                                        h3_tag = card.find_next("h3", {"class": "h5"})
                                        if h3_tag:
                                            a_tag = h3_tag.find_next("a")
                                            if a_tag:
                                                data['url'] = a_tag.get("href")
                                                data['manga_title'] = a_tag.text.strip()
                                        
                                        span_tag = card.find_next("span", {"class": "chapter font-meta"})
                                        if span_tag:
                                            a_tag = span_tag.find_next("a")
                                            if a_tag:
                                                data['chapter_url'] = a_tag.get("href")
                                                data['title'] = a_tag.text.strip()
                                        
                                        if data.get('url') and data.get('chapter_url'):
                                            output.append(data)
                                    except Exception as e:
                                        logger.debug(f"Error parsing update card: {e}")
                                        continue
            except Exception as e:
                logger.warning(f"Error fetching updates page {current_page}: {e}")
            
            current_page += 1
        
        return output
