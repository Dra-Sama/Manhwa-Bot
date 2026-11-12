# Code By @V_Sbotmaker (on Telegram)
from .scraper import shared_scraper
import json 

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus

import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT


class MangaMobWebs:
  def __init__(self):
    super().__init__()
    self.url = "https://comivex.com"
    self.bg = None
    self.sf = "mm"
    self.image_cdn = "https://cdn.mangageko.com/avatar/288x412"
    self.headers = {
      "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
      #"accept-encoding": "gzip, deflate, br, zstd"
      "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
      "connection": "keep-alive",
      "host": "www.mangamob.com",
      "sec-fetch-user": "?1",
      "upgrade-insecure-requests": "1",
      "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"

    }
  
  def get_manga_id(self, page, data):
    bs = BeautifulSoup(page, "html.parser")

    script_tags = bs.find_all("script")
    for script in script_tags:
        if script.string:
            match = re.search(r"manga_id:\s*(\d+)", script.string)
            if match:
              #id = match.group(1)
              data['id'] = match.group(1)

    return None
  


 
  async def search(self, query: str ) -> list:
    query = quote(query)
    request_url = f"{self.url}/ajax/manga/search/suggest?keyword={query}"
    
    djson = await shared_scraper.get(request_url, rjson=True)
    if not isinstance(djson, dict) or "html" not in djson:
      return []
    
    results = []
    try:
      bs = BeautifulSoup(djson['html'], "html.parser")
      for manga in bs.find_all("a"):
        try:
          manga_name = manga.find(class_="manga-name")
          manga_name = manga_name.text.strip() if manga_name else None
          
          manga_url = manga.get("href", None)
          if not manga_url or not manga_name:
            continue
          
          manga_url = urljoin(self.url, manga_url)
          poster = manga.find("img").get("src") if manga.find("img") else None
          
          results.append({
            "title": manga_name,
            "url": manga_url,
            "poster": poster
          })
        except Exception:
          continue
        
    except TypeError:
      return results
    
    except Exception as er:
      logger.error(f"{self.__class__} Error: {er}")
    
    return results

  @staticmethod
  def get_infomation(bs: BeautifulSoup, data: dict) -> None:
    
    title = bs.find(class_="md-title")
    data['title'] = title.text.strip() if title else data['title']
    
    tag_box = bs.select_one("table.info-table")

    status = "N/A"
    if tag_box:
      for tag in tag_box.find_all("tr"):
        if tg_tag := tag.find(class_="it-label"):
          if str(tg_tag.text).lower() == "status":
            if tg_va := tag.find(class_="it-value"):
              status = tg_va.text.strip()
              break
    
    geners = "N/A"
    g_tag = bs.select_one("div.tags-wrap")
    if g_tag:
      geners = ", ".join([str(g.text).strip() for g in g_tag.find_all("a")])
      
    summary = bs.select_one("div#synopsis.synopsis-text.collapsed")
    summary = str(summary.text).strip() if summary else "N/A"
    
    data['msg'] = DEAULT_MSG_FORMAT.format(
      title=data['title'],
      status=status,
      genres=geners,
      summary=summary[:200],
      url=data['url']
    )
    
  async def get_chapters(self, data: dict, page: int = 1) -> dict:
    results: dict = data.copy()
    
    content = await shared_scraper.get(data['url'])

    if not content:
      return results
    
    bs = BeautifulSoup(content, "html.parser")
    self.get_infomation(bs, results)

    results.setdefault("chapters", [])
    for chapter in bs.select("li.ch-item"):
      chapter_url = chapter.find("a").get("href", None) if chapter.find("a") else None
      if not chapter_url:
        continue

      chapter_url = urljoin(self.url, chapter_url)
      chapter_title = chapter.find(class_="ch-num")
      
      chapter_title = chapter_title.text.strip() if chapter_title else "N/A"
      results['chapters'].append({
        "title": chapter_title,
        "url": chapter_url,
        "manga_title": results['title'],
        "poster": results['poster'] if 'poster' in results else None
      })
    return results
    
  def iter_chapters(self, data, page: int = 1):
    chapters_list = []
    
    if "chapters" not in data:
      return []
    
    chapters_list = data['chapters']
    
    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  
  async def get_pictures(self, url: str, data=None) -> list:
    content = await shared_scraper.get(url)
    if not content:
      return []
    
    bs = BeautifulSoup(content, "html.parser")
    
    c_list = bs.find_all(class_="page-wrapper")
    
    i_list = [ img.find_next("img") for img in c_list ]

    return [ i.get("src") for i in i_list ]
  
