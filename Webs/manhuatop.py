# Code By @V_Sbotmaker (on Telegram)

from .scraper import shared_scraper as scraper
import json

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus, urlencode

import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT

class ManhuaTopWebs:
  __slots__ = ('url', 'api_url', 'sf', 'headers')
  def __init__(self):
    super().__init__()
    self.url = "https://manhuatop.org"
    self.api_url = "https://manhuatop.org/wp-admin/admin-ajax.php"
    self.sf = "MTop"
    
    self.headers = {
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
      "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
      "Connection": "keep-alive",
      "Host": "manhuatop.org",
      "Sec-Fetch-Dest": "document",
      "Sec-Fetch-Mode": "navigate",
      "Sec-Fetch-Site": "none",
      "Sec-Fetch-User": "?1",
      "Upgrade-Insecure-Requests": "1",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"
    }

  async def search(self, query: str = ""):
    search_url = f"{self.url}/?s={quote_plus(query)}&post_type=wp-manga"
    html = await scraper.get(search_url, headers=self.headers)
    if not html: 
      return []

    results = []
    try:
      soup = BeautifulSoup(html, "html.parser")
      results = []
      for div in soup.select("div.c-tabs-item__content"):
          a_tag = div.find("a", href=True)
          img_tag = div.find("img")
          title_tag = div.find("h2")
          if a_tag and img_tag and title_tag:
              title = title_tag.get_text(strip=True)
              url = a_tag["href"]
              thumbnail = img_tag.get("data-src") or img_tag.get("src")
              if thumbnail and thumbnail.startswith("//"):
                  thumbnail = "https:" + thumbnail
              elif thumbnail and thumbnail.startswith("/"):
                  thumbnail = urljoin(self.url, thumbnail)

              results.append({
                  "title": title,
                  "url": url,
                  "poster": thumbnail
              })
    except Exception as e:
      logger.error(f"ManhuaTop Error: {e}")
    finally:
      return results

  async def get_chapters(self, data, page: int=1):
    results = data.copy()
    html = await scraper.get(data['url'], headers=self.headers)
    if not html:
      return results
    
    soup = BeautifulSoup(html, "html.parser")

    # Cover
    cover = None
    img_tag = soup.select_one("div.summary_image img")
    if img_tag:
        cover = img_tag.get("data-src") or img_tag.get("src")
        if cover and cover.startswith("//"):
          results['poster'] = "https:" + cover
        elif cover and cover.startswith("/"):
          results['poster'] = urljoin(self.url, cover)

    # Summary
    summary = None
    desc = soup.select_one(".description-summary .summary__content")
    if desc:
        p = desc.find("p")
        summary = p.get_text(strip=True) if p else desc.get_text(" ", strip=True)
    if not summary:
        meta_desc = soup.find("meta", {"name": "description"})
        if meta_desc and meta_desc.get("content"):
            summary = meta_desc["content"].strip()

    # Genres
    genres = []
    genre_div = soup.select_one("div.post-content_item.manga_genre .genres-content")
    if genre_div:
        for a in genre_div.find_all("a"):
            g = a.text.strip()
            if g:
                genres.append(g)
    genres = ", ".join(genres) if genres else "N/A"

    # Status
    status = None
    status_div = soup.select_one("div.post-content_item.manga_status .summary-content")
    if status_div:
        status = status_div.get_text(strip=True)
    
    results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=status if status else "N/A",
        genres=genres if genres else "N/A",
        summary=summary[:400] if summary else "N/A",
        url=results['url']
    )
    
    # Chapters
    try:
      if results['url'].endswith("/"):
        ajax_url = results['url'] + "ajax/chapters/"
      else:
        ajax_url = results['url'] + "/ajax/chapters/"
      
      headers = self.headers.copy()
      headers['Accept'] = '*/*'
      headers['Origin'] = "https://manhuatop.org"
      headers['Referer'] = results['url']
      headers['Sec-Fetch-Dest'] = "empty"
      headers['Sec-Fetch-Mode'] = "cors"
      headers['Sec-Fetch-Site'] = "same-origin"
      headers['X-Requested-With'] = 'XMLHttpRequest'
      
      html = await scraper.post(ajax_url, headers=headers)
      if not html:
        return results
      
      soup = BeautifulSoup(html, "html.parser")
      results['chapters'] = []
      for li in soup.find_all("li"):
        a = li.find("a")
        if a:
          ch_title = a.get_text(strip=True)
          ch_url = urljoin(self.url, a.get("href", "").strip())
          results['chapters'].append((ch_title, ch_url))
    except Exception as e:
      logger.error(f"ManhuaTop Chapters Error: {e}")
    
    return results

  def iter_chapters(self, data, page: int=1):
    chapters_list = []

    if data['chapters']:
      try:
        for card in data['chapters']:
          chapters_list.append({
            "title": card[0],
            "url": card[1],
            "manga_title": data['title'],
            "poster": data['poster'] if 'poster' in data else None,
          })
      except Exception as err:
        logger.error(f"ManhuaUS Error: {err}")

    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    response = await scraper.get(url, headers=self.headers)
    if not response:
      return []
    
    image_links = []
    
    bs = BeautifulSoup(response, "html.parser")
    try:
      for img in bs.select(".reading-content img"):
        src = img.get("data-src") or img.get("src")
        if src and "loading" not in src:
          if src.startswith("//"):
            src = "https:" + src
          elif src.startswith("/"):
            src = urljoin(self.url, src)
          
          image_links.append(src)
    except:
      try:
        cards = bs.find_all(class_="page-break no-gaps")
        
        mangas = [card.findNext('img') for card in cards]
        
        image_links = [manga.get("data-src").strip() for manga in mangas]
      except:
        image_links = []
    
    return image_links
