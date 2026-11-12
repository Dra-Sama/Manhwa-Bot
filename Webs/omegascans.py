# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper
import json

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus

import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT


class OmgeaScansWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://omegascans.org/"
    self.bg = None
    self.sf = "osw"
    self.headers = {}

  def get_series_id(self, html_content):
    pattern = r'series_id\\":(\d+)'
    matches = re.findall(pattern, html_content)
    if matches:
      unique_series_ids = list(set(matches))
      for series_id in unique_series_ids:
        try: 
          return int(series_id)
        except Exception: 
          continue
    else:
        return None

  async def search(self, query: str = ""):
    url = "https://api.omegascans.org/query"
    search_param = {"adult": "true", "query_string": query}

    mangas = await self.get(url, rjson=True, params=search_param)
    if not mangas:
      return []
    
    results = []
    if mangas["meta"]["total"] > 0 and "data" in mangas:
      for card in mangas['data']:
        if card['series_type'] == "Comic":
          card['url'] = f'https://omegascans.org/series/{card["series_slug"]}'
          card['poster'] = card.pop('thumbnail')
          results.append(card)

    return results

  async def get_chapters(self, data, page: int=1):
    results = {}
    if ('free_chapters' not in data) and (series_id := self.get_series_id(await self.get(data['url']))):
      api_url = f"https://api.omegascans.org/chapter/query?page=1&perPage=3000000000000000000&series_id={series_id}"
      chapters = await self.get(api_url, rjson=True)
      if chapters and "meta" in chapters and "data" in chapters:
        results['chapters'] = chapters.get('data', [])
        results['slug'] = results['chapters'][0]['series']['series_slug'] if results['chapters'] else None
        results['title'] = data.get("title", "N/A")
        results['url'] = data.get("url", "N/A")

    else:
      results['chapters'] = data.get('free_chapters', [])

      results['title'] = data['title']
      results['poster'] = data.get('poster', None)
      results['slug'] = data.pop('series_slug', None)
      results['url'] = data['url']

      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=data['title'],
        status=data.get('status', 'N/A'),
        genres=data.get('genres', 'N/A'),
        summary=data.get('description', 'N/A')[:200],
        url=data.get('url', 'N/A')
      )

    return results


  def iter_chapters(self, data, page: int=1):
    chapters_list = []

    if 'chapters' in data:
     for card in data['chapters']:

       chapters_list.append({
         "title": card['chapter_name'],
         "url": f"https://omegascans.org/series/{data['slug']}/{card['chapter_slug']}",
         "manga_title": data['title'],
         "poster": data['poster'] if 'poster' in data else None,
         })

    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    content = await self.get(url, cs=True)

    soup = BeautifulSoup(content, 'html.parser') if content else None
    img_tags = soup.find_all('img') if soup else []
    images_url = []
    for img in img_tags:
      img_url = img.get('data-src') if img.get('data-src') else img.get('src')
      if not img_url:
        continue
      
      img_url = str(img_url)
      if "media.omegascans.org" in img_url and "uploads" in img_url:
        images_url.append(img_url)

    return images_url
