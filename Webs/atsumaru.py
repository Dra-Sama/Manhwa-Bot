# Code By @V_Sbotmaker (on Telegram)

from .scraper import Scraper, shared_scraper
import json, re
from bs4 import BeautifulSoup

from loguru import logger
from urllib.parse import urlparse, urljoin, quote, quote_plus

from .utitls import DEAULT_MSG_FORMAT, ATSU_MSG_FORMAT

class AtsumaruWebs:
  url = "https://atsu.moe"
  sf = "atsu"
    
  headers = {
      "Accept": "*/*",
      #"Accept-Encoding": "gzip, deflate, br, zstd",
      "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
      "Connection": "keep-alive",
      "Host": "atsu.moe",
      "Referer": "https://atsu.moe/",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"
  }

  async def search(self, query: str = ""):
    search_url = f"https://atsu.moe/collections/manga/documents/search?q={quote_plus(query)}&limit=12&query_by=title%2CenglishTitle%2CotherNames&query_by_weights=3%2C2%2C1&include_fields=id%2Ctitle%2CenglishTitle%2Cposter&num_typos=4%2C3%2C2"
    
    data = await shared_scraper.get(search_url, rjson=True, headers=self.headers)
    
    if not data or "hits" not in data:
      return []
      
    results = []
    for doc in data["hits"]:
      try:
        doc_ = doc.get("document", {})
        #doc_['title'] = doc_.pop("englishTitle")
        doc_['url'] = f"https://atsu.moe/manga/{doc_['id']}"
        doc_['poster'] = f"https://atsu.moe{doc_['poster']}"
        results.append(doc_)
      except:
        pass

    return results

  async def get_chapters(self, data, page: int = 1):
    results = data.copy()
    if "id" not in results:
      results['id'] = results['url'].split("/")[-1]
    
    url = f"https://atsu.moe/api/manga/page?id={results['id']}"
    data = await shared_scraper.get(url, rjson=True, headers=self.headers)
    if not data or "mangaPage" not in data:
      return results

    mdata = data["mangaPage"]
    # -- Authors --
    #authors = mdata.get("authors", [])
    #authors = ", ".join([a.get("name", "") for a in authors]) if authors else "N/A"

    # -- Title ---
    title = mdata.get("englishTitle") or mdata.get("title") or results['title']
    results['title'] = title
    
    alt_titles = mdata.get("otherNames", [])
    alt_titles = ", ".join(alt_titles) if alt_titles else "N/A"

    # --- Poster ---
    if "poster" not in results or not results['poster']:
      _poster = mdata.get("poster", "")
      if _poster and _poster.get("image", None):
        results['poster'] = f"https://atsu.moe{_poster.get('image')}"
      elif _poster and _poster.get("id", None):
        results['poster'] = f"https://atsu.moe/static/{_poster.get('id')}"

    # --- Type ---
    type = mdata.get("type", "N/A")
    
    # -- genres --
    genres = mdata.get("tags", [])
    genres = ", ".join([g.get("name", "") for g in genres]) if genres else "N/A"
    
    # -- summary --
    summary = mdata.get("synopsis", "N/A")

    # -- Other Url -- 
    ani_id = mdata.get("anilistId", None)
    malId = mdata.get("malId", None)
    #mangaBakaId = mdata.get("mangaBakaId", None)
    #mangaUpdatesId = mdata.get("mangaUpdatesId", None)

    # -- status ---
    status = mdata.get("status", "N/A")

    results['msg'] = ATSU_MSG_FORMAT.format(
      title=title,
      alt_title=alt_titles if alt_titles else 'N/A',
      genres=genres if genres else 'N/A',
      type=type if type else 'N/A',
      status=status if status else 'N/A',
      summary=summary[:200] if summary else 'N/A',
      url=results['url'],
    )
    
    if ani_id:
      results['msg'] += f"\n**=> <a href=https://anilist.co/manga/{ani_id}>AniList</a>**"
    if malId:
      results['msg'] += f"\n**=> <a href=https://myanimelist.net/manga/{malId}>MyAnimeList</a>**"
    
    if len(results['msg']) > 1024:
      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=title,
        status=status if status else 'N/A',
        genres=genres if genres else 'N/A',
        summary=summary[:200] if summary else 'N/A',
        url=results['url'],
      )
    
    # -- Chapters --
    mdata = await shared_scraper.get(
      f"https://atsu.moe/api/manga/allChapters?mangaId={results['id']}",
      rjson=True, headers=self.headers
    )
    if not mdata or "chapters" not in mdata:
      return results
    
    results['chapters'] = []
    for chapter in mdata.get("chapters", []):
      results['chapters'].append(
        {
          "url": f"https://atsu.moe/api/read/chapter?mangaId={results['id']}&chapterId={chapter['id']}", #https://atsu.moe/api/read/chapter?mangaId=oZOG5&chapterId=m16Iypw7
          "title": chapter.get("title", "Chapter") or f"Chapter {chapter.get('number', 'N/A')}",
          "poster": results['poster'] if 'poster' in results else None,
          "manga_title": results['title']
        }
      )
    
    return results

  def iter_chapters(self, data, page: int = 1):
    if "chapters" not in data:
      return []
    
    return data['chapters'][(page - 1)*60:page*60] if page != 1 else data['chapters']

  async def get_pictures(self, url, data=None):
    # https://atsu.moe/api/read/chapter?mangaId=oZOG5&chapterId=m16Iypw7
    rdata = await shared_scraper.get(url, rjson=True, headers=self.headers)
    
    if not rdata or "readChapter" not in rdata:
      return []

    
    pages = rdata.get("readChapter", {}).get("pages", [])
    return [
      f"https://atsu.moe/{cdata.get('image')}"
      for cdata in pages
    ]
  
