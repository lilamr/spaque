"""
core/leaflet_cache.py
Download dan cache Leaflet JS/CSS lokal agar peta bekerja offline.
"""

from __future__ import annotations
import os
import urllib.request
from pathlib import Path

CACHE_DIR  = Path.home() / ".spaque" / "assets"
JS_PATH    = CACHE_DIR / "leaflet.min.js"
CSS_PATH   = CACHE_DIR / "leaflet.min.css"

LEAFLET_JS_URL  = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
LEAFLET_CSS_URL = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"

_js_cache:  str | None = None
_css_cache: str | None = None


def get_leaflet_js() -> str | None:
    """Return Leaflet JS string, None jika tidak tersedia."""
    global _js_cache
    if _js_cache:
        return _js_cache
    if JS_PATH.exists():
        _js_cache = JS_PATH.read_text(encoding="utf-8")
        return _js_cache
    return _try_download_js()


def get_leaflet_css() -> str | None:
    global _css_cache
    if _css_cache:
        return _css_cache
    if CSS_PATH.exists():
        _css_cache = CSS_PATH.read_text(encoding="utf-8")
        return _css_cache
    return _try_download_css()


def is_available() -> bool:
    return JS_PATH.exists() and CSS_PATH.exists()


def download(timeout: int = 10) -> tuple[bool, str]:
    """Download Leaflet assets. Returns (success, message)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        js  = urllib.request.urlopen(LEAFLET_JS_URL,  timeout=timeout).read()
        css = urllib.request.urlopen(LEAFLET_CSS_URL, timeout=timeout).read()
        JS_PATH.write_bytes(js)
        CSS_PATH.write_bytes(css)
        global _js_cache, _css_cache
        _js_cache  = js.decode("utf-8")
        _css_cache = css.decode("utf-8")
        return True, f"Leaflet berhasil diunduh ({len(js)//1024} KB)"
    except Exception as e:
        return False, str(e)


def _try_download_js() -> str | None:
    ok, _ = download(timeout=5)
    return _js_cache if ok else None


def _try_download_css() -> str | None:
    if is_available():
        return CSS_PATH.read_text(encoding="utf-8")
    return None
