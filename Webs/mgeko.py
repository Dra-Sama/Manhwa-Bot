# Code By @V_Sbotmaker (on Telegram)

from .scraper import Scraper
import random

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus

import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT

def get_worker_url():
  return ""

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) "
        "Gecko/20100101 Firefox/117.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
}

scraper = Scraper(HEADERS)

class MgekoWebs:
  url = "https://www.mgeko.cc/"
  sf = "mgeko"


  async def search(self, query: str = ""):
    request_url = f"https://www.mgeko.cc/search/?search={quote_plus(query)}"
    mangas = await scraper.get(request_url, cs=True)
    results = []

    if mangas:
        bs = BeautifulSoup(mangas, "html.parser")
        ul = bs.find("ul", class_="novel-list grid col col2")

        if ul:
            cards = ul.find_all("li", class_="novel-item")
            if cards:
                for card in cards:
                    try:
                        data = {}
                        a_tag = card.find("a")
                        if not a_tag:
                            continue

                        data['title'] = a_tag.get('title') or a_tag.find("h4").text.strip()
                        data['url'] = urljoin(self.url, a_tag['href'])

                        img_tag = card.find("img")
                        if img_tag:
                            data['poster'] = img_tag.get('data-src') or img_tag.get('src')
                            if data['poster'] and data['poster'].startswith('/'):
                                data['poster'] = urljoin(self.url, data['poster'])
                        else:
                            data['poster'] = None

                        results.append(data)
                    except Exception:
                        continue

    # Fallback to autocomplete if nothing found via search page
    if not results:
        url = f"https://www.mgeko.cc/autocomplete?term={quote_plus(query)}"
        request_url = f"{get_worker_url()}?url={quote(url, safe='')}"

        mangas = await scraper.get(request_url, cs=True)
        if not mangas:
            return []

        bs = BeautifulSoup(mangas, "html.parser")

        cards = bs.find_all("li") if bs else None
        if cards:
            for card in cards:
                try:
                    data = {}
                    data['title'] = card.find_next("a")['title']
                    data['poster'] = card.find_next("img")['src']
                    data['url'] = urljoin(self.url, card.find_next("a")['href'])

                    results.append(data)
                except Exception:
                    continue

    return results

  async def get_chapters(self, data, page: int=1):
    results = data.copy()
    request_url = f"""{get_worker_url()}?url={quote(results['url'], safe="")}"""

    content = await scraper.get(request_url)
    if not content:
      return results

    bs = BeautifulSoup(content, "html.parser")

    cover = None
    cover_tag = bs.find("img", {"class": "series-cover"})
    if not cover_tag:
        manga_page = bs.find("div", {"id": "manga-page"})
        if manga_page:
            cover_tag = manga_page.find("img")

    if cover_tag and cover_tag.has_attr("src"):

      cover = cover_tag['src'].strip()
      if cover.startswith('/'):
          cover = urljoin("https://readermc.org", cover)

      cover = get_worker_url() + "?url=" + quote(cover, safe="")

    con = bs.find(class_="categories")
    if con:
      gen = ' '.join([con.text.strip() for con in con.find_all("a")])

      des = bs.find("p", class_="description").text.strip() if bs.find("p", class_="description") else "N/A"


      results['msg'] = DEAULT_MSG_FORMAT.format(
          title=results['title'],
          status="N/A",
          genres=gen,
          summary=des[:200],
          url=results['url']
      )

    chapters_url = f"{results['url']}all-chapters/"
    request_url = f"""{get_worker_url()}?url={quote(chapters_url, safe="")}"""
    chapters = await scraper.get(request_url)

    results['chapters'] = chapters if chapters else None

    return results

  def iter_chapters(self, data, page: int=1):
    chapters_list = []

    if 'chapters' in data:
      try:
        bs = BeautifulSoup(data['chapters'], "html.parser")

        ul = bs.find('div', {'id': 'chpagedlist'}) if bs else None

        lis = ul.find_all('li') if ul else None
      except Exception:
        return []

      if not lis:
        return


      for card in lis:
        try:
          chapter_slug = str(card.find_next("a")['title'])
          chapter_search = re.search(r"chapter-([\d]+(?:\.[\d]+)?)\-([\w-]+)", str(chapter_slug))
          chapter_text = f"{chapter_search.group(1)}-{chapter_search.group(2)}" if chapter_search else chapter_slug

          chapters_list.append({
            "title": chapter_text,
            "url": urljoin(self.url, str(card.find_next("a")['href'])),
            "manga_title": data['title'],
            "poster": data['poster'] if 'poster' in data else None,
          })
        except Exception:
          continue

    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    request_url = f"""{get_worker_url()}?url={quote(url, safe="")}"""

    content = await scraper.get(request_url, cs=True)
    if not content:
      return []

    bs = BeautifulSoup(content, "html.parser")

    ul = bs.find("div", {"id": "chapter-reader"})
    if not ul:
      return []

    images = ul.find_all('img')

    images_url = [quote(img.get('src'), safe=':/%') for img in images] if images else []

    return images_url
