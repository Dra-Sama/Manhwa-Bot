# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper
import json, re
from bs4 import BeautifulSoup

from loguru import logger
from urllib.parse import urlparse, urljoin, quote, quote_plus

from .utitls import DEAULT_MSG_FORMAT

class MangaBuddyWebs(Scraper):

  def __init__(self):
    super().__init__()
    self.url = "https://mangabuddy.com"
    self.sf = "manbu"
    self.headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"
    }

  async def search(self, query: str = ""):
    search_url = f"{self.url}/search?q={quote_plus(query)}"
    html = await self.get(search_url, headers=self.headers)
    
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for card in soup.select("div.book-item"):
        a_tag = card.find('a')
        img_tag = card.find("img")
        if not a_tag or not img_tag:
            continue
        
        title = a_tag.get("title", "").strip() or img_tag.get("alt", "").strip()
        url = urljoin(self.url, a_tag.get('href', '').strip())
        thumbnail = img_tag.get('data-src', '').strip() or img_tag.get('src', '').strip()
        if thumbnail.startswith("/"):
            thumbnail = urljoin(self.url, thumbnail)
        if title and url:
            results.append({
                "title": title,
                "url": url,
                "poster": thumbnail
            })
      
    return results

  async def get_chapters(self, data, page: int = 1):
    results = data
    html = await self.get(results['url'], headers=self.headers, timeout=15)
    soup = BeautifulSoup(html, "html.parser")

    # --- Poster --- #
    cover = None
    meta_cover = soup.find("meta", property="og:image")
    if meta_cover and meta_cover.get("content"):
        results['poster'] = meta_cover["content"].strip()
    if not results['poster']:
        meta_cover = soup.find("meta", {"name": "twitter:image"})
        if meta_cover and meta_cover.get("content"):
            results['poster'] = meta_cover["content"].strip()
    
    if not results['poster']:
        poster_div = soup.find("div", class_="manga-poster")
        if poster_div:
            img = poster_div.find("img")
            if img and (img.get("data-src") or img.get("src")):
                cover = img.get("data-src") or img.get("src")
                cover = cover.strip()
                if cover.startswith("/"):
                    cover = urljoin(self.url, cover)
                    results['poster'] = cover
      
    # --- Summary/Description ---
    summary = None
    meta_desc = soup.find("meta", {"name": "description"})
    if meta_desc and meta_desc.get("content"):
        summary = meta_desc["content"].strip()
    if not summary:
        meta_desc = soup.find("meta", property="og:description")
        if meta_desc and meta_desc.get("content"):
            summary = meta_desc["content"].strip()
    if not summary:
        meta_desc = soup.find("meta", {"name": "twitter:description"})
        if meta_desc and meta_desc.get("content"):
            summary = meta_desc["content"].strip()

    # --- Genres
    genres = []
    for p in soup.find_all("p"):
        strong = p.find("strong")
        if strong and "genres" in strong.text.lower():
            for a in p.find_all("a"):
                genre = a.text.strip()
                genre = genre.rstrip(",").strip()
                if genre:
                    genres.append(genre)
            break
    genres = ", ".join(genres) if genres else "N/A"
    
    # --- Status ---
    status = None
    for p in soup.find_all("p"):
        strong = p.find("strong")
        if strong and "status" in strong.text.lower():
            txt = p.get_text(" ", strip=True)
            m = re.search(r"status\s*[:\-]\s*([A-Za-z ]+)", txt, re.I)
            if m:
                status = m.group(1).strip()
            else:
                strong_next = strong.next_sibling
                if strong_next and isinstance(strong_next, str):
                    status = strong_next.strip(" :\n")
            break
    if not status:
        for meta_name in ["description", "og:description", "twitter:description"]:
            meta = soup.find("meta", {"name": meta_name}) or soup.find("meta", {"property": meta_name})
            if meta and meta.get("content"):
                m = re.search(r"status\s*[:\-]\s*([A-Za-z ]+)", meta["content"], re.I)
                if m:
                    status = m.group(1).strip()
                    break
    
    results['msg'] = DEAULT_MSG_FORMAT.format(
      title=results['title'],
      status=status if status else "N/A",
      genres=genres,
      summary=summary[:200] if summary else "N/A",
      url=results['url']
    )
    
    # --- Chapters ---
    chapters = []
    chapters_section = soup.find("ul", id="chapter-list")
    if chapters_section:
        for li in chapters_section.find_all("li"):
            a = li.find("a")
            if not a:
                continue
            ch_title = a.find("strong", class_="chapter-title")
            if ch_title:
                title_text = ch_title.get_text(strip=True)
            else:
                title_text = a.get_text(strip=True)
            ch_url = urljoin(self.url, a.get("href", ""))
            chapters.append((title_text, ch_url))
        #chapters = chapters[::-1]
    results['chapters'] = chapters
    
    return results

  def iter_chapters(self, data, page: int = 1):
    chapters_list = []

    if data['chapters']:
      for card in data['chapters']:
        chapters_list.append({
            "title": card[0],
            "url": card[1],
            "manga_title": data['title'],
            "poster": data['poster'] if 'poster' in data else None,
        })

    return chapters_list[(page - 1) * 60:page *
                         60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    html = await self.get(url, headers=self.headers)

    imgs = []
    m = re.search(r"var\s+chapImages\s*=\s*'([^']+)'", html)
    if m:
      imgs = [img.strip() for img in m.group(1).split(",") if img.strip()]
    else:
      soup = BeautifulSoup(html, "html.parser")
      img_tags = soup.select("div#images img")
      imgs = [img.get("data-src") or img.get("src") for img in img_tags if img.get("data-src") or img.get("src")]
      
    return imgs
