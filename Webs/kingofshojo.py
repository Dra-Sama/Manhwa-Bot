# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper
import json

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus

import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT


class KingofShojoWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://kingofshojo.com"
    self.sf = "kos"
    self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0'}

  async def search(self, query: str = ""):
    url = f"{self.url}/search/{quote_plus(query)}/"
    html = await self.get(url, headers=self.headers)
    if not html:
      return []

    soup = BeautifulSoup(html, "html.parser")
    results = []
    for bsx in soup.select("div.bsx"):
        a_tag = bsx.find("a")
        img_tag = bsx.find("img")
        if not a_tag or not img_tag:
            continue
        title = img_tag.get("title", "").strip() or img_tag.get("alt", "").strip() or a_tag.get("title", "").strip()
      
        url = urljoin(self.url, a_tag.get("href", "").strip())
        thumbnail = img_tag.get("src", "").strip()
        if thumbnail.startswith("//"):
            thumbnail = "https:" + thumbnail
        elif thumbnail.startswith("/"):
            thumbnail = urljoin(self.url, thumbnail)
        
        if title and url:
            results.append({
                "title": title,
                "url": url,
                "poster": thumbnail
            })
    
    return results


  async def get_chapters(self, data, page: int=1):
    results = data.copy()
    html = await self.get(results['url'], headers=self.headers)
    if html:
      soup = BeautifulSoup(html, "html.parser")

      # Cover
      if "poster" not in results or not results['poster']:
        thumb_div = soup.find("div", class_="thumb")
        if thumb_div:
          img = thumb_div.find("img")
          if img and img.get("src"):
              results['poster'] = img["src"].strip()
            
              if results['poster'].startswith("//"):
                results['poster'] = "https:" + results['poster']
              elif results['poster'].startswith("/"):
                results['poster'] = urljoin(self.url, results['poster'])
        
        if not results['poster']:
          meta_img = soup.find("meta", property="og:image")
          if meta_img and meta_img.get("content"):
            results['poster'] = meta_img["content"].strip()

      # Summary
      desc_div = soup.find("div", class_="entry-content entry-content-single")
      summary = None
      if desc_div:
          summary = desc_div.get_text(" ", strip=True)
      if not summary:
          meta_desc = soup.find("meta", {"name": "description"})
          if meta_desc and meta_desc.get("content"):
              summary = meta_desc["content"].strip()
      if not summary:
          meta_desc = soup.find("meta", property="og:description")
          if meta_desc and meta_desc.get("content"):
              summary = meta_desc["content"].strip()

      # Genres
      genres = []
      genre_div = soup.find("div", class_="seriestugenre")
      if genre_div:
          for a in genre_div.find_all("a"):
              g = a.text.strip()
              if g:
                  genres.append(g)
      
      genres = ", ".join(genres) if genres else "N/A"

      # Status
      try:
        status = next(
            (tds[1].get_text(strip=True) 
             for tr in (soup.find("table", class_="infotable") or []).find_all("tr") 
             for tds in [tr.find_all("td")] 
             if len(tds) >= 2 and "status" in tds[0].get_text(strip=True).lower()
            ), 
            None
        )
      except:
        status = "N/A"

      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=status if status else "N/A",
        genres=genres if genres else "N/A",
        summary=summary[:200] if summary else "N/A",
        url=results['url']
      )
      
      # Chapters
      results['chapters'] = []
      chapter_list = soup.find("div", id="chapterlist")
      if chapter_list:
          for li in chapter_list.find_all("li"):
              a = li.find("a")
              ch_title = None
              if a:
                  ch_num = a.find("span", class_="chapternum")
                  ch_title = ch_num.get_text(strip=True) if ch_num else a.get_text(strip=True)
                  ch_url = urljoin(self.url, a.get("href", "").strip())
                  if ch_title and ch_url:
                    results['chapters'].append((ch_title, ch_url))
    


    return results

  def iter_chapters(self, data, page: int=1):
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

    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    try:
      html = await self.get(url, headers=self.headers)
      soup = BeautifulSoup(html, "html.parser")
      images = []

      reader_div = soup.find("div", id="readerarea")
      if reader_div:
        imgs = reader_div.find_all("img")
        for img in imgs:
          src = img.get("src") or img.get("data-src")
          if src:
            if src.startswith("//"):
              src = "https:" + src
            elif src.startswith("/"):
              src = urljoin(self.url, src)
            
            images.append(src)
      if not images:
        imgs = soup.find_all("img")
        for img in imgs:
          src = img.get("src") or img.get("data-src")
          if src and "chapter" in src:
            if src.startswith("//"):
              src = "https:" + src
            elif src.startswith("/"):
              src = urljoin(self.url, src)
            
            images.append(src)
      
      return images

    except Exception as e:
      logger.error(f"KingofShojo Error: {e}")
      return []




