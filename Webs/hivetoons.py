# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper
import json, re
from bs4 import BeautifulSoup

from loguru import logger
from urllib.parse import urlparse, urljoin, quote, quote_plus

from .utitls import DEAULT_MSG_FORMAT, ATSU_MSG_FORMAT


class HiveToonsWebs(Scraper):
    def __init__(self):
        super().__init__()
        self.url = "https://hivetoons.org"
        self.sf = "htns"

        self.headers = {
            "Accept": "*/*",
            # "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Host": "api.hivetoons.org",
            "Origin": "https://hivetoons.org",
            "Referer": "https://hivetoons.org/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0",
        }

    async def search(self, query: str = ""):
        search_url = f"https://api.hivetoons.org/api/query?searchTerm={quote(query)}&perPage=1000"
        data = await self.get(search_url, rjson=True, headers=self.headers)
        if not data or "posts" not in data:
            return []

        results = []
        for doc in data.get("posts", []):
            try:
                data = {}
                if (
                    doc.get("isNovel", False) is False
                    or doc.get("seriesType", "Manga") != "NOVEL"
                ):
                    data["title"] = doc["postTitle"]
                    data["url"] = f"https://hivetoons.org/series/{doc['slug']}"
                    data["poster"] = doc["featuredImage"]
                    # data['id'] = doc['id']

                    _type = doc.get("seriesType", None)
                    _summary = doc.get("postContent", None)
                    _genres = doc.get("genres", [])
                    _genres = (
                        ", ".join([g.get("name", "") for g in _genres])
                        if _genres
                        else None
                    )
                    _alt_titles = doc.get("alternativeTitles", None)
                    # _alt_titles = ", ".join(_alt_titles) if _alt_titles else None
                    _status = doc.get("seriesStatus", None)

                    data["msg"] = ATSU_MSG_FORMAT.format(
                        title=data["title"],
                        alt_title=_alt_titles if _alt_titles else "N/A",
                        genres=_genres if _genres else "N/A",
                        type=_type if _type else "N/A",
                        status=_status if _status else "N/A",
                        summary=_summary[:200] if _summary else "N/A",
                        url=data["url"],
                    )
                    if len(data["msg"]) > 1024:
                        data["msg"] = DEAULT_MSG_FORMAT.format(
                            title=data["title"],
                            status=_status if _status else "N/A",
                            genres=_genres if _genres else "N/A",
                            summary=_summary[:200] if _summary else "N/A",
                            url=data["url"],
                        )

                    results.append(data)

            except Exception:
                pass

        return results

    async def get_chapters(self, data, page: int = 1):
        def clean_json(json_data):
            while True:
                if "\\" in json_data:
                    json_data = json_data.replace("\\", "")
                else:
                    break
            return json_data

        results = data.copy()
        headers = self.headers.copy()
        headers["Host"] = "hivetoons.org"

        HTML = await self.get(results["url"], headers=headers)
        if not HTML:
            return results

        bs = BeautifulSoup(HTML, "html.parser")

        # --- Poster ---
        if "poster" not in results or not results["poster"]:
            poster_ = bs.find(class_="relative contents")
            results["poster"] = poster_.find_next("img").get("src") if poster_ else None

        if "msg" not in results:
            tags = bs.find_all(
                class_="flex sm:justify-between justify-start items-center gap-2"
            )

            status_ = None
            type_ = None
            for tag in tags:
                h1_ = tag.find("h1").text.strip() if tag.find("h1") else None
                if h1_ and h1_ == "Status":
                    status_ = (
                        tag.find("span").text.strip() if tag.find("span") else None
                    )
                elif h1_ and h1_ == "Type":
                    type_ = tag.find("span").text.strip() if tag.find("span") else None

            # -- Summary --
            summary_ = bs.find("div", {"itemprop": "description"})
            summary_ = summary_.text.strip() if summary_ else None

            # -- Genres --
            genres_ = bs.find(class_="flex flex-wrap gap-1 md:gap-2 mt-2 mb-2")
            genres_ = (
                ", ".join([g.text.strip() for g in genres_.find_all("a")])
                if genres_
                else None
            )

            results["msg"] = ATSU_MSG_FORMAT.format(
                title=data["title"],
                alt_title="N/A",
                genres=genres_ if genres_ else "N/A",
                type=type_ if type_ else "N/A",
                status=status_ if status_ else "N/A",
                summary=summary_[:200] if summary_ else "N/A",
                url=data["url"],
            )
            if len(results["msg"]) > 1024:
                results["msg"] = DEAULT_MSG_FORMAT.format(
                    title=data["title"],
                    status=status_ if status_ else "N/A",
                    genres=genres_ if genres_ else "N/A",
                    summary=summary_[:200] if summary_ else "N/A",
                    url=data["url"],
                )
        try:
            results["chapters"] = []

            chapters_tags = bs.find_all(
                "a",
                class_="flex items-center justify-between p-3 hover:bg-gray-100 dark:hover:bg-white/5 transition-colors group",
            )
            for chapter in chapters_tags:
                chapter_url = chapter.get("href", None)
                if not chapter_url:
                    continue

                chapter_num = chapter_url.split("-")[-1]
                results["chapters"].append(chapter_num)

        except Exception:
            pass

        return results

    @staticmethod
    def complete_sequence_fast(existing_list: list) -> list:
        my_list = [item.replace("_", ".") for item in existing_list]

        max_num = 0
        for item in my_list:
            try:
                max_num = max(max_num, int(float(item.replace("_", "."))))
            except:
                pass

        completed = [str(i) for i in range(1, max_num + 1)]

        for item in my_list:
            item = item.replace("_", ".")
            try:
                if "." in item and float(item) != int(float(item)):
                    completed.append(item)
            except:
                completed.append(item)

        # Sort numbers only (strings at end)
        completed.sort(
            key=lambda x: (
                not x.replace(".", "").replace("-", "").isdigit(),
                float(x) if x.replace(".", "", 1).replace("-", "", 1).isdigit() else 0,
            )
        )

        completed.reverse()

        return completed

    def iter_chapters(self, data, page: int = 1):
        chapters_list = []

        if "chapters" in data:
            try:
                for chapter in self.complete_sequence_fast(data["chapters"]):
                    chapters_list.append(
                        {
                            "title": chapter,
                            "url": f"{data['url']}/chapter-{chapter}",
                            "manga_title": data["title"],
                            "poster": data["poster"] if "poster" in data else None,
                        }
                    )

            except Exception as err:
                logger.exception(f"HiveToon Error: {err}")
                return []

        return (
            chapters_list[(page - 1) * 60 : page * 60] if page != 1 else chapters_list
        )

    async def get_pictures(self, url, data=None):
        trans_table = str.maketrans({"\\": ""})

        headers = self.headers.copy()
        headers["Host"] = "hivetoons.org"

        html = await self.get(url, headers=headers, cs=True)
        
        if not html:
            return []

        image_urls = []
        try:
            bs = BeautifulSoup(html, "html.parser")
            image_metas = bs.find_all('meta', {'itemprop': 'image'})
            

            
            if images := [ img.get("content") for img in image_metas ]:
                return images

            # It is just for fun 
            
            images = bs.select("img.h-auto.w-full.object-contain")
            
            images_tag = bs.find("script", text=lambda x: x and r'\"images\":[' in x)
            
            if not images_tag:
                return image_urls

            pattern = r'\\"images\\":(\[.*?\])'
            match = re.search(pattern, str(images_tag))
            
            m_group = getattr(match, "group", None)
            if not m_group:
                return image_urls

            image_json = json.dumps(m_group(1))
            
            new_dump = image_json.translate(trans_table)
            image_urls = re.findall(r'"url":"(https?://[^"]+)"', new_dump)

              
            return list(dict.fromkeys(image_urls))

        except Exception as e:
            logger.error(e)
            return []
