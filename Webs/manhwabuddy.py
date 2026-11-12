# Code By @V_Sbotmaker (on Telegram)


from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus

from Webs.utitls import DEAULT_MSG_FORMAT
from .scraper import Scraper


BASE_URL = "https://manhwabuddy.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "Referer": BASE_URL
}

class ManhwaBuddySource:
    sf = "mnby"
    url = BASE_URL

    # -------------------------------------------------
    # SEARCH
    # -------------------------------------------------
    @classmethod
    async def search(cls, query):
        search_url = f"{BASE_URL}/search/?s={quote_plus(query)}"
        html = await Scraper(headers=HEADERS).get(search_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []

        for item in soup.select("div.latest-item"):
            a = item.select_one("a[href]")
            img = item.select_one("img")

            if not a:
                continue

            title = a.get("title") or a.get_text(strip=True)
            url = urljoin(BASE_URL, str(a.get("href")))

            cover = None
            if img:
                cover = img.get("src")
                if cover and str(cover.startswith("/")):
                    cover = urljoin(BASE_URL, str(cover))

            results.append({
                "title": title,
                "url": url,
                "poster": cover,
            })

        return results

    # -------------------------------------------------
    # MANGA INFO
    # -------------------------------------------------
    @classmethod
    async def get_chapters(cls, data: dict, page: int = 1):
        html = await Scraper(headers=HEADERS).get(data['url'])
        if not html:
            return data
        
        results = data.copy()
        soup = BeautifulSoup(html, "html.parser")

        # Cover
        cover = soup.select_one("img.img-cover")
        cover = cover.get("src") if cover else None
        if cover:
            results['poster'] = cover

        # Summary
        summary = soup.select_one("div.short-desc-content p")
        summary = summary.get_text(strip=True) if summary else "N/A"

        # -------------------------------------------------
        # RELEASE + STATUS
        # -------------------------------------------------
        status = None
        
        post_status = soup.select_one("div.post-status ul.main-info-list")
        if post_status:
            for li in post_status.find_all("li"):
                label = li.find("h5")
                value = li.find("span")
        
                if not label or not value:
                    continue
        
                key = label.get_text(strip=True).lower()
                val = value.get_text(strip=True)
        
                if key == "status":
                    status = val
        
        # -------------------------------------------------
        # GENRES
        # -------------------------------------------------
        genres = []
        for h5 in soup.find_all("h5"):
            if h5.get_text(strip=True) == "Genres":
                genre_div = h5.find_next_sibling("div")
                if genre_div:
                    for a in genre_div.find_all("a"):
                        genres.append(a.get_text(strip=True))
                break
        genres = ", ".join(genres) if genres else "N/A"

        results['msg'] = DEAULT_MSG_FORMAT.format(
            title=data['title'],
            url=data['url'],
            summary=summary,
            status=status,
            genres=genres,
        )
        # Chapters
        chapters = []
        for a in soup.select("ul.chapter-list li a"):
            ch_title = a.select_one("span.chapter-name")
            ch_title = ch_title.get_text(strip=True) if ch_title else a.get_text(strip=True)
            ch_url = urljoin(BASE_URL, a.get("href"))

            chapters.append((ch_title, ch_url))
        
        results['chapters'] = chapters
        
        return results
    
    def iter_chapters(self, data, page: int=1):
        chapters_list = []

        if 'chapters' in data:
          chapters_list = [
            {
              "title": card[0],
              "url": card[1],
              "manga_title": data['title'],
              "poster": data['poster'] if 'poster' in data else None
            }
            for card in data['chapters']
          ]

        return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

    # -------------------------------------------------
    # CHAPTER IMAGES
    # -------------------------------------------------
    @classmethod
    async def get_pictures(cls, chapter_url, data: dict = {}):
        html = await Scraper(headers=HEADERS).get(chapter_url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "html.parser")
        images = []

        for img in soup.select("div.reading-content img"):
            src = img.get("data-src") or img.get("src")
            if not src:
                continue
            
            images.append(src)

        return images
