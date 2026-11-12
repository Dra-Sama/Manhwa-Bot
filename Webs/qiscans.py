# Code By @V_Sbotmaker (on Telegram)
import random

from .scraper import Scraper
import json, re
from bs4 import BeautifulSoup

from loguru import logger
from urllib.parse import quote_plus, quote

from .utitls import DEAULT_MSG_FORMAT, ATSU_MSG_FORMAT
from copy import deepcopy


API_HEADERS = {
  "Accept": "application/json, text/plain, */*",
  #"Accept-Encoding": "gzip, deflate, br, zstd",
  "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
  "Connection": "keep-alive",
  "Host": "api.qimanhwa.com",
  "Origin": "https://qimanhwa.com",
  "Referer": "https://qimanhwa.com",
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"
}

def create_link(url: str ) -> str:
  worker_url = random.choice([
    "https://api.shanksytprem.workers.dev/proxy?url=",
    "https://odd-leaf-f894.shanksshanks-12222.workers.dev/proxy?url=",
  ])
  return worker_url + quote(url)


class QiScansWebs:
  url = "https://qimanhwa.com"
  sf = "qiss"

  async def search(self, query: str ):
    search_url = f"https://api.qimanhwa.com/api/query?searchTerm={quote_plus(query)}&perPage=1000"

    data = await Scraper(API_HEADERS, tor=True).get(search_url, cs=True, rjson=True)
    if not data or "posts" not in data:
      return []

    results = []
    for doc in data.get("posts", []):
      try:
        data = {}
        if doc.get("isNovel", False) is False or doc.get("seriesType", "Manga") != "NOVEL":
          data['title'] = doc['postTitle'].strip()
          data['url'] = f"{self.url}/series/{doc['slug']}?{doc['id']}"
          
          data['poster'] = doc['featuredImage']
          #data['poster'] += "&headers=" + quote(IMAGES_HEADERS_JSON)
          #data['id'] = doc['id']

          _type = doc.get('seriesType', None)
          _summary = doc.get('postContent', None)
          _genres = doc.get("genres", [])
          _genres = ", ".join([g.get("name", "") for g in _genres]) if _genres else None
          _alt_titles = doc.get("alternativeTitles", None)
          #_alt_titles = ", ".join(_alt_titles) if _alt_titles else None
          _status = doc.get("seriesStatus", None)

          data['msg'] = ATSU_MSG_FORMAT.format(
            title=data['title'],
            alt_title=_alt_titles if _alt_titles else 'N/A',
            genres=_genres if _genres else 'N/A',
            type=_type if _type else 'N/A',
            status=_status if _status else 'N/A',
            summary=_summary[:200] if _summary else 'N/A',
            url=data['url']
          )
          if len(data['msg']) > 1024:
            data['msg'] = DEAULT_MSG_FORMAT.format(
              title=data['title'],
              status=_status if _status else 'N/A',
              genres=_genres if _genres else 'N/A',
              summary=_summary[:200] if _summary else 'N/A',
              url=data['url']
            )
          results.append(data)
      except:
        pass

    return results
  
  async def get_chapters(self, data, page: int = 1):
    results = data.copy()
    
    if "?" not in results['url']:
      return results
    
    post_id = results['url'].split("?")
    manga_url = post_id[0]
    post_id = post_id[-1]
    
    api_url = f"https://api.qimanhwa.com/api/chapters?postId={post_id}&skip=0&take=100&order=desc&search=&userId=undefined"
    data = await Scraper(API_HEADERS, tor=True).get(api_url, rjson=True, cs=True)
    if not data or "post" not in data or "chapters" not in data['post']:
      return results

    results['chapters'] = []
    for chapter in data['post']['chapters']:
      if chapter.get('isPermanentlyLocked', False) in [False, "false"]:
        chapter_slug = chapter.get('slug', None)
        
        chapter_url = manga_url + chapter_slug if manga_url.endswith("/") else manga_url + "/" + chapter_slug
        chapter_title = chapter.get('number', "N/A")
        
        if "poster" not in results:
          results['poster'] = chapter.get('mangaPost', {}).get("featuredImage", None)

        results['title'] = chapter.get('mangaPost', {}).get("postTitle", None) or results['title']
        results['chapters'].append({
          "title": chapter_title,
          "url": chapter_url,
          "manga_title": results['title'],
          "poster": results['poster'] if 'poster' in results else None
        })
    
    return results


    

  def iter_chapters(self, data, page: int = 1):
    chapters_list = data['chapters'] if 'chapters' in data else []
    return chapters_list[(page - 1)*60:page*60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    def clean_script(script_tag: str) -> str:
      while True:
        script_tag = script_tag.replace("<script>self.__next_f.push(", "")
        script_tag = script_tag.replace(")</script>", "")
        script_tag = script_tag.replace("self.__next_f.push(", " ")
        script_tag = script_tag.removesuffix(")")
        if "\\" in script_tag:
          script_tag = script_tag.replace("\\", "")
        else:
          break
      
      return script_tag
                                  
    headers = deepcopy(API_HEADERS.copy())
    headers['Accept'] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    headers['Host'] = "qimanhwa.com"
    del headers['Origin']
    del headers['Referer']
    
    response = await Scraper(headers, tor=True).get(url, cs=True)
    if not response:
      return []
    
    bs = BeautifulSoup(response, "html.parser")
    script_tag = bs.find("script", text=lambda x: r'{\"API_Response\":{\"chapter\":' in x)
    if not script_tag:
      return []
    
    try:
      script_tag = clean_script(script_tag.text)
      search_image_tag = re.search(r'\"images\":(\[.*?\])', script_tag)
      search_image_tag = search_image_tag.group(1) if search_image_tag else "[]"
      image_list = json.loads(search_image_tag)
      return [ image['url'] for image in image_list ]
    
    except Exception:
      return []
    
