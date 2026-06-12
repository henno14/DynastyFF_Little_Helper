LATITUDE = 44.2312
LONGITUDE = -76.4860
TIMEZONE = "America/Toronto"
LOCATION_NAME = "Kingston, ON"

PORT = 8080
USE_12H = False
SHOW_SECONDS = False

REST_START = 1   # 01:00 local
REST_END = 6     # 06:00 local

CACHE_FILE        = "weather_cache.json"
STOCKS_CACHE_FILE = "stocks_cache.json"
NEWS_CACHE_FILE   = "news_cache.json"
FETCH_INTERVAL = 900  # seconds between Open-Meteo polls (their model updates every 15 min)

NEWS_SOURCES = [
    {"label": "Globe", "url": "https://www.theglobeandmail.com/arc/outboundfeeds/rss/category/canada/"},
    {"label": "Kingstonist", "url": "https://www.kingstonist.com/feed/"},
    {"label": "Global",     "url": "https://globalnews.ca/kingston/feed/"},
    {"label": "RTÉ",  "url": "https://www.rte.ie/feeds/rss/?index=/news"},
    {"label": "BBC",  "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
]
NEWS_PER_SOURCE = 4        # headlines per feed
NEWS_FETCH_INTERVAL = 900  # 15 minutes

STOCKS = [
    {"symbol": "GC=F",    "label": "GOLD", "unit": "USD/oz",  "is_index": False},
    {"symbol": "CL=F",    "label": "OIL",  "unit": "USD/bbl", "is_index": False},
    {"symbol": "^GSPTSE", "label": "TSX",  "unit": "pts",     "is_index": True},
    {"symbol": "^GSPC",   "label": "S&P",  "unit": "pts",     "is_index": True},
    {"symbol": "EURCAD=X", "label": "EUR/CAD", "unit": "CAD/EUR", "is_index": False},
]
STOCK_FETCH_INTERVAL = 600

# Full browser UA — Kingstonist's bot protection 403s anything that looks like a bot
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"}
