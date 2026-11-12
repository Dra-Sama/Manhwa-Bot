# Code By @V_Sbotmaker (on Telegram)
import random
from .scraper import Scraper
import json

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus

import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT
from copy import deepcopy


BASE_URL = "https://mangayy.org"
AJAX_URL = f"{BASE_URL}/wp-admin/admin-ajax.php"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1"
}

AJAX_HEADERS = {
    "User-Agent": BROWSER_HEADERS["User-Agent"],
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": BASE_URL,
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin"
}

worker_url = random.choice([
  "https://bpass-sophia-01.apple99450.workers.dev/proxy?url=",
  "https://silent-mountain-6cc5.ksshan918.workers.dev/proxy?url=",
  "https://lively-violet-30f8.sandeshs2410.workers.dev/proxy?url="
])



class MangayyWebs:
  url = "https://mangayy.org"
  sf = "ikin"

  @classmethod
  async def search(cls, query: str = ""):
    payload = {
      "action": "wp-manga-search-manga",
      "title": query
    }

    headers = deepcopy(AJAX_HEADERS)
    headers["Referer"] = BASE_URL + "/"
    
    json_text = await Scraper().post(
        worker_url + AJAX_URL,
        data=payload,
        headers=headers,
        cs=True,
        timeout=30
    )
    data  = json.loads(json_text) if json_text else None

    if not data:
      return []
    
    results = []

    if data.get("success") and isinstance(data.get("data"), list):
        for item in data["data"]:
            title = item.get("title", "").strip()
            url = item.get("url", "").strip()
            #typ = item.get("type", "manga")

            if title and url:
                results.append({
                    "title": title,
                    "url": url
                })

    return results
    

  async def get_chapters(self, data, page: int=1):
    results = deepcopy(data)
    
    headers = deepcopy(BROWSER_HEADERS)
    headers["Referer"] = BASE_URL + "/"

    content = await Scraper().get(
      worker_url + data['url'],
      cs=True,
      headers=headers,
    )
    
    if not content:
      return results
    
    
    soup = BeautifulSoup(content, "html.parser")

    cover_tag = soup.select_one(".summary_image img")
    if cover_tag:
      results['poster'] = str(cover_tag["src"]).strip()

    summary_tag = soup.select_one("div.description-summary")
    summary = summary_tag.get_text(" ", strip=True) if summary_tag else "N/A"

    genres = [
        a.get_text(strip=True)
        for a in soup.select("div.genres-content a")
    ]
    genres = ", ".join(genres)
    
    try:
        status = next(
          (
            item.select_one('.summary-content').get_text(strip=True) 
            if item.select_one('.summary-content') else None
            for item in soup.select("div.post-content_item")
            if 'status' in item.select_one('.summary-heading').get_text(strip=True).lower()
          ),
          "N/A"
        )
    except Exception:
      status = "N/A"
      
    results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=status if status else "N/A",
        genres=genres if genres else "N/A",
        summary=summary[:400] if summary else "N/A",
        url=results['url']
    )
      
      
     
    if results['url'].endswith("/"):
        ajax_url = results['url'] + "ajax/chapters/"
    else:
        ajax_url = results['url'] + "/ajax/chapters/"
      
    ajax_headers = deepcopy(AJAX_HEADERS)
    ajax_headers["Referer"] = data['url']

    chapters_html = await Scraper().post(
        worker_url+ajax_url,
        headers=ajax_headers,
        cs=True,
        timeout=30
    )
    
    if not chapters_html:
      return results

    chapters_soup = BeautifulSoup(chapters_html, "html.parser")
    
    chapters = []
    for li in chapters_soup.select("li.wp-manga-chapter"):
        a = li.find("a")
        if not a:
            continue

        ch_title = a.get_text(strip=True)
        ch_url = str(a.get("href", "")).strip()
      
        if ch_url and not ch_url.startswith("http"):
          ch_url = BASE_URL + "/" + ch_url.lstrip("/")
          
        chapters.append({
            "title": ch_title,
            "url": ch_url,
            "manga_title": data['title'],
            "poster": data['poster'] if 'poster' in data else None,
        })
    results['chapters'] = chapters[::-1]

    return results

  def iter_chapters(self, data, page: int=1):
    chapters_list = data['chapters'] if data and 'chapters' in data else []
    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    headers = deepcopy(BROWSER_HEADERS)
    headers["Referer"] = url

    html = await Scraper().get(
        worker_url+url,
        headers=headers,
        cs=True,
        timeout=30
    )
    if not html:
      return []

    soup = BeautifulSoup(html, "html.parser")

    images = []

    for img in soup.select("img.wp-manga-chapter-img"):
        url = str((
            img.get("data-src") or
            img.get("data-lazy-src") or
            img.get("src") or
            ""
        )).strip()

        if url.startswith("//"):
            url = "https:" + url

        if url.startswith("http"):
            images.append("https://lively-violet-30f8.sandeshs2410.workers.dev/proxy?url="+url)

    return images





