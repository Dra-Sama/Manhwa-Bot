# Code By @V_Sbotmaker (on Telegram)
from .scraper import shared_scraper as scraper
import json, re
from bs4 import BeautifulSoup

from loguru import logger
from urllib.parse import urlparse, urljoin, quote, quote_plus

from .utitls import DEAULT_MSG_FORMAT


class ResetScansWebs:
  __slots__ = ("url", "sf", "headers")
  
  def __init__(self):
    self.url = "https://reset-scans.org/"
    self.sf = "r-s"

    self.headers = {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0",
        "Accept":
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": self.url,
    }

  async def search(self, query: str = ""):
    ajax_url = urljoin(self.url, "wp-admin/admin-ajax.php")
    payload = {"action": "wp-manga-search-manga", "title": query}
    data = await scraper.post(
      ajax_url, rjson=True,
      data=payload, headers=self.headers
    )
    
    results = []
    if data.get("success") and data.get("data"):
      for item in data["data"]:
        results.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "type": item.get("type", "manga"),
        })

    return results

  async def get_chapters(self, data, page: int = 1):
    results = data.copy()
    HTML = await scraper.get(
      results['url'], headers=self.headers
    )
    
    if not HTML:
      return results

    soup = BeautifulSoup(HTML, "html.parser")
    
    cover_tag = soup.select_one(".summary_image img")
    results['poster'] = cover_tag["src"] if cover_tag else None

    summary_tag = soup.select_one("div.description-summary .summary__content")
    summary = summary_tag.get_text(separator="\n",
                                   strip=True) if summary_tag else None

    genres = [
        a.get_text(strip=True) for a in soup.select("div.genres-content a")
    ]

    status = None
    for item in soup.select("div.post-content_item"):
      heading = item.select_one('.summary-heading')
      if heading and 'status' in heading.get_text(strip=True).lower():
        content = item.select_one('.summary-content')
        status = content.get_text(strip=True) if content else None
        break
    
    results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=status if status else "N/A",
        genres=", ".join(genres) if genres else "N/A",
        summary=summary[:200] if summary else "N/A",
        url=results['url']
    )
    
    results['chapters'] = []
    for li in soup.select("li.wp-manga-chapter.free-chap"):
      li_text_a = li.select_one(".li__text a")
      chap_title = li_text_a.get_text(strip=True) if li_text_a else None
      chap_url = li_text_a["href"] if li_text_a and li_text_a.get(
          "href") else None
      if chap_title and chap_url:
        results['chapters'].append((chap_title, chap_url))

    return results

  def iter_chapters(self, data, page: int = 1):
    chapters_list = []

    if "chapters" in data:
      try:
        for chapter in data['chapters']:
          chapters_list.append({
              "title": chapter[0],
              "url": chapter[1],
              "manga_title": data['title'],
              "poster": data['poster'] if 'poster' in data else None
          })

      except Exception as err:
        logger.exception(f" Error: {err}")
        return []

    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    html = await scraper.get(
      url, headers=self.headers, 
      cs=True
    )
    if not html:
      return []

    try:
      soup = BeautifulSoup(html, "html.parser")
      images = []
      for img in soup.select(".reading-content .wp-manga-chapter-img"):
          src = img.get("src")
          if src:
              src = src.strip()
              src = src.replace('\n', '').replace('\r', '').strip()
              if not src.startswith("http"):
                  src = urljoin(self.url, src)
              images.append(src)
      
      return images


    except:
      return []
