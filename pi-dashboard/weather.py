"""Weather from Open-Meteo — Kingston, ON (44.2312, -76.4860)."""
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
import config

log = logging.getLogger(__name__)

_BASE_URL = "https://api.open-meteo.com/v1/forecast"
_PARAMS = {
    "latitude":      config.LATITUDE,
    "longitude":     config.LONGITUDE,
    "timezone":      config.TIMEZONE,
    "forecast_days": 6,
    "current":       "temperature_2m,apparent_temperature,relative_humidity_2m,"
                     "wind_speed_10m,wind_direction_10m,weather_code,is_day,pressure_msl,uv_index",
    "hourly":        "temperature_2m,precipitation_probability,weather_code,is_day,pressure_msl",
    "daily":         "temperature_2m_max,temperature_2m_min,"
                     "precipitation_probability_max,weather_code,sunrise,sunset",
}

_cache      = None
_cache_time = 0

# WMO weather code → human description
_WMO_DESC = {
    0:  "Clear",
    1:  "Mainly clear",
    2:  "Partly cloudy",
    3:  "Overcast",
    45: "Fog",
    48: "Icy fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers",
    81: "Showers",
    82: "Heavy showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}

_DAY_ABBR = {
    0: "Mon", 1: "Tue", 2: "Wed",
    3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uv_label(uv):
    if uv is None: return "—"
    if uv <= 2:    return "Low"
    if uv <= 5:    return "Moderate"
    if uv <= 7:    return "High"
    if uv <= 10:   return "Very High"
    return "Extreme"


def _wmo_desc(code):
    return _WMO_DESC.get(code, "—")


_COMPASS = ['N','NNE','NE','ENE','E','ESE','SE','SSE',
            'S','SSW','SW','WSW','W','WNW','NW','NNW']

def _wind_bearing(deg):
    if deg is None:
        return '—'
    return _COMPASS[int((deg + 11.25) / 22.5) % 16]


def _pressure_trend(hourly):
    """Compare pressure now vs 3 h ago. ±1 hPa over 3 h is the meteorological
    threshold for a meaningful rise/fall."""
    try:
        times     = hourly["time"]
        pressures = hourly["pressure_msl"]
        now_str   = datetime.now(ZoneInfo(config.TIMEZONE)).strftime("%Y-%m-%dT%H")
        idx = next(i for i, t in enumerate(times) if t >= now_str)
        if idx < 3:
            return "→"
        diff = pressures[idx] - pressures[idx - 3]
        if diff >= 1.0:
            return "↑"
        if diff <= -1.0:
            return "↓"
        return "→"
    except (KeyError, TypeError, StopIteration):
        return "→"


def _parse_hhmm(iso_str):
    """'2025-06-01T05:47' → '05:47'  (time part already in local tz from API)."""
    if not iso_str or "T" not in iso_str:
        return ""
    return iso_str.split("T")[1][:5]


def _day_name(iso_date):
    """'2025-06-02' → 'Mon' etc."""
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return _DAY_ABBR[dt.weekday()]
    except (ValueError, KeyError):
        return iso_date[:3]


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def _fetch_openmeteo():
    r = requests.get(
        _BASE_URL,
        params=_PARAMS,
        headers=config.HTTP_HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

def _parse(data):
    cur    = data["current"]
    hourly = data["hourly"]
    daily  = data["daily"]

    # ── Current conditions ──────────────────────────────────────────────────
    code      = cur.get("weather_code", 0)
    uv_index  = cur.get("uv_index")
    temp      = round(cur.get("temperature_2m", 0))
    feels     = round(cur.get("apparent_temperature", temp))
    wind      = round(cur.get("wind_speed_10m", 0))
    humidity  = round(cur.get("relative_humidity_2m", 0))
    pressure  = round(cur.get("pressure_msl", 0)) if cur.get("pressure_msl") else None
    is_day    = bool(cur.get("is_day", 1))

    current = {
        "temp":           temp,
        "feels_like":     feels,
        "wind":           wind,
        "humidity":       humidity,
        "weather_code":   code,
        "pressure":       pressure,
        "pressure_trend": _pressure_trend(hourly),
        "uv_index":       uv_index,
        "uv_label":       _uv_label(uv_index),
        "is_day":         is_day,
        "wind_dir":       _wind_bearing(cur.get("wind_direction_10m")),
        "desc":           _wmo_desc(code),
    }

    # ── Today (daily[0]) ────────────────────────────────────────────────────
    today = {
        "high":       round(daily["temperature_2m_max"][0])
                      if daily["temperature_2m_max"][0] is not None else temp,
        "low":        round(daily["temperature_2m_min"][0])
                      if daily["temperature_2m_min"][0] is not None else temp,
        "precip_pct": daily["precipitation_probability_max"][0] or 0,
        "sunrise":    _parse_hhmm(daily["sunrise"][0]),
        "sunset":     _parse_hhmm(daily["sunset"][0]),
    }

    # ── 5-day forecast (daily[1..5]) ────────────────────────────────────────
    forecast = []
    for i in range(1, 6):
        fc_code = daily["weather_code"][i]
        forecast.append({
            "name":         _day_name(daily["time"][i]),
            "high":         round(daily["temperature_2m_max"][i])
                            if daily["temperature_2m_max"][i] is not None else 0,
            "low":          round(daily["temperature_2m_min"][i])
                            if daily["temperature_2m_min"][i] is not None else 0,
            "desc":         _wmo_desc(fc_code),
            "precip_pct":   daily["precipitation_probability_max"][i] or 0,
            "weather_code": fc_code,
        })

    # ── Raw hourly (stored in cache so hourly survives restarts) ────────────
    raw_hourly = []
    times = hourly.get("time", [])
    for idx, t in enumerate(times):
        raw_hourly.append({
            "time":        t,                                       # "YYYY-MM-DDTHH:00"
            "temp":        round(hourly["temperature_2m"][idx])
                           if hourly["temperature_2m"][idx] is not None else 0,
            "precip_pct":  hourly["precipitation_probability"][idx] or 0,
            "weather_code": hourly["weather_code"][idx],
            "is_day":      bool(hourly["is_day"][idx]),
        })

    return {
        "current":     current,
        "today":       today,
        "forecast":    forecast,
        "_raw_hourly": raw_hourly,
    }


def _parse_hourly(raw_hourly):
    """Return hourly slots starting at the NEXT local hour (current hour excluded —
    the conditions block already covers 'now')."""
    tz_local = ZoneInfo(config.TIMEZONE)
    next_hr  = (datetime.now(tz_local) + timedelta(hours=1)).strftime("%Y-%m-%dT%H")

    idx = next(
        (i for i, h in enumerate(raw_hourly) if h.get("time", "") >= next_hr),
        0,
    )

    result = []
    for h in raw_hourly[idx: idx + 8]:
        try:
            label = h["time"].split("T")[1][:2] + "h"   # "14h"
        except (KeyError, IndexError):
            label = "??h"
        result.append({
            "label":        label,
            "temp":         h["temp"],
            "precip_pct":   h["precip_pct"],
            "weather_code": h["weather_code"],
            "is_day":       h["is_day"],
        })
    return result


# ---------------------------------------------------------------------------
# Public interface (unchanged signatures)
# ---------------------------------------------------------------------------

def fetch():
    global _cache, _cache_time
    try:
        data        = _parse(_fetch_openmeteo())
        _cache      = data
        _cache_time = time.time()
        try:
            with open(config.CACHE_FILE, "w") as f:
                json.dump({"data": data, "fetched_at": _cache_time}, f)
        except OSError as e:
            log.warning("Cache write failed: %s", e)
        log.info("Weather OK — %s°C %s", data["current"]["temp"], data["current"]["desc"])
        return data, False
    except Exception as e:
        log.error("Open-Meteo fetch failed: %s", e)
        return _load_cache(), True


def _load_cache():
    global _cache, _cache_time
    if _cache:
        return _cache
    if os.path.exists(config.CACHE_FILE):
        try:
            with open(config.CACHE_FILE) as f:
                saved = json.load(f)
            _cache      = saved["data"]
            _cache_time = saved.get("fetched_at", 0)
            log.info("Loaded weather from disk cache")
            return _cache
        except Exception as e:
            log.warning("Could not read cache: %s", e)
    return None


def cache_age_minutes():
    if not _cache_time:
        return None
    return round((time.time() - _cache_time) / 60)
