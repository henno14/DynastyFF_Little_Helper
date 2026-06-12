#!/usr/bin/env python3
"""Raspberry Pi weather/clock dashboard server — iOS 12 / iPad Air edition."""

import base64
import json
import logging
import math
import os
import threading
import time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import config
import weather
import news
import stocks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Moon phase
# ---------------------------------------------------------------------------

def _moon_phase():
    """Return (phase_fraction, name, symbol). 0=new, 0.5=full."""
    known_new = date(2000, 1, 6)
    days = (date.today() - known_new).days
    cycle = 29.53058867
    phase = (days % cycle) / cycle
    if phase < 0.03 or phase > 0.97:
        return phase, "New Moon",        "\U0001f311"  # 🌑
    elif phase < 0.22:
        return phase, "Waxing Crescent", "\U0001f312"  # 🌒
    elif phase < 0.28:
        return phase, "First Quarter",   "\U0001f313"  # 🌓
    elif phase < 0.47:
        return phase, "Waxing Gibbous",  "\U0001f314"  # 🌔
    elif phase < 0.53:
        return phase, "Full Moon",       "\U0001f315"  # 🌕
    elif phase < 0.72:
        return phase, "Waning Gibbous",  "\U0001f316"  # 🌖
    elif phase < 0.78:
        return phase, "Last Quarter",    "\U0001f317"  # 🌗
    else:
        return phase, "Waning Crescent", "\U0001f318"  # 🌘


def _moon_svg(phase, size=84):
    r = size // 2
    cx = cy = r
    illum = round((1 - math.cos(phase * 2 * math.pi)) / 2 * 100)
    if phase < 0.5:
        norm = phase * 2
        ex = round(abs(r * (1 - 2 * norm)), 1)
        if norm < 0.5:
            lit  = '<rect x="%d" y="0" width="%d" height="%d" fill="#ddd8c4"/>' % (cx, r, size)
            dark = '<rect x="0" y="0" width="%d" height="%d" fill="#141414"/>' % (r, size)
            term = '<ellipse cx="%d" cy="%d" rx="%s" ry="%d" fill="#141414"/>' % (cx, cy, ex, r)
        else:
            lit  = '<rect x="%d" y="0" width="%d" height="%d" fill="#ddd8c4"/>' % (cx, r, size)
            dark = '<rect x="0" y="0" width="%d" height="%d" fill="#141414"/>' % (r, size)
            term = '<ellipse cx="%d" cy="%d" rx="%s" ry="%d" fill="#ddd8c4"/>' % (cx, cy, ex, r)
    else:
        norm = (phase - 0.5) * 2
        ex = round(abs(r * (1 - 2 * norm)), 1)
        if norm < 0.5:
            lit  = '<rect x="0" y="0" width="%d" height="%d" fill="#ddd8c4"/>' % (r, size)
            dark = '<rect x="%d" y="0" width="%d" height="%d" fill="#141414"/>' % (cx, r, size)
            term = '<ellipse cx="%d" cy="%d" rx="%s" ry="%d" fill="#ddd8c4"/>' % (cx, cy, ex, r)
        else:
            lit  = '<rect x="0" y="0" width="%d" height="%d" fill="#ddd8c4"/>' % (r, size)
            dark = '<rect x="%d" y="0" width="%d" height="%d" fill="#141414"/>' % (cx, r, size)
            term = '<ellipse cx="%d" cy="%d" rx="%s" ry="%d" fill="#141414"/>' % (cx, cy, ex, r)
    clip_id = 'mc'
    svg = (
        '<svg width="%d" height="%d" viewBox="0 0 %d %d" '
        'xmlns="http://www.w3.org/2000/svg" style="display:block;width:100%%;height:auto;">'
        '<defs><clipPath id="%s"><circle cx="%d" cy="%d" r="%d"/></clipPath></defs>'
        '<circle cx="%d" cy="%d" r="%d" fill="#141414" stroke="#252525" stroke-width="1.5"/>'
        '<g clip-path="url(#%s)">%s%s%s</g>'
        '</svg>'
    ) % (size, size, size, size,
         clip_id, cx, cy, r - 1,
         cx, cy, r - 1,
         clip_id, lit, dark, term)
    return svg, illum


# ---------------------------------------------------------------------------
# HTML shell — all data rendered client-side via fetch('/data')
# ---------------------------------------------------------------------------

_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard.html')
with open(_HTML_PATH, 'rb') as _f:
    _HTML = _f.read()

ICON_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

BLACK_PAGE = b"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<meta http-equiv="refresh" content="120">
<style>html,body{margin:0;width:100%;height:100vh;background:#000;}</style>
</head>
<body></body>
</html>"""

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_weather_data  = None
_weather_stale = False
_stock_data    = []
_lock          = threading.Lock()

_moon_cache    = None    # (name, icon, svg, illum) — recomputed once per day
_moon_date     = None


# ---------------------------------------------------------------------------
# Background fetch loops
# ---------------------------------------------------------------------------

def _weather_loop():
    global _weather_data, _weather_stale
    while True:
        data, stale = weather.fetch()
        with _lock:
            _weather_data  = data
            _weather_stale = stale
        time.sleep(config.FETCH_INTERVAL)


def _stock_loop():
    global _stock_data
    while True:
        data = stocks.fetch()
        with _lock:
            _stock_data = data
        time.sleep(config.STOCK_FETCH_INTERVAL)


def _news_loop():
    while True:
        news.fetch()
        time.sleep(config.NEWS_FETCH_INTERVAL)


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

def _is_rest():
    h = datetime.now().hour
    s, e = config.REST_START, config.REST_END
    return (s <= h < e) if s < e else (h >= s or h < e)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.info("HTTP %s", fmt % args)

    def do_GET(self):
        if self.path == '/icon.png':
            self._send(200, 'image/png', ICON_PNG)

        elif self.path == '/data' or self.path.startswith('/data?'):
            self._serve_data()

        elif self.path == '/':
            if _is_rest():
                self._send(200, 'text/html; charset=utf-8', BLACK_PAGE)
            else:
                self._send(200, 'text/html; charset=utf-8', _HTML)

        else:
            self._send(404, 'text/plain', b'Not found')

    def _serve_data(self):
        with _lock:
            w_data  = _weather_data
            stale   = _weather_stale
            s_data  = list(_stock_data)

        global _moon_cache, _moon_date
        today = date.today()
        if today != _moon_date or _moon_cache is None:
            _moon_date = today
            phase, moon_name, moon_icon = _moon_phase()
            moon_svg_str, moon_illum = _moon_svg(phase)
            _moon_cache = (moon_name, moon_icon, moon_svg_str, moon_illum)
        moon_name, moon_icon, moon_svg_str, moon_illum = _moon_cache

        # Re-parse hourly fresh on every request so displayed hours stay current
        w_out = dict(w_data) if w_data else {}
        raw_hourly = w_out.pop('_raw_hourly', None)
        if raw_hourly:
            w_out['hourly'] = weather._parse_hourly(raw_hourly)
        if 'hourly' not in w_out:
            w_out['hourly'] = []

        payload = {
            'weather':     w_out,
            'stocks':      s_data,
            'news':        news.headlines(),
            'rest':        _is_rest(),
            'stale':       stale,
            'stale_age':   weather.cache_age_minutes(),
            'moon_name':   moon_name,
            'moon_icon':   moon_icon,
            'moon_svg':    moon_svg_str,
            'moon_illum':  moon_illum,
        }
        body = json.dumps(payload).encode('utf-8')
        self._send(200, 'application/json; charset=utf-8', body)

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    log.info("Starting dashboard on port %d", config.PORT)

    for target in (_weather_loop, _stock_loop, _news_loop):
        threading.Thread(target=target, daemon=True).start()

    time.sleep(3)  # let first fetches complete

    server = HTTPServer(('', config.PORT), Handler)
    log.info("Serving at http://0.0.0.0:%d/", config.PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down")
