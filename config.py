import os
from pathlib import Path
from time import time

from loguru import logger

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _str(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes"}


def _int_list(name: str) -> list[int]:
    return [int(x) for x in os.environ.get(name, "").replace(",", " ").split()]


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _load_pics(path: str = "pics.txt") -> tuple[str, ...]:
    """One image URL per line. Blank lines and lines starting with # are ignored."""
    file = Path(path)
    if not file.exists():
        return ()
    return tuple(
        line.strip()
        for line in file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )


class Vars:
    # Telegram credentials (required, no defaults)
    API_ID = int(_required("API_ID"))
    API_HASH = _required("API_HASH")
    BOT_TOKEN = _required("BOT_TOKEN")
    DB_URL = _required("DB_URL")
    DB_NAME = _str("DB_NAME", "test")

    plugins = {"root": "TG"}

    # Feature flags
    AUTO_F = _bool("AUTO_FEATURES", True)  # auto upload / auto update
    IM_FAST = _bool("IM_FAST", False)
    USE_SHARED_WORKERS = _bool("USE_SHARED_WORKERS", True)
    WORKERS_PER_USER = _int("WORKERS_PER_USER", 4)
    IS_PRIVATE = _bool("IS_PRIVATE", False)  # admins-only mode

    # Channels
    LOG_CHANNEL = _int("LOG_CHANNEL", 0)
    UPDATE_CHANNEL = _int("UPDATE_CHANNEL", 0)
    CONSTANT_DUMP_CHANNEL = _str("CONSTANT_DUMP_CHANNEL")

    # Access control
    OWNER = _str("OWNER", "")
    ADMINS = _int_list("ADMINS")  # space or comma separated user IDs

    # Web (Render / Koyeb)
    PORT = _int("PORT", 5000)
    WEBS_HOST = _str("WEBS_HOST")

    # Shortener
    SHORTENER = _str("SHORTENER")
    SHORTENER_API = _str("SHORTENER_API", "")  # use {} for the url, e.g. api.site/?url={}
    DURATION = _int("DURATION", 20)  # hours

    # Force subscribe: "Button Name:channel_username, Other Name:other_channel"
    FORCE_SUB_CHANNEL = _str("FORCE_SUB_CHANNEL", "")
    FORCE_SUB_TEXT = _str(
        "FORCE_SUB_TEXT",
        "<b><i>❗️ You must join our channel before using this feature:</i></b>",
    )

    BYPASS_TXT = _str(
        "BYPASS_TXT",
        "<blockquote><b>Bypass detected</b></blockquote>\n"
        "<blockquote>Please solve the verification again.</blockquote>",
    )
    ADMIN_MODE_TXT = _str(
        "ADMIN_MODE_TXT",
        "<blockquote>Admin mode is currently enabled, so the bot is unavailable.</blockquote>\n"
        "<blockquote>Please try again later.</blockquote>",
    )

    PICS = _load_pics()
    PING = time()


DEFAULT_SETTINGS: dict = {}
Bot_cmds: dict = {}
remove_site_sf = ["cf"]
