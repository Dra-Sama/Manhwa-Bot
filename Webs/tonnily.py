# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper
import json

from bs4 import BeautifulSoup
from urllib.parse import urlencode, urljoin, quote, quote_plus

import json
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT, BYPASS_URL_2 as BYPASS_URL


IMAGES_HEADERS = {
  "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
  "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
  "Connection": "keep-alive",
  "Host": "cdn.toonily.com",
  "Referer": "https://toonily.com/",
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
}
IMAGES_HEADERS_quote = quote(json.dumps(IMAGES_HEADERS))


class ToonilyWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://toonily.com/"
    self.api_url = "https://toonily.com/wp-admin/admin-ajax.php"
    self.sf = "toon"
    self.search_headers = {
      "accept": "text/html",
      #"accept-encoding": "gzip, deflate, br, zstd",
      "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
      "connection": "keep-alive",
      #"content-length": "156",
      "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
      "host": "toonily.com",
      "origin": "https://toonily.com",
      "referer": "https://toonily.com/",
      "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    }

    self.headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    #"Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-GB,en;q=0.9",
    "Connection": "keep-alive",
    "Host": "toonily.com",
    "Referer": "https://toonily.com/",
    "Sec-Fetch-User": "?1",
    "Sec-GPC": "1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
  }

  async def search(self, query: str = ""):
    params = {
      "action": "ajaxsearchpro_search",
      "aspp": quote_plus(query),  # or quote_plus if you prefer
      "asid": "1",
      "asp_inst_id": "1_1",
      "options": "filters_initial=1&filters_changed=0&qtranslate_lang=0&current_page_id=14"
    }

    query_string = urlencode(params, quote_via=quote)
    leng = str(len(query_string))

    headers = self.search_headers
    headers['content-length'] = leng
    bypass_url = BYPASS_URL.format(quote(self.api_url))
    bypass_url += f"&headers={quote(json.dumps(headers))}"

    mangas = await self.post(bypass_url, data=query_string)
    bs = BeautifulSoup(mangas, "html.parser") if mangas else None

    cards = bs.find_all(class_="asp_content") if bs else []

    results = []
    for card in cards:
      data = {}
      data['url'] = card.findNext("a", class_="asp_res_url").get("href")
      data['title'] = card.findNext("a", class_="asp_res_url").text.strip()
      data['poster'] = card.findNext("img").get("src")
      results.append(data)

    return results

  async def get_chapters(self, data, page: int=1):
    results = data.copy()

    headers = self.headers
    headers['Purpose'] = "prefetch"
    url = BYPASS_URL.format(quote(results['url']))
    url += f"&headers={quote(json.dumps(headers))}"
    try: 
      content = await self.get(url)
    except: 
      content = None

    if not content:
      return results

    bs = BeautifulSoup(content, "html.parser")

    # --- genres ---
    genres_ = bs.find(class_="genres-content")
    genres_ = genres_.find_all("a") if genres_ else None
    genres_ = ", ".join([genre.text.strip() for genre in genres_]) if genres_ else "N/A"

    # --- Status --- 
    status_ = bs.find(class_="post-status")
    try:
      status_ = next(
        (
          item.find_next("div").text.strip()
          for item in status_.find_all("h5")
          if "status" in item.text.strip().lower()
        ),
        "N/A"
      )
    except Exception:
      status_ = "N/A"
    
    # --- Summary ---
    summary_ = bs.find(class_="summary__content")
    summary_ = summary_.text.strip() if summary_ else "N/A"

    results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=status_ if status_ else "N/A",
        genres=genres_ if genres_ else "N/A",
        summary=summary_ if summary_ else "N/A",
        url=results['url']
    )

    container = bs.find("ul", class_="main version-chap no-volumn") if bs else None
    cards = container.find_all("li") if container else []
    results['chapters'] = []
    for card in cards:
      try:
        data = {}
        data["title"] = card.find_next("a").text.strip()
        data["url"] = card.find_next("a").get("href")
        data["manga_title"] = results['title']
        data["poster"] = results['poster'] if 'poster' in results else None
        results['chapters'].append(data)
      except:
        continue

    return results


  def iter_chapters(self, data, page: int=1):
    if "chapters" in data:
      return data['chapters'][(page - 1) * 60:page * 60] if page != 1 else data['chapters']

  async def get_pictures(self, url, data=None):
    url = BYPASS_URL.format(quote(url))
    url += f"&headers={quote(json.dumps(self.headers))}"

    content = await self.get(url, cs=True)
    if not content:
      return 
    
    bs = BeautifulSoup(content, "html.parser") 

    container = bs.find(class_="reading-content") if bs else None

    cards = container.find_all(class_="page-break no-gaps") if container else None
    images_url = []
    if cards:
      for card in cards:
        try:
          url = card.findNext("img").get("data-src")
          url = BYPASS_URL.format(quote(url))
          url += f"&headers={IMAGES_HEADERS_quote}"
          images_url.append(url)
        except Exception:
          continue

    return images_url
