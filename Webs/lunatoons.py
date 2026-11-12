# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper
import json

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus

import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT

IMAGE_BASE = "https://image.meowing.org/uploads/"
BYPASS_URL = "https://api.shanksytprem.workers.dev/proxy?url={}"

class LunatoonsWebs(Scraper):

  def __init__(self):
    super().__init__()
    self.url = "https://lunatoons.org"
    self.sf = "lutoo"
    self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"}

  async def search(self, query: str = ""):
    url = BYPASS_URL.format(quote(f"{self.url}/series/"))
    html = await self.get(url, headers=self.headers)
    
    if not html:
      return []

    soup = BeautifulSoup(html, "html.parser")
    all_results = []

    for button in soup.select("#searched_series > button"):
      a_tag = button.find("a", href=True)
      if not a_tag:
        continue

      title_tag = button.select_one("h3")
      if not title_tag:
        continue

      result_title = title_tag.get_text(strip=True)
      if not result_title:
        continue

      result_url = title_tag.find_parent("a").get("href")

      cover_div = a_tag.find("div", style=re.compile("background-image"))
      cover = ""
      if cover_div and cover_div["style"]:
        m = re.search(r"url\((.*?)\)", cover_div["style"])
        if m:
          cover = m.group(1)

      all_results.append({
          "title": result_title,
          "url": f"{self.url}{result_url}",
          "poster": cover,
      })

    filtered_results = [
        result for result in all_results
        if query.lower() in result['title'].lower()
    ]

    return filtered_results

  async def get_chapters(self, data, page: int = 1):
    results = data
    url = BYPASS_URL.format(quote(results['url']))
    content = await self.get(url, headers=self.headers)
    if content:
      soup = BeautifulSoup(content, "html.parser")

      # Summary
      summary = None
      meta_desc = soup.select_one('meta[property="og:description"]') or soup.select_one('meta[name="description"]')
      if meta_desc and meta_desc.has_attr("content"):
          summary = meta_desc["content"]

      # Genres
      genres = None
      meta_keywords = soup.select_one('meta[name="keywords"]')
      if meta_keywords and meta_keywords.has_attr("content"):
        genres = [g.strip() for g in meta_keywords["content"].split(",") if g.strip()]
        genres = ", ".join(genres) if genres else "N/A"

      # Status
      status = None
      status_span = soup.find("span", string=re.compile(r"Status", re.I))
      if status_span:
          parent_div = status_span.find_parent("div", class_=re.compile("font-medium"))
          if parent_div and parent_div.find_next_sibling("div"):
              status_div = parent_div.find_next_sibling("div")
              status = status_div.get_text(strip=True)

      # Cover
      meta_cover = soup.select_one('meta[property="og:image"]')
      if meta_cover and meta_cover.has_attr("content"):
          results['poster'] = meta_cover["content"]
      
      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=status if status else "N/A",
        genres=genres if genres else "N/A",
        summary=summary[:400] if summary else "N/A",
        url=results['url']
      )
      
      # Chapters
      results['chapters'] = []
      for a in soup.select('a[href*="/chapter/"]'):
          chapter_title = a.get("title", "").strip()
          ch_url = a.get("href")
          if chapter_title and ch_url:
            results['chapters'].append((
                  chapter_title,
                  self.url + ch_url if ch_url.startswith("/") else ch_url
            ))
      
    return results

  def iter_chapters(self, data, page: int = 1):
    chapters_list = []
    if not data['chapters']:
      return []

    for card in data['chapters']:
      try:
        chapters_list.append({
            "title": card[0],
            "url": card[1],
            "manga_title": data['title'],
            "poster": data['poster'] if 'poster' in data else None,
        })
      except:
        continue

    return chapters_list[(page - 1) * 60:page *
                         60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    url = BYPASS_URL.format(quote(url))
    html = await self.get(url, headers=self.headers)
    if not html:
      return []

    soup = BeautifulSoup(html, "html.parser")

    uids = []
    for img in soup.find_all("img", uid=True):
        uid = img.get("uid")
        if uid and uid not in uids:
            uids.append(uid)

    return [f"{IMAGE_BASE}{uid}" for uid in uids]

