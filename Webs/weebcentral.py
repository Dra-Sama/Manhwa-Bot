# Code By @V_Sbotmaker (on Telegram)

from .scraper import shared_scraper as scraper

from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlencode

from loguru import logger
from .utitls import DEAULT_MSG_FORMAT
from copy import deepcopy as copy
import random 


def get_worker_url() -> str:
  return random.choice([
    "https://fragrant-fog-9033.leechwork3.workers.dev/",
    "https://yt.ritikmishra0617-pro.workers.dev/"
  ])


class WeebCentralWebs:
  url = "https://weebcentral.com/"
  sf = "weebc"
  headers = {
      "Accept": "*/*",
      "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
      "Connection": "keep-alive",
      "Content-Type": "application/x-www-form-urlencoded",
      "Host": "weebcentral.com",
      "HX-Request": "true",
      "Origin": "https://weebcentral.com",
      "Referer": "https://weebcentral.com/",
      "sec-ch-ua": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
      "sec-ch-ua-mobile": "?0",
      "sec-ch-ua-platform": "Windows",
      "Sec-Fetch-Dest": "empty",
      "Sec-Fetch-Mode": "cors",
      "Sec-Fetch-Site": "same-origin",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    }

  async def search(self, query: str = ""):
    results = []
    request_url = get_worker_url() + f"w?query={quote_plus(query)}"
    content = await scraper.get(request_url) 
    if not content:
      return results
    
    bs = BeautifulSoup(content, "html.parser")
      
    cards = bs.find_all("a")
    for card in cards:
      url = card.get('href')
      if not url: continue
        
      poster = card.findNext("img")['src'].strip()
      title = card.findNext("div").findNext("div").text.strip()
      
      results.append({"url": url, "poster": poster, "title": title})

    return results

  async def get_chapters(self, data, page: int=1):
    results = data
    try:
      link = data['url'].split("/")
      new_link = "/".join(link[:-1]) + "/full-chapter-list"
      
      chapters = await scraper.get(data['url'], cs=True)

      if not chapters:
        return results
      
      
      bs = BeautifulSoup(chapters, "html.parser")
        
      tags_= bs.find(class_="flex flex-col gap-4")
      tags_ = tags_.find_all("li") if tags_ else []
      geners = None
      if tags_:
          for tag in tags_:
            tag_fornt = tag.findNext("strong").text.strip()
            tag_back = tag.find_all("span")
            tag_back = [i.text.strip() for i in tag_back]
            tag_back = ' '.join(tag_back) if tag_back else None
            if tag_back and tag_fornt:
              if tag_fornt == "Tags(s)":
                geners = tag_back
                break
        
      desc = bs.find("section", class_="md:w-8/12 flex flex-col gap-4")
      des = desc.find(class_="flex flex-col gap-4") if desc else None
        
      des = des.find_next("li") if des else None
      des = des.text.strip() if des else None
        
      results['msg'] = DEAULT_MSG_FORMAT.format(
          title=results['title'],
          status="N/A",
          genres=geners if geners else "N/A",
          summary=des[:200] if des else "N/A",
          url=results['url']
      )
      
      try: 
        headers = copy(self.headers)
        headers['HX-Current-URL'] = results['url']
        headers['HX-Target'] = "chapter-list"
        headers['HX-Request'] = "true"
        
        #new_link = get_worker_url() + quote(new_link)
        chapters = await scraper.get(new_link, cs=True, headers=headers)
      except: 
        chapters = None
      
      if chapters:
        bs = BeautifulSoup(chapters, "html.parser")
        
        chapters = bs.find_all("a", class_=lambda x: x and "hover:bg-base-300" in x)

        results['chapters'] = []
        params = {
            'is_prev': 'False',
            'current_page': '1',  # Ensure this is correctly named
            'reading_style': 'long_strip'
        }
        
        for a in chapters:
          ch_url = a.get("href")
          if not ch_url:
            continue

          outer_span = a.find("span", class_="grow flex items-center gap-2")
          episode_title = None
          if outer_span:
              inner_spans = outer_span.find_all("span", recursive=False)
              if inner_spans:
                  episode_title = inner_spans[0].get_text(strip=True)

          if episode_title and ch_url:
            results['chapters'].append({
              "title": episode_title,
              "url": f"{ch_url}/images?{urlencode(params)}",
              "manga_title": data['title'],
              "poster": data['poster'] if 'poster' in data else None,
            })
    except Exception as err:
      logger.exception(f"WeebCentral Chapters: {err}")
    
    return results

  def iter_chapters(self, data, page: int=1):
    chapters_list = data.get("chapters", [])
    
    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    image_links = []
    
    url = url.replace("%C2%", "&")
    response = await scraper.get(url, cs=True)# headers=self.headers)
    if response:
      bs = BeautifulSoup(response, "html.parser")
      for i in bs.find_all("img"):
        img = str(i.get('src', "None"))
        
        if "manga" in img or img != '/static/images/brand.png':
          image_links.append(img)

    return image_links


  
