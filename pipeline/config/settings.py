"""
settings.py — Load and validate all environment configuration for the LeadFlow pipeline.
"""

import os
from dotenv import load_dotenv

# Load .env from the pipeline root (one level up from config/)
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=_env_path, override=False)


def _require(key: str) -> str:
    """Return the value of a required env var or raise a clear error."""
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            "Check your .env file or shell environment."
        )
    return val


def _int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise EnvironmentError(
            f"Environment variable '{key}' must be an integer, got: {raw!r}"
        )


# ---------------------------------------------------------------------------
# Required
# ---------------------------------------------------------------------------
SUPABASE_URL: str = _require("SUPABASE_URL")
SUPABASE_KEY: str = _require("SUPABASE_KEY")
OPENAI_API_KEY: str = _require("OPENAI_API_KEY")

# ---------------------------------------------------------------------------
# Optional with defaults
# ---------------------------------------------------------------------------
CONCURRENCY: int = _int("CONCURRENCY", 5)
PLAYWRIGHT_TIMEOUT_MS: int = _int("PLAYWRIGHT_TIMEOUT_MS", 15000)

# ---------------------------------------------------------------------------
# Derived / static
# ---------------------------------------------------------------------------
DATA_DIR: str = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# User-agent rotation pool — real Chrome/Firefox UA strings (UK-plausible)
USER_AGENTS: list[str] = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) "
        "Gecko/20100101 Firefox/123.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) "
        "Gecko/20100101 Firefox/122.0"
    ),
]

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL: int = 30

# How long (seconds) a running job is considered stale
STALE_JOB_THRESHOLD_SECONDS: int = 7200  # 2 hours

# Lead staleness window for dedup (days)
LEAD_STALENESS_DAYS: int = 30

# Yell.com search URL template
YELL_SEARCH_URL: str = (
    "https://www.yell.com/ucs/UcsSearchAction.do"
    "?keywords={keyword}&location={city}"
)

# Keywords to search on Yell
YELL_KEYWORDS: list[str] = ["barbershop", "hair+salon"]

# Max pages to paginate per Yell search
YELL_MAX_PAGES: int = 5
