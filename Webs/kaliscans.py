# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus

from loguru import logger
from .utitls import DEAULT_MSG_FORMAT

import re


class KaliScansWebs(Scraper):

  def __init__(self):
    super().__init__()
    self.url = "https://kaliscan.io"

    self.sf = "kis"
    self.headers = {
        'Accept': '*/*',
        #'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://kaliscan.io/',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36'
    }

  async def search(self, query: str = ""):
    search_url = f"{self.url}/search"
    params = {"q": query}

    html = await self.get(search_url, params=params, headers=self.headers)
    if not html:
      return []

    soup = BeautifulSoup(html, "html.parser")
    results = []
    for item in soup.select(".list.manga-list .book-item"):
      a_tag = item.select_one(".thumb a")
      if not a_tag:
        continue

      manga_url = urljoin(self.url, a_tag.get("href", ""))
      img_tag = a_tag.find("img")
      thumbnail = img_tag.get("data-src") or img_tag.get(
          "src") if img_tag else None

      title = None
      title_tag = item.select_one(".title h3 a")
      title = title_tag.get_text().strip() if title_tag else a_tag.get(
          "title", "").strip()

      genres = [g.get_text(strip=True) for g in item.select(".genres span")]
      summary = ""
      summary_tag = item.select_one(".summary p")
      if summary_tag:
        summary = summary_tag.get_text(strip=True)

      results.append({
          "title": title,
          "url": manga_url,
          "poster": thumbnail,
          "genres": genres,
          "summary": summary
      })

    return results

  async def get_chapters(self, data, page: int = 1):
    results = data.copy()
    html = await self.get(data['url'], headers=self.headers)

    if html:
      soup = BeautifulSoup(html, "html.parser")

      # Status
      status = None
      meta_box = soup.select_one("div.meta.box")
      if meta_box:
        for p in meta_box.find_all("p"):
          strong = p.find("strong")
          if strong and "Status" in strong.get_text():
            status_span = p.find("span")
            if status_span:
              status = status_span.get_text(strip=True)
            break

      # Genres
      genres = None
      if "genres" in results:
        genres = results.pop("genres")
      elif meta_box:
        for p in meta_box.find_all("p"):
          strong = p.find("strong")
          if strong and "Genres" in strong.get_text():
            genres = [
                a.get_text(strip=True).replace(",", "")
                for a in p.find_all("a")
            ]
            genres = [g for g in genres if g]
            genres = ", ".join(genres) if genres else "N/A"
            break

      # Cover
      cover_tag = soup.select_one("div.img-cover img")
      cover_url = None
      if cover_tag:
        cover_url = cover_tag.get("data-src") or cover_tag.get("src")
        if cover_url and cover_url.startswith("/"):
          cover_url = urljoin(self.url, cover_url)

      summary = ""
      if "summary" in results:
        summary = results.pop("summary")
      else:
        summary_div = soup.select_one("div.section-body.summary")
        if summary_div:
          for p in summary_div.find_all("p"):
            text = p.get_text(separator="\n", strip=True)
            if text:
              summary = text
              break

      results['msg'] = DEAULT_MSG_FORMAT.format(
          title=results['title'],
          status=status if status else "N/A",
          genres=genres if genres else "N/A",
          summary=summary[:400] if summary else "N/A",
          url=results['url'],
      )

      # Manga id
      m = re.search(r'/manga/(\d+)-', results['url'])
      manga_id = m.group(1) if m else None

      # Chapters
      try:
        results['chapters'] = []
        chaplist_url = f"{self.url}/service/backend/chaplist/?manga_id={manga_id}"
        
        chaplist_html = await self.get(chaplist_url, headers=self.headers)
        if chaplist_html:
          chap_soup = BeautifulSoup(chaplist_html, "html.parser")
          for li in chap_soup.select("ul.chapter-list > li"):
            a_tag = li.find("a")
            if not a_tag:
              continue
            
            chapter_title_tag = a_tag.find('strong', class_='chapter-title')
            chapter_title = chapter_title_tag.get_text(
              strip=True) if chapter_title_tag else a_tag.get("title",
                                                              "").strip()
            chapter_url = urljoin(self.url, a_tag['href'])
            results['chapters'].append((chapter_title, chapter_url))
      except Exception as e:
        logger.error(f"Error KaliScans Chapters: {e}")

    return results

  def iter_chapters(self, data, page: int = 1):
    chapters_list = []
    if not data['chapters']:
      return []

    for chapters in data['chapters']:
      try:
        chapters_list.append({
            "title":
            chapters[0],
            "url":
            chapters[1],
            "manga_title":
            data['title'],
            "poster":
            data['poster'] if 'poster' in data else None,
        })
      except:
        continue

    return chapters_list[(page - 1) * 60:page *
                         60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    try:
      html = await self.get(url, headers=self.headers)
      m = re.search(r'var\s+chapterId\s*=\s*(\d+)', html)
      if not m:
        return []
      
      chapter_id = m.group(1)
      ajax_url = f"{self.url}/service/backend/chapterServer/?server_id=1&chapter_id={chapter_id}"
      ajax_html = await self.get(ajax_url, headers=self.headers)
      
      soup = BeautifulSoup(ajax_html, "html.parser")
      pages = []
      for div in soup.select('div.chapter-image.chapter-lazy-image.server-1'):
        img_url = div.get('data-src')
        if img_url:
            pages.append(img_url)
      
      return pages
    except Exception as e:
      logger.error(f"Error KaliScans Images: {e}")
      return []
