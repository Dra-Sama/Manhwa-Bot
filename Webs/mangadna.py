# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper
import json

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus, urlencode

import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT


class ManhaDNAWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://mangadna.com"
    self.sf = "DNA"
    self.headers = {
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
      #"Accept-Encoding": "gzip, deflate, br, zstd",
      "Accept-Language": "en-GB,en;q=0.8",
      "Connection": "keep-alive",
      #"Content-Length": "19",
      "Host": "mangadna.com",
      "Origin": "https://mangadna.com",
      "Sec-GPC": "1",
      "Upgrade-Insecure-Requests": "1",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    }

  async def search(self, query: str = ""):
    url = f"https://mangadna.com/search?q={quote_plus(query)}"
    html = await self.get(url, headers=self.headers)
    if not html: 
      return []

    results = []
    try:
      bs = BeautifulSoup(html, "html.parser")

      con = bs.find(class_="listupd")
      cards = con.find_all(class_="hinner")

      for card in cards:
        _tag = card.find(class_="htitle")
        data = {}

        data['url'] = urljoin(self.url, _tag.find_next("a").get("href"))
        data['title'] = card.find_next("a").get("title")


        data['poster'] = card.find_next("img").get("data-src")
        results.append(data)

    except Exception as e:
      logger.exception(f"MangaDNA Error: {e}")
    finally:
      return results

  async def get_chapters(self, data, page: int=1):
    results = data.copy()

    content = await self.get(results['url'], headers=self.headers)
    bs = BeautifulSoup(content, "html.parser") if content else None
    if bs:
      # -- Poster ---
      if "poster" not in results or not results['poster']:
        try:
          results['poster'] = bs.find(class_="summary_image").find_next("img").get("data-src") if bs.find(class_="thumb") else None
        except: 
          pass

      con = bs.find(class_="post-content")

      # -- Genres --
      genres_ = con.find_next(class_="genres-content")
      genres_ = ", ".join([g.text.strip() for g in genres_.find_all("a")]) if genres_ else "N/A"

      # --- Summary ---
      des = bs.find(class_="dsct").text.strip() if bs.find(class_="dsct") else "N/A"

      # -- Status ---
      status_ = con.find_next(class_="post-status")
      status_ = next(
        (
          tag_.find_next("div").text.strip()
          for tag_ in status_.find_all(class_="summary-heading")
          if tag_.text.strip().lower() == "status"
        ),
        "N/A"
      ) if status_ else "N/A"

      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=status_ if status_ else "N/A",
        genres=genres_ if genres_ else "N/A",
        summary=des[:200] if des else "N/A",
        url=results['url'],
      )

    chapters = bs.find("ul", class_="row-content-chapter")

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
            "url": urljoin(self.url, card['href']),
            "manga_title": data['title'],
            "poster": data['poster'] if 'poster' in data else None,
          })
      except Exception as err:
        logger.exception(f"MangaDNA Error: {err}")

    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    response = await self.get(url, headers=self.headers)
    if not response:
      return []

    bs = BeautifulSoup(response, "html.parser")

    cards = bs.find(class_="read-content")

    if not cards:
      return []

    mangas = cards.find_all("img") if cards else None

    image_links = [manga.get("data-src").strip() or manga.get("src").strip() for manga in mangas] if mangas else []

    return image_links
