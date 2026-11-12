# Code By @V_Sbotmaker (on Telegram)

from __future__ import annotations


PLAYWRIGHT_AVAILABLE = False

try:
    from playwright.async_api import Browser, Playwright, async_playwright
    PLAYWRIGHT_AVAILABLE = True
except Exception:  # playwright is optional
    Playwright = Browser = async_playwright = None  # type: ignore




SELENIUMBASE_AVAILABLE = False
try:
    from seleniumbase import cdp_driver # async mode
    SELENIUMBASE_AVAILABLE = True
except Exception:
    pass

try:
    import psutil
    _PSUTIL = True
except Exception:
    _PSUTIL = False


from loguru import logger

import sys, os , signal , gc
import base64
import json

import subprocess

import asyncio
import functools
import random
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress
from json import JSONDecodeError
from typing import Optional

import tldextract
from cloudscraper import create_scraper
from curl_cffi import requests as cffi_requests
from curl_cffi.requests.exceptions import (
    ConnectionError as CffiConnectionError,
    HTTPError as CffiHTTPError,
    ProxyError as CffiProxyError,
    Timeout as CffiTimeout,
)

from requests.exceptions import (
    ConnectionError as ReqConnectionError,
    HTTPError as ReqHTTPError,
    ProxyError as ReqProxyError,
    Timeout as ReqTimeout,
)
_IS_WINDOWS = sys.platform == "win32"
_IS_LINUX   = sys.platform == "linux"




if not _PSUTIL and _IS_WINDOWS:
    logger.warning("[CF] psutil not installed — Chrome cleanup will be less precise on Windows.")


# ──────────────────────────────────────────────────────────────────────────────
# Resource auto-scaling 
# ──────────────────────────────────────────────────────────────────────────────
def _env_int(name: str, default: int) -> int:
    try:
        v = int(os.environ.get(name, ""))
        return v if v > 0 else default
    except (TypeError, ValueError):
        return default


_CPU = os.cpu_count() or 2
_IS_HF = bool(os.environ.get("SPACE_ID") or os.environ.get("SPACE_HOST"))
_LOW_RESOURCE = _IS_HF or _CPU <= 2

THREAD_WORKERS    = _env_int("SCRAPER_THREAD_WORKERS", min(8 * _CPU, 64))
DOMAIN_LIMIT      = _env_int("SCRAPER_DOMAIN_LIMIT", max(2, min(2 * _CPU, 12)))


BROWSER_CONCURRENCY = _env_int("SCRAPER_BROWSER_CONCURRENCY", 2 if _LOW_RESOURCE else min(3, max(2, _CPU // 2)))
PW_MAX_CONTEXTS     = _env_int("SCRAPER_PW_CONTEXTS", 2 if _LOW_RESOURCE else max(2, _CPU))

# ── Browser tab pool (sb.get) ──────────────────────────────────────────────────
TAB_BASE    = _env_int("SCRAPER_TAB_BASE", 3)
TAB_MAX     = _env_int("SCRAPER_TAB_MAX", 10)
PER_TAB_RAM = _env_int("SCRAPER_PER_TAB_RAM_MB", 350) * 1024 * 1024


def _ram_headroom() -> bool:
    """True when there is enough free RAM to open one more tab past TAB_BASE."""
    if not _PSUTIL:
        return False  
    
    try:
        return psutil.virtual_memory().available > PER_TAB_RAM
    except Exception:
        return False


DEFAULT_TIMEOUT = 80
MAX_BACKOFF = 16
_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(
                    max_workers=THREAD_WORKERS, thread_name_prefix="scraper"
                )
    return _executor


async def _to_thread(fn, *args, **kwargs):
    """Run a blocking callable on the shared bounded pool (loop-agnostic)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _get_executor(), functools.partial(fn, *args, **kwargs)
    )


TOR_HOST, TOR_PORT = "127.0.0.1", 9050
TOR_PROXIES = {
    "http": f"socks5h://{TOR_HOST}:{TOR_PORT}",
    "https": f"socks5h://{TOR_HOST}:{TOR_PORT}",
}

RETRYABLE_ERRORS = (
    CffiConnectionError, CffiProxyError, CffiTimeout,
    ReqConnectionError, ReqProxyError, ReqTimeout,
)
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


UA_POOL = [
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "sec_ch_ua_mobile": "?0",
        "sec_ch_ua_platform": '"Windows"',
    },
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "sec_ch_ua_mobile": "?0",
        "sec_ch_ua_platform": '"macOS"',
    },
    {
        "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "sec_ch_ua_mobile": "?0",
        "sec_ch_ua_platform": '"Linux"',
    },
    {
        "ua": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.53 Mobile Safari/537.36",
        "sec_ch_ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "sec_ch_ua_mobile": "?1",
        "sec_ch_ua_platform": '"Android"',
    },
    {
        "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/125.0.6422.80 Mobile/15E148 Safari/604.1",
        "sec_ch_ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "sec_ch_ua_mobile": "?1",
        "sec_ch_ua_platform": '"iOS"',
    },
]


_NAV_PLATFORM = {'"Windows"': "Win32", '"macOS"': "MacIntel", '"Linux"': "Linux x86_64"}
_HOST_CH_PLATFORM = '"Windows"' if _IS_WINDOWS else ('"Linux"' if _IS_LINUX else '"macOS"')
_DESKTOP_UAS = [
    u for u in UA_POOL
    if u["sec_ch_ua_mobile"] == "?0" and u["sec_ch_ua_platform"] == _HOST_CH_PLATFORM
] or [u for u in UA_POOL if u["sec_ch_ua_mobile"] == "?0"]


def pick_browser_ua() -> dict:
    u = random.choice(_DESKTOP_UAS)
    return {"ua": u["ua"], "platform": _NAV_PLATFORM.get(u["sec_ch_ua_platform"], "Win32")}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def get_domain(url: str) -> str:
    e = tldextract.extract(url)
    return f"{e.domain}.{e.suffix}" if e.suffix else e.domain


def get_headers(url: str, extra: Optional[dict] = None) -> dict:
    domain = get_domain(url)
    chosen = random.choice(UA_POOL)
    h = {
        "User-Agent": chosen["ua"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": chosen["sec_ch_ua"],
        "Sec-Ch-Ua-Mobile": chosen["sec_ch_ua_mobile"],
        "Sec-Ch-Ua-Platform": chosen["sec_ch_ua_platform"],
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "Referer": f"https://{domain}/",
    }
    if extra:
        h.update(extra)
    
    return h


def is_tor_running(tor: bool, timeout: float = 3.0) -> bool:
    """Synchronous socket probe of the Tor SOCKS port — no HTTP overhead."""
    if not tor:
        return False
    
    try:
        with socket.create_connection((TOR_HOST, TOR_PORT), timeout=timeout):
            return True
    except OSError:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Session
# ──────────────────────────────────────────────────────────────────────────────
_thread_local = threading.local()


def _get_cffi_session() -> cffi_requests.Session:
    sess = getattr(_thread_local, "cffi_session", None)
    if sess is None:
        sess = _thread_local.cffi_session = cffi_requests.Session(impersonate="chrome")
    return sess


def _get_cs_session():
    sess = getattr(_thread_local, "cs_session", None)
    if sess is None:
        try:
            sess = _thread_local.cs_session = create_scraper(browser="chrome", turbo_mode=True)
        except Exception:
            sess = _thread_local.cs_session = create_scraper(browser="chrome")
    return sess


def _close_thread_sessions() -> None:
    for attr in ("cffi_session", "cs_session"):
        sess = getattr(_thread_local, attr, None)
        if sess is not None:
            try:
                sess.close()
            except Exception:
                pass

            setattr(_thread_local, attr, None)


# ──────────────────────────────────────────────────────────────────────────────
# Playwright pool
# ──────────────────────────────────────────────────────────────────────────────
class PlaywrightPool:
    def __init__(
        self,
        max_contexts: int = PW_MAX_CONTEXTS,
        domain_limit: int = 3,
        headless: bool = True,
        tor: bool = False,
    ):
        self.headless = headless
        self.tor = tor
        self.domain_limit = domain_limit

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

        self._lock = asyncio.Lock()
        self._global_sem = asyncio.Semaphore(max_contexts)
        self._domain_sem: dict[str, asyncio.Semaphore] = {}

    @staticmethod
    def _context_with_ua(context_kwargs: Optional[dict]) -> dict:
        """Apply a random UA + matching client hints, unless the caller overrode them."""
        ck = dict(context_kwargs or {})
        chosen = random.choice(UA_POOL)
        ck.setdefault("user_agent", chosen["ua"])
        ck.setdefault("is_mobile", chosen["sec_ch_ua_mobile"] == "?1")
        headers = {
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": chosen["sec_ch_ua"],
            "Sec-Ch-Ua-Mobile": chosen["sec_ch_ua_mobile"],
            "Sec-Ch-Ua-Platform": chosen["sec_ch_ua_platform"],
        }
        headers.update(ck.get("extra_http_headers") or {})
        ck["extra_http_headers"] = headers

        return ck

    def _get_domain_sem(self, domain: str) -> asyncio.Semaphore:
        sem = self._domain_sem.get(domain)
        if sem is None:
            sem = self._domain_sem[domain] = asyncio.Semaphore(self.domain_limit)
        
        return sem

    async def _start_playwright(self) -> bool:
        if self._playwright is not None:
            return True
    
        if async_playwright is None:
            logger.error("Playwright is not installed.")
            return False
        
        self._playwright = await async_playwright().start()
        return True

    async def _launch_browser(
            self, broswer_kwargs: Optional[dict] = None
        ) -> Optional[Browser]:

        opts = dict(broswer_kwargs or {})  # copy: never mutate the caller's dict

        tor = opts.pop("tor", None)
        tor = self.tor if tor is None else tor
        tor = is_tor_running(tor)

        headless = opts.pop("headless", None)
        headless = self.headless if headless is None else headless

        proxy = {"server": f"socks5://{TOR_HOST}:{TOR_PORT}"} if tor else None

        return await self._playwright.chromium.launch(
            headless=headless,
            proxy=proxy,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-zygote",
            ],
            **opts,
        )

    async def _ensure_browser(
            self, broswer_kwargs: Optional[dict] = None
        ) -> Optional[Browser]:
        """Return the single shared browser, launching it on first use.

        Domains are isolated by *context* (created per tab in get_tab/render),
        not by separate browser processes — one Chrome (~300 MB) plus cheap
        contexts (~10 MB each) instead of a whole Chrome per domain.
        ``broswer_kwargs`` only takes effect on the first (launching) call.
        """
        async with self._lock:
            if self._browser is not None:
                return self._browser

            try:
                if not await self._start_playwright():
                    return None

                self._browser = await self._launch_browser(broswer_kwargs)
                return self._browser
            except Exception as e:
                logger.exception(f"Failed to launch Playwright browser: {e}")
                await self._close_locked()
                return None

    async def render(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: int = 60_000,
        context_kwargs: Optional[dict] = None,
    ) -> Optional[str]:
        """Fetch fully-rendered HTML for JS-heavy pages. Returns None on failure."""
        domain = get_domain(url)
        ctx_kwargs = self._context_with_ua(context_kwargs)
        async with self._global_sem, self._get_domain_sem(domain):
            browser = await self._ensure_browser()
            if browser is None:
                return None
            
            context = None
            try:
                context = await browser.new_context(**ctx_kwargs)
                page = await context.new_page()

                await page.goto(url, wait_until=wait_until, timeout=timeout)
                return await page.content()
            except Exception as e:
                logger.error(f"Playwright render failed for {url}: {e}")
                return None
            
            finally:
                if context is not None:
                    try:
                        await context.close()
                    except Exception:
                        pass

    @asynccontextmanager
    async def get_tab(
        self,
        url: str,
        context_kwargs: Optional[dict] = None,
        broswer_kwargs: Optional[dict] = None,
    ):
        """
        Yield a Playwright page (tab) for the URL's domain. All domains share a
        single browser; each tab gets its own context (random UA) for isolation,
        closed on exit. Yields None if Playwright is unavailable or the browser
        fails to launch.
        """
        domain = get_domain(url)
        ctx_kwargs = self._context_with_ua(context_kwargs)
        async with self._global_sem, self._get_domain_sem(domain):
            browser = await self._ensure_browser(broswer_kwargs or None)
            if browser is None:
                yield None
                return
            
            context = None
            try:
                context = await browser.new_context(**ctx_kwargs)
                page = await context.new_page()
                yield page
            finally:
                if context is not None:
                    try:
                        await context.close()
                    except Exception:
                        pass

    async def _close_locked(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass

            self._browser = None
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        
            self._playwright = None

    async def close(self) -> None:
        async with self._lock:
            await self._close_locked()

# =============================================
# Driver Pool 
# =============================================
_DISPLAY_BASE    = 99
_DISPLAY_MAX     = 200
_display_counter = 0
_display_lock    = threading.Lock()

def _next_display() -> int:
    global _display_counter
    with _display_lock:
        _display_counter = (_display_counter + 1) % (_DISPLAY_MAX - _DISPLAY_BASE)
        return _DISPLAY_BASE + _display_counter


VIRTUAL_DISPLAY = None

def start_virtual_display():
    global VIRTUAL_DISPLAY
    import sys
    if not sys.platform.startswith("win") and VIRTUAL_DISPLAY is None:
        try:
            from sbvirtualdisplay import Display
            print("[CFB] Starting virtual display (Xvfb) on Linux...")
            VIRTUAL_DISPLAY = Display(visible=True, size=(1366, 768), backend="xvfb", use_xauth=True)
            VIRTUAL_DISPLAY.start()
            print("[CFB] Virtual display started successfully")
        except Exception as e:
            print(f"[CFB] Failed to start virtual display (Xvfb): {e}")
            print("[CFB] WARNING: Bypassing Turnstile captcha might fail if Xvfb is not installed. Run 'sudo apt-get install xvfb' if needed.")

# Initialize virtual display on import if running on Linux
start_virtual_display()

linux_args = [
            "--disable-dev-shm-usage", "--no-sandbox",
            "--disable-setuid-sandbox", "--disable-gpu-sandbox",
]
windows_args = ["--disable-features=RendererCodeIntegrity"]
        
chromium_args = [
            "--disable-gpu", "--disable-software-rasterizer",
            "--disable-background-networking", "--disable-extensions",
            "--disable-default-apps", "--disable-sync", "--disable-translate",
            "--metrics-recording-only", "--no-first-run", "--mute-audio",
            "--hide-scrollbars", "--window-size=1920,1080", "--window-position=0,0",
            *(linux_args if _IS_LINUX else windows_args),
 ]

_LAUNCH_GAP = 0.4
_TAB_REGISTER_TRIES = 60   # × 0.1s  ≈ 6s
_TAB_READY_TRIES    = 60   # × 0.15s ≈ 9s

class BrowserHub:
    __slots__ = ("driver", "drv_pid", "pgid", "tor", "_launch_lock", "_open_lock", "_gate", "_active")

    def __init__(self):
        self.driver = None
        self.drv_pid: int = 0
        self.pgid: int = 0
        self.tor: bool = False
        self._launch_lock = asyncio.Lock()   # only one Chrome launch at a time
        self._open_lock = asyncio.Lock()     # serialize the quick create-tab step
        self._gate = asyncio.Condition()
        self._active = 0                      # tabs currently open

    # ── Process cleaners ──────────────────────────────────────────────────────
    def _kill_tree_windows(self, pid: int) -> None:
        if not pid:
            return
        if not _PSUTIL:
            try:
                subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"], capture_output=True, timeout=5)
            except Exception:
                pass
            return
        try:
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                with suppress(psutil.NoSuchProcess):
                    child.kill()
            parent.kill()
        except psutil.NoSuchProcess:
            pass

    def _kill_pgid_linux(self, pgid: int) -> None:
        if not pgid or pgid <= 1:
            return
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def _kill(self) -> None:
        if _IS_LINUX and self.pgid and self.pgid > 1:
            self._kill_pgid_linux(self.pgid)
        elif _IS_WINDOWS and self.drv_pid:
            self._kill_tree_windows(self.drv_pid)
        self.driver = None
        self.pgid = 0
        self.drv_pid = 0

    # ── Launch / relaunch ─────────────────────────────────────────────────────
    async def _launch(self, tor: bool) -> None:
        headless = not _IS_WINDOWS and (VIRTUAL_DISPLAY is None)
        use_tor = is_tor_running(tor)

        logger.info("[CF] Launching browser")

        self.driver = await cdp_driver.start_async(
            uc=True, headless=headless,
            incognito=True, no_sandbox=True,
            chromium_args=chromium_args,
            proxy="socks5://127.0.0.1:9050" if use_tor else None,
        )
        self.drv_pid = self.driver._process_pid
        self.tor = use_tor
        if _IS_LINUX:
            self.pgid = os.getpgid(self.drv_pid)

        logger.info(f"[CF] Browser launched (pid={self.drv_pid})")

    async def _ensure_browser(self, tor: bool):
        """Return a live Chrome, launching (or relaunching) it if needed."""
        if not SELENIUMBASE_AVAILABLE:
            logger.error("[CF] SeleniumBase is missing. Cannot use browser fallback.")
            return None

        async with self._launch_lock:
            alive = False
            if self.driver is not None:
                alive = bool(self.drv_pid) and psutil.pid_exists(self.drv_pid)

            want_tor = is_tor_running(tor)
            if alive and (self.tor == want_tor or self._active > 0):
                return self.driver

            if self.driver is not None:
                self._kill()

            try:
                await self._launch(tor)
                await asyncio.sleep(_LAUNCH_GAP)
                return self.driver
            except Exception as er:
                logger.exception(er)
                self._kill()
                return None

    # ── RAM-aware tab gate ────────────────────────────────────────────────────
    async def _acquire_slot(self) -> None:
        async with self._gate:
            while not (self._active < TAB_BASE
                       or (self._active < TAB_MAX and _ram_headroom())):
                await self._gate.wait()
            self._active += 1

    async def _release_slot(self) -> None:
        async with self._gate:
            self._active -= 1
            self._gate.notify(1)

    async def _open_tab(self, browser, url: str):
        """Open a fresh page tab and navigate it to ``url``.

        cdp_driver's ``Browser.get(new_tab=True)`` is unreliable on this build:
        ``connection.send(create_target(...))`` returns ``None`` and the follow-up
        ``next(filter(...))`` raises ``StopIteration``. seleniumbase's own
        ``open_new_tab`` (core/sb_cdp.py) works around it by creating the target,
        listing targets, finding the new one, and rebuilding the ``Tab`` from an
        existing tab's websocket URL. We mirror that here.

        Only the quick create-and-register step is serialized (so concurrent opens
        can't confuse the "which target is new" diff); navigation and page work
        run in parallel afterwards.
        """
        # import mycdp as cdp  # vendored by seleniumbase
        # from seleniumbase.undetected.cdp_driver import tab as cdp_tab

        if url and ":" not in url:
            url = "https://" + url

        async with self._open_lock:
            conn = browser.main_tab  # a page connection (browser.connection returns None here)

            before = await conn.send(cdp.target.get_targets())
            before_ids = {str(t.target_id) for t in before}

            target_id = None
            with suppress(Exception):
                target_id = await conn.send(cdp.target.create_target("about:blank"))

            tid = str(target_id) if target_id else None

            found = None
            for _ in range(_TAB_REGISTER_TRIES):
                targets = await conn.send(cdp.target.get_targets())
                if tid:
                    found = next((t for t in targets if str(t.target_id) == tid), None)
                if found is None:
                    fresh = [
                        t for t in targets
                        if str(t.target_id) not in before_ids
                        and getattr(t, "type_", None) == "page"
                    ]
                    if fresh:
                        found = fresh[-1]
                if found is not None:
                    break
                await asyncio.sleep(0.1)

            if found is None:
                raise RuntimeError(f"new tab for {url} never registered")

            tab_url = browser.tabs[0].websocket_url
            new_tab_url = tab_url.split("/page/")[0] + "/page/" + str(found.target_id)
            page = cdp_tab.Tab(new_tab_url, found, browser)
            page.browser = browser
            browser.targets.append(page)

        # ── Navigate the new tab (outside the lock → parallel) ──────────────
        with suppress(Exception):
            await page.send(cdp.network.enable())
        

        if os.environ.get("CF_ROTATE_UA") == "1":
            ua = pick_browser_ua()
            with suppress(Exception):
                await page.set_user_agent(
                    user_agent=ua["ua"],
                    accept_language="en-US,en;q=0.9",
                    platform=ua["platform"],
                )
            
        await page.send(cdp.page.navigate(url=url))

        for _ in range(_TAB_READY_TRIES):
            try:
                if await page.evaluate("document.readyState") == "complete":
                    break
            except Exception:
                pass
            await asyncio.sleep(0.15)

        return page

    @asynccontextmanager
    async def tab(self, url: str, tor: bool = False):
        """Yield a fresh tab navigated to ``url``; close it on exit.

        Yields None if Chrome is unavailable or fails to launch. The slot is held
        for the whole lifetime of the tab so the RAM gate reflects real usage.
        """
        await self._acquire_slot()
        page = None
        try:
            browser = await self._ensure_browser(tor)
            if browser is None:
                yield None
                return
            
            page = await self._open_tab(browser, url)
            yield page
        finally:
            if page is not None:
                with suppress(Exception):
                    await page.close()
                
                with suppress(Exception):
                    page.browser.targets.remove(page)
                
            await self._release_slot()

    async def aclose(self) -> None:
        """Kill the browser process tree. Call at shutdown."""
        async with self._launch_lock:
            self._kill()


browser_hub = BrowserHub()


# ══════════════════════════════════════════════════════════════════════════════
# Cookie store
# ══════════════════════════════════════════════════════════════════════════════
import time
CF_COOKIE_TTL = 2 * 60

class _CookieStore:
    __slots__ = ("_store", "_lock")

    def __init__(self) -> None:
        self._store: dict[str, tuple[list, float]] = {}
        self._lock  = threading.Lock()

    def get(self, domain: str) -> Optional[list]:
        with self._lock:
            entry = self._store.get(domain)
            if entry is None:
                return None
            
            cookies, ts = entry

            if time.monotonic() - ts > CF_COOKIE_TTL:
                self._store.pop(domain, None)
                return None
            
            return cookies

    def set(self, domain: str, cookies: list) -> None:
        with self._lock:
            self._store[domain] = (cookies, time.monotonic())

CF_COOKIES = _CookieStore()

# =====================================================
# SelemuinManager (SM)
# =====================================================

class SM:
    __slots__ = ('_solve_locks')
    def __init__(self):
        self._solve_locks: dict[str, asyncio.Lock] = {}

    def _domain_solve_lock(self, domain: str) -> asyncio.Lock:
        lock = self._solve_locks.get(domain)
        if lock is None:
            lock = self._solve_locks[domain] = asyncio.Lock()
        return lock

    async def _cf_state(self, page) -> str:
        try:
            title =( await page.get_title()).lower()
            if "just a moment" not in title:
                return "passed"
            
            html = ( await page.get_page_source() ).lower()
            if "challenges.cloudflare.com" in html:
                return "turnstile"
            
            if "checking your browser" in html:
                return "js" 
            
            return "blocked"
        except Exception as er :
            logger.exception(er)
            return "passed" 
    

    async def _wait_for_loads(self, page, max_wait: float = 9.0):
        try:
            deadline = time.monotonic() + max_wait
            while time.monotonic() < deadline:
                if await page.evaluate("document.readyState") == "complete":
                    break
            
            await asyncio.sleep(0.15)
            prev, stable = 0, 0
            
            while time.monotonic() < deadline:
                length = len(await page.get_page_source())
                stable = stable + 1 if length == prev else 0
                if stable >= 3:
                    break
                prev = length
                await asyncio.sleep(0.25)
        except Exception as er:
            logger.exception(er)
        
        return None 
    
    async def human_behaviour(self, page):
        try:
            await page.evaluate("window.focus();")
            x = random.randint(100, 700)
            y = random.randint(100, 500)
            
            await page.evaluate(f"""(() => {{
let cx = window._mx || 0, cy = window._my || 0;
let steps = 15;
let step = 0;
function move() {{
                if (step >= steps) {{ window._mx = {x}; window._my = {y}; return; }}
                let t = step / steps;
                let nx = cx + ({x} - cx) * t + (Math.random() - 0.5) * 5;
                let ny = cy + ({y} - cy) * t + (Math.random() - 0.5) * 5;
                document.dispatchEvent(new MouseEvent('mousemove', {{
                    clientX: nx, clientY: ny, bubbles: true
                }}));
                step++;
                setTimeout(move, 10 + Math.random() * 20);
}}
move();
}})();""")
            await asyncio.sleep(0.3)
            
            await page.evaluate("""
document.body.dispatchEvent(new MouseEvent('click', {
                clientX: Math.random() * 500 + 100,
                clientY: Math.random() * 300 + 100,
                bubbles: true
}));""")
            await asyncio.sleep(0.2)
            
            # Move mouse away (like human losing interest)
            x2 = random.randint(400, 800)
            y2 = random.randint(300, 600)
            await page.evaluate(f"""(() => {{
let cx = {x}, cy = {y};
let steps = 20;
let step = 0;
function moveAway() {{
                if (step >= steps) {{ window._mx = {x2}; window._my = {y2}; return; }}
                let t = step / steps;
                let nx = cx + ({x2} - cx) * t + (Math.random() - 0.5) * 8;
                let ny = cy + ({y2} - cy) * t + (Math.random() - 0.5) * 8;
                document.dispatchEvent(new MouseEvent('mousemove', {{
                    clientX: nx, clientY: ny, bubbles: true
                }}));
                step++;
                setTimeout(moveAway, 15 + Math.random() * 25);
}}
moveAway();
}})();""")
            await asyncio.sleep(0.2)

            # try to click at cloudflare
            with suppress(Exception):
                await page.click_captcha()
        except Exception as er:
            logger.exception(er)
        
        return None 
    
    @staticmethod
    async def setup_browser(
            tab, cookies: Optional[list] = None, user_agent: Optional[str] = None, 
            accept_language: str = "en-US,en;q=0.9", 
            platform: str = "Win32"
        ) -> None:

        # --- Set User-Agent ---
        try:
            if user_agent:
                await tab.set_user_agent(
                    user_agent=user_agent,
                    accept_language=accept_language,
                    platform=platform,
                )
                logger.debug(f"✅ User-Agent set: {user_agent[:60]}...")
            
            # --- Load Cookies ---
            if cookies:
                try:
                    await tab.browser.cookies.set_all(cookies)
                    logger.debug(f"✅ Loaded {len(cookies)} cookies")
                except Exception as er:
                    logger.exception(er)
            
            # --- Reload to apply everything ---
            await tab.reload()
            logger.info("✅ Page reloaded with new settings")
        except Exception as er:
            logger.exception(er)
        return None


    async def solve_cf(self, page, domain: str) -> None:
        async with self._domain_solve_lock(domain):
            try:
                if cached := CF_COOKIES.get(domain):
                    await self.setup_browser(
                        page,
                        user_agent=cached.get('user_agent'),
                        cookies=cached.get('cookies'),
                    )
                    await self._wait_for_loads(page)
                    if await self._cf_state(page) == "passed":
                        logger.info(f"{domain} using cache and bypass successfully")
                        return

                for attempt in range(12):
                    solved = False
                    state = await self._cf_state(page)
                    logger.debug(f"[CF] Mitigation Attempt {attempt + 1}: Current state -> {state}")

                    if state == "passed":
                        headers = {
                            'cookies': await page.browser.cookies.get_all(requests_cookie_format=False),
                            'cookie_str': await page.get_cookie_string(),
                            'user_agent': await page.get_user_agent(),
                        }
                        CF_COOKIES.set(domain, headers)
                        await self._wait_for_loads(page)
                        logger.info(f"[CF] Cookie session validated & cached: {domain}")
                        return

                    if state == "turnstile":
                        await self.human_behaviour(page)
                        for fn in (
                            page.solve_captcha,
                            page.click_captcha
                        ):
                            try:
                                await fn()
                                solved = True
                                break
                            except Exception:
                                pass

                        if await self._cf_state(page) == "passed":
                            continue

                    if not solved:
                        try:
                            await page.click_captcha()
                            solved = True
                        except Exception:
                            pass

                    await asyncio.sleep(3.5)

                raise TimeoutError(f"Cloudflare interaction block timed out after 12 attempts: {domain}")
            except Exception as er:
                logger.exception(er)

            return None
    
    async def try_using_cookies(self, headers, url):
        logger.debug(f"Try to using cookies at {url}")

        def req():
            try:
                session = _get_cffi_session()
                response = session.get(
                    url,
                    headers={
                        'User-Agent': headers.get('user_agent', ''),
                        'Cookie': headers.get('cookie_str', ''),
                    },
                    timeout=DEFAULT_TIMEOUT,
                )
                if response.status_code != 200:
                    logger.info(f"Fail to Use Cookies at {url}")
                    return None
                return response.text
            except Exception as er:
                logger.warning(f"Cookie reuse failed at {url}: {er}")
                return None

        return await _to_thread(req)
    
    async def download_file(
        self, url: str,
        file_path: str,
        tor: bool = False
    ) -> Optional[str]:
        domain = get_domain(url)
        try:
            async with browser_hub.tab(url, tor=tor) as page:
                if page is None:
                    return None

                # return bytes
                script = (
                    "(async () => {"
                    "  try {"
                    "    const resp = await fetch(" + json.dumps(url) + ", {credentials: 'include'});"
                    "    if (!resp.ok) return {ok: false, status: resp.status};"
                    "    const bytes = new Uint8Array(await resp.arrayBuffer());"
                    "    let binary = '';"
                    "    const chunk = 0x8000;"
                    "    for (let i = 0; i < bytes.length; i += chunk) {"
                    "      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));"
                    "    }"
                    "    return {ok: true, status: resp.status, data: btoa(binary)};"
                    "  } catch (e) { return {ok: false, error: String(e)}; }"
                    "})()"
                )
                
                try:
                    if await self._cf_state(page) != "passed":
                        await self.solve_cf(page, domain)
                    
                    await asyncio.sleep(0.4)
                    
                    result = await page.evaluate(script, await_promise=True)
                    
                    if not result or not result.get("ok") or not result.get("data"):
                        logger.warning(f"Download failed {url}: {result}")
                        return None
                    
                    data = base64.b64decode(result["data"])
                    if not data:
                        logger.warning(f"Empty download {url}")
                        return None
                    
                    parent = os.path.dirname(file_path)
                    if parent:
                        os.makedirs(parent, exist_ok=True)
                    
                    with open(file_path, "wb") as f:
                        f.write(data)
                    
                except Exception as er:
                    logger.exception(er)
                    return None 

                return file_path
        except Exception as er:
            logger.exception(er)
        return None

    async def download_files(
        self,
        items: list,
        tor: bool = False,
        concurrency: int = 4,
    ) -> list:
        """
        Batch download many files reusing a single CF-solved browser tab.

        `items` is a list of (url, file_path) tuples or {'url', 'file_path'}
        dicts. The tab/Cloudflare bypass is done once, then every URL is
        fetched through that same page context (in chunks of `concurrency`).

        Returns a list aligned with `items`: the written file_path on success,
        or None for any entry that failed.
        """
        # ── normalize input to (url, file_path) pairs ───────────────────────
        norm = []
        for it in items:
            if isinstance(it, dict):
                norm.append((it.get("url"), it.get("file_path")))
            elif isinstance(it, (list, tuple)) and len(it) >= 2:
                norm.append((it[0], it[1]))
            else:
                norm.append((None, None))

        results = [None] * len(norm)
        if not norm:
            return results

        first_url = next((u for u, _ in norm if u), None)
        if not first_url:
            return results

        domain = get_domain(first_url)
        concurrency = max(1, int(concurrency))

        try:
            async with browser_hub.tab(first_url, tor=tor) as page:
                if page is None:
                    return results

                if await self._cf_state(page) != "passed":
                    await self.solve_cf(page, domain)

                await asyncio.sleep(0.4)

                # ── fetch in chunks through the same (CF-solved) page ───────
                for start in range(0, len(norm), concurrency):
                    chunk = norm[start:start + concurrency]
                    urls = [u for u, _ in chunk]

                    script = (
                        "(async (urls) => {"
                        "  const fetchOne = async (u) => {"
                        "    if (!u) return {ok: false, error: 'no url'};"
                        "    try {"
                        "      const resp = await fetch(u, {credentials: 'include'});"
                        "      if (!resp.ok) return {ok: false, status: resp.status};"
                        "      const bytes = new Uint8Array(await resp.arrayBuffer());"
                        "      let binary = '';"
                        "      const c = 0x8000;"
                        "      for (let i = 0; i < bytes.length; i += c) {"
                        "        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + c));"
                        "      }"
                        "      return {ok: true, status: resp.status, data: btoa(binary)};"
                        "    } catch (e) { return {ok: false, error: String(e)}; }"
                        "  };"
                        "  return await Promise.all(urls.map(fetchOne));"
                        "})(" + json.dumps(urls) + ")"
                    )

                    try:
                        chunk_results = await page.evaluate(script, await_promise=True)
                    except Exception as er:
                        logger.warning(f"Batch chunk failed @{start}: {er}")
                        chunk_results = []

                    if not isinstance(chunk_results, list):
                        chunk_results = []

                    for offset, (url, file_path) in enumerate(chunk):
                        if not url or not file_path:
                            continue

                        res = chunk_results[offset] if offset < len(chunk_results) else None
                        if not res or not res.get("ok") or not res.get("data"):
                            logger.warning(f"Download failed {url}: {res}")
                            continue

                        try:
                            data = base64.b64decode(res["data"])
                            if not data:
                                logger.warning(f"Empty download {url}")
                                continue

                            parent = os.path.dirname(file_path)
                            if parent:
                                os.makedirs(parent, exist_ok=True)

                            with open(file_path, "wb") as f:
                                f.write(data)

                            results[start + offset] = file_path
                        except Exception as e:
                            logger.warning(f"Write failed {file_path}: {e}")
                        
        except Exception as er:
            logger.exception(er)

        return results

    async def get(
        self, url: str, **kwargs,
    ):
        get_cookies = kwargs.get("get_cookies", False)
        s_script    = kwargs.get("s_script", None)
        a_script    = kwargs.get("a_script", None)
        tor         = kwargs.get("tor", False)
        #needs_browser = bool(s_script or a_script)
        wait_for    = kwargs.get('wait_for', 0)
        scripts     = kwargs.get('scripts', [])
        domain = get_domain(url)

        # ── Fast path: domain already solved ────────────────────────────────
        # not work , idk why
        #if not needs_browser and not get_cookies:
        #    cached = CF_COOKIES.get(domain)
        #    if cached:
        #        r = await self.try_using_cookies(headers=cached, url=url)
        #        if r is not None:
        #            return r


        try:
            async with browser_hub.tab(url, tor=tor) as page:
                if page is None:
                    return None

                if await self._cf_state(page) != "passed":
                    await self.solve_cf(page, domain)

                await asyncio.sleep(0.4)

                if wait_for:
                    try:
                        await asyncio.sleep(int(wait_for))
                    except Exception:
                        pass 
                
                if s_script:
                    return await page.evaluate(f"(() => {{ {s_script} }})()")

                if a_script:
                    return await page.evaluate(
                        f"(async () => {{ {a_script} }})()",
                        await_promise=True,
                    )
                if scripts:
                    # return last results 
                    results = None
                    for script in scripts:
                        results = await page.evaluate(script)
                        await asyncio.sleep(0.3)
                    return results

                if get_cookies:
                    return (
                        await page.get_page_source(),
                        await page.browser.cookies.get_all(requests_cookie_format=False),
                    )

                return await page.get_page_source()
        except Exception as er:
            logger.exception(er)
            return None


      
        
        


sb = SM()


# ──────────────────────────────────────────────────────────────────────────────
# Scraper
# ──────────────────────────────────────────────────────────────────────────────
class Scraper:
    """
    Async HTTP scraper:
      - per-domain concurrency limiting (semaphore)
      - thread-local sessions (curl_cffi default, cloudscraper via cs=True)
      - transient-only retries with exponential backoff
      - optional Playwright rendering (render=True / .render())
      - optional Tor routing
    """

    __slots__ = ("headers", "tor", "_domain_sm", "_pw_pool", "_pw_kwargs", "_closed")

    def __init__(
        self,
        headers: Optional[dict] = None,
        tor: bool = False,
        playwright_kwargs: Optional[dict] = None,
    ):
        self.headers = headers or {}
        self.tor = is_tor_running(tor)  # downgrades to False if Tor isn't actually up
        self._domain_sm: dict[str, asyncio.Semaphore] = {}
        self._pw_pool: Optional[PlaywrightPool] = None
        self._pw_kwargs = playwright_kwargs or {}
        self._closed = False

    # ── domain semaphore ──────────────────────────────────────────────────────
    @asynccontextmanager
    async def _domain_semaphore(self, url: str):
        domain = get_domain(url)
        sem = self._domain_sm.get(domain)

        if sem is None:
            sem = self._domain_sm[domain] = asyncio.Semaphore(DOMAIN_LIMIT)
        
        async with sem:
            yield

    # ── HTTP (runs in a worker thread) ────────────────────────────────────────
    def _internal_request(self, method, url, use_cs, rjson, **kwargs):
        extra = self.headers.copy()
        if "headers" in kwargs:
            extra.update(kwargs.pop("headers"))
        final_headers = get_headers(url, extra)

        if kwargs.pop("tor", False) or self.tor:
            kwargs["proxies"] = TOR_PROXIES

        session = _get_cs_session() if use_cs else _get_cffi_session()
        resp = session.request(method, url, headers=final_headers, **kwargs)
        try:
            resp.raise_for_status()
            return resp.json() if rjson else resp.text
        
        finally:
            try:
                resp.close()
            except Exception:
                pass

    @staticmethod
    def _status_of(exc) -> Optional[int]:
        resp = getattr(exc, "response", None)
        return getattr(resp, "status_code", None)

    async def _make_request(
        self, method, url, rjson=False, cs=False, retries=2, **kwargs,
    ):
        if self._closed:
            logger.warning(f"Scraper is closed; dropping request to {url}")
            return None

        kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
        last_error: Optional[Exception] = None

        for attempt in range(retries + 1):
            if attempt:
                await asyncio.sleep(min(2 ** attempt, MAX_BACKOFF) + random.uniform(0, 0.5))
            try:
                async with self._domain_semaphore(url):
                    return await _to_thread(
                        self._internal_request, method, url, cs, rjson, **kwargs
                    )
                
            except asyncio.CancelledError:
                logger.warning(f"Request cancelled: {url}")
                raise
            
            except RETRYABLE_ERRORS as e:
                last_error = e
                logger.warning(f"{type(e).__name__} (attempt {attempt + 1}) → {url}")
            
            except (CffiHTTPError, ReqHTTPError) as e:
                last_error = e
                status = self._status_of(e)
                if status not in RETRYABLE_STATUS:
                    logger.error(f"HTTP {status} (permanent) → {url}")
                    return None
                logger.warning(f"HTTP {status} (attempt {attempt + 1}) → {url}")
                
            except JSONDecodeError as e:
                logger.error(f"Invalid JSON → {url}: {e}")
                return None
            except Exception as e:
                logger.exception(f"Unexpected error → {url}: {e}")
                return None

        logger.error(f"All {retries + 1} attempts failed for {url}: {last_error}")
        return None

    async def get(self, url, rjson=False, cs=False, render=False, retries=2, **kwargs):
        if render:
            return await self.render(url, **kwargs)
    
        return await self._make_request("GET", url, rjson, cs, retries, **kwargs)

    async def post(self, url, rjson=False, cs=False, retries=2, **kwargs):
        return await self._make_request("POST", url, rjson, cs, retries, **kwargs)

    # ── Playwright ────────────────────────────────────────────────────────────
    def _get_pool(self) -> PlaywrightPool:
        if self._pw_pool is None:
            self._pw_pool = PlaywrightPool(tor=self.tor, **self._pw_kwargs)
        
        return self._pw_pool

    async def render(self, url, **kwargs):
        if self._closed:
            logger.warning(f"Scraper is closed; dropping render for {url}")
            return None
        return await self._get_pool().render(url, **kwargs)

    def get_tab(
            self, url, 
            broswer_kwargs: Optional[dict] = None,
            context_kwargs: Optional[dict] = None
        ):
        """Async context manager yielding a Playwright tab for the URL's domain.

        Usage:
            async with scraper.get_tab(url) as page:
                await page.goto(url)
                ...
        """
        return self._get_pool().get_tab(
            url, context_kwargs=context_kwargs,
            broswer_kwargs=broswer_kwargs
         )

    # ── lifecycle ─────────────────────────────────────────────────────────────
    async def _cleanup_playwright(self) -> None:
        if self._pw_pool is not None:
            await self._pw_pool.close()
            self._pw_pool = None

    async def reset(self) -> None:
        _close_thread_sessions()
        await self._cleanup_playwright()
        self._domain_sm.clear()
        self._closed = False
        logger.info("Scraper reset complete")

    async def close(self) -> None:
        """Full shutdown — call once at program exit."""
        if self._closed:
            return
        
        self._closed = True
        _close_thread_sessions()
        await self._cleanup_playwright()
        logger.info("Scraper closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()


# ──────────────────────────────────────────────────────────────────────────────
# Global instance
# ──────────────────────────────────────────────────────────────────────────────
shared_scraper = Scraper()
