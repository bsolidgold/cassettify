from __future__ import annotations
from pathlib import Path

COOKIE_FILE = Path.home() / ".cassettify" / "cookies.txt"

# Order to try when auto-detecting. Chromium-family first (most common),
# Firefox (unencrypted, no prompt), Safari last (needs Full Disk Access).
_BROWSER_ORDER = [
    "chrome", "brave", "edge", "chromium", "vivaldi", "opera", "firefox", "safari",
]


class _QuietLogger:
    """Swallow yt-dlp's chatter so it doesn't corrupt the TUI / console."""
    def debug(self, *a, **k): pass
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass


def extract(browser: str | None = None) -> str | None:
    """Pull YouTube/Google cookies from a browser into COOKIE_FILE.

    Tries the given browser, or auto-detects across the common ones.
    Returns the browser name on success, or None if nothing worked.
    """
    from yt_dlp.cookies import extract_cookies_from_browser, YoutubeDLCookieJar

    candidates = [browser] if browser else _BROWSER_ORDER
    for name in candidates:
        try:
            jar = extract_cookies_from_browser(name, logger=_QuietLogger())
        except Exception:
            continue
        relevant = [c for c in jar if "youtube" in c.domain or "google" in c.domain]
        if not relevant:
            continue
        COOKIE_FILE.parent.mkdir(exist_ok=True)
        out = YoutubeDLCookieJar(str(COOKIE_FILE))
        for c in relevant:
            out.set_cookie(c)
        out.save(ignore_discard=True, ignore_expires=True)
        return name
    return None
