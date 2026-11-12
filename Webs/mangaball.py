# Code By @V_Sbotmaker (on Telegram)

from asyncio import to_thread

from .scraper import Scraper
import json

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus, urlencode

import re
from loguru import logger
from .utitls import DEAULT_MSG_FORMAT, BALL_MSG_FORMAT



LANGUAGE_FLAGS = {
  "ar": {"lang": "Arabic"}, "bg": {"lang": "Bulgarian"},
  "bn": {"lang": "Bengali"}, "ca": {"lang": "Catalan"},
  "ca-ad": {"lang": "Catalan (Andorra)"}, "ca-es": {"lang": "Catalan (Spain)"},
  "ca-fr": {"lang": "Catalan (France)"}, "ca-it": {"lang": "Catalan (Italy)"},
  "ca-pt": {"lang": "Catalan (Portugal)"}, "cn": {"lang": "Chinese"},
  "cs": {"lang": "Czech"}, "da": {"lang": "Danish"},
  "de": {"lang": "German"}, "el": {"lang": "Greek"},
  "en": {"lang": "English"}, "es": {"lang": "Spanish"},
  "es-ar": {"lang": "Spanish (Argentina)"}, "es-mx": {"lang": "Spanish (Mexico)"},
  "es-es": {"lang": "Spanish (Spain)"}, "es-la": {"lang": "Spanish (Latin America)"},
  "es-419": {"lang": "Spanish (Latin America)"},
  "fa": {"lang": "Persian"}, "fi": {"lang": "Finnish"},
  "fr": {"lang": "French"}, "he": {"lang": "Hebrew"},
  "hi": {"lang": "Hindi"}, "hu": {"lang": "Hungarian"},
  "id": {"lang": "Indonesian"}, "it": {"lang": "Italian"},
  "it-it": {"lang": "Italian (Italy)"}, "ja": {"lang": "Japanese"},
  "jp": {"lang": "Japanese (Japan)"}, "ko": {"lang": "Korean"},
  "kr": {"lang": "Korean"}, "ml": {"lang": "Malayalam"},
  "ms": {"lang": "Malay"}, "ne": {"lang": "Nepali"},
  "nl": {"lang": "Dutch"}, "nl-be": {"lang": "Dutch (Belgium)"},
  "no": {"lang": "Norwegian"}, "pl": {"lang": "Polish"},
  "pt-br": {"lang": "Portuguese (Brazil)"},
  "pt-pt": {"lang": "Portuguese (Portugal)"},
  "ro": {"lang": "Romanian"}, "ru": {"lang": "Russian"},
  "sk": {"lang": "Slovak"}, "sl": {"lang": "Slovenian"},
  "sq": {"lang": "Albanian"}, "sr": {"lang": "Serbian"},
  "sr-cyrl": {"lang": "Serbian (Cyrillic)"}, "sv": {"lang": "Swedish"},
  "ta": {"lang": "Tamil"}, "th": {"lang": "Thai"},
  "th-hk": {"lang": "Thai (Hong Kong)"}, "th-kh": {"lang": "Thai (Cambodia)"},
  "th-la": {"lang": "Thai (Laos)"}, "th-my": {"lang": "Thai (Malaysia)"},
  "th-sg": {"lang": "Thai (Singapore)"}, "tr": {"lang": "Turkish"},
  "uk": {"lang": "Ukrainian"}, "vi": {"lang": "Vietnamese"},
  "zh": {"lang": "Chinese"}, "zh-cn": {"lang": "Chinese (Simplified)"},
  "zh-hk": {"lang": "Chinese (Hong Kong)"}, "zh-mo": {"lang": "Chinese (Macau)"},
  "zh-sg": {"lang": "Chinese (Singapore)"}, "zh-tw": {"lang": "Chinese (Taiwan)"},
}

demographic_types = {
  # Formats
  "Manga", "Manhwa", "Manhua", "Webtoon", "Comic",

  # Demographics
  "Shounen", "Shoujo", "Seinen", "Josei",

  # Themes / Tropes / Styles / Maturity
  "Isekai", "Reincarnation", "Transmigration", "Regression",
  "Villainess", "Otome Game",
  "School Life", "Office Life", "Survival",
  "Post-Apocalyptic", "Tragedy",
  "Philosophical", "Supernatural", "Magic", "Martial Arts",
  "Historical", "Military", "Sports", "Music", "Cooking",
  "Medical", "Detective", "Crime", "Dystopian", "Gore",
  "Thriller", "Mature", "Adult",

  # Extra Themes / Tropes
  "Cyberpunk", "Steampunk", "Vampires", "Zombies",
  "Idol", "Mecha", "Demons", "Angels", "Ghosts",
  "Villain Protagonist", "Anti-Hero", "Revenge",
  "Time Travel", "Parallel World", "Cultivation",
  "Family", "Friendship", "Adventure", "Magic School",
  "Royalty", "Political", "Slice of Life Comedy", "Comedy Drama",
  "Sexual Violence", "Office Workers", "Long Strip", "Full Color",
}

def get_language_name(short):
  return LANGUAGE_FLAGS.get(short, {}).get("lang", short)


from cloudscraper import create_scraper

_MBL_UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"


def fetch_html(url: str) -> str:
  with create_scraper() as session:
    resp = session.get(url, timeout=60, headers={"User-Agent": _MBL_UA})
  return resp.text


def _extract_manga_id(url: str) -> str | None:
  m = re.search(r'([0-9a-f]{24})(?:/)?$', url.rstrip('/'))
  if m:
    return m.group(1)
  # fallback: last segment
  return url.rstrip('/').split('/')[-1].split('-')[-1]


class MangaBallWebs:
  url: str = "https://mangaball.net/"
  sf: str = "MBL"

  # ──────────────────────────────────────────────────────────────────────
  # Internal helpers
  # ──────────────────────────────────────────────────────────────────────

  def _get_session_with_csrf(self):
    """
    Return (session, csrf_token).
    CRITICAL: must use the SAME session for homepage fetch AND API POST,
    because mangaball.net validates the CSRF token against the session cookie.
    Opening a new session for the POST causes HTTP 403.
    """
    session = create_scraper()
    resp = session.get(self.url, headers={"User-Agent": _MBL_UA}, timeout=60)
    soup = BeautifulSoup(resp.text, "html.parser")

    csrf = None
    tag = soup.find("meta", {"name": "csrf-token"})
    if tag:
      csrf = tag.get("content")

    if not csrf:
      inp = soup.find("input", {"name": "_token"})
      if inp:
        csrf = inp.get("value")

    return session, csrf

  # ──────────────────────────────────────────────────────────────────────
  # Search
  # ──────────────────────────────────────────────────────────────────────

  def post_search(self, query: str) -> dict:
    session, csrf_token = self._get_session_with_csrf()
    if not csrf_token:
      logger.warning("MangaBall: could not get CSRF token for search")
      return {}

    url = urljoin(self.url, "api/v1/smart-search/search/")
    headers = {
      'Accept': 'application/json, */*',
      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
      'User-Agent': _MBL_UA,
      'Origin': self.url.rstrip("/"),
      'Referer': self.url,
      'X-Csrf-Token': csrf_token,
      'X-Requested-With': 'XMLHttpRequest',
    }
    session.headers.update(headers)
    resp = session.post(url, data={"search_input": query}, timeout=60)
    session.close()
    return resp.json()

  async def search(self, query: str = ""):
    def truncate_title(title):
      try:
        return title.split('(')[0].strip()
      except Exception:
        return title

    results = []
    try:
      data: dict = await to_thread(self.post_search, query)

      for entry in data.get("data", {}).get("manga", []):
        mtitle = entry.get("title", "").strip()
        murl = entry.get("url", "")
        if murl.startswith("/"):
          murl = urljoin(self.url, murl.lstrip("/"))
        elif not murl.startswith("http"):
          murl = urljoin(self.url, murl)

        thumb = entry.get("img", "")
        mtitle = truncate_title(mtitle)
        results.append({
          "title": mtitle,
          "url": murl,
          "poster": thumb,
        })

    except Exception as e:
      logger.exception(f"MangaBall Search Error: {e}")
    finally:
      return results


  async def get_chapters(self, data, page: int = 1) -> dict:
    results = data.copy()
    try:
      html = await to_thread(lambda: fetch_html(results['url']))
      soup = BeautifulSoup(html, "html.parser")

      # ── Title ────────────────────────────────────────────────────────
      og_title = soup.find("meta", property="og:title")
      if og_title and og_title.get("content"):
        raw = og_title["content"].strip()

        clean = raw.split('(')[0].strip() or raw
        results['title'] = clean


      # ── Poster ───────────────────────────────────────────────────────
      if not results.get('poster'):
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
          results['poster'] = og_img["content"]

      # ── Description ──────────────────────────────────────────────────
      summary = "N/A"
      og_desc = soup.find("meta", property="og:description")
      if og_desc and og_desc.get("content"):
        summary = og_desc["content"].strip()
      if not summary or summary == "N/A":
        meta_desc = soup.find("meta", {"name": "description"})
        if meta_desc and meta_desc.get("content"):
          summary = meta_desc["content"].strip()

      manga_id = None
      m = re.search(r"const\s+titleId\s*=\s*['\"]([0-9a-f]{24})['\"]", html)
      if m:
        manga_id = m.group(1)

      if not manga_id:
        tag = soup.find(attrs={"data-title-id": True})
        if tag:
          manga_id = tag.get("data-title-id")

      if not manga_id:
        manga_id = _extract_manga_id(results['url'])
        
      status = "N/A"
      genres = "N/A"
      rating = "N/A"
      year = "N/A"
      alt_titles = "N/A"

      # Try old selectors first (in case site reverts)
      title_tag = soup.find("h4", class_="comic-title")
      if title_tag:
        results['title'] = title_tag.text.strip()

      alt_box = soup.find("div", class_="alternate-name-container")
      if alt_box:
        spans = [s.text.strip() for s in alt_box.find_all("span", class_="badge")]
        alt_titles = ", ".join(spans[:3]) if spans else "N/A"

      desc_box = soup.find("div", class_="description-text")
      if desc_box:
        p = desc_box.find("p")
        if p and p.text.strip():
          summary = p.text.strip()
        else:
          summary = desc_box.get_text(separator="\n", strip=True) or summary

      for badge in soup.find_all("span", class_="badge"):
        badge_text = badge.get_text(strip=True).lower()
        if badge_text in ("ongoing", "completed", "hiatus"):
          status = badge_text.capitalize()
          break

      badges_info = soup.find_all("span", class_="badge bg-info bg-opacity-75")
      for badge in badges_info:
        if "Year:" in badge.get_text():
          year = badge.get_text().split("Year:")[-1].strip()
          break

      raw_genres = []
      for row in soup.find_all("div", class_="d-flex flex-wrap gap-2 mb-3 align-items-center"):
        badges = row.find_all("span", class_="badge")
        if badges and badges[0].get_text(strip=True).lower().startswith("tags"):
          raw_genres = [span.get_text(strip=True) for span in badges[1:]]
          break
      if raw_genres:
        genres_list = [g for g in raw_genres if g not in demographic_types]
        genres = ", ".join(genres_list) if genres_list else "Unknown"

      for item in soup.find_all("div", class_="highlight-item"):
        i_tag = item.find("i", class_="fa-star")
        if i_tag:
          value = item.find("span", class_="text-light")
          if value:
            rating = value.text.strip()
          break

      # ── Format message ───────────────────────────────────────────────
      results['msg'] = BALL_MSG_FORMAT.format(
        title=results['title'],
        alt_title=alt_titles,
        status=status,
        genres=genres,
        rating=rating,
        year=year,
        summary=summary[:200] if summary else 'N/A',
        url=results['url'],
      )
      if len(results['msg']) > 1024:
        results['msg'] = DEAULT_MSG_FORMAT.format(
          title=results['title'],
          status=status,
          genres=genres,
          summary=summary[:200] if summary else 'N/A',
          url=results['url'],
        )

      # ── Chapter list ─────────────────────────────────────────────────
      results['chapters'] = await self._get_chapters(manga_id, results['url'])

    except Exception as e:
      logger.exception(f"MangaBall get_chapters Error: {e}")
    finally:
      return results

  # ──────────────────────────────────────────────────────────────────────
  # Chapter listing API
  # ──────────────────────────────────────────────────────────────────────

  def post_chapters(self, manga_id: str, referer: str = "") -> dict:
    session, csrf_token = self._get_session_with_csrf()
    if not csrf_token:
      session.close()
      return {}

    url = urljoin(self.url, "api/v1/chapter/chapter-listing-by-title-id/")
    headers = {
      'Accept': 'application/json, */*',
      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
      'User-Agent': _MBL_UA,
      'Origin': self.url.rstrip("/"),
      'Referer': referer or self.url,
      'X-Csrf-Token': csrf_token,
      'X-Requested-With': 'XMLHttpRequest',
    }
    resp = session.post(url, data={"title_id": manga_id}, headers=headers, timeout=60)
    session.close()
    return resp.json()

  async def _get_chapters(self, manga_id: str, referer: str = "") -> list:
    if not manga_id:
      return []
    try:
      data = await to_thread(self.post_chapters, manga_id, referer)
    except Exception as e:
      logger.exception(f"MangaBall _get_chapters network error: {e}")
      return []

    all_chapters = data.get("ALL_CHAPTERS", [])
    results = []

    for chapter in all_chapters:
      chap_num = chapter.get("number") or "Chapter"
      title = chapter.get("title") or ""
      translations = chapter.get("translations", [])

      for t in translations:
        lang_short = t.get("language", "")
        lang_full = get_language_name(lang_short)

        if lang_full == "English":
          chap_url = t.get("url", "")
       
          if chap_url.startswith("http://"):
            chap_url = "https://" + chap_url[7:]
          chap_title = f"{chap_num}{' - ' + title if title and title != chap_num else ''}"
          results.append((chap_title, chap_url))

    return results

  def extract_chapter_num(self, chapter_title):
    m = re.match(r"([0-9]+(?:\.[0-9]+)?)", chapter_title)
    if m:
      try:
        return float(m.group(1))
      except Exception:
        return None
    return None

  # ──────────────────────────────────────────────────────────────────────
  # Chapter iteration (for paginated display)
  # ──────────────────────────────────────────────────────────────────────

  def iter_chapters(self, data, page: int = 1) -> list:
    chapters_list = []

    if 'chapters' in data:
      try:
        for card in data['chapters']:
          chapters_list.append({
            "title": card[0],
            "url": card[1],
            "manga_title": data['title'],
            "poster": data.get('poster'),
          })
      except Exception as err:
        logger.exception(f"MangaBall iter_chapters Error: {err}")

    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  # ──────────────────────────────────────────────────────────────────────
  # Chapter images
  # ──────────────────────────────────────────────────────────────────────

  async def get_pictures(self, url: str, data=None):
  
    resp = await to_thread(lambda: fetch_html(url))

    if not resp:
      return []

    m = re.search(r'const chapterImages\s*=\s*JSON\.parse\(`([^`]*)`', resp)
    if not m:
      logger.warning(f"MangaBall: chapterImages not found in {url}")
      return []

    try:
      imglist = json.loads(m.group(1))
      return imglist
    except json.JSONDecodeError as e:
      logger.error(f"MangaBall: failed to parse chapterImages JSON: {e}")
      return []
