# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper

from bs4 import BeautifulSoup
from urllib.parse import quote, urlencode

import json
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT, BYPASS_URL_2 as BYPASS_URL

API_HEADERS = {
  "Accept": "application/json, text/javascript, */*; q=0.01",
  "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
  "Connection": "keep-alive",
  #"Content-Length": "39",
  "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
  "Host": "allporncomic.com",
  "Origin": "https://allporncomic.com",
  "Referer": "https://allporncomic.com/home-3/",
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
  "X-Requested-With": "XMLHttpRequest",
}

HEADERS = {
  "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
  "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
  "Connection": "keep-alive",
  "Host": "allporncomic.com",
  "Upgrade-Insecure-Requests": "1",
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
}

IMAGES_HEADERS = {
  "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
  "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
  "Connection": "keep-alive",
  "Host": "allporncomic.com",
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
}
class AllPornComicWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://allporncomic.com"
    self.bg = None
    self.sf = "apc"


  async def search(self, query: str = ""):
    try:
      api_url = "https://allporncomic.com/wp-admin/admin-ajax.php"
      params = {"action":"wp-manga-search-manga", "title": query}

      query_string = urlencode(params, quote_via=quote)
      leng = str(len(query_string))

      headers = API_HEADERS.copy()
      headers['Content-Length'] = leng

      bypass_url = BYPASS_URL.format(quote(api_url))
      bypass_url += f"&headers={quote(json.dumps(headers))}"

      mangas = await self.post(bypass_url, data=query_string, rjson=True)

      return mangas.get('data', []) if mangas and "data" in mangas else []

    except Exception as err:
      logger.exception(f"ALLPORNCOMIC Error: {err}")
      return []

  async def get_chapters(self, data, page: int=1):
    results = data.copy()
    url = BYPASS_URL.format(quote(results['url']))
    content = await self.get(url, cs=True)
    if not content:
      return results

    bs = BeautifulSoup(content, "html.parser")
  
    container = bs.find(class_="genres-content")
    if not container:
      return results
    
    geners = container.text.strip() if container else "N/A"

    container = bs.find(class_="description-summary") if bs else None

    des = container.text.strip() if container else "N/A"
    try:
      status_= bs.find(class_="post-status")
      status_ = status_.find("h5").find_next("div").text.strip()
    except Exception:
      status_ = "N/A"

    results['msg'] = DEAULT_MSG_FORMAT.format(
      title=results['title'],
      status=status_,
      genres=geners,
      summary=des[:400],
      url=results['url']
    )
    chapters = bs.find("ul", class_="main version-chap no-volumn")
    if not chapters:
      return chapters
    
    chapters = chapters.find_all("li")
    if not chapters:
      return results
      
    try:
      results['chapters'] = [
        (chapter_url, chapter_title)
        for chapter in chapters
        if (chapter_url := chapter.find("a")['href']) and (chapter_title := chapter.find("a").text.strip())
      ] 
    except Exception:
      pass

    return results


  def iter_chapters(self, data, page: int=1):
    chapters_list = []

    if 'chapters' in data:
      chapters_list = [
        {
          "title": card[1],
          "url": card[0],
          "manga_title": data['title'],
          "poster": data['poster'] if 'poster' in data else None
        }
        for card in data['chapters']
      ]

    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    url = BYPASS_URL.format(quote(url))
    url += "&headers=" + quote(json.dumps(HEADERS))

    content = await self.get(url)

    bs = BeautifulSoup(content, "html.parser") if content else None
    if not bs:
      return []
    
    card = bs.find(class_="reading-content")
    if not card:
      return []
    
    mangas = card.find_all('img')

    images_url = [manga.get("data-src").strip() for manga in mangas] if mangas else []

    images_url = [BYPASS_URL.format(quote(image_url)) + "&headers=" + quote(json.dumps(IMAGES_HEADERS)) for image_url in images_url] if images_url else []

    return images_url
