# Code By @V_Sbotmaker (on Telegram)
from .scraper import shared_scraper as scraper
import urllib.parse
from .utitls import DEAULT_MSG_FORMAT
import asyncio
from loguru import logger


class APISourceWebs:
    def __init__(self, source_id: str, name: str, base_url: str, api_type: str = "vercel"):
        self.source_id = source_id
        self.name = name
        self.url = base_url
        self.api_type = api_type
        self.sf = source_id

        if api_type == "railway":
            self.api_base = "https://manga-cf-api-production.up.railway.app"
        elif api_type == "heroku":
            self.api_base = "https://ykyk-3709f79a83fc.herokuapp.com"
        else:
            self.api_base = "https://manga-api-plum.vercel.app"

    async def search(self, query: str = ""):
        url = f"{self.api_base}/{self.source_id}/search?q={urllib.parse.quote_plus(query)}"
        try:
            data = await asyncio.wait_for(
                scraper.get(url, rjson=True),
                timeout=11.5
            )
            if not data or not isinstance(data, list):
                return []
            results = []
            for item in data:
                results.append({
                    "url": item.get("url", ""),
                    "poster": item.get("thumbnail", item.get("poster", "")),
                    "title": item.get("title", ""),
                })
            return results
        except asyncio.TimeoutError:
            logger.warning(f"[API Web Search] {self.name} timed out")
            return []
        except Exception as e:
            logger.error(f"[API Web Search] {self.name} error: {e}")
            return []

    async def get_chapters(self, data: dict):
        results = data.copy()
        manga_url = results.get("url")
        if not manga_url:
            return results

        url = f"{self.api_base}/{self.source_id}/chapters?url={urllib.parse.quote_plus(manga_url)}"
        try:
            chapters_data = await asyncio.wait_for(
                scraper.get(url, rjson=True),
                timeout=122.0
            )
            if not chapters_data or not isinstance(chapters_data, list):
                results["chapters"] = []
                return results

            chapters_list = []
            for ch in chapters_data:
                chapters_list.append({
                    "title": ch.get("title", ""),
                    "url": ch.get("url", ""),
                    "manga_title": results.get("title"),
                    "poster": results.get("poster"),
                })

            results["chapters"] = chapters_list
            results["msg"] = DEAULT_MSG_FORMAT.format(
                title=results.get("title", "N/A"),
                status="N/A",
                genres="N/A",
                summary="N/A",
                url=manga_url,
            )
            return results
        except asyncio.TimeoutError:
            logger.warning(f"[API Web Chapters] {self.name} timed out")
            results["chapters"] = []
            return results
        except Exception as e:
            logger.error(f"[API Web Chapters] {self.name} error: {e}")
            results["chapters"] = []
            return results

    async def get_pictures(self, url: str, data=None):
        api_url = f"{self.api_base}/{self.source_id}/images?url={urllib.parse.quote_plus(url)}"
        try:
            images = await asyncio.wait_for(
                scraper.get(api_url, rjson=True),
                timeout=122.0
            )
            if isinstance(images, list):
                return images
            return []
        except asyncio.TimeoutError:
            logger.warning(f"[API Web Images] {self.name} timed out")
            return []
        except Exception as e:
            logger.error(f"[API Web Images] {self.name} error: {e}")
            return []


class ComicKAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="comick", name="ComicK", base_url="https://comick.live", api_type="vercel")


class QiManhwaAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="qimanhwa", name="Qi Manhwa", base_url="https://qimanhwa.com", api_type="vercel")


class HentaraAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="hentara", name="Hentara", base_url="https://hentara.com", api_type="vercel")


class KaganeAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="kagane", name="Kagane", base_url="https://kagane.to", api_type="heroku")


# ========== NEW API SOURCES (AquaReader & KaliScans moved to API) ==========
class AllmangaAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="mkissa", name="mkissa", base_url="https://mkissa.to", api_type="vercel")

class AquaReaderAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="aquareader", name="Aqua Manga", base_url="https://aquareader.org", api_type="vercel")


class KaliScansAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="kaliscan", name="KaliScan", base_url="https://kaliscan.io", api_type="vercel")


# ========== NEW API SOURCES FROM API ==========

class AnisaScansAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="anisascans", name="AnisaScans", base_url="https://anisascans.in", api_type="vercel")


class ComicKFanAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="comickfan", name="ComicK Fanmade", base_url="https://comickfan.com", api_type="vercel")


class ManhuaHotAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="manhuahot", name="ManhuaHot", base_url="https://manhuahot.com", api_type="vercel")


class MangaPillAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="mangapill", name="MangaPill", base_url="https://mangapill.com", api_type="vercel")


class ScansGGAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="scansgg", name="ScansGG", base_url="https://scans.gg", api_type="vercel")


class ManhwaZoneAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="manhwazone", name="ManhwaZone", base_url="https://manhwazone.com", api_type="vercel")


class MangaKAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="mangak", name="MangaK", base_url="https://mangak.io", api_type="vercel")


class ManganatoAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="manganato", name="Manganato", base_url="https://www.mangabats.com", api_type="vercel")


class MangaHeAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="mangahe", name="MangaHe", base_url="https://mangahe.com", api_type="vercel")


class BrainrotComicsAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="brainrotcomics", name="Brainrot Comics", base_url="https://brainrotcomics.com", api_type="vercel")


class BakkinAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="bakkin", name="Bakkin", base_url="https://bakkin.moe", api_type="vercel")


class BunMangaAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="bunmanga", name="BunManga", base_url="https://bunmanga.com", api_type="vercel")


class Hentai4FreeAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="hentai4free", name="Hentai4Free", base_url="https://hentai4free.net", api_type="vercel")


class MangaFoxAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="mangafox", name="MangaFox", base_url="https://m.fanfox.net", api_type="vercel")


class MantaAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="manta", name="Manta", base_url="https://manta.net", api_type="vercel")


class RitharScansAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="ritharscans", name="Rithar Scans", base_url="https://ritharscans.com", api_type="vercel")


class WitchScansAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="witchscans", name="Witch Scans", base_url="https://witchscans.com", api_type="vercel")


class MangaHubAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="mangahub", name="MangaHub", base_url="https://mangahub.io", api_type="vercel")


class WebtoonsAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="webtoons", name="Webtoons", base_url="https://www.webtoons.com", api_type="vercel")


class MangaGGAPIWebs(APISourceWebs):
    def __init__(self):
        super().__init__(source_id="mangagg", name="MangaGG", base_url="https://mangagg.com", api_type="vercel")
