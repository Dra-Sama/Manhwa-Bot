# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus

from loguru import logger
from .utitls import T_MSG_FORMAT

COOKIES = {'nsfw': '2', 'wd': '452x887'}


class MangaParkWebs(Scraper):

  def __init__(self):
    super().__init__()
    self.url = "https://mangapark.net"
    self.api_base = "https://api.mangacloud.org"

    self.sf = "mpk"
    self.headers = {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"
    }

  async def search(self, query: str = ""):
    url = f"{self.url}/search?word={quote_plus(query)}"
    text = await self.get(url, headers=self.headers, cookies=COOKIES)

    if not text:
      return []

    soup = BeautifulSoup(text, "html.parser")
    results = []
    for card in soup.select("div.group.relative.w-full"):
      a = card.find("a")
      img = card.find("img")
      if not a or not img:
        continue
      title = img.get("title", "").strip()
      url = urljoin(self.url, a.get("href", ""))
      thumbnail = img.get("src", "")
      if thumbnail and thumbnail.startswith("/"):
        thumbnail = urljoin(self.url, thumbnail)
      if title and url:
        results.append({"title": title, "url": url, "poster": thumbnail})

    return results

  async def get_chapters(self, data, page: int = 1):
    results = data
    content = await self.get(results['url'],
                             headers=self.headers,
                             cookies=COOKIES)
    if not content: return []

    soup = BeautifulSoup(content, "html.parser")

    # --- SUMMARY ---
    summary = None
    limit_html = soup.select_one("div.limit-html.prose")
    if limit_html:
      summary = "\n".join([
          d.get_text(" ", strip=True)
          for d in limit_html.find_all("div", recursive=False)
      ])
    if not summary:
      meta = soup.find("meta", attrs={"name": "description"})
      if meta:
        summary = meta.get("content", "").strip()

    # --- STATUS ---
    status = None
    status_tag = soup.find("span", class_="font-bold uppercase text-success")
    if status_tag:
      status = status_tag.get_text(strip=True)
    if not status:
      meta = soup.find("meta", property="og:description")
      if meta:
        desc = meta.get("content", "")
        if "ongoing" in desc.lower():
          status = "Ongoing"
        elif "completed" in desc.lower():
          status = "Completed"

    # --- LANGUAGE ---
    language = None
    container = soup.find("div",
                          class_=lambda c: c and "whitespace-nowrap" in c)
    if container:
      spans = container.find_all("span", class_=lambda c: c and "mr-1" in c)
      for s in spans:
        txt = s.get_text(strip=True)
        if txt.lower() == "tr from":
          continue
        if txt and txt.isalpha():
          language = txt
          break

    # --- GENRES ---
    genres = []
    genres_div = soup.find("div", class_="flex items-center flex-wrap")
    if genres_div:
      for span in genres_div.find_all("span", class_="whitespace-nowrap"):
        g = span.get_text(strip=True)
        if g:
          genres.append(g)
      for bold in genres_div.find_all("span",
                                      class_="whitespace-nowrap font-bold"):
        g = bold.get_text(strip=True)
        if g and g not in genres:
          genres.append(g)
      genres = [
          g.replace(",", "") for g in genres if g and g.lower() != "genres:"
      ]
    if not genres:
      meta = soup.find("meta", attrs={"name": "keywords"})
      if meta:
        genres = [
            g.strip() for g in meta.get("content", "").split(",") if g.strip()
        ]
        genres = [g for g in genres if g.isalpha() and len(g) > 2]

    genres = ", ".join(genres) if genres else "N/A"

    # --- COVER ---
    cover_url = None
    img = soup.select_one("div.w-24.md\\:w-52 img")
    if img:
      cover_url = img.get("src")
    if cover_url and cover_url.startswith("/"):
      cover_url = urljoin(self.url, cover_url)
    if not cover_url:
      meta = soup.find("meta", property="og:image")
      if meta:
        cover_url = meta.get("content", "").strip()
        if cover_url.startswith("/"):
          results['poster'] = urljoin(self.url, cover_url)

    # --- CHAPTERS ---
    results['chapters'] = []
    for a in soup.select(
        "main [data-name='chapter-list'] a.link-hover.link-primary"):
      href = a.get("href", "")
      if "/title/" in href:
        chapter_url = urljoin(self.url, href)
        name = a.get_text(strip=True)
        results['chapters'].append((name, chapter_url))

    results['msg'] = T_MSG_FORMAT.format(
        title=results['title'],
        status=status if status else "N/A",
        genres=genres if genres else "N/A",
        summary=summary[:400] if summary else "N/A",
        language=language if language else "N/A",
        url=results['url'],
    )

    return results

  def iter_chapters(self, data, page: int = 1):
    chapters_list = []

    if 'chapters' not in data:
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
    text = await self.get(url, headers=self.headers, cookies=COOKIES)
    soup = BeautifulSoup(text, "html.parser")
    script = soup.find("script", {"type": "qwik/json"})
    image_urls = []
    if script and script.string:
      import json, re
      try:
        data = json.loads(script.string.strip())
        objs = data.get("objs", [])
        for item in objs:
          if isinstance(item, str) and item.startswith("https://"):
            if re.search(r"\.(jpg|jpeg|png|webp)$", item, re.IGNORECASE):
              image_urls.append(item)
      except Exception:
        pass

    return image_urls
