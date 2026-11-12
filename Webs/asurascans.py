# Code By @V_Sbotmaker (on Telegram)
from .scraper import shared_scraper as scraper
import json

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus

import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT
from copy import deepcopy as copy



class AsuraScansWebs:
  url: str = "https://asurascans.com"
  sf: str = "as"
  cs: bool = True 
  
  api_url: str = "https://api.asurascans.com"
  headers: dict = {
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
      "Host": "asurascans.com",
      "Connection": "keep-alive",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
  }
  
  async def search(self, query: str = "") -> list:
    results = []
    headers = copy(self.headers)
    headers['Host'] = "api.asurascans.com"
    headers['Accept'] = "application/json, text/plain, */*"
    
    search_url = f"{self.api_url}/api/search?q={quote(query)}"
    
    mangas = await scraper.get(
      search_url, cs=True, rjson=True,
      headers=headers
    )
    
    if not isinstance(mangas, dict):
      return results
    
    if "data" not in mangas or not isinstance(mangas['data'], list):
      return results
    
    for manga_data in mangas['data']:
      cover = manga_data.get("cover", None)
      title = manga_data.get("title", None)
      url = manga_data.get("public_url", None)
      if not url:
        continue

      url = urljoin(self.url, url)
      
      genres = manga_data.get("genres", [])
      genres = [ g['name'] for g in genres if "name" in g ]
      genres = ", ".join(genres) if genres else "N/A"
      status = manga_data.get("status", "N/A")
      description = manga_data.get("description", "N/A").strip()

      msg = DEAULT_MSG_FORMAT.format(
        title=title,
        status=status,
        genres=genres,
        summary=description[:400],
        url=url
      )
      results.append({
        "title": title,
        "url": url,
        "poster": cover,
        "msg": msg
      })
    
    return results

  async def get_chapters(self, data: dict, page: int=1) -> dict:
    results = data.copy()
    del data
    
    content = await scraper.get(
      results['url'], cs=True, headers=self.headers
    )
    if not content:
      return results
    
    
    bs = BeautifulSoup(content, "html.parser")
    
    if "poster" not in results or not results['poster']:
      ptag = bs.select_one("div.rounded-xl.z-0.w-full.h-full.absolute.top-0.left-0")
      if ptag and (img_tag := ptag.find_next("img")):
        img_tag = img_tag.get("src")
        results['poster'] = img_tag.strip() if img_tag else None
    
    if "msg" not in results or not results['msg']:
      # Description
      desc = bs.select_one("div.mt-3.relative")
      desc = desc.find_next("p") if desc else None
      desc = desc.text.strip() if desc else "N/A" 
      
      # Genres
      gene_tag = bs.select_one("div.hidden.lg\\:flex.max-w-full.gap-2.flex-wrap")
      genres = gene_tag.find_all("a") if gene_tag else []
      genres = ", ".join([ g.text.strip() for g in genres if g.text ])
      
      status = bs.select_one('span.text-base.font-bold[class*="text-[#A78BFA]"].capitalize')
      status = status.text.strip() if status else "N/A"
      
      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=results.get('type', "N/A"),
        genres=genres,
        summary=desc[:400],
        url=results['url']
      )

    
    container = bs.select_one("div.divide-y.divide-white\\/5")
    results['chapters'] = []
    for chapter in container.find_all("a"):
      chapter_url = chapter.get("href", None)
      if not chapter_url:
        continue
      chapter_url = urljoin(self.url, chapter_url)
      
      chapter_title = self.chapter_title(chapter.find_next("span"))
      if not chapter_title:
        continue
      
      results['chapters'].append({
          "title": chapter_title,
          "url": chapter_url,
          "manga_title": results['title'],
          "poster": results['poster'] if 'poster' in results else None,
      })
    
    return results
  
  @staticmethod
  def chapter_title(title) -> str:
    parts = []

    for content in title.contents:
        if content.name == 'span':
            parts.append(content.text.strip())
        elif isinstance(content, str):
            parts.append(content.strip())
    
    return ' '.join(parts).replace("  ", " ")

  
  def iter_chapters(self, data, page: int=1) -> list:
    if "chapters" not in data:
      return []
    
    return data['chapters'][(page - 1) * 60:page * 60] if page != 1 else data['chapters']

  @staticmethod
  def clean_astro(props_str: str):
    while True:
      props_str = props_str.replace('&quot;', '"')
      try:
        return json.loads(props_str)
      except Exception:
        continue
      
  async def get_pictures(self, url, data=None) -> list:
    image_url = []
    
    response: str = await scraper.get(url, cs=True, headers=self.headers)
    if not response:
      return image_url

    bs = BeautifulSoup(response, "html.parser")
    
    astro_tag = bs.find_all("astro-island")
    for astro_ in astro_tag:
      astro_text = astro_.get("props", None)
      if not isinstance(astro_text, str):
        continue
      
      astro_text = self.clean_astro(astro_text)
      if not astro_text:
        continue

      
      if "pages" not in astro_text:
        continue
      for img in astro_text['pages']:
        if not isinstance(img, list):
          continue
        
        for img_x in img:
          try:
            if not isinstance(img_x[1], dict):
              continue
            
            image_url.append(img_x[1]['url'][-1])
          except Exception:
            continue

    return image_url

  
