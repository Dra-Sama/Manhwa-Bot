# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper
import json
from bs4 import BeautifulSoup

from loguru import logger
from .utitls import DEAULT_MSG_FORMAT


class ComickWebs(Scraper):

  def __init__(self):
    super().__init__()
    self.url = "https://comick.io"
    self.bg = None
    self.sf = "ck"
    self.headers = {
        "Accept":
        "application/json",
        "Referer":
        "https://comick.cc",
        "User-Agent":
        "Tachiyomi Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Mobile Safari/537.36",
    }
    self.search_query = dict()

  async def get_hid(self, slug: str):
    url = f"https://api.comick.fun/comic/{slug}?lang=en"

    response = await self.get(url, cs=True, headers=self.headers, rjson=True)

    return response["comic"]["hid"] if response else None

  async def get_information(self, slug, data):
    url = f"https://api.comick.fun/comic/{slug}/?t=0"
    series = await self.get(url, cs=True, rjson=True, headers=self.headers)

    if series is None:
      return None

    title = series["comic"]["title"]
    status = {1: "Ongoing", 2: "Completed", 3: "Cancelled", 4: "On Hiatus"}
    status = status.get(series.get("comic", {}).get("status", "N/A"), "N/A")

    url = f"https://comick.io/comic/{slug}"
    file_key = series["comic"]["md_covers"][0]["b2key"]
    
    cover = f"https://meo.comick.pictures/{file_key}"
    data['poster'] = cover
    data['url'] = url

    genres_list = [
        i["md_genres"]["name"] for i in series["comic"]["md_comic_md_genres"]
    ]
    genres = ", ".join(genres_list) or "N/A"

    try:
      desc = series["comic"]["desc"]
    except:
      desc = "N/A"

    desc = desc if desc else "N/A"
    data['title'] = title

    data['msg'] = DEAULT_MSG_FORMAT.format(title=title,
                                           status=status,
                                           genres=genres,
                                           summary=desc[:200],
                                           url=url)

  async def search(self, query: str = ""):
    if query.lower in self.search_query:
      mangas = self.search_query[query.lower]
      return mangas

    url = f"https://api.comick.fun/v1.0/search/?type=comic&page=1&limit=8&q={query}&t=false"
    mangas = await self.get(url, cs=True, rjson=True, headers=self.headers)
    for manga in mangas:
      url = f"https://comick.io/comic/{manga['slug']}"

      file_key = manga["md_covers"][0]["b2key"]

      images = f"https://meo.comick.pictures/{file_key}"

      manga['url'] = url
      manga['poster'] = images

    self.search_query[query.lower] = mangas

    return mangas

  async def get_chapters(self, data, page: int = 1):
    results = {}
    if not 'hid' in data:
      if 'slug' not in data:
        data['slug'] = data['url'].split("/")[-1]

      data['hid'] = await self.get_hid(data['slug'])

    url = f"https://api.comick.fun/comic/{data['hid']}/chapters?lang=en&page={str(page)}"

    results = await self.get(url, cs=True, rjson=True, headers=self.headers)
    if results:
      await self.get_information(data['slug'], results)

      results['title'] = data['title']
      if "url" not in results:
        results['url'] = data['url']

    return results

  def iter_chapters(self, data, page=1):
    if not data or 'chapters' not in data:
      return []

    chapters_list = []
    for chapter in data['chapters']:
      title = chapter.get("title", None)
      #title = title.replace("None", "")
      title = f"{chapter['chap']} - {title}" if title else f"Chapter {chapter['chap']}"
      try:
        md_group = chapter.get("group_name", ["None"])[0]
      except:
        md_group = None
      title = f"{title} ({md_group})" if md_group else title
      chapters_list.append({
          "title":
          title,
          "url":
          f"{data['url']}/{chapter['hid']}-chapter-{chapter['chap']}-en",
          "slug":
          chapter['hid'],
          "manga_title":
          data['title'],
          "group_name":
          md_group,
          "poster":
          data['poster'] if 'poster' in data else None,
      })

    return chapters_list

  async def get_pictures(self, url, data=None):
    response = await self.get(url, cs=True, headers=self.headers)
    bs = BeautifulSoup(response, "html.parser")
    container = bs.find("script", {"id": "__NEXT_DATA__"})

    con = container.text.strip()
    con = json.loads(con)

    images = con["props"]["pageProps"]["chapter"]["md_images"]
    images_url = [
        f"https://meo.comick.pictures/{image['b2key']}" for image in images
    ]

    return images_url

  async def get_updates(self, page: int = 1):
    output = []
    while page <= 5:
      url = f"https://api.comick.fun/chapter?page={page}&device-memory=8&order=new"
      results = await self.get(url, cs=True, rjson=True, headers=self.headers)

      for data in results:
        url = f"https://comick.io/comic/{data['md_comics']['slug']}"
        file_key = data["md_comics"]['md_covers'][0]["b2key"]

        images = f"https://meo.comick.pictures/{file_key}"
        chapter_url = f"{url}/{data['hid']}-chapter-{data['chap']}-en"

        data['poster'] = images
        data['chapter_url'] = chapter_url

        data['url'] = url
        data['manga_title'] = data['md_comics']['title']
        data['title'] = f"Chapter {data['chap']}"

        output.append(data)

      page += 1

    return output
