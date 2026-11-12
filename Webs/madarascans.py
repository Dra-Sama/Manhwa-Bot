# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper
import json
from bs4 import BeautifulSoup

from .utitls import DEAULT_MSG_FORMAT
import re
from urllib.parse import quote_plus, quote

scraper = Scraper()

BASE_URL = "https://madarascans.com"
PROXY_BASE = "https://madarascans.li-13-presidential.workers.dev/proxy?url="
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0",
    "Referer": BASE_URL + "/"
}


class MadaraScans:
    def __init__(self):
        super().__init__()
        self.url = BASE_URL
        self.sf = "msn"

    async def search(self, query: str = ""):
        search_url = f"{BASE_URL}/?s={quote_plus(query)}"
        request_url = PROXY_BASE + quote(search_url)
        
        html = await scraper.get(request_url, cs=True, timeout=20)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for bsx in soup.select(".listupd .bsx"):
            a_tag = bsx.select_one("a")
            if not a_tag:
                continue
            
            url = a_tag.get("href", "").strip()
            title = a_tag.get("title") or (bsx.select_one(".tt").get_text(strip=True) if bsx.select_one(".tt") else None)
            img_tag = bsx.select_one("img")
            thumbnail = str(img_tag["src"]) if img_tag else None
            thumbnail = PROXY_BASE + quote(thumbnail) if thumbnail else None
            results.append({
                "title": title,
                "url": url,
                "poster": thumbnail
            })

        return results

    @staticmethod
    def get_infomation(soup: BeautifulSoup, data):
        if "poster" not in data or not data["poster"]:
            cover_tag = soup.select_one(".thumb img")
            data['poster'] = PROXY_BASE + quote(str(cover_tag["src"])) if cover_tag else None

        desc_tag = soup.select_one(".summary .entry-content")
        summary = desc_tag.get_text("\n", strip=True) if desc_tag else None

        genre_tag = soup.select_one(".wd-full .mgen")
        genres = ",  ".join([a.get_text(strip=True) for a in genre_tag.find_all("a")]) if genre_tag else "N/A"

        status = next(
            (
                i_tag.get_text(strip=True)
                for imptdt in soup.select(".tsinfo .imptdt")
                if (h1 := imptdt.select_one("h1")) and "status" in h1.get_text(strip=True).lower()
                and (i_tag := imptdt.select_one("i"))
            ),
            "N/A"
        )
        
        data['msg'] = DEAULT_MSG_FORMAT.format(
            title=data['title'],
            status=status,
            genres=genres,
            summary=summary[:300] if summary else "N/A",
            url=data['url']
        )


    async def get_chapters(self, data, page: int = 1):
        results = data.copy()
        request_url = PROXY_BASE + quote(results['url'])
        html = await scraper.get(request_url, cs=True, timeout=15)
        if not html:
            return results

        bs = BeautifulSoup(html, "html.parser")
        self.get_infomation(bs, results)

        results['chapters'] = []
        for li in bs.select("#chapterlist li"):
            a = li.select_one("a")
            if not a:
                continue
            
            chap_num = a.select_one(".chapternum")
            ch_title = chap_num.get_text(strip=True) if chap_num else a.get_text(strip=True)
            
            ch_title = ch_title.strip()
            ch_title = ch_title.replace("\t", "").replace("Chapter", "")
            
            href = a.get("href")
            if not href:
                continue
            
            ch_url = href.strip()
            info = {
                "title": ch_title,
                "url": ch_url,
                "manga_title": results['title'],
                "poster": results['poster'] if 'poster' in results else None
            }
            results['chapters'].append(info)
            
        if not results['chapters']:
            for inep in bs.select(".lastend .inepcx"):
                a = inep.select_one("a")
                if not a or "chapter" not in a.get_text(strip=True).lower():
                    continue
                ch_title_elem = a.select_one(".epcur") or a.select_one("span")
                ch_title = ch_title_elem.get_text(strip=True) if ch_title_elem else a.get_text(strip=True)
                
                ch_title = ch_title.strip()
                ch_title = ch_title.replace("\t", "").replace("Chapter", "")
                
                href = a.get("href")
                if not href:
                    continue
                
                ch_url = href.strip()
                info = {
                    "title": ch_title,
                    "url": ch_url,
                    "manga_title": results['title'],
                    "poster": results['poster'] if 'poster' in results else None
                }
                results['chapters'].append(info)

        return results

    def iter_chapters(self, data, page: int = 1, scanlator_slug: str = ""):
        if not data or 'chapters' not in data:
            return []

        return data['chapters'][(page - 1) * 60:page *60] if page != 1 else data['chapters']

    async def get_pictures(self, url, data=None):
        request_url = PROXY_BASE + url
        html = await scraper.get(request_url, cs=True, timeout=20)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")

        images = []
        for script in soup.find_all("script"):
            if script.string and "ts_reader.run(" in script.string:
                m = re.search(r'ts_reader\.run\((\{.*?\})\);', script.string, re.DOTALL)
                if m:
                    try:
                        data_str = m.group(1)
                        data_str = data_str.replace("'", '"').replace("True", "true").replace("False", "false")
                        data_str = re.sub(r",(\s*[\]}])", r"\1", data_str)
                        data = json.loads(data_str)
                        sources = data.get("sources", [])
                        if sources:
                            for source in sources:
                                imgs = source.get("images", [])
                                for img_url in imgs:
                                    if img_url.startswith("http"):
                                        images.append(PROXY_BASE + quote(img_url))
                        break
                    except Exception:
                        continue
        if not images:
            for img in soup.select("#readerarea img"):
                src = img.get("src") or img.get("data-src")
                src = str(src)
                if src and src.startswith("http"):
                    images.append(PROXY_BASE + quote(src))
        
        return images



