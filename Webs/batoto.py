# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper
import json, re
from bs4 import BeautifulSoup

from loguru import logger
from urllib.parse import urlparse, urljoin, quote, quote_plus

from .utitls import T_MSG_FORMAT

class BatotoWebs(Scraper):

  def __init__(self):
    super().__init__()
    self.url = "https://batotoo.com"

    self.bg = None
    self.sf = "btot"
    self.headers = {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"
    }

  async def search(self, query: str = ""):
    search_url = f"{self.url}/search?word={quote_plus(query)}"
    html = await self.get(search_url, headers=self.headers)

    soup = BeautifulSoup(html, "html.parser")
    results = []
    for col in soup.select("#series-list .col.item"):
      a_tag = col.select_one("a.item-cover")
      if not a_tag:
        continue

      url = urljoin(self.url, a_tag["href"])
      img_tag = a_tag.find("img")
      thumbnail = img_tag["src"] if img_tag and img_tag.has_attr(
          "src") else None

      try: title = col.find("a", class_="item-title").text
      except: title = None

      if title and url:
        results.append({"title": title, "url": url, "poster": thumbnail})

    return results

  async def get_chapters(self, data, page: int = 1):
    results = data
    html = await self.get(results['url'], headers=self.headers, timeout=15)

    soup = BeautifulSoup(html, "html.parser")

    tags_ = soup.find_all("div", class_="attr-item") 
    genres = "N/A"
    status = "N/A"
    if tags_:
      for tag in tags_:
        tag_ = tag.find("b")
        if tag_ and tag_.text == "Genres:":
          genres = tag.find("span").text.strip()
          genres = genres.split(", ")
          genres = ", ".join([i.strip() for i in genres])

        elif tag_ and tag_.text == "Original work:":
          status = tag.find("span").text.strip()

    summary = soup.find(class_="limit-html")
    summary = summary.text if summary else "N/A"
  
    # --- Translated Language ---
    translated_language = None
    for item in soup.select(".attr-item"):
        label = item.select_one("b.text-muted")
        if label and "translated language" in label.get_text(strip=True).lower():
            lang_span = item.find("span")
            if lang_span:
                translated_language = lang_span.get_text(strip=True)
            break

    results['msg'] = T_MSG_FORMAT.format(
      title=results['title'],
      status=status,
      genres=genres,
      language=translated_language if translated_language else "N/A",
      summary=summary[:100],
      url=results['url']
    )

    # --- Chapters ---
    chapters = []
    for div in soup.select(".episode-list .main > div.item"):
      a = div.find("a", class_="chapt")
      if a:
        ch_title = a.get_text(strip=True)
        ch_url = urljoin(self.url, a["href"])
        chapters.append((ch_title, ch_url))

    #chapters = chapters[::-1]
    results['chapters'] = chapters

    return results

  def iter_chapters(self, data, page: int = 1):
    chapters_list = []

    if data['chapters']:
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

    return chapters_list[(page - 1) * 60:page *
                         60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    html = await self.get(url, headers=self.headers)

    m = re.search(r'const imgHttps\s*=\s*(\[[^\]]+\])', html)
    if m:
      import ast
      try:
        imgs = ast.literal_eval(m.group(1))
      except Exception:
        imgs = []
      images = [
          url if url.startswith("http") else urljoin(self.url, url)
          for url in imgs
      ]
      return images

    soup = BeautifulSoup(html, "html.parser")
    images = []
    for img in soup.select("#viewer img"):
      src = img.get("src")
      if src and src.startswith("http"):
        images.append(src)

    return images

  async def get_updates(self, page: int = 1):
    output = []
    url = "https://batotoo.com/latest?langs=en"
    html = await self.get(url, headers=self.headers)
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all(class_="col item line-b no-flag")
    if cards:
      for card in cards:
        try:
          data = {}
          data['url'] = urljoin(self.url, card.find("a").get('href'))
          data['poster'] = card.find("img").get('src')
          data['manga_title'] = card.find("a",
                                          class_='item-title').text.strip()

          data['title'] = card.find("a", class_="visited").text.strip()
          data['chapter_url'] = urljoin(
              self.url,
              card.find("a", class_="visited").get('href'))

          output.append(data)
        except:
          continue

    return output
