# Code By @V_Sbotmaker (on Telegram)
import json
from Webs.utitls import DEAULT_MSG_FORMAT
from bs4 import BeautifulSoup

from .scraper import Scraper
from copy import deepcopy
from typing import Optional


API_HEADERS = {
  "Accept": "*/*",
  "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
  "Connection": "keep-alive",
  #"Content-Length": "37",
  "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
  "Host": "elftoon.com",
  "Origin": "https://elftoon.com",
  "Referer": "https://elftoon.com/",
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
  "X-Requested-With": "XMLHttpRequest"
}


class ElftoonWebs:
  url : str = "https://elftoon.com"
  api_url: str = "https://elftoon.com/wp-admin/admin-ajax.php"
  sf: str = "ef.t"
  
  async def search(self, query: str) -> list:
    params: dict = {
      "action": "ts_ac_do_search",
      "ts_ac_query": query
    }
    headers = deepcopy(API_HEADERS)
    
    content_len = len("&".join(f"{k}={v}" for k, v in params.items()))
    headers['Content-Length'] = str(content_len)
    
    response = await Scraper(headers=headers).post(
      self.api_url, data=params, rjson=True, 
      cs=True
    )
    
    if not response or not isinstance(response, dict):
      return []
    
    if "series" not in response or "all" not in response['series'][0]:
      return []

    if not isinstance(response['series'][0]['all'], list):
      return []

    results = []
    for manga_data in response['series'][0]['all']:
      results.append({
        "title": manga_data['post_title'],
        "url": manga_data['post_link'],
        "poster": manga_data['post_image'],
        "post_genres": manga_data.get('post_genres', None),
        "post_status": manga_data.get('post_status', None)
      })
    
    return results

  async def get_chapters(self, data: dict, page: int = 1) -> dict:
    results = deepcopy(data)
    del data
    response = await Scraper().get(results['url'], cs=True)
    
    if not response:
      return results
    
    bs = BeautifulSoup(response, "html.parser")
    
    """ Genres """
    generes = results.get("post_genres", None)
    if not generes:
      gen_tags = bs.select_one("span.mgen")
      gen_list = gen_tags.find_all("a") if gen_tags else []
      generes = ", ".join([g.text.strip() for g in gen_list]) if gen_list else None

    
    """ Tags """
    status = results.get("post_status", None)
    if not status:
      tag_tag = bs.select_one("div.tsinfo.bixbox")
      status_tag = tag_tag.find_all("div", class_="imptdt") if tag_tag else []
      status_tag = getattr(status_tag[0], "text", None)
      status = str(status_tag.strip()) if status_tag else "N/A"
      status = status.replace("Status:", "").strip()

    
    """ Poster """
    if "poster" not in results or results['poster'] is None:
      con_tag = bs.select_one("div.info-left-margin")
      poster_tag = con_tag.find("img") if con_tag else None
      results['poster'] = poster_tag.get("src") if poster_tag else None
    
    """ Summary """
    summary = bs.select_one("div.wd-full")
    if summary:
      summary = summary.find("p")
      summary = str(getattr(summary, "text", "N/A"))
      summary = summary.strip()
    
    summary = str(summary)
    
    results['msg'] = DEAULT_MSG_FORMAT.format(
      title=results['title'],
       status=status if status else "N/A",
       genres=generes if generes else "N/A",
       summary=summary[:200] if summary else "N/A",
       url=results['url']
    )

    
    """ Chapters """
    chapters_tag = bs.select_one("div#chapterlist.eplister")
    if not chapters_tag:
      return results
    
    chapters_tag = chapters_tag.find("ul")
    if not chapters_tag:
      return results
    
    results['chapters'] = []
    for chapter_data in chapters_tag.find_all("li"):
      a_tag = chapter_data.find("a")
      chapter_url = a_tag.get("href", None) if a_tag else None
      
      if not isinstance(chapter_url, str):
        continue

      chapter_title = a_tag.get("aria-label", None) if a_tag else None
      if not isinstance(chapter_title, str):
        span_tag = chapter_data.find("span", class_="chapternum")
        chapter_title = getattr(span_tag, "text", None)
     
      if not isinstance(chapter_title, str):
        continue
      
      results['chapters'].append({
        "title": chapter_title.strip(),
        "url": chapter_url.strip(),
        "manga_title": results['title'],
        "poster": results['poster'] if 'poster' in results else None
      })
    
    return results
  
  def iter_chapters(self, data: dict, page: int = 1) -> list:
    return data.get("chapters", [])[(page - 1) * 60:page * 60] if page != 1 else data.get("chapters", [])
  
  async def get_pictures(self, url: str, data: Optional[dict] = None) -> list:
    response = await Scraper().get(url, cs=True)
    if not response:
      return []
    
    bs = BeautifulSoup(response, "html.parser")
    script_tag = bs.find("script", text=lambda x: x and """ts_reader.run({""" in x)
    if not script_tag:
      return []
    
    script_txt = str(script_tag.text).strip()
    script_txt = script_txt.replace("ts_reader.run(", "")
    script_txt = script_txt.replace(");", "")
    try:
      script_tag = json.loads(script_txt)
      images_list = script_tag.get("sources", [])[0].get("images", [])
      
      return images_list
      
    except json.JSONDecodeError:
      return []
    
    except Exception:
      return []
    
    return []
    
    
    
      
      
    
    
