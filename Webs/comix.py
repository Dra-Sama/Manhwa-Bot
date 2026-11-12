# Code By @V_Sbotmaker (on Telegram)
from .scraper import shared_scraper as scraper
import urllib.parse

from loguru import logger
from .utitls import DEAULT_MSG_FORMAT, ALL_MSG_FORMAT

from bs4 import BeautifulSoup
from Tools.base import TTLCache
import asyncio, json, re


_CHAPTER_CAPTURE_JS = r"""
(() => {
  const rewriteUrl = (u) => {
    if (typeof u === 'string' && u.indexOf('/chapters') !== -1 && /[?&]limit=\d+/.test(u)) {
      return u.replace(/([?&]limit=)\d+/, '$1100');
    }
    return u;
  };

  const originalOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(method, u) {
    arguments[1] = rewriteUrl(u);
    return originalOpen.apply(this, arguments);
  };

  if (window.fetch) {
    const originalFetch = window.fetch.bind(window);
    window.fetch = function(input, init) {
      try {
        if (typeof input === 'string') {
          input = rewriteUrl(input);
        } else if (input && typeof input.url === 'string') {
          const rewritten = rewriteUrl(input.url);
          if (rewritten !== input.url) {
            input = new Request(rewritten, input);
          }
        }
      } catch (e) {}
      return originalFetch(input, init);
    };
  }

  const originalParse = JSON.parse;
  const seen = new Set();
  const items = [];
  let submitted = false;

  const submit = () => {
    if (submitted) return;
    submitted = true;
    window.__COMIX_PAYLOAD__ = JSON.stringify(items);
    window.__COMIX_DONE__ = true;
  };

  JSON.parse = new Proxy(originalParse, {
    apply(target, thisArg, args) {
      const parsed = Reflect.apply(target, thisArg, args);
      try {
        if (!submitted && parsed && parsed.result && Array.isArray(parsed.result.items)
            && parsed.result.items.length > 0 && parsed.result.items[0]
            && parsed.result.items[0].id !== undefined
            && parsed.result.items[0].mangaId !== undefined) {
          const meta = parsed.result.meta || parsed.result.pagination || {};
          const page = meta.page || 1;
          if (!seen.has(page)) {
            seen.add(page);
            for (const it of parsed.result.items) items.push(it);
            if (meta.hasNext) {
              let tries = 0;
              const iv = setInterval(function () {
                const btn = document.querySelector('.mchap-foot button[aria-label*=Next]');
                if (btn && !btn.disabled) {
                  btn.click();
                  clearInterval(iv);
                } else if (++tries > 50) {
                  clearInterval(iv);
                  submit();
                }
              }, 100);
            } else {
              submit();
            }
          }
        }
      } catch (e) {}
      return parsed;
    }
  });
})();
"""

_IMAGE_CAPTURE_JS = r"""
(() => {
  const originalParse = JSON.parse;
  JSON.parse = new Proxy(originalParse, {
    apply(target, thisArg, args) {
      const parsed = Reflect.apply(target, thisArg, args);
      try {
        if (parsed && parsed.result && parsed.result.pages) {
          window.__COMIX_PAYLOAD__ = JSON.stringify(parsed.result.pages);
          window.__COMIX_DONE__ = true;
        }
      } catch (e) {}
      return parsed;
    }
  });
})();
"""




# ── Scraper ──
class ComixWebs:
    __slots__ = (
        'url', 'api_url', 
        'sf', '_cache',
        '_lock', 'dlock',
        'broswer_kwargs', 'headers',
    )
    def __init__(self):
        self.url = "https://comix.to"
        self.api_url = "https://comix.to/api/v1/"

        self.sf: str                        = "cx"
        self._cache                         = TTLCache( default_timeout=5*60 ) # 5 mins 
        self._lock: dict[str, asyncio.Lock] = {}
        self.dlock: asyncio.Lock            = asyncio.Lock()

        self.broswer_kwargs: dict           = {
            "tor": True,
        }
        self.headers = {
            "Accept": "application/json",
            "Referer": "https://comix.to/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        }

    async def search(self, query: str = ""):
        url = f"{self.api_url}manga?keyword={urllib.parse.quote_plus(query)}&order[relevance]=desc&limit=20&page=1"
        data = await scraper.get(
            url, cs=True,
            rjson=True,
            headers=self.headers,
        )

        if not data:
            return []

        result = data.get("result", {})
        items = result.get("items", []) if isinstance(result, dict) else []

        results = []
        for item in items:
            hid = item.get("hid") or item.get("hash_id") or ""
            slug = item.get("slug") or hid
            title = item.get("title", "")
            poster = item.get("poster", {})
            poster_url = poster.get("medium", poster.get("small", "")) if isinstance(poster, dict) else ""

            url_path = item.get("url") or f"/title/{hid}"
            if not url_path.startswith("http"):
                url_path = f"https://comix.to{url_path if url_path.startswith('/') else '/'+url_path}"

            results.append({
                "url": url_path,
                "poster": poster_url,
                "title": title,
                "hash_id": hid,
                "slug": slug,
            })

        return results

    @staticmethod
    def get_infomation(manga_data: dict, data: dict) -> None:
        data['title'] = manga_data.get('title')
        altTitles = manga_data.get('altTitles', [])
        altTitles = ", ".join(altTitles)

        # --- Cover ---
        if "poster" not in data or not data.get('poster'):
            data['poster'] = data.get('poster', {}).get('medium')

        # --- Summary ---
        synopsis = data.get('synopsis', '')
        summary = (
            synopsis.
            replace('\n', '')
            .replace('<br>', '')
        )

        # --- Genres, Themes, etc ---
        genres = data.get('genres', [])
        genres = [
            i.get('title') 
            for i in genres 
            if isinstance(i, dict)
        ]
        genres = ", ".join(genres)

        status = data.get('status')
        mtype = data.get('type')
        
        links = data.get('links', {})
        mal_url = links.get('mal')
        al_url = links.get('al')

        # --- Year & Status
        year = data.get('year')

        data["msg"] = ALL_MSG_FORMAT.format(
            title=data["title"],
            alt_title=altTitles,
            type=mtype,
            status=status,
            genres=genres,
            year=year,
            summary=summary[:200],
            url=data["url"],
            anilist=mal_url,
            myanime=al_url,
        )
        if len(data["msg"]) > 1024:
            data["msg"] = DEAULT_MSG_FORMAT.format(
                title=data["title"],
                status=status,
                genres=genres,
                summary=summary[:200],
                url=data["url"],
            )
    
    def get_lock(self, url: str) -> asyncio.Lock:
        if url not in self._lock:
            self._lock[url] = asyncio.Lock()
        return self._lock[url]
    
    def extract_json(self, jsos_data: dict):
        queries = jsos_data.get("queries")
        if not isinstance(queries, dict):
            return 
        
        for key, value in queries.items():
            if isinstance(key, str) and '"detail"' in key and isinstance(value, dict):
                return value
        
        return None


    async def work_chapters(self, manga_url : str, results: dict):
        try:
            async with scraper.get_tab(manga_url, broswer_kwargs=self.broswer_kwargs) as page:
                if not page:
                    return 
                
                await page.add_init_script(_CHAPTER_CAPTURE_JS)
                await page.goto(manga_url, wait_until="domcontentloaded", timeout=30000)

                script_text = await page.locator("#initial-data").text_content()
                if not script_text:
                    logger.error(f"{manga_url} : initial-data Json not Found ")
                    return results
                
                manga_data = self.extract_json(json.loads(script_text))
                if not manga_data:
                    logger.error("manga_data didnot found")
                    return results

                manga_id = manga_data.get("id")
                if not manga_id:
                    logger.error(f"{manga_id = } ")
                    return results
                
                hid = manga_data.get("hid")
                if not hid:
                    return results
                
                html = manga_data.get("synopsisHtml") or manga_data.get("synopsis") or ""
                if not html:
                    return results
                
                await asyncio.to_thread(lambda: self.get_infomation(manga_data, results))

                try:
                    await page.wait_for_function("window.__COMIX_DONE__ === true", timeout=40000)
                except Exception:
                    await page.wait_for_timeout(3000)
                
                payload = await page.evaluate("window.__COMIX_PAYLOAD__ || '[]'")

                try:
                    chapters = json.loads(payload)
                except Exception:
                    chapters = []
                
                
                if not isinstance(chapters, list):
                    return results
                
                results['chapters'] = chapters
                return results
                
        except Exception as er:
            logger.exception(er)
        
        return results
        
    async def get_chapters(self, data, page: int = 1) -> dict:
        results = data.copy()
        manga_url = results.get('url')
        if not manga_url:
            return results
        
        if manga_url in self._cache:
            return self._cache[manga_url] 
        
        try:
            lock_ = self.get_lock(manga_url)
            async with lock_:
                if manga_url in self._cache:
                    return self._cache[manga_url] 
                
                r = await self.work_chapters(manga_url=manga_url, results=results)
                self._cache[manga_url] = r
                return r
        except Exception as er:
            logger.exception(er)
        
        return results

            
        

    def iter_chapters(self, data, page=1):
        if not data or "chapters" not in data:
            return []
        
        try:
            slug = data.get('url')
            slug = slug.split("/")[-1]
        except Exception:
            slug = None 
        
       
        chapters_list = []
        for ch in data["chapters"]:
            url = ch.get("url")
            ch_num = str(ch.get("number", "")).removesuffix(".0")

            if not url and slug:
                ch_id = ch.get("id") or ch.get("chapter_id")
                if not ch_id:
                    continue

                url = f"title/{slug}/{ch_id}-chapter-{ch_num}"
            
            if not url:
                continue
        
            group = ch.get("group") or ch.get("scanlation_group")
            group_name = group.get("name", "") if isinstance(group, dict) else None
            if not group_name and (ch.get("isOfficial") or ch.get("is_official")):
                group_name = "Official"

            chapters_list.append({
                "title": ch_num,
                "url": f"{url if url.startswith('https://comix.to/') else 'https://comix.to/' + url }",
                "manga_title": data.get("title"),
                "poster": data.get("poster"),
                "group_name": group_name,
            })

        return chapters_list[(page - 1) * 40:page * 40] if page != 1 else chapters_list
    
    async def pic_worker(self, url) -> list:
        try:
            async with scraper.get_tab(
                url,
                broswer_kwargs=self.broswer_kwargs
            ) as page:
                if not page:
                    logger.error('Not Page for pic_worker comix')
                    return []
                
                await page.add_init_script(_IMAGE_CAPTURE_JS)
                await page.goto(
                    url,
                    wait_until="domcontentloaded", 
                    timeout=30000
                )
                try:
                    await page.wait_for_function("window.__COMIX_DONE__ === true", timeout=40000)
                except Exception:
                    await page.wait_for_timeout(3000)

                payload = await page.evaluate("window.__COMIX_PAYLOAD__ || null")
                if not payload:
                    return []

                logger.debug(f"comix image payload bytes: {len(payload)}")

                data = json.loads(payload)
                if not isinstance(data, dict):
                    return []
                
                pages = data.get("items") or []
                base_url = data.get("baseUrl") or ""
                scrambled_base = re.sub(r"/i/(?=[bh])", "/si/", base_url) if base_url else base_url

                images_url = []
                for page_item in pages:
                    if not isinstance(page_item, dict):
                        continue

                    raw_url = page_item.get("url")
                    if not raw_url:
                        continue

                    is_scrambled = page_item.get("s") == 1

                    effective_base = (scrambled_base if is_scrambled else base_url) or ""

                    if effective_base and not raw_url.startswith("http"):
                        url = effective_base.rstrip("/") + "/" + raw_url.lstrip("/")
                    else:
                        url = raw_url

                   
                    images_url.append(url)

               
                return images_url
            
        except Exception as er:
            logger.exception(er)
        
        return []
                
    async def get_pictures(self, url, data=None):
        if url in self._cache:
            return self._cache[url]

        _lock = self.get_lock(url)
        async with _lock:
            if url not in self._cache:
                self._cache[url] = await self.pic_worker(url)

            return self._cache[url]
            
            

            
