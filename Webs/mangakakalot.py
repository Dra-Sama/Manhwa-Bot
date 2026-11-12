# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper
import json

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus

import re, ast
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT


class MangaKakalotGGWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://www.mangakakalot.gg"
    self.sf = "mkgg"
    self.headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0",
        "Referer": self.url,
    }


  async def search(self, query: str = ""):
    search_query = quote_plus(query.strip().replace(" ", "_"))
    search_url = f"{self.url}/search/story/{search_query}"
    html = await self.get(search_url, headers=self.headers)
    
    if not html:
      return []

    soup = BeautifulSoup(html, "html.parser")
    results = []
    for item in soup.select("div.panel_story_list div.story_item"):
        a_image = item.select_one("a[href] > img")
        a_link = item.select_one("a[href]")
        title_tag = item.select_one("div.story_item_right h3.story_name a")
        if not (title_tag and a_link):
            continue
        title = title_tag.get_text(strip=True)
        url = a_link["href"]
        if not url.startswith("http"):
            url = urljoin(self.url, url)
        
        thumbnail = a_image["src"] if a_image and a_image.get("src") else None
        results.append({
            "title": title,
            "url": url,
            "poster": thumbnail,
        })
    return results

  async def get_chapters(self, data, page: int=1):
    results = data
    content = await self.get(results['url'], headers=self.headers)
    if content:
      soup = BeautifulSoup(content, "html.parser")
      
      summary = ""
      content_box = soup.select_one("div#contentBox")
      if content_box:
        for tag in content_box.find_all(['h2', 'script']):
            tag.extract()
        summary = content_box.get_text(separator="\n", strip=True)
      
      try:
        genres = [
          a.get_text(strip=True)
          for a in soup.select("div.genres-wrap div.genre-list a")
          if a.get_text(strip=True)
        ]
        genres = ", ".join(genres)
      except:
        genres = "N/A"
      
      status = None
      for div in soup.select("div.info-wrap > div"):
        label = div.find("p")
        if label and label.get_text(strip=True).lower() == "status:":
            ps = div.find_all("p")
            if len(ps) > 1:
                status = ps[1].get_text(strip=True)
                break
      
      if not status:
        for li in soup.select("ul.manga-info-text li"):
            if "status :" in li.get_text(strip=True).lower():
                status = li.get_text(strip=True).split(":", 1)[-1].strip()
                break
      
      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=status if status else "N/A",
        genres=genres if genres else "N/A",
        summary=summary[:400] if summary else "N/A",
        url=results['url']
      )
      
      results['chapters'] = []
      for row in soup.select("div#chapter div.chapter-list div.row"):
        a = row.select_one("span > a")
        if a:
            ch_title = a.get_text(strip=True)
            ch_url = a.get("href")
            if ch_url and not ch_url.startswith("https://www.mangakakalot.gg/manga"):
              ch_url = urljoin(results['url'], ch_url)
              results['chapters'].append((ch_title, ch_url))
            elif ch_url and ch_url.startswith("https://www.mangakakalot.gg/manga"):
              results['chapters'].append((ch_title, ch_url))
      
      cover_url = None
      img = soup.select_one("div.thumbnail-wrap img")
      if not img:
        img = soup.select_one("div.manga-info-pic img")
      if img and img.get("src"):
        results['poster'] = img["src"]
      
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
    html = await self.get(url, headers=self.headers)
    if not html:
      return []
      
    soup = BeautifulSoup(html, "html.parser")
    images = []

    chapter_images_js = re.search(r'var\s+chapterImages\s*=\s*(\[[^\]]+\])', html)
    cdns_js = re.search(r'var\s+cdns\s*=\s*(\[[^\]]+\])', html)

    if chapter_images_js and cdns_js:
        try:
            img_list = ast.literal_eval(chapter_images_js.group(1))
            cdn_list = ast.literal_eval(cdns_js.group(1))
            cdn_url = cdn_list[0].replace('\\/', '/').strip('"').strip("'")
            for rel_img in img_list:
                rel_img = rel_img.replace('\\/', '/').strip('"').strip("'")
                img_url = cdn_url.rstrip('/') + '/' + rel_img.lstrip('/')
                images.append(img_url)
        except Exception:
            pass
    else:
        for img in soup.select(".container-chapter-reader img"):
            src = img.get("src") or ""
            if src and src.startswith("http"):
                images.append(src)

    if not images:
        backup_images_js = re.search(r'var\s+backupImage\s*=\s*(\[[^\]]+\])', html)
        if chapter_images_js and backup_images_js:
            try:
                img_list = ast.literal_eval(chapter_images_js.group(1))
                backup_list = ast.literal_eval(backup_images_js.group(1))
                backup_url = backup_list[0].replace('\\/', '/').strip('"').strip("'")
                for rel_img in img_list:
                    rel_img = rel_img.replace('\\/', '/').strip('"').strip("'")
                    img_url = backup_url.rstrip('/') + '/' + rel_img.lstrip('/')
                    images.append(img_url)
            except Exception:
                pass

    return images





