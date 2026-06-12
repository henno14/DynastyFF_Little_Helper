import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf
import config

log = logging.getLogger(__name__)

_cache = []
_cache_time = 0


def _fetch_one(cfg):
    symbol = cfg["symbol"]
    tk = yf.Ticker(symbol)

    fi = tk.fast_info
    price = fi.last_price
    if price is None:
        raise ValueError("No price data")

    prev = fi.previous_close or price
    change_pct = ((price - prev) / prev * 100) if prev else 0

    w52_low  = getattr(fi, 'year_low',  None) or price
    w52_high = getattr(fi, 'year_high', None) or price
    w52_pct  = max(0.0, min(100.0, (price - w52_low) / (w52_high - w52_low) * 100)) if w52_high > w52_low else 50.0

    log.info("Stock OK: %s %.4g (%.2f%%)", cfg["label"], price, change_pct)
    return {
        "label":      cfg["label"],
        "price":      _fmt_price(price, cfg["is_index"]),
        "change_pct": round(change_pct, 4),
        "up":         change_pct >= 0,
        "w52_pct":    round(w52_pct, 1),
    }


def _load_disk_cache():
    global _cache, _cache_time
    if not os.path.exists(config.STOCKS_CACHE_FILE):
        return
    try:
        with open(config.STOCKS_CACHE_FILE) as f:
            saved = json.load(f)
        _cache = saved["data"]
        for s in _cache:
            s.pop("sparkline", None)
        _cache_time = saved.get("fetched_at", 0)
        log.info("Loaded stocks from disk cache (%d items)", len(_cache))
    except Exception as e:
        log.warning("Could not read stocks cache: %s", e)


def _save_disk_cache(data):
    try:
        with open(config.STOCKS_CACHE_FILE, "w") as f:
            json.dump({"data": data, "fetched_at": _cache_time}, f)
    except OSError as e:
        log.warning("Could not write stocks cache: %s", e)


def fetch():
    global _cache, _cache_time
    results = []

    with ThreadPoolExecutor(max_workers=len(config.STOCKS)) as ex:
        futures = {ex.submit(_fetch_one, cfg): cfg for cfg in config.STOCKS}
        for future in as_completed(futures):
            cfg = futures[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                log.error("Stock fetch failed [%s]: %s", cfg["label"], e)

    order = {cfg["label"]: i for i, cfg in enumerate(config.STOCKS)}
    results.sort(key=lambda r: order.get(r["label"], 99))

    if results:
        _cache = results
        _cache_time = time.time()
        _save_disk_cache(_cache)
    else:
        log.warning("All stock fetches failed — showing last known prices")

    return _cache


def _fmt_price(price, is_index):
    if is_index:
        return "{:,.0f}".format(price)
    return "{:,.2f}".format(price)


_load_disk_cache()
