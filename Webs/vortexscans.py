# Code By @V_Sbotmaker (on Telegram)
from typing import Generator

from .scraper import shared_scraper

import json, re
from bs4 import BeautifulSoup

from loguru import logger
from urllib.parse import urlparse, urljoin, quote, quote_plus

from .utitls import DEAULT_MSG_FORMAT, ATSU_MSG_FORMAT, cp_list
import random


class VortexScansWebs:
  url = "https://vortexscans.org"
  sf = "vts"

  headers = {
      "Accept": "*/*",
      #"Accept-Encoding": "gzip, deflate, br, zstd",
      "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
      "Connection": "keep-alive",
      "Host": "api.vortexscans.org",
      "Origin": "https://vortexscans.org",
      "Referer": "https://vortexscans.org/",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"
  }

  async def search(self, query: str = ""):
    search_url = f"https://api.vortexscans.org/api/query?searchTerm={quote(query)}&perPage=1000"
    
    data = await shared_scraper.get(search_url, rjson=True, cs=True, headers=self.headers)
    
    if not data or "posts" not in data:
      return []

    results = []
    for doc in data.get("posts", []):
      try:
        data = {}
        if doc.get("isNovel", False) is False or doc.get("seriesType", "Manga") != "NOVEL":
          data['title'] = doc['postTitle'].strip()
          data['url'] = f"https://vortexscans.org/series/{doc['slug']}"
          data['poster'] = doc['featuredImage']
       
          data['id'] = doc['id']

          _type = doc.get('seriesType', None)
          _summary = doc.get('postContent', None)
          _genres = doc.get("genres", [])
          _genres = ", ".join([g.get("name", "") for g in _genres]) if _genres else None
          _alt_titles = doc.get("alternativeTitles", None)
          #_alt_titles = ", ".join(_alt_titles) if _alt_titles else None
          _status = doc.get("seriesStatus", None)

          data['msg'] = ATSU_MSG_FORMAT.format(
            title=data['title'],
            alt_title=_alt_titles if _alt_titles else 'N/A',
            genres=_genres if _genres else 'N/A',
            type=_type if _type else 'N/A',
            status=_status if _status else 'N/A',
            summary=_summary[:200] if _summary else 'N/A',
            url=data['url']
          )
          if len(data['msg']) > 1024:
            data['msg'] = DEAULT_MSG_FORMAT.format(
              title=data['title'],
              status=_status if _status else 'N/A',
              genres=_genres if _genres else 'N/A',
              summary=_summary[:200] if _summary else 'N/A',
              url=data['url']
            )
          results.append(data)
      except:
        pass

    return results

  async def get_chapters(self, data, page: int = 1):
    results = data.copy()

    post_id = results.get("id")

    if not post_id:
      # Resolve existing saved manga entries without a stored post ID.
      slug = results["url"].rstrip("/").split("/")[-1]

      lookup = await shared_scraper.get(
        "https://api.vortexscans.org/api/query",
        rjson=True,
        cs=True,
        headers=self.headers,
        params={"searchTerm": slug.replace("-", " "), "perPage": 100},
      )

      for item in (lookup or {}).get("posts", []):
        if item.get("slug") == slug:
          post_id = item.get("id")
          break

    if not post_id:
      results["chapters"] = []
      return results

    results["id"] = post_id

    response = await shared_scraper.get(
      f"https://api.vortexscans.org/api/chapters?postId={post_id}",
      rjson=True,
      cs=True,
      headers=self.headers,
    )

    if not isinstance(response, dict):
      results["chapters"] = []
      return results

    slug = results["url"].rstrip("/").split("/")[-1]
    chapters = (response.get("post") or {}).get("chapters") or []

    results["chapters"] = [
      {
        "title": str(ch.get("number", ch.get("title", "Chapter"))),
        "url": (
          f"https://vortexscans.org/series/{slug}/"
          f"{ch['slug']}?chapterId={ch['id']}"
        ),
        "chapter_id": ch["id"],
        "manga_title": results["title"],
        "poster": results.get("poster"),
      }
      for ch in chapters
      if ch.get("id")
      and ch.get("slug")
      and ch.get("isAccessible", not ch.get("isLocked", False))
    ]

    return results


  
    
  def iter_chapters(self, data, page: int = 1):
    if "chapters" not in data:
      return []
    
    chapters_list = data.get('chapters', [])

    return chapters_list[(page - 1)*60:page*60] if page != 1 else chapters_list

      
    

  
  async def get_pictures(self, url, data=None):
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    chapter_id = params.get("chapterId", [None])[0]

    if not chapter_id and isinstance(data, dict):
      chapter_id = data.get("chapter_id")

    if not chapter_id:
      logger.warning(f"VortexScans: Missing chapter ID for {url}")
      return []

    response = await shared_scraper.get(
      f"https://api.vortexscans.org/api/chapter?chapterId={chapter_id}",
      rjson=True,
      cs=True,
      headers=self.headers,
    )

    if not isinstance(response, dict):
      return []

    chapter = response.get("chapter") or {}
    images = chapter.get("images") or []

    images = sorted(
      images,
      key=lambda item: item.get("order", 0)
    )

    return [
      item["url"]
      for item in images
      if isinstance(item, dict)
      and isinstance(item.get("url"), str)
      and item["url"].startswith(("https://", "http://"))
    ]
