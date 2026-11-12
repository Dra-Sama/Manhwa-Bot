# Code By @V_Sbotmaker (on Telegram)
import urllib.parse
import binascii
import re
from bs4 import BeautifulSoup
from .scraper import shared_scraper as scraper
from .utitls import ATSU_MSG_FORMAT, DEAULT_MSG_FORMAT
from loguru import logger

print = logger.info
def generate_vrf(input_str):
    input_bytes = urllib.parse.quote(input_str, safe="").encode()

    for key_b64, seed_b64, prefix_b64, schedule in (
        (key_l, seed_A, prefix_O, schedule_c),
        (key_g, seed_V, prefix_v, schedule_y),
        (key_B, seed_N, prefix_L, schedule_b),
        (key_m, seed_P, prefix_p, schedule_j),
        (key_F, seed_k, prefix_W, schedule_e),
    ):
        input_bytes = transform(
            rc4(binascii.a2b_base64(key_b64), input_bytes),
            binascii.a2b_base64(seed_b64),
            binascii.a2b_base64(prefix_b64),
            schedule,
        )

    return binascii.b2a_base64(bytes(input_bytes), newline=False).rstrip(
        b"=").replace(b"+", b"-").replace(b"/", b"_").decode()


def transform(input_bytes, seed, prefix, schedule):
    prefix_len = len(prefix)
    out = []
    for idx, c in enumerate(input_bytes):
        if idx < prefix_len:
            out.append(prefix[idx] or 0)
        out.append(schedule[idx % 10]((c ^ seed[idx % 32]) & 255) & 255)
    return out


def rc4(key, input_bytes):
    lkey = len(key)
    j = 0
    s = list(range(256))
    for i in range(256):
        j = (j + s[i] + key[i % lkey]) & 255
        s[i], s[j] = s[j], s[i]
    out = []
    i = j = 0
    for c in input_bytes:
        i = (i + 1) & 255
        j = (j + s[i]) & 255
        s[i], s[j] = s[j], s[i]
        k = s[(s[i] + s[j]) & 255]
        out.append(c ^ k)
    return out


def add8(n): return lambda c: (c + n) & 255
def sub8(n): return lambda c: (c - n + 256) & 255
def xor8(n): return lambda c: (c ^ n) & 255
def rotl8(n): return lambda c: ((c << n) | (c >> (8 - n))) & 255
def rotr8(n): return lambda c: ((c >> n) | (c << (8 - n))) & 255

schedule_c = (sub8(223), rotr8(4), rotr8(4), add8(234), rotr8(7), rotr8(2), rotr8(7), sub8(223), rotr8(7), rotr8(6))
schedule_y = (add8(19), rotr8(7), add8(19), rotr8(6), add8(19), rotr8(1), add8(19), rotr8(6), rotr8(7), rotr8(4))
schedule_b = (sub8(223), rotr8(1), add8(19), sub8(223), rotl8(2), sub8(223), add8(19), rotl8(1), rotl8(2), rotl8(1))
schedule_j = (add8(19), rotl8(1), rotl8(1), rotr8(1), add8(234), rotl8(1), sub8(223), rotl8(6), rotl8(4), rotl8(1))
schedule_e = (rotr8(1), rotl8(1), rotl8(6), rotr8(1), rotl8(2), rotr8(4), rotl8(1), rotl8(1), sub8(223), rotl8(2))

key_l = "FgxyJUQDPUGSzwbAq/ToWn4/e8jYzvabE+dLMb1XU1o="
key_g = "CQx3CLwswJAnM1VxOqX+y+f3eUns03ulxv8Z+0gUyik="
key_B = "fAS+otFLkKsKAJzu3yU+rGOlbbFVq+u+LaS6+s1eCJs="
key_m = "Oy45fQVK9kq9019+VysXVlz1F9S1YwYKgXyzGlZrijo="
key_F = "aoDIdXezm2l3HrcnQdkPJTDT8+W6mcl2/02ewBHfPzg="

seed_A = "yH6MXnMEcDVWO/9a6P9W92BAh1eRLVFxFlWTHUqQ474="
seed_V = "RK7y4dZ0azs9Uqz+bbFB46Bx2K9EHg74ndxknY9uknA="
seed_N = "rqr9HeTQOg8TlFiIGZpJaxcvAaKHwMwrkqojJCpcvoc="
seed_P = "/4GPpmZXYpn5RpkP7FC/dt8SXz7W30nUZTe8wb+3xmU="
seed_k = "wsSGSBXKWA9q1oDJpjtJddVxH+evCfL5SO9HZnUDFU8="

prefix_O = "l9PavRg="
prefix_v = "Ml2v7ag1Jg=="
prefix_L = "i/Va0UxrbMo="
prefix_p = "WFjKAHGEkQM="
prefix_W = "5Rr27rWd"


class MangaFireWebs:
    __slots__ = ('url', 'sf',)
    def __init__(self):
        self.url = "https://mangafire.to"
        self.sf = "m.fi"

    async def search(self, query: str):
        vrf = generate_vrf(query.strip())
        url = f"https://mangafire.to/filter?keyword={urllib.parse.quote_plus(query.strip())}&vrf={vrf}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://mangafire.to/"
        }
        
        try:
            html = await scraper.get(url, headers=headers)
            soup = BeautifulSoup(html, "html.parser")
            results = []
            
            for card in soup.select(".original .card, .card, .inner"):
                poster_a = card.select_one("a.poster")
                if not poster_a:
                    continue
                manga_url = poster_a.get("href")
                if not manga_url:
                    continue
                if not manga_url.startswith("http"):
                    manga_url = urllib.parse.urljoin("https://mangafire.to", manga_url)
                
                title_a = card.select_one(".info > a")
                if not title_a:
                    title_a = card.select_one("a.poster")
                
                title = ""
                if title_a:
                    title = title_a.get_text(strip=True)
                if not title and poster_a.find("img"):
                    title = poster_a.find("img").get("alt", "")
                
                img_tag = poster_a.find("img")
                poster_url = img_tag.get("src") if img_tag else ""
                
                if title and manga_url:
                    results.append({
                        "title": title,
                        "url": manga_url,
                        "poster": poster_url,
                    })
            
            seen = set()
            deduped = []
            for r in results:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    deduped.append(r)
            
            return deduped
        except Exception as e:
            print(f"[MangaFire] Search error: {e}")
            return []

    async def get_chapters(self, data: dict):
        results = data.copy()

        manga_url = results.get('url')
        manga_id = manga_url.rstrip('/').split('.')[-1]
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": manga_url
        }
        
        try:
            html = await scraper.get(manga_url, headers=headers)
            soup = BeautifulSoup(html, "html.parser")
            
            title = None
            title_tag = soup.find(itemprop="name")
            if title_tag:
                title = title_tag.get_text(strip=True)
            else:
                title_tag = soup.select_one(".info h1")
                if title_tag:
                    title = title_tag.get_text(strip=True)
            
            cover = None
            poster_div = soup.select_one(".poster")
            if poster_div:
                img_tag = poster_div.find("img")
                if img_tag:
                    results['poster'] = img_tag.get("src")
                    
            alt_title = None
            h6_tag = soup.find("h6")
            if h6_tag:
                alt_title = h6_tag.get_text(strip=True)
                
            summary = "No description available"
            synopsis_div = soup.select_one("#synopsis")
            if synopsis_div:
                for script in synopsis_div.find_all("script"):
                    script.extract()
                summary = synopsis_div.get_text(strip=True)
                
            info_dict = {}
            for meta in soup.select(".meta > div"):
                label_span = meta.find("span")
                if label_span:
                    label = label_span.get_text(strip=True).replace(":", "").lower()
                    label_span.extract()
                    value = meta.get_text(strip=True)
                    info_dict[label] = value
            

            status = info_dict.get("status", "Unknown")
            genres_str = info_dict.get("genres", "")
            genres = ", ".join([g.strip() for g in genres_str.split(",") if g.strip()])
            authors = info_dict.get("author", "Unknown")
            
            results['msg'] = ATSU_MSG_FORMAT.format(
                title=title,
                alt_title=alt_title if alt_title else 'N/A',
                genres=genres if genres else 'N/A',
                type=type if type else 'N/A',
                status=status if status else 'N/A',
                summary=summary[:200] if summary else 'N/A',
                url=results['url'],
            )

            if len(results["msg"]) > 1024:
                results["msg"] = DEAULT_MSG_FORMAT.format(
                    title=results["title"],
                    status=status,
                    genres=genres,
                    summary=summary[:200],
                    url=results["url"],
                )

            # Fetch Chapters via AJAX
            vrf = generate_vrf(f"{manga_id}@chapter@en")
            ajax_url = f"https://mangafire.to/ajax/read/{manga_id}/chapter/en?vrf={vrf}"
            
            ajax_headers = headers.copy()
            ajax_headers["X-Requested-With"] = "XMLHttpRequest"
            


            chapters = []
            try:
                res_json = await scraper.get(ajax_url, headers=ajax_headers, rjson=True)
                html_chaps = res_json.get("result", {}).get("html", "")
                
                soup_ch = BeautifulSoup(html_chaps, "html.parser")
                for a in soup_ch.find_all("a", href=True):
                    ch_number = a.get("data-number")
                    ch_title = a.get_text(strip=True)
                    
                    if ch_number:
                        chapter_title = f"Chapter {ch_number}"
                        if ":" in ch_title:
                            extra = ch_title.split(":", 1)[-1].strip()
                            if extra:
                                chapter_title = f"Chapter {ch_number}: {extra}"
                    else:
                        chapter_title = ch_title
                        
                    ch_url = a["href"]
                    if not ch_url.startswith("http"):
                        ch_url = urllib.parse.urljoin("https://mangafire.to", ch_url)
                        
                    chapters.append({
                      'title': chapter_title,
                      'url':  ch_url,
                      "manga_title": results.get('title'),
                      "poster": results.get('poster'),
                    })

            except Exception as chap_err:
                print(f"[MangaFire] Chapters AJAX error: {chap_err}")
            
            results['chapters'] = chapters

            return results
        except Exception as e:
            print(f"[MangaFire] Get info error: {e}")
            return None

    
    async def get_pictures(self, chapter_url: str, data: dict = None) -> list:
        match = re.search(r"/read/([\w-]+\.(\w+))/([\w-]+)/([\w-]+)", chapter_url)
        if not match:
            return []
            
        manga_path, manga_id, lang, chapter_slug = match.groups()
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": chapter_url,
            "X-Requested-With": "XMLHttpRequest"
        }
        
        try:
            # 1. Fetch chapters to lookup data-id
            vrf = generate_vrf(f"{manga_id}@chapter@{lang}")
            ajax_url = f"https://mangafire.to/ajax/read/{manga_id}/chapter/{lang}?vrf={vrf}"
            
            res_json = await scraper.get(ajax_url, headers=headers, rjson=True)
            html_chaps = res_json.get("result", {}).get("html", "")
            
            soup_ch = BeautifulSoup(html_chaps, "html.parser")
            chapter_id = None
            for a in soup_ch.find_all("a", href=True):
                if chapter_slug in a["href"]:
                    chapter_id = a.get("data-id")
                    break
                    
            if not chapter_id:
                return []
                
            # 2. Fetch images using chapter_id
            images_vrf = generate_vrf(f"chapter@{chapter_id}")
            images_url = f"https://mangafire.to/ajax/read/chapter/{chapter_id}?vrf={images_vrf}"
            
            images_json = await scraper.get(images_url, headers=headers, rjson=True)
            images = images_json.get("result", {}).get("images", [])
            
            return [img[0] for img in images if img]
        except Exception as e:
            logger.error(f"[MangaFire] Get chapter images error: {e}")
            return []

  
