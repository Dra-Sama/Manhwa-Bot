# Code By @V_Sbotmaker (on Telegram)

from .scraper import Scraper

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus

from loguru import logger
from .utitls import DEAULT_MSG_FORMAT
import random


PROXY = random.choice([
    "https://holy-credit-da93.lajosip431.workers.dev/proxy?url=",
    'https://allmanga-img.joyelo8017.workers.dev/proxy?url=',
    'https://allmanga-img-02.sophiebae.workers.dev/proxy?url=',
    'https://allmanga-img.muniu8ac2geo.workers.dev/proxy?url='
])

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://demonicscans.org/",
    "Connection": "keep-alive",
}

scraper = Scraper(headers=HEADERS)


class DemonicScansWebs:
  url = "https://demonicscans.org/"
  sf = "ds"

  async def search(self, query: str = ""):
    
    url = f'https://demonicscans.org/search.php?manga={quote_plus(query)}'
    search_url = PROXY + quote(url, safe='')
    
    mangas = await scraper.get(search_url, cs=True)
    if not mangas:
      return []
    
    bs = BeautifulSoup(mangas, "html.parser")
    cards = bs.find_all("a")
    results = []
    for card in cards:
      try:
        data = {}
        data['url'] = urljoin(self.url, card.get('href').strip())
        poster = card.find_next('img').get('src').strip()
        
        parsed = urlparse(poster)
        poster = quote(parsed.path)
        poster = parsed._replace(path=poster).geturl()
        
        data['poster'] = poster
        data['title'] = card.find_next('div').find_next("div").text.strip()
        
        results.append(data)
      except Exception:
        continue
    
    return results

  async def get_chapters(self, data, page: int=1):
    results = data
    request_url = PROXY + quote(results['url'], safe='')

    content = await scraper.get(request_url, cs=True)
    if not content:
      return results
    

    bs = BeautifulSoup(content, "html.parser")
    chap = bs.find("div", {"id": "chapters-list"})
    
    chap = chap.find_all("a") if chap else []
    results['chapters'] = chap
      
    des = bs.find(class_="white-font")
    des = des.text.strip() if des else "N/A"
      
    gen = bs.find("div", {"class": "genres-list"})
    gen = " ".join([g.text.strip() for g in gen.find_all("li")]) if gen else "N/A"
      
    status_ = bs.find('li', string='Status')
    status = status_.find_next_sibling('li').text if status_ else "N/A"

    results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=status,
        genres=gen,
        summary=des[:200],
        url=results['url']
    )

    return results

  def iter_chapters(self, data, page: int=1):
    chapters_list = []

    if "chapters" not in data:
      return []
    
    for card in data['chapters']:
      titles = card.get("href").split("=")[-1]
      
      manga_url = data['url'].replace("manga", "title")
      url = f"{manga_url}/chapter/{titles}/1"
      
      chapters_list.append({
        "title": titles,
        "url": url,
        "manga_title": data['title'],
        "poster": data['poster'] if 'poster' in data else None,
      })

    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list

  async def get_pictures(self, url, data=None):
    request_url = PROXY + quote(url, safe='')
    response = await scraper.get(request_url, cs=True)

    if not response:
      return []
    
    bs = BeautifulSoup(response, "html.parser")
    
    imgs_tags = bs.find_all('img', {"style": "max-width:100%;"})
    #print(imgs_tags)
    image_links = []
    for img in imgs_tags:
      images_link = img.get('src').strip()
      if images_link != "/img/free_ads.jpg":
        if images_link == "/img/wsup.gif":
          continue
        
        try:
          parsed = urlparse(images_link)
          poster = quote(parsed.path)
          
          images_link = parsed._replace(path=poster).geturl()
          image_links.append(images_link)
        except Exception:
          continue
      
    return image_links
