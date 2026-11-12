# Code By @V_Sbotmaker (on Telegram)
from asyncio import gather, to_thread
from .scraper import Scraper

from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus

import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT


class TaaddWebs(Scraper):

  def __init__(self):
    super().__init__()
    self.url = "https://www.taadd.com"
    self.sf = "tadc"

    self.headers = {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"
    }

  async def search(self, query: str = ""):
    """Search for manga on Taadd (TenManga) using the main desktop site results page structure."""

    search_url = f"{self.url}/search/?wd={quote_plus(query)}"
    html = await self.get(search_url, headers=self.headers)
    if not html:
      return []

    results = []
    try:
      soup = BeautifulSoup(html, "html.parser")
      results = []
      # Desktop structure: clistChr > ul > li (skip .dot-line1)
      clist = soup.select_one("div.clistChr ul")
      if clist:
        for li in clist.find_all("li", recursive=False):
          # skip separator lines
          if "dot-line1" in li.get("class", []):
            continue

          cover = li.find("div", class_="cover")
          intro = li.find("div", class_="intro")
          if not cover or not intro:
            continue

          a_main = cover.find("a", href=True)
          img_tag = cover.find("img")
          h2 = intro.find("h2")
          title_a = h2.find("a", href=True) if h2 else None
          title = title_a.get("title") if title_a and title_a.has_attr(
              "title") else (title_a.text.strip() if title_a else None)
          url = a_main["href"] if a_main else (
              title_a["href"] if title_a else None)
          if url and not url.startswith("http"):
            url = urljoin(self.url, url)

          thumbnail = img_tag["src"].strip(
          ) if img_tag and img_tag.has_attr("src") else None
          if thumbnail and not thumbnail.startswith("http"):
            thumbnail = urljoin(self.url, thumbnail)

          # Optional: summary is in the <a> below h2, inside <span>
          desc_a = intro.select_one("span > a[title]")
          summary = desc_a.text.strip() if desc_a else None
          if title and url:
            results.append({
                "title": title,
                "url": url,
                "poster": thumbnail,
                "summary": summary
            })
    except Exception as e:
      logger.error(f"ManhuaTop Error: {e}")
    finally:
      return results

  async def get_chapters(self, data, page: int = 1):
    results = data.copy()
    html = await self.get(data['url'], headers=self.headers)
    if not html:
      return results

    try:
      soup = BeautifulSoup(html, "html.parser")

      # poster
      if "poster" not in results or not results['poster']:
        cover_tag = soup.select_one("td > a > img")
        if cover_tag and cover_tag.has_attr("src"):
          cover = cover_tag["src"]
          if not cover.startswith("http"):
            results['poster'] = urljoin(self.url, cover)
          else:
            results['poster'] = cover

      # Summary
      if "summary" not in results or not results['summary']:
        summary = None
        for b in soup.find_all("b"):
          if "Summary" in b.text:
            summary_p = b.parent
            if summary_p:
              summary = summary_p.text.split("Summary", 1)[-1].strip()
            break

        if not summary:
          # fallback: look for summary in <td> elements
          for td in soup.find_all("td"):
            if "unravels when her husband" in td.text:
              summary = td.text.strip()
              break
      else:
        summary = results.pop('summary')

      # Genres/Categories
      genres = []
      cats_row = soup.find("td", string=lambda t: t and "Categories:" in t)
      if not cats_row:
        # fallback: parse all <a class="red"> inside the categories row
        for a in soup.select("a.red"):
          if "/category/" in a.get("href", ""):
            genres.append(a.get_text(strip=True))
      else:
        for a in cats_row.find_all("a", class_="red"):
          genres.append(a.get_text(strip=True))

      genres = ", ".join(genres) if genres else "N/A"

      # Status
      status = None
      for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        for td in tds:
          if "Status:" in td.text:
            status = td.text.split("Status:", 1)[-1].strip()
            break

      # Chapters
      results['chapters'] = []
      chapter_table = soup.find("div", class_="chapter_list")
      highest_num = 0
      ch_info = []
      if chapter_table:
        for tr in chapter_table.find_all("tr"):
          tds = tr.find_all("td")
          if len(tds) < 2:
            continue
          a = tds[0].find("a", href=True)
          if not a:
            continue
          ch_title = a.get_text(strip=True)
          ch_url = a["href"]
          if not ch_url.startswith("http"):
            ch_url = urljoin(self.url, ch_url)
          m = re.search(r'\b(\d+)\b', ch_title)
          num = int(m.group(1)) if m else None
          if num and num > highest_num:
            highest_num = num
          ch_info.append((ch_title, ch_url, num))

      for ch_title, ch_url, num in ch_info:
        if num:
          results['chapters'].append((f"Chapter {num}", ch_url))
        else:
          results['chapters'].append((ch_title, ch_url))

    except Exception as e:
      logger.error(f"ManhuaTop Chapters Error: {e}")

    return results

  def iter_chapters(self, data, page: int = 1):
    chapters_list = []

    if "chapters" in data:
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
        logger.error(f"ManhuaUS Error: {err}")

    return chapters_list[(page - 1) * 60:page *
                         60] if page != 1 else chapters_list

  
  async def get_pictures(self, url, data=None):
    async def fetch_image_from_page(session, page_url):
      """Helper function to fetch an image URL from a single page."""
      try:
        resp = session.get(page_url)
        resp.raise_for_status()
      except :
        return None
      
      soup = BeautifulSoup(resp.text, "html.parser")

      # Try the og:image meta tag first
      meta_tag = soup.find('meta', property="og:image")
      if meta_tag and meta_tag.has_attr('content'):
          return meta_tag['content']

      # Fallback to the img tag
      img = soup.select_one('#viewer img, .read_img img')
      if img and img.has_attr('src'):
          img_url = img['src']
          if not img_url.startswith("http"):
              return urljoin(page_url, img_url)
          
          return img_url
      
      return None

    #images = []
    page_urls = []
    
    session = self.session
    session.headers.update(self.headers)
    try:
      resp = session.get(url)
      resp.raise_for_status()

      soup = BeautifulSoup(resp.text, "html.parser")

      # Extract all URLs from the page select dropdown
      page_select = soup.find('select', {'id': 'page'})
      if page_select:
          for option in page_select.find_all('option'):
              page_url = option.get('value')
              if page_url:
                  page_urls.append(page_url)
      
      else:
          visited = set()
          cur_url = url
          while cur_url and cur_url not in visited:
              visited.add(cur_url)
              page_urls.append(cur_url)
            
              next_html = session.get(cur_url).text
              m = re.search(r'next_page\s*=\s*"([^"]+)"', next_html)
              if m:
                  next_url = m.group(1)
              else:
                  a_next = BeautifulSoup(next_html, "html.parser").select_one('#viewer a, .read_img a')
                  next_url = a_next['href'] if a_next and a_next.has_attr('href') else None

              if next_url:
                  if not next_url.startswith("http"):
                      next_url = urljoin(self.url, next_url)
                  cur_url = next_url
              else:
                  break

      if not page_urls:
          print("No page URLs found. Exiting.")
          return []

      # Step 2: Concurrently fetch images from all pages
      tasks = [fetch_image_from_page(session, url) for url in page_urls]
      all_images = await gather(*tasks)

    finally:
      try: session.close()
      except: pass

    # Step 3: Remove duplicates and return a clean list
    deduped = []
    seen = set()
    for img_url in all_images:
      if img_url and img_url not in seen:
          deduped.append(img_url)
          seen.add(img_url)

    return deduped
