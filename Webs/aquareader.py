# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper, shared_scraper
import json, re
from bs4 import BeautifulSoup

from loguru import logger
from urllib.parse import urlparse, urljoin, quote, quote_plus

from .utitls import DEAULT_MSG_FORMAT


class AquaReaderWebs:
  url = "https://aquareader.net"
  sf = "aqre"

  async def search(self, query: str = ""):
    search_url = f"{self.url}/?s={quote_plus(query)}&post_type=wp-manga"
    html = await shared_scraper.get(search_url)

    soup = BeautifulSoup(html, "html.parser")
    results = []
    for row in soup.select(".c-tabs-item__content"):
      title_tag = row.select_one(".post-title a")
      if not title_tag:
        continue
      result_title = title_tag.get_text(strip=True)
      result_url = title_tag['href']
      img_tag = row.select_one(".tab-thumb img")
      thumbnail = img_tag['src'] if img_tag else None
      genres = [
          a.get_text(strip=True) for a in row.select("div.genres-content a")
      ]
      status = None
      for item in row.select("div.post-content_item"):
        heading = item.select_one('.summary-heading')
        if heading and 'status' in heading.get_text(strip=True).lower():
          content = item.select_one('.summary-content')
          status = content.get_text(strip=True) if content else None
          break

      results.append({
          "title": result_title,
          "url": result_url,
          "poster": thumbnail,
          "genres": genres if genres else "N/A",
          "status": status if status else "N/A"
      })

    return results

  async def get_chapters(self, data, page: int = 1):
    results = data.copy()
    try:
      html = await shared_scraper.get(results['url'])
      
      soup = BeautifulSoup(html, "html.parser")
      
      # Summary
      summary_tag = soup.select_one("div.description-summary .summary__content")
      summary = summary_tag.get_text(separator="\n", strip=True) if summary_tag else None
      
      # Genres
      genres = [a.get_text(strip=True) for a in soup.select("div.genres-content a")]
      genres = ", ".join(genres) if genres else "N/A"

      poster_tag = soup.select_one("div.summary_image")
      if poster_tag:
        poster_tag = poster_tag.find("img")
        results['poster'] = poster_tag.get('src', None) if poster_tag else None
      
      # Status
      status = None
      for item in soup.select("div.post-content_item"):
        heading = item.select_one('.summary-heading')
        if heading and 'status' in heading.get_text(strip=True).lower():
            content = item.select_one('.summary-content')
            status = content.get_text(strip=True) if content else None
            break
      
      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=status if status else results['status'],
        genres=genres if genres else results['genres'],
        summary=summary[:200] if summary else "N/A",
        url=results['url']
      )
      
      # Chapters
      if results['url'].endswith("/"):
        ajax_url = results['url'] + "ajax/chapters/"
      else:
        ajax_url = results['url'] + "/ajax/chapters/"
      
      results['chapters'] = []
      
      chapters_html = await shared_scraper.get(ajax_url)
      chapters_soup = BeautifulSoup(chapters_html, "html.parser")
      for li in chapters_soup.select("li.wp-manga-chapter"):
        a = li.find("a")
        if a:
          results['chapters'].append((a.get_text(strip=True), a["href"]))
          
    except Exception as err:
      logger.exception(f"AquaReader: {err}")
    
    return results

  def iter_chapters(self, data, page: int = 1):
    chapters_list = []

    if "chapters" in data:
      for card in data['chapters']:
        chapters_list.append({
            "title": card[0],
            "url": card[1],
            "manga_title": data['title'],
            "poster": data['poster'] if 'poster' in data else None,
        })

    return chapters_list[(page - 1) * 60:page *60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    html = await shared_scraper.get(url)
    
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one('.reading-content')
    img_urls = []

    if not container:
      return []
    
    for img in container.find_all("img", class_="wp-manga-chapter-img"):
      url = str(img.get("data-src") or img.get("src") or "").strip()
      if url and url.startswith("http"):
        img_urls.append(url)
    
    return img_urls
