# Code By @V_Sbotmaker (on Telegram)
from typing import List, Dict
from curl_cffi import requests


class KaganeScraper:
    """Kagane scraper using Ykyk API with curl_cffi"""

    API_BASE = "https://ykyk-3709f79a83fc.herokuapp.com"

    def __init__(self):
        self.source_id = "kagane"
        self.name = "Kagane"
        self.base_url = "https://kagane.to"
        self.icon = "🌌"

    def _request(self, endpoint: str, params: dict = None, timeout: float = 20.0) -> dict:
        """Internal request helper with retry"""
        params = params or {}

        for attempt in range(3):
            try:
                response = requests.get(
                    f"{self.API_BASE}/{endpoint}",
                    params=params,
                    timeout=timeout,
                    impersonate="chrome"
                )
                response.raise_for_status()
                return response.json()

            except Exception as e:
                if attempt < 2:
                    print(f"[Kagane] Retry {attempt + 1}: {e}")
                else:
                    print(f"[Kagane] Request failed: {e}")

        return {}

    def search(self, query: str) -> List[Dict]:
        data = self._request(
            "search",
            {"query": query},
            timeout=15
        )

        return [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "series_id": item.get("series_id", ""),
                "chapters": item.get("chapters", 0),
                "thumbnail": item.get("thumbnail", ""),
                "source": self.source_id,
                "source_name": self.name,
                "icon": self.icon,
            }
            for item in data.get("results", [])
        ]

    def get_chapters(self, manga_url: str) -> List[Dict]:
        data = self._request(
            "chapters",
            {"url": manga_url},
            timeout=20
        )

        return [
            {
                "chapter_no": ch.get("chapter_no", ""),
                "title": ch.get("title", ""),
                "book_id": ch.get("book_id", ""),
                "pages": ch.get("pages", 0),
                "sort_no": ch.get("sort_no", 0.0),
                "reader_url": ch.get("reader_url", ""),
                "url": ch.get("reader_url", ""),
            }
            for ch in data.get("chapters", [])
        ]

    def get_chapter_images(self, chapter_url: str) -> List[str]:
        data = self._request(
            "images",
            {"url": chapter_url},
            timeout=25
        )
        return data.get("images", [])

    def get_manga_details(self, manga_url: str) -> Dict:
        # API doesn't provide details endpoint
        return {}


if __name__ == "__main__":
    scraper = KaganeScraper()

    results = scraper.search("One Piece")
    print(results)

    if results:
        chapters = scraper.get_chapters(results[0]["url"])
        print(chapters[:2])

        if chapters:
            images = scraper.get_chapter_images(chapters[0]["url"])
            print(images[:3])
