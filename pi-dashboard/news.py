import json
import logging
import os
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import config

log = logging.getLogger(__name__)

_cache = []
_cache_time = 0

_HEADERS = config.HTTP_HEADERS


def fetch():
    global _cache, _cache_time
    headlines = []

    with ThreadPoolExecutor(max_workers=len(config.NEWS_SOURCES)) as ex:
        futures = {ex.submit(_fetch_feed, src["url"], src["label"]): src for src in config.NEWS_SOURCES}
        for future in as_completed(futures):
            src = futures[future]
            try:
                items = future.result()
                headlines.extend(items)
                log.info("News OK: %s (%d headlines)", src["label"], len(items))
            except Exception as e:
                log.warning("News feed failed [%s]: %s", src["label"], e)

    if headlines:
        _cache = headlines
        _cache_time = time.time()
        _save_disk_cache(_cache)
    else:
        log.warning("All news feeds failed; using cache (%d items)", len(_cache))

    return _cache


def _fetch_feed(url, label):
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            resp.raise_for_status()
            break
        except Exception:
            if attempt == 0:
                time.sleep(2)
            else:
                raise
    root = ET.fromstring(resp.content)
    items = root.findall(".//item")
    out = []
    for item in items[: config.NEWS_PER_SOURCE]:
        title = item.findtext("title", "").strip()
        title = title.replace("<![CDATA[", "").replace("]]>", "").strip()
        if not title:
            continue
        if len(title) > 95:
            title = title[:95].rsplit(" ", 1)[0] + "…"
        out.append({"source": label, "text": title})
    return out


def _load_disk_cache():
    global _cache, _cache_time
    if not os.path.exists(config.NEWS_CACHE_FILE):
        return
    try:
        with open(config.NEWS_CACHE_FILE) as f:
            saved = json.load(f)
        _cache = saved["data"]
        _cache_time = saved.get("fetched_at", 0)
        log.info("Loaded news from disk cache (%d items)", len(_cache))
    except Exception as e:
        log.warning("Could not read news cache: %s", e)


def _save_disk_cache(data):
    try:
        with open(config.NEWS_CACHE_FILE, "w") as f:
            json.dump({"data": data, "fetched_at": _cache_time}, f)
    except OSError as e:
        log.warning("Could not write news cache: %s", e)


def headlines():
    return list(_cache)


# Load disk cache immediately on import so headlines survive service restarts
_load_disk_cache()
