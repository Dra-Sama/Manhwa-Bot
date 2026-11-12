# Code By @V_Sbotmaker (on Telegram)
from .scraper import Scraper

from urllib.parse import quote, unquote

from loguru import logger
from .utitls import ALL_MSG_FORMAT, DEAULT_MSG_FORMAT

import re
import json
import random
import time
import base64
import hashlib

from Crypto.Cipher import AES


def get_worker_url():
    return random.choice([
        "https://nanobridge.nanobridge-proxy.workers.dev/proxy?url="
    ])


HEADERS = {
    "authority": "api.allanime.day",
    "method": "GET",
    "scheme": "https",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "origin": "https://mkissa.to",
    "pragma": "no-cache",
    "referer": "https://mkissa.to/",
    "sec-ch-ua": '"Chromium";v="137", "Not(A)Brand";v="24"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"Android"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36",
}

scraper = Scraper(headers=HEADERS, tor=True)
_NUM_PATTERN = re.compile(r"(\d+)")


class AllMangaWebs:
    # Crypto constants from working code (file 2)
    MASK_HEX = "5ddc3a1ac04f5b0ae3f33bce61f78e4c209bb2a850d9c5d7dad9c2706d99a34d"
    MASK = bytes.fromhex(MASK_HEX)
    BUILD_ID = "11"
    BF = 5 * 60 * 1000  # 5 minutes in milliseconds

    def __init__(self):
        self.url = "https://mkissa.to/"
        self.api_url = "https://api.allanime.day/api"

        self.sf = "alm"
        self.headers = HEADERS
        self.SEARCH_HASH: str = (
            "2d48e19fb67ddcac42fbb885204b6abb0a84f406f15ef83f36de4a66f49f651a"
        )
        self.INFO_HASH: str = (
            "90024aeae9c1a4d3ace0473871dd1902e47fbcb8781ccbcd8ad81f8bb1f313ee"
        )
        self.CHAPTER_HASH: str = (
            "a062f1b131dae3d17c1950fad14640d066b988ac10347ed49cfbe70f5e7f661b"
        )
        self.IMAGE_HASH: str = "466783e19a7540387e34265be906bebbe853857088d45d28af922ab8668ebb31"

    # ============================================
    # CRYPTO METHODS (from working code - file 2)
    # ============================================

    async def _get_crypto_data(self) -> dict:
        """Fetch homepage and extract __aaCrypto epoch and partB"""
        try:
            resp = await scraper.get(self.url, rjson=False, cs=True)
            if not resp or hasattr(resp, 'status_code') and resp.status_code != 200:
                logger.error(f"AllManga: Failed to fetch homepage")
                return None
            text = resp.text if hasattr(resp, 'text') else str(resp)
            m = re.search(r'window\.__aaCrypto\s*=\s*(\{.*?\});', text)
            if not m:
                logger.error("AllManga: Could not find window.__aaCrypto on homepage")
                return None
            return json.loads(m.group(1))
        except Exception as e:
            logger.error(f"AllManga error getting crypto data: {e}")
            return None

    def _decrypt_part_b(self, part_b_b64: str) -> bytes:
        part_b_bytes = base64.b64decode(part_b_b64)
        return bytes(b ^ self.MASK[i % len(self.MASK)] for i, b in enumerate(part_b_bytes))

    def _generate_aa_req(self, query_hash: str, epoch: int, key_bytes: bytes) -> str:
        timestamp = int(time.time() * 1000)
        rounded_ts = (timestamp // self.BF) * self.BF

        iv_msg = f"{epoch}:{self.BUILD_ID}:{query_hash}:{rounded_ts}"
        iv_hash = hashlib.sha256(iv_msg.encode("utf-8")).digest()
        iv = iv_hash[:12]

        payload_dict = {
            "v": 1,
            "ts": rounded_ts,
            "epoch": epoch,
            "buildId": self.BUILD_ID,
            "qh": query_hash
        }
        payload_json = json.dumps(payload_dict, separators=(",", ":"))

        cipher = AES.new(key_bytes, AES.MODE_GCM, nonce=iv)
        ciphertext, tag = cipher.encrypt_and_digest(payload_json.encode("utf-8"))

        token_bytes = bytes([1]) + iv + ciphertext + tag
        return base64.b64encode(token_bytes).decode("utf-8")

    def _decrypt_response_gcm(self, encrypted_b64: str, key_bytes: bytes) -> dict:
        raw = base64.b64decode(encrypted_b64)
        version = raw[0]
        if version != 1:
            raise ValueError("Unsupported encryption version")

        iv = raw[1:13]
        ciphertext_with_tag = raw[13:]

        # AES-GCM tag is the last 16 bytes
        ciphertext = ciphertext_with_tag[:-16]
        tag = ciphertext_with_tag[-16:]

        cipher = AES.new(key_bytes, AES.MODE_GCM, nonce=iv)
        decrypted_bytes = cipher.decrypt_and_verify(ciphertext, tag)
        return json.loads(decrypted_bytes.decode("utf-8"))

    def determine_type(self, country):
        if country == "JP":
            return "Manga"
        if country == "KR":
            return "Manhwa"
        if country == "CN":
            return "Manhua"

        return "Comic"

    async def search(self, query: str = ""):
        global scraper

        payload = {
            "search": {"query": query, "isManga": True},
            "limit": 24,
            "page": 1,
            "translationType": "sub",
            "countryOrigin": "ALL",
        }
        extensions = {"persistedQuery": {"version": 1, "sha256Hash": self.SEARCH_HASH}}
        params = {
            "variables": json.dumps(payload),
            "extensions": json.dumps(extensions),
        }

        results = []
        try:
            data = await scraper.get(self.api_url, rjson=True, params=params, cs=True)
            if not data:
                return []

            edges = data.get("data", {}).get("mangas", {}).get("edges", [])
            for result in edges:
                title = result.get("englishName") or result.get("name") or ""
                manga_id = result.get("_id")
                url = f"https://mkissa.to/manga/{manga_id}"

                thumbnail = result.get("thumbnail", "")
                if thumbnail and not thumbnail.startswith("http"):
                    thumbnail = (
                        "https://agendao.youtube-anime.com/"
                        + thumbnail.lstrip("/")
                    )

                results.append({"title": title, "url": url, "poster": thumbnail})
        except Exception as e:
            logger.exception(f"AllManga Error: {e}")
        finally:
            return results

    @staticmethod
    def complete_sequence_fast(existing_list: list, add_above: int = 1) -> list:
        if not existing_list:
            return []

        nums = [float(x) for x in existing_list]

        max_val = max(nums)
        min_val = min(nums)

        sorted_nums = sorted(nums)
        increment = min(sorted_nums[i+1] - sorted_nums[i] 
                       for i in range(len(sorted_nums)-1) 
                       if sorted_nums[i+1] > sorted_nums[i])

        full_sequence = []
        if add_above > 0:
            for i in range(1, add_above + 1):
                val = max_val + i * increment
                if val.is_integer():
                    full_sequence.append(int(val))
                else:
                    full_sequence.append(val)

        steps = int((max_val - min_val) / increment) + 1
        for i in range(steps):
            val = max_val - i * increment
            if val.is_integer():
                full_sequence.append(int(val))
            else:
                full_sequence.append(val)

        if min_val > 1:
            remaining_steps = int((min_val - 1) / increment)
            for i in range(1, remaining_steps + 1):
                val = min_val - i * increment
                if val.is_integer():
                    full_sequence.append(int(val))
                else:
                    full_sequence.append(val)

        return full_sequence

    async def get_chapters(self, data, page: int = 1) -> dict:
        global scraper
        results = data.copy()

        manga_id = results["url"].rstrip("/").split("/")[-1]

        variables = {
                    "_id": manga_id,
                    "search": {
                            "allowAdult": False,
                            "allowUnknown": False
                    }
        }
        extensions = {
                    "persistedQuery": {
                            "version": 1,
                            "sha256Hash": "d77781dcf964b97aea0be621dbde430e89e200b58526823ee6010dd11c3ca96a"
                    }
        }
        params = {
                    "variables": json.dumps(variables),
                    "extensions": json.dumps(extensions)
        }
        try:
            data = await scraper.get(
                self.api_url, rjson=True,
                cs=True, headers=HEADERS,
                params=params
            )
        except Exception as e:
            return results

        manga = (
            data.get("data", {})
            .get("manga", {})
        )

        if not manga:
            return results

        # -----------------------------------------
        # TITLE
        # -----------------------------------------

        results['title'] = (
            manga.get("englishName")
            or manga.get("name")
            or "Unknown"
        )

        # -----------------------------------------
        # COVER
        # -----------------------------------------

        cover = manga.get("thumbnail", None)

        if cover and not cover.startswith("http"):
            cover = (
                "https://agendao.youtube-anime.com/"
                + cover.lstrip("/")
            )
        results['poster'] = cover

        # -----------------------------------------
        # DESCRIPTION
        # -----------------------------------------

        description = (
            manga.get("description")
            or "No Description Available."
        )

        description = re.sub(
            r"<.*?>",
            "",
            description
        ).strip()

        # -----------------------------------------
        # TYPE
        # -----------------------------------------

        country = manga.get("countryOfOrigin", "")

        if country == "JP":
            mtype = "Manga"
        elif country == "KR":
            mtype = "Manhwa"
        elif country == "CN":
            mtype = "Manhua"
        else:
            mtype = "Comic"

        # -----------------------------------------
        # STATUS
        # -----------------------------------------

        status = manga.get("status") or "Unknown"

        # -----------------------------------------
        # YEAR
        # -----------------------------------------

        aired = manga.get("airedStart", {})
        year = str(aired.get("year", "?"))

        # -----------------------------------------
        # RATING
        # -----------------------------------------

        rating = str(
            manga.get("score")
            or manga.get("averageScore")
            or "?"
        )

        # -----------------------------------------
        # ALT TITLES
        # -----------------------------------------

        raw_alt_titles = manga.get("altNames", [])

        english_alt = []
        other_alt = []

        for t in raw_alt_titles:

            if not isinstance(t, str):
                continue

            t = t.strip()

            if not t:
                continue

            # english-only titles
            if re.fullmatch(r"[A-Za-z0-9\s\-\':,!.?&()]+", t):
                if t not in english_alt and t != results['title']:
                    english_alt.append(t)

            else:
                if t not in other_alt:
                    other_alt.append(t)

        # Prefer english titles
        final_alt = english_alt[:3]

        # fallback to others if no english
        if not final_alt:
            final_alt = other_alt[:3]

        alt_titles = ", ".join(final_alt) if final_alt else "None"

        # -----------------------------------------
        # AUTHORS
        # -----------------------------------------

        authors = manga.get("authors", [])

        if isinstance(authors, list):
            authors = ", ".join(authors[:5])
        else:
            authors = "Unknown"

        # -----------------------------------------
        # GENRES
        # -----------------------------------------

        genres = manga.get("genres", [])

        if isinstance(genres, list):
            genres = ", ".join(genres)
        else:
            genres = ""

        results["msg"] = ALL_MSG_FORMAT.format(
            title=results["title"],
            status=status,
            genres=genres,
            summary=description[:100],
            url=results["url"],
            anilist="",
            myanime="",
            alt_title=alt_titles,
            type=mtype,
            year=year,
        )

        if len(results["msg"]) > 1024:
            results["msg"] = DEAULT_MSG_FORMAT.format(
                title=results["title"],
                status=status,
                genres=genres,
                summary=description[:200],
                url=results["url"],
            )

        # -----------------------------------------
        # CHAPTERS
        # -----------------------------------------

        results["chapters"] = []

        available = (
            manga.get("availableChaptersDetail", {})
            .get("sub", [])
        )

        def safe_float(x):
            try:
                return float(x)
            except:
                return 999999

        available = sorted(
            available,
            key=safe_float
        )

        for ch in available:
            results["chapters"].append(
                {
                    "title": f"Chapter {ch}",
                    "url": f"https://mkissa.to/manga/{manga_id}/chapter-{ch}-sub",
                    "manga_title": results["title"],
                    "poster": results["poster"] if "poster" in results else None,
                }
            )


        return results

    def iter_chapters(self, data, page: int = 1) -> list:
        if "chapters" not in data:
            return []

        return (
            data['chapters'][(page - 1) * 60 : page * 60] if page != 1 else data['chapters']
        )

    @staticmethod
    def parse_api_params(resp_url: str) -> int:
        try:
            filename = resp_url.split("/")[-1]
            match_ = re.search(r"(\d+)", filename)
            return int(match_.group(1)) if match_ else 0
        except Exception:
            return 0

    def filter_list(self, images_url: list) -> list:
        if not images_url:
            return images_url

        first_num = self.parse_api_params(images_url[0])
        last_num = self.parse_api_params(images_url[-1])

        # Single pass to extract base and extension
        first_url = images_url[0]
        slash_idx = first_url.rfind("/")
        spl_link = first_url[:slash_idx]

        filename = first_url[slash_idx + 1:]
        dot_idx = filename.rfind(".")
        file_ext = filename[dot_idx + 1:]
        name_part = filename[:dot_idx]

        num_match = _NUM_PATTERN.search(name_part)
        if num_match:
            prefix = name_part[:num_match.start()]
            suffix = name_part[num_match.end():]
            return [f"{spl_link}/{prefix}{i}{suffix}.{file_ext}" 
                    for i in range(first_num, last_num + 1)]

        # Fallback
        images_list = [f"{spl_link}/{i}.{file_ext}" for i in range(first_num, last_num + 1)]

        return [get_worker_url() + quote(img) for img in images_list]

    async def get_pictures(self, url, data=None):
        """Get chapter images with working crypto from file 2 logic"""
        path = url.rstrip("/").split("mkissa.to/manga/", 1)[-1]
        parts = path.split("/")

        manga_id = parts[0]
        chapter_slug = parts[1] if len(parts) > 1 else ""

        m = re.search(r"chapter-([\d.]+)", chapter_slug)
        if not m:
            return []

        chapter_num = m.group(1)
        trans = "dub" if chapter_slug.endswith("-dub") else "sub"

        # ==========================================
        # NEW CRYPTO LOGIC (from working code)
        # ==========================================

        # 1. Fetch __aaCrypto config and derive key
        crypto_data = await self._get_crypto_data()
        if not crypto_data:
            logger.error("AllManga: Failed to get dynamic crypto data from homepage")
            return []

        epoch = crypto_data["epoch"]
        part_b = crypto_data["partB"]
        key_bytes = self._decrypt_part_b(part_b)

        # 2. Define full raw query (from working code)
        query_str = """query(
  $mangaId: String!
  $translationType: VaildTranslationTypeMangaEnumType!
  $chapterString: String!
  $page: Int
  $limit: Int!
  $offset: Int
) {
  chapterPages(
    mangaId: $mangaId
    translationType: $translationType
    chapterString: $chapterString
    page: $page
    limit: $limit
    offset: $offset
  ) {
    edges {
      streamerId
      sourceName
      chapterString
      pictureUrls
      pictureUrlsProcessed
      pictureUrlHead
      notes
      uploadDate
      sourceUrl
      priority
      versionFix
    }
    pageInfo {
      total
    }
    pageStatus {
      _id
      notes
      thumbnail
      pageId
      showId
      views
      likesCount
      commentCount
      dislikesCount
      reviewCount
      userScoreCount
      userScoreTotalValue
      userScoreAverValue
      viewers {
        firstViewers {
          viewCount
          lastWatchedDate
          user {
            _id
            displayName
            picture
            hideMe
            brief
          }
        }
        recViewers {
          viewCount
          lastWatchedDate
          user {
            _id
            displayName
            picture
            hideMe
            brief
          }
        }
      }
    }
    manga {
      _id
      name
      englishName
      nativeName
      slugTime
      thumbnail
      lastChapterInfo
      lastChapterDate
      chapterCount
      volumes
      type
      season
      score
      airedStart
      availableChapters
      lastUpdateEnd
      countryOfOrigin
      characterCount
      description
      thumbnails
      authors
      genres
      status
      altNames
      averageScore
      rating
      broadcastInterval
      banner
      airedEnd
      magazine
      characters
      availableChaptersDetail
      availableChapters
      prevideos
      nameOnlyString
      relatedShows
      relatedMangas
      isAdult
      countryOfOrigin
      tags
      type
    }
  }
}"""

        query_hash = hashlib.sha256(query_str.encode("utf-8")).hexdigest()
        token = self._generate_aa_req(query_hash, epoch, key_bytes)

        variables = {
            "mangaId": manga_id,
            "translationType": trans,
            "chapterString": chapter_num,
            "limit": 1000,
            "offset": 0
        }

        payload = {
            "query": query_str,
            "variables": variables,
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": query_hash
                },
                "aaReq": token
            }
        }

        api_headers = {
            **HEADERS,
            "Referer": f"{self.url}",
            "Origin": self.url.rstrip("/"),
            "Content-Type": "application/json"
        }

        try:
            data = await scraper.post(
                self.api_url,
                rjson=True,
                cs=True,
                headers=api_headers,
                json=payload
            )

            if not data:
                return []

            if "errors" in data:
                logger.error(f"AllManga GraphQL error: {data['errors']}")
                return []

        except Exception as e:
            logger.error(f"AllManga API error: {e}")
            return []

        # -------------------------------------------------
        # DECRYPT RESPONSE (new working logic)
        # -------------------------------------------------

        encrypted = data.get("data", {}).get("tobeparsed")

        if encrypted:
            try:
                data = self._decrypt_response_gcm(encrypted, key_bytes)
            except Exception as e:
                logger.error(f"AllManga decrypt failed: {e}")
                return []

        chapter_pages = (
            data.get("chapterPages", {})
            .get("edges", [])
        )

        if not chapter_pages:
            return []

        source = chapter_pages[0]
        head = source.get("pictureUrlHead", "")
        picture_urls = source.get("pictureUrls", [])

        images = []
        for img in picture_urls:
            url = img.get("url") if isinstance(img, dict) else img
            if not url:
                continue

            # Handle both relative and absolute URLs
            if url.startswith("http"):
                full = url
            else:
                full = head + url if head else f"https://agendao.youtube-anime.com/{url.lstrip('/')}"

            images.append(full)

        return images
