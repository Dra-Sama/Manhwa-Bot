# Code By @V_Sbotmaker (on Telegram)
from Webs.utitls import DEAULT_MSG_FORMAT
from .scraper import shared_scraper as scraper 
from urllib.parse import quote_plus
from bs4 import BeautifulSoup



headers = {
  "Accept": "*/*",
  "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
  "Connection": "keep-alive",
  "Content-Type": "application/json",
  "Cookie": "user_theme=crimson; user_bg_mode=default",
  "Host": "roliascan.com",
  "Origin": "https://roliascan.com",
  "Referer": "https://roliascan.com/",
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
}


# ======================================================
# Token 
# ======================================================
import hashlib
from datetime import datetime, timezone
import time

def generate_token():
    timestamp = int(time.time())
    hour = datetime.now(timezone.utc).strftime('%Y%m%d%H')  # YYYYMMDDhh
    secret = 'mng_ch_' + hour
    hash_input = str(timestamp) + secret
    full_hash = hashlib.md5(hash_input.encode()).hexdigest()
    token = full_hash[:16]
    return {'token': token, 'timestamp': timestamp}



class RoliaScanWebs:
  __slots__ = ('url', 'sf')

  def __init__(self):
    self.url: str = "https://roliascan.com"
    self.sf: str = "r.s"
    
  async def  search(self, query: str ) -> list:
    api_url = f"{self.url}/auth/search"
    params = {
      "query": query,
      "limit": 20
    }
    data = await scraper.post(api_url, json=params, cs=True, rjson=True)
    
    if not data or not data.get("results"):
      return []

    results = []
    for manga in data['results']:
      if not isinstance(manga, dict):
        continue
      
      poster = manga.pop("thumbnail")
      title = manga.get("title")
      url = manga.pop("permalink") + '/' + str(manga['id'])
      
      results.append({
        "title": title,
        "poster": poster,
        "url": url
      })
      
    return results

  # ===============================================
  # Info 
  # ===============================================
  @staticmethod
  async def get_info(manga_id: str, results: dict) -> None:
    request_url = f"https://roliascan.com/wp-json/wp/v2/manga/{manga_id}?_embed"
    data = await scraper.get(request_url, cs=True, rjson=True)
    if not data:
      return 

    _embedded = data.get("_embedded", {})
    # ===========================================================
    # Poster 
    # ===========================================================
    if not results.get("poster"):
      poster_list = data.get("wp:featuredmedia", [])
      poster_dict = poster_list[0] if poster_list else {}
      results['poster'] = poster_dict.get("source_url") if isinstance(poster_dict, dict) else None
    
    # ===========================================================
    # Genres
    # ===========================================================
    geners_list = _embedded.get("wp:term", [])
    geners_list = geners_list[0] if geners_list else []
    genres = ", ".join([g['name'] for g in geners_list if isinstance(g, dict) and g.get("name")])

    # ===========================================================
    # Description
    # ===========================================================
    description = data.get("content", {}).get("rendered", "N/A")

    results['msg'] = DEAULT_MSG_FORMAT.format(
      title=results['title'],
      status=data.get("status", "N/A"),
      genres=genres,
      summary=description[:400],
      url=results.get("url")
    )
    
    
    
    
      
  async def get_chapters(self, data: dict, page: int=1) -> dict:
    results = data.copy()
    try:
      manga_id = results['url'].split('/')[-1]
    except Exception:
      return results

    await self.get_info(manga_id, results)
    
    # =============================================
    # Chapters
    # =============================================
    token_data = generate_token()
    
    params = {
        'manga_id': manga_id,
        'offset': 0,
        'limit': 500,
        'order': 'DESC',
        '_t': token_data['token'],
        '_ts': token_data['timestamp'],
    }
    request_url = f"{self.url}/auth/manga-chapters"
    data =  await scraper.get(request_url, params=params, cs=True, rjson=True)
    if not data or not data.get("chapters"):
      return results
    
    results['chapters'] = []
    for chapter in data['chapters']:
      if not isinstance(chapter, dict):
        continue
      
      chapter_num = chapter.get("chapter")
      chapter_url = chapter.get("url")
      if not chapter_num or not chapter_url:
        continue

      chapter_url = chapter_url + "/" + str(chapter['id'])
      
      results['chapters'].append({
        "title": str(chapter_num),
        "url": chapter_url,
        "manga_title": results['title'],
        "poster": results.get('poster'),
      })
    
    return results

  @staticmethod
  def iter_chapters(data: dict, page: int=1) -> list:
    chapters = data.get("chapters", [])
    return  chapters[(page - 1) * 60:page * 60] if page != 1 else chapters
    
  async def get_pictures(self, url: str, data: dict | None = None) -> list:
    try:
      chapter_id = url.split("/")[-1]
    except Exception:
      return []
    
    request_url = f"{self.url}/auth/chapter-content?chapter_id={chapter_id}"
    data =  await scraper.get(request_url, cs=True, rjson=True)
    if not data or not data.get("images"):
      return []
    
    return data.get("images")
    
    
    
      
      
      
    
    
