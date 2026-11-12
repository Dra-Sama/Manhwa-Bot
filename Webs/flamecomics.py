# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper
import json

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus

import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT


class FlameComicsWebs(Scraper):
    def __init__(self):
      super().__init__()
      self.url = "https://flamecomics.xyz"
      self.sf = "fc"
      self.thumbnail = "https://flamecomics.xyz/_next/image?url=https%3A%2F%2Fcdn.flamecomics.xyz%2Fuploads%2Fimages%2Fseries%2F{id}%2F{thumb}&w=720&q=100"
      self.manga_url = "https://flamecomics.xyz/series/{id}"

      self.manga_api_id = "https://flamecomics.xyz/_next/data/CCokIcwOARfLGc-auhM_F/series/{id}.json"
      self.page_image = "https://cdn.flamecomics.xyz/uploads/images/series/{id}/{token}/{name}"

      self.sm_data = "CCokIcwOARfLGc-auhM_F"

      self.bg = True
      self.headers = {
        "Accept": "*/*",
        "Host": "flamecomics.xyz",
        "Connection": "keep-alive",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
      }

    def normalize(self, text):
      return ' '.join(text.lower().strip().split())

    async def search(self, query: str = ""):
      url = "https://flamecomics.xyz/api/series"
      content = await self.get(url, rjson=True, headers=self.headers)

      results = []
      search_normalized = self.normalize(query)
      if content:
        for data in content:
          title_normalized = self.normalize(data["label"])
          if search_normalized in title_normalized:
            data['title'] = data["label"]

            data['poster'] = self.thumbnail.format(id = str(data['id']), thumb = str(data["image"]))
            data['url'] = self.manga_url.format(id = str(data["id"]))
            
            results.append(data)

      return results

    async def get_chapters(self, data, page: int=1):
      results = data
      content = await self.get(results['url'], headers=self.headers)
      if content:
        bs = BeautifulSoup(content, "html.parser")
        container = bs.find("script", {"id": "__NEXT_DATA__"})
        content = json.loads(container.text.strip()) if container else None
        if content:
          results['chapters'] = content['props']['pageProps']['chapters']
          content = content['props']['pageProps']['series']

          results['id'] = content['series_id']
          description = content['description']
          geners  = ", ".join([g for g in content['tags']])

          results['msg'] = DEAULT_MSG_FORMAT.format(
            title=results['title'],
            status=results['status'] if "status" in results else "N/A",
            genres=geners,
            summary=description[:200],
            url=results['url']
          )

      return results

    def iter_chapters(self, data, page: int=1):
      chapters_list = []
      if not data['chapters']:
        return chapters_list
      
      for card in data['chapters']:
        chapters_list.append({
            "title": card['chapter'],
            "url": f"{data['url']}/{card['token']}",
            "manga_title": data['title'],
            "poster": data['poster'] if 'poster' in data else None,
        })

      return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

    async def get_pictures(self, url, data=None):
      try:
        content = await self.get(url, headers=self.headers)
        bs = BeautifulSoup(content, "html.parser")
        container = bs.find("div", {"style": "position:relative"})
        cards = container.find_all("img") if container else []
        return [ card['src'] for card in cards if card['src'].startswith("http") ]
      except:
        return []
