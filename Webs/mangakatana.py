# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper
import json

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus

import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT


class MangaKatanaWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://mangakatana.com"
    self.sf = "mkt"
    self.headers = {
      "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
      "accept-encoding": "gzip, deflate, br, zstd",
      "accept-language": "en-GB,en;q=0.8",
      "connection": "keep-alive",
      "host": "mangakatana.com",
      "referer": "https://mangakatana.com/",
      "sec-fetch-user": "?1",
      "sec-gpc": "1",
      "upgrade-insecure-requests": "1",
      "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    }

  async def search(self, query: str = ""):
    url = f"https://mangakatana.com/?search={quote_plus(query)}&search_by=book_name"
    mangas = await self.get(url, headers=self.headers)
    if not mangas:
      return []
    
    bs = BeautifulSoup(mangas, "html.parser")
    
    container = bs.find("div", {"id": "book_list"}) if bs else None

    results = []
    if container:
      cards = container.find_all(class_="item")
      if cards:
        for card in cards:
          try:
            _tag = card.find_next("h3", class_="title")
            data = {}
            
            data['url'] = _tag.find_next("a").get('href').strip()
            data['title'] = _tag.find_next('a').text.strip()
            
            data['poster'] = card.find_next(class_='wrap_img').find_next("img").get('src')
            
            _genres = card.find_next(class_="genres uk-hidden-small")
            
            data['genres'] = ", ".join([g.text.strip() for g in _genres.find_all("a")]) if _genres else None
            _summary = card.find_next(class_="summary")
            data['summary'] = _summary.text.strip() if _summary else None
            
            results.append(data)
          except:
            continue

    return results

  async def get_chapters(self, data, page: int=1):
    results = data
    content = await self.get(results['url'], headers=self.headers)
    if content:
      bs = BeautifulSoup(content, "html.parser")

      # -- Poster --
      if "poster" not in results or not results['poster']:
        _poster = bs.find(class_="cover")
        _poster = _poster.find_next("img").get("src") if _poster else None
        results['poster'] = _poster
      
      # -- Summary --
      _summary = None
      if "summary" not in results or not results['summary']:
        _summary = bs.find(class_="summary")
        _summary = _summary.find_next("p").text.strip() if _summary and _summary.find_next("p") else "N/A"
      else:
        _summary = results.pop('summary')
      
      _tag = bs.find("ul", class_="meta d-table")
      
      # --- Genres ---
      _genres = None
      if "genres" not in results or not results['genres']:
        _genres = _tag.find(class_="genres") if _genres else None
        _genres = ", ".join([g.text.strip() for g in _genres.find_all("a")]) if _genres else "N/A"
      else:
        _genres = results.pop('genres')

      # --- Status ---
      _status = next(
        (i.find_next("div").find_next("div").text.strip() for i in _tag.find_all("li") if "Status:" in i.text), "N/A"
      ) if _tag else "N/A"
      
      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=_status if _status else "N/A",
        genres=_genres if _genres else "N/A",
        summary=_summary[:400] if _summary else "N/A",
        url=results['url']
      )

      container = bs.find(class_="chapters")
      cards = container.find_all("tr") if container else None
      results['chapters'] = [card.find_next("a") for card in cards] if cards else None

    return results

  def iter_chapters(self, data, page: int=1):
    chapters_list = []
    if not data['chapters']:
      return []
      
    
    for card in data['chapters']:
      try:
        chapters_list.append({
          "title": card.text.strip(),
          "url": card.get("href"),
          "manga_title": data['title'],
          "poster": data['poster'] if 'poster' in data else None,
        })
      except:
        continue

    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    try:
      response = await self.get(url, headers=self.headers)
      bs = BeautifulSoup(response, "html.parser")
      
      script_tags = bs.find_all('script')
      image_links = []
      for script in script_tags:
        if script.string and "$(document).on" in script.string and "var thzq=['" in script.string:
          pattern = r"var thzq\s*=\s*\[([^\]]+)\];"
          match = re.search(pattern, script.string)
          if match:
            image_link = match.group(1).replace("'", "").split(",")
            image_links = [image for image in image_link 
                           if image not in ["None", None, "", " "]]
            
            return image_links
            
    except Exception as e:
      logger.error(f"MangaKatana Error: {e}")
      return []
              
          
        

