# Code By @V_Sbotmaker (on Telegram)
from .scraper import shared_scraper as scraper , sb
from urllib.parse import quote_plus
from loguru import logger
from bs4 import BeautifulSoup
from .utitls import ALL_MSG_FORMAT, DEAULT_MSG_FORMAT
import json




class MangadotWebs:
    __slots__ = (
        'url', 'sf', 'name', 
        'sb'
    )
    def __init__(self):
        self.url  = "https://mangadot.net"
        self.sf   = "m.dn"
        self.name = "Mangadot [cf]"
        self.sb   = True
    
    async def search(self, query: str) -> list:
        request_url = f"{self.url}/search?search={quote_plus(query)}"
        results = []

        try:
            html = await sb.get(request_url)
            if not html:
                return results
        
            bs = BeautifulSoup(html, 'html.parser')

            a_tags = bs.find_all( 'a', class_="group flex flex-col gap-1.5" )
            if not a_tags:
                return []
            
            for tag in a_tags:
                manga_url = tag.get('href')
                if not manga_url:
                    continue

                manga_url = f"{self.url}{manga_url}"

                poster = tag.find('img')
                poster = self.url + poster.get('src') if poster else None 

                title_tag = tag.find(class_="line-clamp-2 text-[12px] font-normal leading-[1.28] text-[#fafafa]")
                title = str(title_tag.text).strip() if hasattr(title_tag, 'text') else 'N/A'

                results.append({
                    'title': title,
                    'url': manga_url,
                    'poster': poster
                })
        except Exception as er:
            logger.error(f"{self.name} Search Issue : {er}")
        
        return results


    async def get_chapters(self, rdata: dict, page: int = 1) -> dict:
        results: dict = rdata.copy()
        try:
            html = await sb.get(results['url'])
            if not html:
                return results
            
            bs = BeautifulSoup(html, 'html.parser')

            # ==========================
            # Poster 
            # ==========================
            poster_tag = bs.select_one('img.h-full.w-full.object-cover.transition-all.duration-200')
            if poster_tag and not results.get('poster') and poster_tag.get('src'):
                results['poster'] = self.url + poster_tag.get('src')
            
            # ==========================
            # Summary
            # ==========================
            summary_tag = bs.select_one(r'div.text-sm.text-white\/60.leading-\[1\.7\].transition-all.duration-500.max-h-\[96px\].overflow-hidden')
            summary     = 'N/A'
            if summary_tag:
                summary = str(summary_tag.text).strip()
            


            details_tag = bs.select(r'div.flex.items-center.justify-between.gap-3.py-2.border-b.border-white\/\[0\.04\]')
            status = "N/A"
            for tag in details_tag:
                spans = tag.find_all('span')
                if len(spans) >= 2:
                    key = spans[0].text.strip()
                    if "origin" == key.lower():
                        status = spans[1].text.strip()
                        break 
            
            # =======================================
            # Status 
            # =======================================
            status = "N/A"
            origin_label = bs.find('span', string=lambda t: t and t.strip().lower() == 'origin')
            if origin_label:
                parent_div = origin_label.find_parent('div', class_=lambda c: c and 'flex' in c if isinstance(c, str) else False)
                if parent_div:
                    try:
                        value_span = parent_div.find_all('span')[-1]
                        status = value_span.text.strip()
                    except Exception:
                        pass
            
            # ====================================
            # Type
            # ====================================
            mtype = "Comic"
            for ctype in ('Manga', 'Manhwa', 'Manhua', 'kr', 'jp', 'cn'):
                origin_label = bs.find('span', string=lambda t: t and t.strip().lower() == ctype.lower())
                mtype = ctype
                break 
            

            # ===================================
            # Alt Titles 
            # ===================================
            alt_titles = "N/A"
            alt_title_tag = bs.select_one(r'div.mt-1\.5.text-xs.text-white\/55.leading-relaxed')
            if alt_title_tag:
                alt_titles = ", ".join([str(i.text).strip() for i in alt_title_tag.find_all('span') if hasattr(i, 'text')])
            
            # ==============================
            # External 
            # ==============================
            external_tag = bs.select_one(r'div.flex.items-center.gap-1\.5')
            e_a_tags = external_tag.find_all('a')

            anilist = "" 
            myanime = ""
            for tag in e_a_tags:
                href = tag.get('href')
                if not href:
                    continue

                if href.startswith('https://anilist'):
                    anilist = href
                
                elif href.startswith('https://www.mangaupdates'):
                    myanime = href
            
            # =======================================
            # Genres 
            # =======================================
            genres_ = bs.select_one(r'div.flex.flex-wrap.justify-center.sm\:justify-start.gap-1\.5')
            genres = "N/A"
            if genres_:
                genres = ", ".join([str(i.text).strip() for i in genres_.find_all('a') if hasattr(i, 'text')])
            
            # ========================================
            # MSG Format
            # ========================================
            results['msg'] = ALL_MSG_FORMAT.format(
                title=results.get('title'),
                status=status,
                genres=genres,
                summary=summary[:100],
                url=results["url"],
                anilist=anilist,
                myanime=myanime,
                alt_title=alt_titles,
                type=mtype,
                year="",
            )
            if len(results["msg"]) > 1024:
                results["msg"] = DEAULT_MSG_FORMAT.format(
                    title=results["title"],
                    status=status,
                    genres=genres,
                    summary=summary[:200],
                    url=results["url"],
                )
            
            # ======================================
            # Chapters 
            # ======================================
            try:
                manga_id = str(results['url']).split('/')[-1]
            except Exception:
                return results
            
            request_url = f"{self.url}/api/manga/{manga_id}/chapters/list"
            html = await sb.get(request_url)
            if not html:
                return results
            
            bs = BeautifulSoup(html, 'html.parser')

            pre_tag = bs.find('pre')
            if not pre_tag:
                return results
            try:
                chapter_datas = json.loads(pre_tag.text)
            except Exception:
                return results
        
            results['chapters'] = []
            for cdata in reversed(chapter_datas):
                if not isinstance(cdata, dict):
                    continue

                # https://mangadot.net/chapter/33240#p=1
                id = cdata.get('id')
                if not id:
                    continue 

                results['chapters'].append({
                    'title': cdata.get('chapter_number'),
                    'url':  f"{self.url}/chapter/{id}",
                    "manga_title": results.get('title'),
                    "poster": results.get('poster'),
                    "group_name": cdata.get('group_name'),
                })
        except Exception as er:
            logger.error(f"{self.name} Get_chapters Issue: {er}")
        
        return results
    
    
    async def get_pictures(self, url: str, data: dict = None) -> list:
        try:
            chapter_id: str = url.split('/')[-1]
        except Exception:
            return []
        
        results = []
        try:
            request_url = f"{self.url}/api/uploads/{chapter_id}/images"
            
            html = await sb.get(request_url)
            if not html:
                return results
            
            bs = BeautifulSoup(html, 'html.parser')

            pre_tag = bs.find('pre')
            if not pre_tag:
                return results
            try:
                images_data = json.loads(pre_tag.text)
            except Exception:
                return results
            
            images =  images_data.get('images', [])
            if not images:
                return results
            
            for img in images:
                if not isinstance(img, dict) and not img.get('url'):
                    continue

                img_url = self.url + img.get('url')
                if img_url in results:
                    continue
                
                results.append(img_url)
            
        except Exception as er:
            logger.error(f"{self.url} get_pictures Issue: {er}")

        return results
