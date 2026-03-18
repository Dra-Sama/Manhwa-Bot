
from .scraper import Scraper
import json

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus

import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT


class ManhuaFastWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://manhuafast.net/"
    self.bg = None
    self.sf = "mufa"
    self.headers = {
      #"Accept": "*/*",
      "Connection": "keep-alive",
      "Host":"manhuafast.net",
      "Referer": "https://manhuafast.net/",
      "sec-ch-ua": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
      "sec-ch-ua-mobile": "?0",
      "sec-ch-ua-platform": "Windows",
      "Sec-Fetch-Dest": "empty",
      "Sec-Fetch-Mode": "cors",
      "Sec-Fetch-Site": "same-origin",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    }

  async def search(self, query: str = ""):
    url = f"https://manhuafast.net/?s={quote_plus(query)}&post_type=wp-manga&post_type=wp-manga"
    try:
      mangas = await self.get(url, headers=self.headers)
    except:
      try: mangas = await self.get(url, cs=True, headers=self.headers)
      except: return []

    bs = BeautifulSoup(mangas, "html.parser")
    con = bs.find(class_="tab-content-wrap")
    cards = con.find_all("div", class_="row c-tabs-item__content")
    results = []
    for card in cards:
      data = {}
      data['url'] = card.find_next("a").get('href').strip()
      
      data['poster'] = card.find_next("img").get('data-src').strip()
      data['title'] = card.find_next('h3').text.strip()

      results.append(data)
    
    return results

  async def get_chapters(self, data, page: int=1):
    results = data
    content = await self.get(results['url'], headers=self.headers)
    if content:
      bs = BeautifulSoup(content, "html.parser")
      con = bs.find(class_="summary_content_wrap")
      
      generes = con.find_next(class_="genres-content")
      generes = ", ".join([g.text.strip() for g in generes.find_all("a")]) if generes else "N/A"
      
      des = bs.find(class_="summary__content show-more").text.strip() if bs.find(class_="summary__content show-more") else "N/A"
      
      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status="N/A",
        genres=generes,
        summary=des[:200],
        url=results['url']
      )
      
    try: 
      chapters = await self.post(f"{results['url']}ajax/chapters/", headers=self.headers)
    except:
      try: chapters = await self.post(f"{results['url']}ajax/chapters/", cs=True, headers=self.headers)
      except: chapters = None
    
    results['chapters'] = chapters if chapters else []

    return results

  def iter_chapters(self, data, page: int=1):
    chapters_list = []
    
    if data['chapters']:
      bs = BeautifulSoup(data['chapters'], "html.parser")
      
      cards = bs.find_all("a")
      for card in cards:
        link = card.get("href", ":")
        if link and link.startswith("https://manhuafast.net/manga"):
          chapters_list.append({
            "title": card.text.strip(),
            "url": link,
            "manga_title": data['title'],
            "poster": data['poster'] if 'poster' in data else None,
          })
    
    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    response = await self.get(url, headers=self.headers)
    bs = BeautifulSoup(response, "html.parser")

    div_tags = bs.find(class_="reading-content")
    imgs_tags = div_tags.find_all(class_="page-break no-gaps")
    
    image_links = []
    for img in imgs_tags:
      image_url = img.find_next('img').get('data-src').strip()
      image_url = image_url.replace('https:///', 'https://')
      image_links.append(image_url)
    
    return image_links
