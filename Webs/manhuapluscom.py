# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper

from bs4 import BeautifulSoup
from urllib.parse import quote, quote_plus

from loguru import logger
from .utitls import DEAULT_MSG_FORMAT

import re


class ManhuaPlusComWebs(Scraper):

  def __init__(self):
    super().__init__()
    self.url = "https://manhuaplus.com/"
    self.sf = "diva"
    self.headers = {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"
    }

  async def search(self, query: str = ""):
    url = f"{self.url}?s={query}&post_type=wp-manga"
    html = await self.get(url, headers=self.headers)
    if not html:
      return []

    results = []
    try:
      bs = BeautifulSoup(html, "html.parser")
      cards = bs.find("div", {"class": "c-tabs-item"})
      if not cards:
        return []

      mangas = cards.find_all('div', {'class': 'tab-thumb'})

      for manga in mangas:
        results.append({
            "title": manga.a.get('title'),
            "url": manga.a.get('href'),
            "poster": manga.findNext('img').get('data-src'),
        })
    except Exception as e:
      logger.exception(f"mangaplus Error: {e}")
    finally:
      return results

  async def get_chapters(self, data, page: int = 1):
    results = data.copy()
    page = await self.get(results['url'], headers=self.headers)

    if not page:
      return results

    soup = BeautifulSoup(page, "html.parser")

    # Cover
    if "poster" not in results or not results['poster']:
      img_tag = soup.select_one(".summary_image img")
      results['poster'] = img_tag.get("data-src") if img_tag else None

    # Summary
    desc_tag = soup.find("div", {"class": "summary__content"})
    summary = None
    if desc_tag:
      p = desc_tag.find('p')
      summary = p.text.strip() if p else desc_tag.text.strip()

    # Genres
    genres = [a.text.strip() for a in soup.select(".genres-content a")]
    genres = ", ".join(genres) if genres else "N/A"

    # Status
    status = None
    status_div = soup.find('div', class_='post-status')
    if status_div:
      for item in status_div.find_all('div', class_='post-content_item'):
        heading = item.find(class_='summary-heading')
        if heading and 'status' in heading.get_text(strip=True).lower():
          content = item.find(class_='summary-content')
          if content:
            status = content.get_text(strip=True)
            break
    
    if not status:
      status_tag = soup.find("div", {"class": "post-status"})
      if status_tag:
        for div in status_tag.find_all("div", {"class": "post-content_item"}):
          label = div.find("h3", {"class": "summary-heading"})
          if label and "Status" in label.text:
            status_span = div.find("span", {"class": "summary-content"})
            if status_span:
              status = status_span.text.strip()
    
    results['msg'] = DEAULT_MSG_FORMAT.format(
      title=results['title'],
      status=status if status else "N/A",
      genres=genres if genres else "N/A",
      summary=summary[:200] if summary else "N/A",
      url=results['url']
    )

    # Chapters
    results['chapters'] = []
    if results['url'].endswith('/'):
      ajax_url = results['url'] + "ajax/chapters/"
    else:
      ajax_url = results['url'] + "/ajax/chapters/"
    
    ajax_html = await self.get(ajax_url, headers=self.headers)
    if not ajax_html:
      return results
    
    ajax_soup = BeautifulSoup(ajax_html, "html.parser")
    lis = ajax_soup.find_all("li", {"class": "wp-manga-chapter"})
    for li in lis:
      a = li.find("a")
      if a:
        chaptitle = a.text.strip()
        ch_url = a.get("href")
        results['chapters'].append((chaptitle, ch_url))

    return results

  def iter_chapters(self, data, page: int = 1):
    chapters_list = []

    if data['chapters']:
      try:
        for card in data['chapters']:
          chapters_list.append({
              "title":
              card[0],
              "url":
              card[1],
              "manga_title":
              data['title'],
              "poster":
              data['poster'] if 'poster' in data else None,
          })
      except Exception as err:
        logger.exception(f"DiavToons Error: {err}")

    return chapters_list[(page - 1) * 60:page *
                         60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    response = await self.get(url, headers=self.headers)
    if not response:
      return []
    
    soup = BeautifulSoup(response, "html.parser")
    content = soup.find("div", {"class": "reading-content"})
    if not content:
        return []
    
    images = content.find_all("img")
    return [quote(img.get("src"), safe=":/%") for img in images if img.get("src")] if images else []


