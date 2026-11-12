# Code By @V_Sbotmaker (on Telegram)
from typing import Generator

from .scraper import shared_scraper

import json, re
from bs4 import BeautifulSoup

from loguru import logger
from urllib.parse import urlparse, urljoin, quote, quote_plus

from .utitls import DEAULT_MSG_FORMAT, ATSU_MSG_FORMAT, cp_list
import random


class VortexScansWebs:
  url = "https://vortexscans.org"
  sf = "vts"

  headers = {
      "Accept": "*/*",
      #"Accept-Encoding": "gzip, deflate, br, zstd",
      "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
      "Connection": "keep-alive",
      "Host": "api.vortexscans.org",
      "Origin": "https://vortexscans.org",
      "Referer": "https://vortexscans.org/",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"
  }

  async def search(self, query: str = ""):
    search_url = f"https://api.vortexscans.org/api/query?searchTerm={quote(query)}&perPage=1000"
    
    data = await shared_scraper.get(search_url, rjson=True, cs=True, headers=self.headers)
    
    if not data or "posts" not in data:
      return []

    results = []
    for doc in data.get("posts", []):
      try:
        data = {}
        if doc.get("isNovel", False) is False or doc.get("seriesType", "Manga") != "NOVEL":
          data['title'] = doc['postTitle'].strip()
          data['url'] = f"https://vortexscans.org/series/{doc['slug']}"
          data['poster'] = doc['featuredImage']
       
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
    def clean_json(json_data):
      while True:
        if "\\" in json_data:
            json_data = json_data.replace("\\", "")
        else:
          break
      return json_data
    
    results = data.copy()
    headers = self.headers.copy()
    headers['Host'] = "vortexscans.org"
    
    HTML = await shared_scraper.get(results['url'], headers=headers, cs=True)
    if not HTML:
      return results

    bs = BeautifulSoup(HTML, "html.parser")

    # --- Poster ---
    if "poster" not in results or not results['poster']:
      poster_ = bs.find(class_="relative contents")
      results['poster'] = poster_.find_next("img").get("src") if poster_ else None
    
    if "msg" not in results:
      tags = bs.find_all(class_="flex sm:justify-between justify-start items-center gap-2")

      status_ = None
      type_ = None
      for tag in tags:
        h1_ = tag.find("h1").text.strip() if tag.find("h1") else None
        if h1_ and h1_ == "Status":
          status_ = tag.find("p").text.strip() if tag.find("p") else None
        elif h1_ and h1_ == "Type":
          type_ = tag.find("span").text.strip() if tag.find("span") else None

      # -- Summary -- 
      summary_ = bs.find("div", {"itemprop": "description"})
      summary_ = summary_.text.strip() if summary_ else None

      # -- Genres --
      genres_ = bs.find_all("a", {"itemprop": "genre"})
      genres_ = ", ".join([g.text.strip() for g in genres_]) if genres_ else None

      results['msg'] = ATSU_MSG_FORMAT.format(
        title=data['title'],
        alt_title='N/A',
        genres=genres_ if genres_ else 'N/A',
        type=type_ if type_ else 'N/A',
        status=status_ if status_ else 'N/A',
        summary=summary_[:200] if summary_ else 'N/A',
        url=data['url']
      )
      if len(results['msg']) > 1024:
        results['msg'] = DEAULT_MSG_FORMAT.format(
          title=data['title'],
          status=status_ if status_ else 'N/A',
          genres=genres_ if genres_ else 'N/A',
          summary=summary_[:200] if summary_ else 'N/A',
          url=data['url']
        )

    self.extract_all_chapters(HTML, results)
    return results

  @staticmethod
  def extract_all_chapters(html_content: str, results: dict) -> None:
      soup = BeautifulSoup(html_content, 'html.parser')

      islands = soup.find_all('astro-island')

      if not islands:
          print("Could not find the chapter data island.")
          return None

      chapter_list = None
      for island in islands:
        try:
          props_str = island.get('props')
          props_data = json.loads(props_str)
          post_wrapper = props_data.get('post')
          if not post_wrapper:
            continue
          
          chapters_wrapper = post_wrapper[1].get('chapters')
          if not chapters_wrapper:
            continue
          
          chapter_list = chapters_wrapper[1]
          
        except Exception:
          continue

      if not chapter_list:
        return None

    
      try:
          results['chapters'] = []
        
          for item in chapter_list:
            details = item[1]

            num = details.get('number', [0, "N/A"])[1]
            slug = details['slug'][1]

            if results['url'].endswith("/"):
              chapter_url = f"{results['url']}{slug}"
            else:
              chapter_url = f"{results['url']}/{slug}"
            
            results['chapters'].append({
              "title": num,
              "url": chapter_url,
              "manga_title": results['title'],
              "poster": results['poster'] if 'poster' in results else None
            })

      except (IndexError, KeyError) as e:
          print(f"Error parsing JSON structure: {e}")
      
      return None

  
    
  def iter_chapters(self, data, page: int = 1):
    if "chapters" not in data:
      return []
    
    chapters_list = data.get('chapters', [])

    return chapters_list[(page - 1)*60:page*60] if page != 1 else chapters_list

  @staticmethod
  def filter_images(images: list) -> list:
    images_list = []
    for image in images:
      try:
        i_url = image.get("src")
        if not i_url:
          continue

        if i_url.startswith('https://storage.vortexscans.org/upload/series') or i_url.startswith('https://storage.vortexscans.org//upload/series'):
          images_list.append(i_url)
      
          
        
      except Exception:
        continue
    
    return images_list
      
    

  
  async def get_pictures(self, url, data=None):
    html = await shared_scraper.get(url, cs=True, headers={
      "Accept": 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
      'Accept-Language': 'en-GB,en;q=0.8',
      'Connection': 'keep-alive',
      'Host': 'vortexscans.org',
      'Sec-Fetch-User': '?1',
      'Sec-GPC': '1',
      'Upgrade-Insecure-Requests': '1',
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
    })
    if not html:
      return []

   
    try:
      bs = BeautifulSoup(html, "html.parser")
      

      return self.filter_images(bs.find_all("img"))

    except:
      return []
