# Code By @V_Sbotmaker (on Telegram)

from .scraper import Scraper
import json

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus, urlencode

import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT


class ManhuaUSWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://manhuaus.com"
    self.api_url = "https://manhuaus.com/wp-admin/admin-ajax.php"
    self.sf = "mhau"
    self.headers = {
      "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
      #"accept-encoding": "gzip, deflate, br, zstd"
      "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
      "connection": "keep-alive",
      "host": "manhuaus.com",
      "referer": "https://manhuaus.com/",
      "sec-fetch-user": "?1",
      "upgrade-insecure-requests": "1",
      "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    }

  async def search(self, query: str = ""):
    url = f"https://manhuaus.com/?s={quote_plus(query)}&post_type=wp-manga&post_type=wp-manga"
    html = await self.get(url, headers=self.headers)
    if not html: 
      return []
    
    results = []
    try:
      bs = BeautifulSoup(html, "html.parser")
      con = bs.find(class_="tab-content-wrap")
      cards = con.find_all(class_="row c-tabs-item__content")
      for card in cards:
        _tag = card.find(class_="tab-thumb c-image-hover")
        data = {}
        data['url'] = _tag.find_next("a").get("href")
        
        data['poster'] = _tag.find_next("img").get("data-src")
        data['title'] = card.find(class_="post-title").find_next("a").text.strip()
        
        _genres = card.find(class_="post-content_item mg_genres nofloat")
        try:
          data['genres'] = ", ".join([g.text.strip() for g in _genres.find_all("a")]) if _genres else None
        except:
          data['genres'] = None
        
        _status = card.find(class_="post-content_item mg_status nofloat")
        try:
          data['status'] = _status.find_next("div").find_next("div").text.strip() if _status else None
        except:
          data['status'] = None
        
        results.append(data)
        
    except Exception as e:
      logger.error(f"ManhuaUS Error: {e}")
    finally:
      return results

  async def get_chapters(self, data, page: int=1):
    results = data.copy()
    
    content = await self.get(results['url'], headers=self.headers)
    bs = BeautifulSoup(content, "html.parser") if content else None
    if bs:
      con = bs.find(class_="summary_content")

      # -- Genres --
      if "genres" in results and results['genres'] not in [None, "None", ""]:
        genres_ = results.pop('genres')
      else:
        genres_ = con.find_next(class_="genres-content")
        genres_ = ", ".join([g.text.strip() for g in genres_.find_all("a")]) if genres_ else "N/A"
      # --- Summary ---
      des = bs.find(class_="summary__content show-more").text.strip() if bs.find(class_="summary__content show-more") else "N/A"
      
      # -- Status ---
      status_ = results.pop('status') if "status" in results and results['status'] not in [None, "None", ""] else "N/A"

      # -- Poster ---
      if "poster" not in results:
        try:
          results['poster'] = bs.find(class_="summary_image").find_next("img").get("data-src") if bs.find(class_="summary_image") else None
        except:
          results['poster'] = None
      
      
      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=status_ if status_ else "N/A",
        genres=genres_ if genres_ else "N/A",
        summary=des[:200] if des else "N/A",
        url=results['url'],
      )

    chapters = bs.find(class_="listing-chapters_wrap cols-2 show-more")
    chapters = chapters.find_all("li") if chapters else None
    results['chapters'] = [
      card.find_next("a")
      for card in chapters 
    ] if chapters else None
    
    return results

  def iter_chapters(self, data, page: int=1):
    chapters_list = []

    if data['chapters']:
      try:
        for card in data['chapters']:
          chapters_list.append({
            "title": card.text.strip(),
            "url": card['href'],
            "manga_title": data['title'],
            "poster": data['poster'] if 'poster' in data else None,
          })
      except Exception as err:
        logger.error(f"ManhuaUS Error: {err}")

    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    response = await self.get(url, headers=self.headers)
    if not response:
      return []
    
    bs = BeautifulSoup(response, "html.parser")

    cards = bs.find_all(class_="page-break no-gaps")

    mangas = [card.findNext('img') for card in cards]

    image_links = [manga.get("data-src").strip() for manga in mangas]
    
    return image_links
