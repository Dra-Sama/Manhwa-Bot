# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper
import json

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus

import re
from loguru import logger

from .utitls import DEAULT_MSG_FORMAT

class PornhwazWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://www.pornhwaz.com"
    self.bg = None
    self.sf = "pzw"
    self.headers = {
      "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
      #"accept-encoding: gzip, deflate, br, zstd"
      "accept-language": "en-US,en;q=0.9",
      "priority": "u=0, i",
      "referer": "https://www.pornhwaz.com/",
      "sec-fetch-user": "?1",
      "upgrade-insecure-requests": "1",
      "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
    }
    self.picture_headers = {
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
      "Accept-Encoding": "gzip, deflate, br, zstd",
      "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
      "Connection": "keep-alive",
      "Host": "www.pornhwaz.com",
      "Sec-Fetch-Dest": "document",
      "Sec-Fetch-Mode": "navigate",
      "Sec-Fetch-Site": "none",
      "Sec-Fetch-User": "?1",
      "Upgrade-Insecure-Requests": "1",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    }

  async def search(self, query: str = ""):
    url = f"https://www.pornhwaz.com/?s={quote_plus(query)}&post_type=wp-manga"
    mangas = await self.get(url, headers=self.headers)
    if not mangas:
      return []
    
    bs = BeautifulSoup(mangas, "html.parser")

    container = bs.find('div', {'class': 'tab-content-wrap'})
    if not container:
      return []
    
    cards = container.find_all("div", {"class": "tab-thumb c-image-hover"})
    
    results = []
    for card in cards:
      data = {}
      data['url'] = urljoin(self.url, card.findNext("a").get("href"))
      data['title'] = card.findNext("a").get("title")

      data['poster'] = card.findNext("img").get("data-src")
      results.append(data)

    return results

  async def get_chapters(self, data, page: int=1):
    results = data.copy()

    content = await self.get(results['url'])
    bs = BeautifulSoup(content, "html.parser") if content else None

    container = bs.find(class_="genres-content") if bs else None
    geners = container.text.strip() if container else "N/A"

    des_ = bs.find(class_="description-summary") if bs else None
    des = des_.find_next("p").text.strip() if des_ and des_.find_next("p") else "N/A"

    status_ = bs.find(class_="post-status")
    try:
      status_ = next(
        (
          item.find_next("div").find_next("div").text.strip()
          for item in status_.find_all(class_="post-content_item")
          if "status" in item.text.strip().lower()
        ),
        "N/A"
      )
    except Exception:
      status_ = "N/A"

    results['msg'] = DEAULT_MSG_FORMAT.format(
      title=results['title'],
      status=status_ if status_ else "N/A",
      genres=geners if geners else "N/A",
      summary=des[:300] if des else "N/A",
      url=results['url'],
    )

    chapter_url = f"{results['url']}ajax/chapters/?t=1"

    chapters = await self.post(chapter_url, headers=self.headers)
    if not chapters:
      return results
    
    chapters = BeautifulSoup(chapters, "html.parser")
    results['chapters'] = chapters

    return results


  def iter_chapters(self, data, page: int=1):
    chapters_list = []

    if 'chapters' in data:
     for card in data['chapters'].find_all("li"):
       chapters_list.append({
         "title": card.find_next("a").text.strip(),
         "url": card.find_next("a")['href'],
         "manga_title": data['title'],
         "poster": data['poster'] if 'poster' in data else None,
         })

    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    content = await self.get(url, headers=self.headers)
    if not content:
      return []

    bs = BeautifulSoup(content, "html.parser")

    cards = bs.findAll("div", {"class": "page-break no-gaps"})

    images_url = [
      containers.findNext("img")["data-src"].strip() 
      if containers.findNext("img").get("data-src") else containers.findNext("img").get("src").strip()
      for containers in cards
    ] if cards else None

    return images_url

  async def get_updates(self, page:int=1):
    return []
