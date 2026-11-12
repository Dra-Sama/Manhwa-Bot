# Code By @V_Sbotmaker (on Telegram)


from .scraper import Scraper, shared_scraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus, quote
import re
import json
from loguru import logger
from .utitls import T_MSG_FORMAT
import random

def get_worker_url() -> str:
  return random.choice([
      "https://holy-credit-da93.lajosip431.workers.dev/proxy?url=",
      "https://odd-leaf-f894.shanksshanks-12222.workers.dev/proxy?url="
  ])

def create_link(url: str) -> str:
    return get_worker_url() + quote(url)

class ThunderScansWebs:
    url = "https://en-thunderscans.com"
    sf = "tsc"
    headers = {
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
    }
    
    async def search(self, query: str = ""):
        url = f"{self.url}/?s={quote_plus(query)}"
        requests_url = get_worker_url() + quote(url)
        
        text = await shared_scraper.get(requests_url, headers=self.headers, cs=True)
        if not text:
            return []
        
        soup = BeautifulSoup(text, "html.parser")
        results = []
        cards = soup.select("div.bs, div.bsx, div.listupd article")
        for card in cards:
            a = (card.select_one("a[href*='/comics/']") or
                 card.select_one("a.series") or
                 card.select_one("a"))
            if not a:
                continue
            
            title_elem = (card.select_one("div.tt") or
                         card.select_one("h2") or
                         card.select_one("h3") or
                         card.select_one("a.series"))
        
            title = title_elem.get_text(strip=True) if title_elem else ""
            if not title:
                img = card.select_one("img")
                if img:
                    title = img.get("alt", "").strip()
            
            url = str(a.get("href", ""))
            if url and not url.startswith("http"):
                url = urljoin(self.url, url)
            
            thumbnail = ""
            img = card.select_one("img")
            if img:
                thumbnail = (img.get("src", "") or
                           img.get("data-src", "") or
                           img.get("data-lazy-src", ""))
            
                if thumbnail and not str(thumbnail).startswith("http"):
                    thumbnail = urljoin(self.url, str(thumbnail))
            
            if title and url:
                results.append({
                    "title": title,
                    "url": url,
                    "poster": create_link(thumbnail) if isinstance(thumbnail, str) else None 
                })
        
        return results
    async def get_chapters(self, data, page: int = 1):
        results = data.copy()

        request_url = get_worker_url() + quote(results['url'])
        content = await shared_scraper.get(request_url, headers=self.headers, cs=True)
        if not content:
            return results
        
        soup = BeautifulSoup(content, "html.parser")
        summary = None
        synopsis_selectors = [
            "div.entry-content p",
            "div.summary__content p",
            "div.desc p",
            "div.synops p",
            "[itemprop='description']"
        ]
        for selector in synopsis_selectors:
            elements = soup.select(selector)
            if elements:
                summary = "\n".join([p.get_text(strip=True) for p in elements if p.get_text(strip=True)])
                if summary:
                    break
        if not summary:
            meta = soup.find("meta", attrs={"name": "description"})
            if meta:
                summary = meta.get("content", "").strip()
        status = None
        status_selectors = [
            "div.post-status div.summary-content",
            "div.tsinfo div.imptdt:contains('Status') i",
            "span.status",
            "[class*='status']"
        ]
        for selector in status_selectors:
            elem = soup.select_one(selector)
            if elem:
                status = elem.get_text(strip=True)
                break
        if not status:
            text_content = soup.get_text()
            if "Ongoing" in text_content:
                status = "Ongoing"
            elif "Completed" in text_content:
                status = "Completed"
        language = "English"
        genres = []
        genre_selectors = [
            "div.genres-content a",
            "div.mgen a",
            "span.mgen a",
            "div.genre a"
        ]
        for selector in genre_selectors:
            elements = soup.select(selector)
            if elements:
                genres = [a.get_text(strip=True) for a in elements if a.get_text(strip=True)]
                if genres:
                    break
        
        genres = ", ".join(genres) if genres else "N/A"
        
        cover_url = results.get('poster', '')
        if not cover_url:
            img_selectors = [
                "div.summary_image img",
                "div.thumb img",
                "img.wp-post-image"
            ]
            for selector in img_selectors:
                img = soup.select_one(selector)
                if img:
                    cover_url = (img.get("src", "") or
                               img.get("data-src", "") or
                               img.get("data-lazy-src", ""))
                    if cover_url:
                        if not str(cover_url).startswith("http"):
                            cover_url = urljoin(self.url, str(cover_url))
                        break
        if cover_url:
            results['poster'] = create_link(cover_url) if isinstance(cover_url, str) else None
        
        results['chapters'] = []
        chapter_items = soup.select("div.eplister ul li")
        for li in chapter_items:
            a = li.select_one("a")
            if not a:
                continue
            if a.get("data-bs-toggle") == "modal":
                continue
            href = a.get("href", "")
            if not href:
                continue
            chapter_url = urljoin(self.url, href)
            name_elem = li.select_one("span.chapternum")
            name = name_elem.get_text(strip=True) if name_elem else a.get_text(strip=True)
            if name:
                results['chapters'].append({
                    'name': name,
                    'url': chapter_url
                })
        
        seen = set()
        unique_chapters = []
        for chapter in results['chapters']:
            if chapter['url'] not in seen:
                seen.add(chapter['url'])
                unique_chapters.append(chapter)
        
        results['chapters'] = unique_chapters
        
        results['msg'] = T_MSG_FORMAT.format(
            title=results['title'],
            status=status if status else "N/A",
            genres=genres if genres else "N/A",
            summary=summary[:400] if summary else "N/A",
            language=language if language else "N/A",
            url=results['url'],
        )
        
        return results
    
    def iter_chapters(self, data, page: int = 1):
        chapters_list = []
        if 'chapters' not in data:
            return []
        
        for chapters in data['chapters']:
            try:
                chapters_list.append({
                    "title": chapters['name'],
                    "url": chapters['url'],
                    "manga_title": data['title'],
                    "poster": data['poster'] if 'poster' in data else None,
                })
            except:
                continue
        
        return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list
        
    async def get_pictures(self, url, data=None):
        request_url = get_worker_url() + quote(url)
        
        text = await shared_scraper.get(request_url, headers=self.headers, cs=True)
        if not text:
            return []
        
        image_urls = []
        ts_reader_pattern = r'ts_reader\.run\s*\('
        match = re.search(ts_reader_pattern, text)
        if match:
            try:
                start_pos = match.end()
                brace_count = 0
                json_end = -1
                in_string = False
                escape_next = False
                for i in range(start_pos, len(text)):
                    char = text[i]
                    if escape_next:
                        escape_next = False
                        continue
                    if char == '\\':
                        escape_next = True
                        continue
                    if char == '"':
                        in_string = not in_string
                        continue
                    if not in_string:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i
                                break
                if json_end != -1:
                    json_str = text[start_pos:json_end + 1]
                    data_obj = json.loads(json_str)
                    if 'sources' in data_obj:
                        for source in data_obj['sources']:
                            if 'images' in source and isinstance(source['images'], list):
                                for img_url in source['images']:
                                    if img_url and img_url.startswith('http'):
                                        image_urls.append(img_url)
                                        
            except (json.JSONDecodeError, ValueError) as e:
                logger.debug(f"Failed to parse ts_reader JSON: {e}")
        
        if not image_urls:
            patterns = [
                r'https:\\/\\/[^\\"]+/(?:manga|wp-content)/[^\\"]+\.(?:jpg|jpeg|png|webp|gif)',
                r'https://[^"\s]+/(?:manga|wp-content)/[^"\s]+\.(?:jpg|jpeg|png|webp|gif)'
            ]
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for url_match in matches:
                    clean_url = url_match.replace('\\/', '/')
                    if clean_url and clean_url.startswith('http'):
                        image_urls.append(clean_url)
        seen = set()
        unique_images = []
        for img_url in image_urls:
            img_url = img_url.strip()
            worker_img = create_link(img_url)
                
            if worker_img and worker_img not in seen:
                seen.add(worker_img)
                unique_images.append(worker_img)
        
        return unique_images
