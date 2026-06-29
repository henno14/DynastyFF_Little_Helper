"""
Sleeper Dynasty Fantasy League — Streamlit Dashboard
Run: streamlit run sleeper_dashboard.py
  or double-click: Run Dashboard.command
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone
import sys
import os
import json
import re
import base64
import html as _html
import statistics as _stats
import contextlib
import requests
import feedparser
import plotly.graph_objects as go
import plotly.express as px

# Reuse all data-fetching logic from the existing tracker (no Excel output triggered)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sleeper_dynasty_tracker import (
    LEAGUE_ID, SPORT, STATS_SEASON, PICK_SEASONS, TREND_LOOKBACK,
    BASE, get,
    fetch_players, fetch_season_stats, fetch_fantasycalc,
    fetch_all_traded_picks, fetch_league_data, derive_league_shape,
    compute_fantasy_pts, build_pos_ranks,
    SCORING_LABELS, DYNASTY_POSITIONS,
)
import insight_text as it   # natural-language insight engine (templates if no API key)

_APP_DIR    = os.path.dirname(os.path.abspath(__file__))
_ASSETS_DIR = os.path.join(_APP_DIR, "assets")


def _asset(name):
    """Read an asset file (SVG/text) from assets/ — returns '' if missing."""
    try:
        with open(os.path.join(_ASSETS_DIR, name), "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


_LOGO_HORIZONTAL = _asset("dynasty-little-helper-horizontal.svg")
_LOGO_STACKED    = _asset("dynasty-little-helper-logo.svg")
_LOGO_FAVICON    = _asset("dynasty-little-helper-favicon.svg")

st.set_page_config(
    page_title="Dynasty FF Lil' Helper",
    page_icon=os.path.join(_ASSETS_DIR, "dynasty-little-helper-favicon.svg"),
    layout="wide",
)

# NOTE: deliberately NOT using st.logo() — it hijacks the collapsed-sidebar
# expand control (which broke "reopen sidebar" in Safari). The brand logo is
# rendered as the clickable Home button inside the sidebar instead (see below).
# The bulk of theming lives in .streamlit/config.toml; the CSS below adds the
# modern type, chrome-hiding, and card/sidebar polish config.toml can't express.

# ── Design tokens — single source of truth (Python side). Mirrors the CSS
#    :root block in inject_theme() and .streamlit/config.toml. Charts/components
#    reference colors by name here instead of hardcoding hex. ─────────────────
TOKENS = {
    # Surfaces
    "bg_page": "#0A0F0C", "bg_surface": "#111814", "bg_raised": "#161E19",
    "bg_inset": "#0E1512", "bg_hover": "#1C2620",
    # Borders
    "border": "#232E27", "border_strong": "#2C3A31", "divider": "#1A231D",
    # Text
    "text_hi": "#F2F5F3", "text_body": "#C7D1CB", "text_mid": "#9AA8A0",
    "text_low": "#7E8C84", "text_faint": "#5E6B64",
    # Accents — ONE system (green=primary/positive, gold=premium/CTA,
    # red=danger, blue=picks/info, purple=future)
    "green": "#2FA866", "green_bright": "#34D17E", "gold": "#E6B422",
    "red": "#E5484D", "blue": "#38BDF8", "purple": "#A78BFA",
    # Pill fills (dark tint) + text
    "pill_green_bg": "#10301F", "pill_green_fg": "#34D17E",
    "pill_gold_bg": "#2E2A0E", "pill_gold_fg": "#E6B422",
    "pill_red_bg": "#331517", "pill_red_fg": "#F2787C",
    "pill_blue_bg": "#0E2A38", "pill_blue_fg": "#7FD3F7",
    "pill_purple_bg": "#231A3A", "pill_purple_fg": "#C4B5FD",
    # Highlighted "your team" row
    "row_you_bg": "#0E1F16", "row_you_border": "#1C4B30",
    # Text on colored buttons
    "on_green": "#04210F", "on_gold": "#2A1E02",
}


def inject_theme():
    """Inject Google fonts, the design-token :root block, and the reusable
    helper classes (.eyebrow / .dlh-card / .pill.*) once at startup. This is
    the single source of truth for the dark "astroturf" look; keep it in sync
    with .streamlit/config.toml and the Python TOKENS dict above."""
    st.markdown("""
<style>
/* Load fonts with @import here, NOT a link tag before this block. Streamlit's
   CommonMark markdown keeps a raw-HTML block that opens with a style tag intact
   to its closing tag (blank lines and all); a block opening with a link tag
   instead ends at the first blank line and spills the rest of this CSS onto the
   page as text. Also: never write the literal closing style tag in a comment
   here, or the block ends early and leaks the same way. */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');
/* ── Design tokens — single source of truth (CSS side) ──────────────────────── */
:root{
  /* Surfaces */
  --bg-page:#0A0F0C; --bg-surface:#111814; --bg-raised:#161E19;
  --bg-inset:#0E1512; --bg-hover:#1C2620;
  /* Borders */
  --border:#232E27; --border-strong:#2C3A31; --divider:#1A231D;
  /* Text */
  --text-hi:#F2F5F3; --text-body:#C7D1CB; --text-mid:#9AA8A0;
  --text-low:#7E8C84; --text-faint:#5E6B64;
  /* Accents — ONE system */
  --green:#2FA866; --green-bright:#34D17E; --gold:#E6B422;
  --red:#E5484D; --blue:#38BDF8; --purple:#A78BFA;
  /* Pill fills + text */
  --pill-green-bg:#10301F; --pill-green-fg:#34D17E;
  --pill-gold-bg:#2E2A0E; --pill-gold-fg:#E6B422;
  --pill-red-bg:#331517; --pill-red-fg:#F2787C;
  --pill-blue-bg:#0E2A38; --pill-blue-fg:#7FD3F7;
  --pill-purple-bg:#231A3A; --pill-purple-fg:#C4B5FD;
  /* Highlighted "your team" row */
  --row-you-bg:#0E1F16; --row-you-border:#1C4B30;
  /* Text on colored buttons */
  --on-green:#04210F; --on-gold:#2A1E02;
  /* Radius */
  --r-card:14px; --r-row:10px; --r-btn:10px; --r-chip:8px;
}

html, body, .stApp, [class*="css"]{
  font-family:'Inter',ui-sans-serif,system-ui,-apple-system,sans-serif;
}
h1,h2,h3,h4,[data-testid="stMetricValue"]{
  font-family:'Space Grotesk','Inter',sans-serif; letter-spacing:-0.01em;
}
h1{ font-weight:700; } h2,h3{ font-weight:600; }

/* ── Hide Streamlit chrome — only the noise (deploy / menu / status / footer /
   decoration). Do NOT hide the whole toolbar/header: the sidebar-expand control
   (stExpandSidebar) lives up there, and hiding stToolbar is what broke "reopen
   sidebar" in Safari + Chrome (you could collapse but not expand). ──────────── */
[data-testid="stToolbarActions"], [data-testid="stMainMenu"],
[data-testid="stAppDeployButton"], [data-testid="stStatusWidget"],
[data-testid="stDecoration"], footer{
  display:none !important;
}
[data-testid="stHeader"]{ background:transparent; }
/* Belt-and-suspenders: always keep the collapsed-sidebar expand control usable */
[data-testid="stExpandSidebar"]{
  display:flex !important; visibility:visible !important; opacity:1 !important;
}

/* ── Layout breathing room ──────────────────────────────────────────────────── */
.block-container{ padding-top:2.2rem; padding-bottom:3rem; max-width:1500px; }
h1{ margin-bottom:.1em; }

/* ── Metric cards — token surface + green→gold accent rail ──────────────────── */
[data-testid="stMetric"]{
  position:relative; overflow:hidden;
  background:var(--bg-surface);
  border:1px solid var(--border); border-radius:var(--r-card);
  padding:15px 18px 13px 21px; box-shadow:0 2px 10px rgba(0,0,0,.28);
  transition:border-color .15s ease, transform .1s ease;
}
[data-testid="stMetric"]::after{
  content:""; position:absolute; left:0; top:0; bottom:0; width:4px;
  background:linear-gradient(180deg,var(--green),var(--gold));
}
[data-testid="stMetric"]:hover{ border-color:var(--border-strong); transform:translateY(-1px); }
[data-testid="stMetricLabel"]{
  color:var(--text-low) !important; font-weight:600;
  text-transform:uppercase; letter-spacing:.08em; font-size:.72rem;
}
[data-testid="stMetricValue"]{ color:var(--text-hi) !important; font-weight:600; }

/* ── Buttons — primary is green, not coral ──────────────────────────────────── */
.stButton>button, .stDownloadButton>button{
  border-radius:var(--r-btn); font-weight:600;
  transition:transform .04s ease, box-shadow .15s ease, border-color .15s ease;
}
.stButton>button:hover{ border-color:var(--green); }
.stButton>button:active{ transform:translateY(1px); }
button[kind="primary"]{ background:var(--green); color:var(--on-green); border:0;
  box-shadow:0 2px 8px rgba(47,168,102,.22); }
button[kind="primary"]:hover{ box-shadow:0 5px 18px rgba(47,168,102,.4); transform:translateY(-1px); }

/* ── Tabs — segmented "sub-menu" pill bar (reads clearly as nav, not text) ───── */
.stTabs [data-baseweb="tab-list"]{
  gap:4px; background:var(--bg-surface); border:1px solid var(--border);
  border-radius:12px; padding:5px; margin-bottom:10px;
  display:inline-flex; flex-wrap:wrap;
}
.stTabs [data-baseweb="tab"]{
  height:auto; border-radius:9px; padding:8px 16px !important;
  background:transparent; color:var(--text-mid); font-weight:600;
  transition:background .12s ease, color .12s ease;
}
.stTabs [data-baseweb="tab"] p{ font-weight:600; font-size:.95rem; }
.stTabs [data-baseweb="tab"]:hover{ background:rgba(255,255,255,.05); color:var(--text-hi); }
.stTabs [aria-selected="true"]{ background:var(--green) !important; color:var(--on-green) !important; }
.stTabs [aria-selected="true"] p{ color:var(--on-green) !important; font-weight:700; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"]{ display:none !important; }

/* ── Sidebar nav: radio → pill list with a green active rail ────────────────── */
[data-testid="stSidebar"] [role="radiogroup"]{ gap:1px; }
[data-testid="stSidebar"] [role="radiogroup"] label{
  border-radius:9px; padding:7px 11px; margin:1px 0; width:100%;
  cursor:pointer; transition:background .12s ease;
}
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child{ display:none; } /* hide radio dot */
[data-testid="stSidebar"] [role="radiogroup"] label:hover{ background:rgba(255,255,255,.05); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){
  background:var(--row-you-bg); box-shadow:inset 3px 0 0 var(--green);
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p{
  color:var(--green-bright) !important; font-weight:700;
}

/* ── Surfaces: dataframes / expanders / inputs get the rounded, bordered look ── */
[data-testid="stDataFrame"]{ border-radius:12px; overflow:hidden; }
[data-testid="stExpander"]{ border-radius:12px; }
hr{ border-color:var(--border); }

/* ── Reusable redesign components (eyebrow / card / status pills) ───────────── */
.eyebrow{ font:600 12px/1 'Inter',sans-serif; letter-spacing:2px;
  text-transform:uppercase; color:var(--text-low); }
.dlh-card{ background:var(--bg-surface); border:1px solid var(--border);
  border-radius:var(--r-card); padding:24px; }
.pill{ display:inline-block; padding:4px 12px; border-radius:999px;
  font:600 12px/1.6 'Inter',sans-serif; }
.pill.green{ background:var(--pill-green-bg); color:var(--pill-green-fg); }
.pill.gold{ background:var(--pill-gold-bg); color:var(--pill-gold-fg); }
.pill.red{ background:var(--pill-red-bg); color:var(--pill-red-fg); }
.pill.blue{ background:var(--pill-blue-bg); color:var(--pill-blue-fg); }
.pill.purple{ background:var(--pill-purple-bg); color:var(--pill-purple-fg); }

/* ── Draft Room war-room: pulsing dot + live-state pills ────────────────────── */
@keyframes dlh-pulse{ 0%{transform:scale(1);opacity:1;} 50%{transform:scale(1.6);opacity:.35;} 100%{transform:scale(1);opacity:1;} }
@keyframes dlh-glow{ 0%,100%{opacity:1;} 50%{opacity:.55;} }
.dlh-dot{ display:inline-block; width:9px; height:9px; border-radius:50%;
  background:var(--gold); animation:dlh-pulse 1.3s ease-in-out infinite; }
.dlh-dot.green{ background:var(--green-bright); }
.dlh-live-pill{ animation:dlh-glow 1.3s ease-in-out infinite; }
</style>
""", unsafe_allow_html=True)


inject_theme()

# ── Persistence — all settings route through _store_get/_store_set (below):
#   Supabase per-user when signed in, session-state when a guest.
#   Keys: favorites · league_prefs:<id> · tags:<id> · draft:<id> · last_league
def load_draft_selections(league_id):
    return _store_get(f"draft:{league_id}", {})

def save_draft_selections(league_id, selections):
    _store_set(f"draft:{league_id}", selections)

def clear_draft_selections(league_id):
    _store_set(f"draft:{league_id}", {})

def load_league_prefs(league_id):
    """Per-league preferences ({'team': ..., 'value_source': ...})."""
    return _store_get(f"league_prefs:{league_id}", {})

def save_league_prefs(league_id, **updates):
    """Merge updates into one league's preferences. None values are removed."""
    lp = dict(load_league_prefs(league_id))
    for k, v in updates.items():
        if v is None:
            lp.pop(k, None)
        else:
            lp[k] = v
    _store_set(f"league_prefs:{league_id}", lp)

def save_last_league(league_id):
    _store_set("last_league", league_id)

def load_last_league():
    return _store_get("last_league", None)

def load_favorites():
    """Favourite player names (set)."""
    return set(_store_get("favorites", []))

def save_favorites(favs):
    _store_set("favorites", sorted(favs))

# ── Player status tags — per league. Collapsed to just the two that drive logic:
#    Trade Block (shopped → powers Suggestions) and Untouchable (never suggested).
#    Sleeper's public API exposes neither a trade block nor favourites, so these
#    stay in-app. (Legacy Keep/Cut tags are migrated out on load.)
TAG_OPTIONS = ["", "Trade Block", "Untouchable"]
TAG_DISPLAY = {
    "Trade Block": "Trade Block",
    "Untouchable": "Untouchable",
}

def _migrate_tags(tags):
    """Collapse the legacy 4-tag set (Untouchable/Keep/Trade/Cut) to the current
    two. Old 'Trade' → 'Trade Block'; 'Keep'/'Cut' are dropped. Idempotent."""
    out = {}
    for name, val in (tags or {}).items():
        if val in ("Trade", "Trade Block"):
            out[name] = "Trade Block"
        elif val == "Untouchable":
            out[name] = "Untouchable"
    return out

def load_player_tags(league_id):
    return _migrate_tags(_store_get(f"tags:{league_id}", {}))

def save_player_tags(league_id, tags):
    _store_set(f"tags:{league_id}", tags)

def plural(n, singular, plural_form=None):
    """'1 player', '2 players', '1 story' — count + correctly-pluralised noun."""
    word = singular if n == 1 else (plural_form or singular + "s")
    return f"{n:,} {word}"

# ── Supabase email sign-in (optional; guest mode when not configured) ─────────
@st.cache_resource(show_spinner=False)
def _sb_auth_client():
    """GoTrue client for email one-time-code sign-in (publishable key).
    Returns None if Supabase isn't configured — the app then runs guest-only."""
    try:
        from supabase import create_client
        url  = st.secrets["SUPABASE_URL"]
        anon = st.secrets.get("SUPABASE_ANON_KEY") or st.secrets["SUPABASE_KEY"]
        return create_client(url, anon)
    except Exception as e:
        print(f"[INFO] Supabase auth not configured ({e}); running guest-only.")
        return None

def auth_available():
    return _sb_auth_client() is not None

def auth_send_code(email):
    """Email a 6-digit sign-in code. Returns (ok, error_message)."""
    c = _sb_auth_client()
    if not c:
        return False, "Sign-in isn't available right now."
    try:
        c.auth.sign_in_with_otp({"email": (email or "").strip(),
                                 "options": {"should_create_user": True}})
        return True, None
    except Exception as e:
        return False, str(e)

def auth_verify_code(email, code):
    """Verify the emailed code. Returns the signed-in email, or None."""
    c = _sb_auth_client()
    if not c:
        return None
    try:
        res = c.auth.verify_otp({"email": (email or "").strip(),
                                 "token": (code or "").strip(), "type": "email"})
        if res and getattr(res, "user", None):
            return res.user.email
    except Exception as e:
        print(f"[WARN] verify_otp failed: {e}")
    return None

# ── Per-user store: Supabase when signed in, session-state when a guest ───────
@st.cache_resource(show_spinner=False)
def _sb_db_client():
    """DB client using the secret key (bypasses RLS). None if not configured."""
    try:
        from supabase import create_client
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        print(f"[INFO] Supabase DB not configured ({e}).")
        return None

def _signed_in():
    return bool(st.session_state.get("auth_email")) and _sb_db_client() is not None

def _store_get(key, default):
    """Read a settings blob: Supabase (signed in) else session-state (guest)."""
    if _signed_in():
        try:
            res = (_sb_db_client().table("user_settings").select("data")
                   .eq("email", st.session_state.auth_email).eq("key", key)
                   .limit(1).execute())
            return res.data[0]["data"] if res.data else default
        except Exception as e:
            print(f"[WARN] store_get {key}: {e}")
            return default
    return st.session_state.get(f"_guest_{key}", default)

def _store_set(key, value):
    """Write a settings blob: Supabase (signed in) else session-state (guest)."""
    if _signed_in():
        try:
            (_sb_db_client().table("user_settings")
             .upsert({"email": st.session_state.auth_email, "key": key, "data": value},
                     on_conflict="email,key").execute())
            return
        except Exception as e:
            print(f"[WARN] store_set {key}: {e}")
            return
    st.session_state[f"_guest_{key}"] = value

def dash_na(df):
    """Display copy where object-column None/NaN render as '—' instead of the
    literal string 'None'. Numeric columns are left alone (NumberColumn shows blank)."""
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].where(df[c].notna(), "—")
    return df

def player_name(p, fallback=""):
    """Return 'First Last' from a Sleeper player dict, or fallback if empty."""
    return f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or fallback

def format_trend(trend):
    """Format a FantasyCalc trend30Day value as '+5', '-3', or '—'."""
    if trend is None:  return "—"
    if trend > 0:      return f"+{trend}"
    return str(trend)


# ── DynastyNerds values fetcher ───────────────────────────────────────────────

DN_CACHE = "dynastynerds_cache.json"

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_dn_values():
    """Fetch DynastyNerds dynasty SuperFlex rankings.
    Parses the DR_DATA JS variable embedded in the dynasty-rankings page.
    Returns {sleeper_id: {value, rank, posRank, trend, rankDelta}} for ~330 players.
    Falls back to disk cache (up to 24h old) if the page is unreachable.
    """
    import json as _json

    # ── Try live fetch ────────────────────────────────────────────────────────
    try:
        resp = requests.get(
            "https://www.dynastynerds.com/dynasty-rankings/",
            headers={"User-Agent": "Mozilla/5.0 (compatible; dynasty-dashboard/1.0)"},
            timeout=20,
        )
        resp.raise_for_status()
        match = re.search(r'var\s+DR_DATA\s*=\s*(\{.*?\});', resp.text, re.DOTALL)
        if not match:
            raise ValueError("DR_DATA block not found in DynastyNerds page")
        data   = _json.loads(match.group(1))
        players_list = data.get("SFLEX") or data.get("PPR") or []
        result = {}
        for p in players_list:
            sid = str(p.get("sleeperId") or "").strip()
            if not sid:
                continue
            result[sid] = {
                "value":     p.get("value"),
                "rank":      p.get("rank"),
                "posRank":   p.get("posRank"),
                "trend":     p.get("trend"),
                "rankDelta": p.get("rankDelta"),
            }
        # Persist to disk cache for fallback
        with open(DN_CACHE, "w") as f:
            _json.dump(result, f)
        return result
    except Exception as e:
        print(f"[WARNING] DynastyNerds live fetch failed: {e}")

    # ── Fallback: disk cache (accept up to 24h old) ───────────────────────────
    if os.path.exists(DN_CACHE):
        age_h = (datetime.now().timestamp() - os.path.getmtime(DN_CACHE)) / 3600
        if age_h < 24:
            print(f"  Using cached DynastyNerds values ({age_h:.1f}h old)")
            with open(DN_CACHE) as f:
                return _json.load(f)

    print("[WARNING] DynastyNerds values unavailable — DN Dynasty source will show no values.")
    return {}


# ── KTC values fetcher ────────────────────────────────────────────────────────

KTC_CACHE = "ktc_cache.json"

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ktc_values():
    """Scrape KTC dynasty SF rankings from the embedded playersArray JS variable.
    Tries requests first (works on Linux/hosted); falls back to subprocess curl,
    which bypasses the LibreSSL TLS incompatibility with KTC's server on macOS.
    Returns {ktcId_str: {name, pos, value (0-10K normalised), rank, posRank}}.
    """
    import json as _json, subprocess as _sub

    _KTC_URL = "https://keeptradecut.com/dynasty-rankings"
    _KTC_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://keeptradecut.com/",
    }

    def _fetch_html():
        try:
            r = requests.get(_KTC_URL, headers=_KTC_HEADERS, timeout=20)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"  KTC via requests failed ({e}); trying curl...")
        r = _sub.run(
            ["curl", "-s", "--max-time", "20",
             "-H", f"User-Agent: {_KTC_HEADERS['User-Agent']}",
             "-H", f"Referer: {_KTC_HEADERS['Referer']}",
             _KTC_URL],
            capture_output=True, text=True, timeout=25,
        )
        if r.returncode != 0:
            raise RuntimeError(f"curl exit {r.returncode}: {r.stderr[:200]}")
        return r.stdout

    try:
        html  = _fetch_html()
        match = re.search(r'var\s+playersArray\s*=\s*(\[.*?\]);', html, re.DOTALL)
        if not match:
            raise ValueError("playersArray not found in KTC page")
        data    = _json.loads(match.group(1))
        max_val = max((p.get("superflexValues") or {}).get("value") or 0 for p in data) or 1
        result  = {}
        for p in data:
            kid = str(p.get("playerID") or "").strip()
            if not kid:
                continue
            sf  = p.get("superflexValues") or {}
            raw = sf.get("value")
            result[kid] = {
                "name":    p.get("playerName"),
                "pos":     p.get("playerPosition"),
                "value":   round(raw / max_val * 10000) if raw is not None else None,
                "rank":    sf.get("rank"),
                "posRank": sf.get("positionalRank"),
            }
        with open(KTC_CACHE, "w") as f:
            _json.dump(result, f)
        return result
    except Exception as e:
        print(f"[WARNING] KTC fetch failed: {e}")
    if os.path.exists(KTC_CACHE):
        age_h = (datetime.now().timestamp() - os.path.getmtime(KTC_CACHE)) / 3600
        if age_h < 24:
            with open(KTC_CACHE) as f:
                return _json.load(f)
    return {}


# ── DynastyProcess values fetcher ─────────────────────────────────────────────

DP_CACHE    = "dp_cache.json"
DP_CW_CACHE = "dp_crosswalk_cache.json"

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_dp_values(num_qbs=2):
    """Fetch DynastyProcess values.csv (weekly) and player-ID crosswalk.
    Format-aware: DP's CSV carries both 1QB and SuperFlex columns, so single-QB
    leagues (num_qbs < 2) read value_1qb/ecr_1qb instead of the 2QB columns.
    Returns (dp_map, cw_ktc_to_sid):
      dp_map        : {sleeper_id: {value, rank, ecr}}
      cw_ktc_to_sid : {ktc_id_str: sleeper_id_str}
    """
    import csv as _csv, io as _io, json as _json
    _val_col = "value_1qb" if num_qbs < 2 else "value_2qb"
    _ecr_col = "ecr_1qb"   if num_qbs < 2 else "ecr_2qb"
    _dp_cache = DP_CACHE.replace(".json", f"_{1 if num_qbs < 2 else 2}qb.json")

    CW_URL  = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
    VAL_URL = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/values.csv"

    _NA = {"", "NA", "na", "nan", "None", "none"}

    cw_fp_to_sid  = {}
    cw_ktc_to_sid = {}
    try:
        cw_resp = requests.get(CW_URL, timeout=20)
        cw_resp.raise_for_status()
        reader = _csv.DictReader(_io.StringIO(cw_resp.text))
        for row in reader:
            sid = str(row.get("sleeper_id") or "").strip()
            fp  = str(row.get("fantasypros_id") or "").strip()
            ktc = str(row.get("ktc_id") or "").strip()
            if sid not in _NA and fp  not in _NA: cw_fp_to_sid[fp]  = sid
            if sid not in _NA and ktc not in _NA: cw_ktc_to_sid[ktc] = sid
        with open(DP_CW_CACHE, "w") as f:
            _json.dump({"fp": cw_fp_to_sid, "ktc": cw_ktc_to_sid}, f)
    except Exception as e:
        print(f"[WARNING] DP crosswalk fetch failed: {e}")
        if os.path.exists(DP_CW_CACHE):
            with open(DP_CW_CACHE) as f:
                _cw = _json.load(f)
                cw_fp_to_sid  = _cw.get("fp", {})
                cw_ktc_to_sid = _cw.get("ktc", {})

    dp_map = {}
    try:
        val_resp = requests.get(VAL_URL, timeout=20)
        val_resp.raise_for_status()
        rows = list(_csv.DictReader(_io.StringIO(val_resp.text)))
        raw_vals = [float(r.get(_val_col) or 0) for r in rows]
        max_val  = max(raw_vals) if raw_vals else 1
        ranked   = sorted(rows, key=lambda r: float(r.get(_val_col) or 0), reverse=True)
        for rank_i, row in enumerate(ranked, 1):
            fp_id = str(row.get("fp_id") or "").strip()
            raw   = row.get(_val_col)
            ecr   = row.get(_ecr_col)
            sid   = cw_fp_to_sid.get(fp_id)
            if not sid or not raw:
                continue
            try:
                dp_map[sid] = {
                    "value": round(float(raw) / max_val * 10000),
                    "rank":  rank_i,
                    "ecr":   float(ecr) if ecr else None,
                }
            except (ValueError, TypeError):
                continue
        with open(_dp_cache, "w") as f:
            _json.dump(dp_map, f)
    except Exception as e:
        print(f"[WARNING] DP values fetch failed: {e}")
        if os.path.exists(_dp_cache):
            age_h = (datetime.now().timestamp() - os.path.getmtime(_dp_cache)) / 3600
            if age_h < 168:
                with open(_dp_cache) as f:
                    dp_map = _json.load(f)

    return dp_map, cw_ktc_to_sid


@st.cache_data(ttl=3600, show_spinner=False)
def _ktc_norm_name(s):
    """Lower-case, strip a trailing generational suffix (Jr./Sr./II–IV)."""
    s = (s or "").strip().lower()
    return re.sub(r'\s+(jr\.?|sr\.?|ii|iii|iv)$', '', s).strip()


def build_ktc_sleeper_map(ktc_by_ktcid, cw_ktc_to_sid, players):
    """Map KTC data to Sleeper player IDs, keyed by Sleeper id.
    Strategy (in order — the crosswalk is trusted FIRST so same-name players resolve
    to the right person):
      1. ID crosswalk (authoritative): dynastyprocess ktc_id→sleeper_id maps each KTC
         player to the exact Sleeper id (~90% coverage).
      2. Name fallback for the KTC players the crosswalk missed — matched against
         Sleeper SKILL players only, skipping ids already claimed in pass 1, and (when
         several Sleeper players share a name) preferring the one whose position matches
         KTC's, is active, and is on an NFL team. This stops a retired/practice-squad
         namesake — or a defender sharing a star's name — from inheriting the value.
    """
    _KTC_SKILL = {"QB", "RB", "WR", "TE"}

    result, claimed = {}, set()
    # Pass 1 — authoritative ID crosswalk
    for kid, d in ktc_by_ktcid.items():
        sid = cw_ktc_to_sid.get(str(kid))
        if sid:
            result[sid] = d
            claimed.add(sid)

    # Index Sleeper SKILL players by normalised name
    sleeper_by_name = {}
    for pid, p in players.items():
        if (p.get("position") or "") not in _KTC_SKILL:
            continue
        nm = _ktc_norm_name(player_name(p))
        if nm:
            sleeper_by_name.setdefault(nm, []).append((pid, p))

    def _best(cands, ktc_pos):
        # Rank candidates: KTC-position match (when KTC carries pos) → active → on-team.
        return sorted(
            cands,
            key=lambda it: (
                1 if (ktc_pos and it[1].get("position") == ktc_pos) else 0,
                1 if it[1].get("active") else 0,
                1 if it[1].get("team") else 0,
            ),
            reverse=True,
        )[0]

    # Pass 2 — name fallback for KTC players not covered by the crosswalk
    for kid, d in ktc_by_ktcid.items():
        if cw_ktc_to_sid.get(str(kid)):
            continue                                   # already mapped authoritatively
        cands = [c for c in sleeper_by_name.get(_ktc_norm_name(d.get("name")), [])
                 if c[0] not in claimed]
        if not cands:
            continue
        best_pid = _best(cands, d.get("pos"))[0]
        result[best_pid] = d
        claimed.add(best_pid)

    return result


def get_active_value(pid, fc_values, val_maps, source):
    """Return normalised player value (0-10K scale) for the active source, or None.
    val_maps = {"dn": dn_map, "ktc": ktc_map, "dp": dp_map}
    """
    fc  = fc_values.get(pid, {})
    dn  = (val_maps or {}).get("dn",  {}).get(pid, {})
    ktc = (val_maps or {}).get("ktc", {}).get(pid, {})
    dp  = (val_maps or {}).get("dp",  {}).get(pid, {})

    def _norm_fc(v):
        return round(v / 10282 * 10000) if v else None

    if source == "FC Dynasty":
        _val = _norm_fc(fc.get("value"))
    elif source == "FC Redraft":            # win-now/seasonal lens — NOT in consensus
        _val = _norm_fc(fc.get("redraftValue"))
    elif source == "DN Dynasty":
        _val = dn.get("value")
    elif source == "KTC":
        _val = ktc.get("value")
    elif source == "DP Values":
        _val = dp.get("value")
    else:  # Consensus Avg — dynasty sources only (redraft excluded by design)
        vals = [v for v in [
            _norm_fc(fc.get("value")),
            dn.get("value"),
            ktc.get("value"),
            dp.get("value"),
        ] if v is not None and v > 0]
        _val = int(sum(vals) / len(vals)) if vals else None

    # Positional Weighting — league-scoring tilt (e.g. TE-premium) applied app-wide via
    # module globals set after the league loads. Picks / unknown positions stay at 1.0.
    _w = globals().get("_POS_WEIGHTS")
    if _w and _val:
        _wm = _w.get(globals().get("_PID_POS", {}).get(pid))
        if _wm and _wm != 1.0:
            _val = round(_val * _wm)
    return _val


def get_active_rank(pid, fc_values, val_maps, source):
    """Return player rank for the active source, or None."""
    fc  = fc_values.get(pid, {})
    dn  = (val_maps or {}).get("dn",  {}).get(pid, {})
    ktc = (val_maps or {}).get("ktc", {}).get(pid, {})
    dp  = (val_maps or {}).get("dp",  {}).get(pid, {})

    if source == "FC Dynasty":
        return fc.get("overallRank")
    elif source == "FC Redraft":
        return fc.get("redraftRank")
    elif source == "DN Dynasty":
        return dn.get("rank")
    elif source == "KTC":
        return ktc.get("rank")
    elif source == "DP Values":
        return dp.get("rank")
    else:  # Consensus Avg
        ranks = [r for r in [
            fc.get("overallRank"),
            dn.get("rank"),
            ktc.get("rank"),
            dp.get("rank"),
        ] if r is not None]
        return int(sum(ranks) / len(ranks)) if ranks else None


def value_col_label(source):
    return {
        "FC Dynasty":    "FC D Value",
        "FC Redraft":    "FC Redraft",
        "DN Dynasty":    "DN Value",
        "KTC":           "KTC Value",
        "DP Values":     "DP Value",
        "Consensus Avg": "Cons. Avg",
    }.get(source, "Value")


# Friendly, un-abbreviated names for the value-source dropdowns. The stored
# session key stays the short form ("FC Dynasty"); only the displayed label changes.
VALUE_SOURCE_LABELS = {
    "FC Dynasty":    "FantasyCalc",
    "FC Redraft":    "FantasyCalc (Redraft)",
    "DN Dynasty":    "DynastyNerds",
    "KTC":           "KeepTradeCut",
    "DP Values":     "DynastyProcess",
    "Consensus Avg": "Consensus Average",
}

def vs_label(source):
    return VALUE_SOURCE_LABELS.get(source, source)

# FantasyCalc Redraft = win-now/seasonal values (no dynasty youth premium). A
# standalone lens for redraft / brand-new leagues; deliberately NOT blended into
# Consensus Average (its meaning differs from the dynasty sources).
REDRAFT_SOURCE = "FC Redraft"

def redraft_note(source):
    return ("**FantasyCalc (Redraft)** — win-now, single-season values (no dynasty "
            "youth premium). Best for **redraft or brand-new leagues**.") if source == REDRAFT_SOURCE else None


# FantasyCalc (API) + DynastyProcess (open data) are licence-clean → public.
# KeepTradeCut + DynastyNerds are scrapes held back pending permission: shown
# only to the owner (OWNER_EMAILS secret) AND only where they're format-correct
# (SuperFlex / 2QB — they're ~1.9x QB-inflated in 1-QB leagues).
ALL_VALUE_SOURCES    = ["FC Dynasty", "FC Redraft", "DN Dynasty", "KTC", "DP Values", "Consensus Avg"]
PUBLIC_VALUE_SOURCES = ["FC Dynasty", "FC Redraft", "DP Values", "Consensus Avg"]


def _is_owner():
    """True when the signed-in email is listed in the OWNER_EMAILS secret."""
    try:
        raw = st.secrets.get("OWNER_EMAILS", "")
    except Exception:
        raw = ""
    owners = {e.strip().lower() for e in (raw or "").split(",") if e.strip()}
    em = (st.session_state.get("auth_email") or "").strip().lower()
    return bool(em) and em in owners


def available_value_sources(num_qbs, owner=False):
    """Value sources offered for this league. Public = FantasyCalc + DynastyProcess
    + Consensus. KTC/DN are owner-only and SuperFlex-only, so they appear only when
    owner and num_qbs >= 2 (in 1-QB they'd be ~1.9x QB-inflated)."""
    if owner and (num_qbs is None or num_qbs >= 2):
        return list(ALL_VALUE_SOURCES)
    return list(PUBLIC_VALUE_SOURCES)


# ── League format helpers — Sleeper avatar tile + KTC-style format badges ─────
IDP_SLOTS = {"DL", "LB", "DB", "IDP_FLEX", "DE", "DT", "CB", "S", "SS", "FS", "EDGE"}

def league_avatar_url(league, thumb=True):
    av = league.get("avatar")
    if not av:
        return None
    return f"https://sleepercdn.com/avatars/{'thumbs/' if thumb else ''}{av}"

def user_avatar_url(user, thumb=True):
    """A team owner's avatar URL: their custom team logo (metadata.avatar — already a
    full sleepercdn URL) if set, else their Sleeper profile avatar, else None."""
    if not user:
        return None
    md_av = (user.get("metadata") or {}).get("avatar")
    if md_av:
        return md_av
    av = user.get("avatar")
    if av:
        return f"https://sleepercdn.com/avatars/{'thumbs/' if thumb else ''}{av}"
    return None

def user_avatar_tag(user, fallback_name="?", px=40, radius=10):
    """HTML for a team owner's Sleeper avatar tile (initial-tile fallback)."""
    _url  = user_avatar_url(user)
    _name = _html.escape(fallback_name or "?")
    if _url:
        return (f'<img src="{_html.escape(_url)}" alt="" style="width:{px}px;height:{px}px;'
                f'border-radius:{radius}px;object-fit:cover;border:1px solid var(--border);flex:0 0 auto;">')
    return (f'<div style="width:{px}px;height:{px}px;border-radius:{radius}px;flex:0 0 auto;'
            f'background:linear-gradient(135deg,#1f6f43,#14532d);display:flex;align-items:center;'
            f'justify-content:center;font-weight:600;font-size:{px*0.42:.0f}px;color:#fff;">'
            f'{(_name[:1] or "?").upper()}</div>')

def league_format_badges(league):
    """KTC-style chips: teams · QB format · starters · PPR · TE-prem · IDP."""
    rp = league.get("roster_positions") or []
    sc = league.get("scoring_settings") or {}
    teams = league.get("total_rosters") or "?"
    if "SUPER_FLEX" in rp:    qb = "Superflex"
    elif rp.count("QB") >= 2: qb = "2QB"
    else:                     qb = "1QB"
    starters = len([p for p in rp if p not in ("BN", "TAXI", "IR")])
    rec = sc.get("rec", 0) or 0
    ppr = "PPR" if rec >= 1 else ("Half-PPR" if rec >= 0.5 else "Standard")
    badges = [f"{teams} teams", qb, f"Start {starters}", ppr]
    if sc.get("bonus_rec_te"): badges.append("TE Premium")
    if set(rp) & IDP_SLOTS:    badges.append("IDP")
    return badges

def league_avatar_tag(league, px=40, radius=10):
    """HTML for the league's Sleeper avatar tile (falls back to a green initial
    tile when the league has no avatar). Reused by the sidebar, setup, and the
    main page title."""
    _url  = league_avatar_url(league)
    _name = _html.escape(league.get("name", "Dynasty League"))
    if _url:
        return (f'<img src="{_url}" alt="" style="width:{px}px;height:{px}px;'
                f'border-radius:{radius}px;object-fit:cover;border:1px solid var(--border);flex:0 0 auto;">')
    return (f'<div style="width:{px}px;height:{px}px;border-radius:{radius}px;flex:0 0 auto;'
            f'background:linear-gradient(135deg,#1f6f43,#14532d);display:flex;align-items:center;'
            f'justify-content:center;font-weight:600;font-size:{px*0.42:.0f}px;color:#fff;">'
            f'{(_name[:1] or "?").upper()}</div>')

def render_league_header(league, name_size="1.05rem"):
    """Avatar tile + league name (replaces the football-emoji title)."""
    _name = _html.escape(league.get("name", "Dynasty League"))
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:11px;margin-bottom:2px;">{league_avatar_tag(league)}'
        f'<div style="font-weight:600;font-size:{name_size};line-height:1.15;">{_name}</div></div>',
        unsafe_allow_html=True,
    )

def render_league_title(league):
    """Big page title with the league avatar tile beside the name (h1-styled)."""
    _name = _html.escape(league.get("name", "Dynasty League"))
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:15px;margin:0 0 .35rem;">'
        f'{league_avatar_tag(league, px=54, radius=14)}'
        f'<h1 style="margin:0;">{_name}</h1></div>',
        unsafe_allow_html=True,
    )

def render_league_badges(league):
    pills = "".join(
        f'<span style="display:inline-block;background:#1b212c;border:1px solid #2a3344;'
        f'border-radius:6px;padding:2px 8px;margin:3px 5px 0 0;font-size:.72rem;'
        f'color:#c7cdd6;">{_html.escape(str(b))}</span>'
        for b in league_format_badges(league)
    )
    st.markdown(f'<div style="margin:2px 0 4px;">{pills}</div>', unsafe_allow_html=True)


POSITION_COLORS = {
    "QB":  "#D6E4F0", "RB":  "#D5F5E3", "WR":  "#FEF9E7",
    "TE":  "#F9EBEA", "K":   "#F2F3F4", "DEF": "#EAF2FF",
    "DL":  "#F5EEF8", "LB":  "#F5EEF8", "DB":  "#F5EEF8",
}

# Shared column formatting — reference these in st.dataframe column_config instead of redefining inline
COL_CFG = {
    "Value":                        st.column_config.NumberColumn(format="%d"),
    "Rank":                         st.column_config.NumberColumn(format="%d"),
    "Pos Rank":                     st.column_config.NumberColumn(format="%d"),
    "League Avg":                   st.column_config.NumberColumn(format="%d"),
    "Pick FC Value":                st.column_config.NumberColumn(format="%d"),
    "Rookie FC Val":                st.column_config.NumberColumn(format="%d"),
    f"{STATS_SEASON} Pts":         st.column_config.NumberColumn(format="%.1f"),
    "Avg Pts":                      st.column_config.NumberColumn(format="%.1f"),
    "Cons. Avg":                    st.column_config.NumberColumn(format="%d"),
    "Points":                       st.column_config.NumberColumn(format="%.2f"),
}


def fav_grid(dv, name_col, editor_key, col_cfg=None, styler_fn=None):
    """Render a grid with a clickable Fav favourites column (first column).
    Favourites are keyed by player display name, shared across all grids,
    and persisted to favorites.json. Only the Fav column is editable.
    styler_fn: optional fn(df) -> Styler for row highlighting (applies to
    non-editable columns only, per st.data_editor behaviour)."""
    favs = st.session_state.favorites
    dv = dv.copy().reset_index(drop=True)
    if dv.empty:
        st.info("No players match your filters. Try clearing the search or changing position.")
        return
    dv = dash_na(dv)   # object-column None/NaN → '—' (no literal 'None')
    dv.insert(0, "Fav", dv[name_col].map(lambda n: n in favs))
    cfg = {**(col_cfg or {}), "Fav": st.column_config.CheckboxColumn("Fav", default=False)}
    disabled = [c for c in dv.columns if c != "Fav"]
    data = styler_fn(dv) if styler_fn else dv
    # Wrap in a form so ticking stars batches into ONE save (no per-cell full-page
    # rerun / "jump"). Fixed height stops the grid reflowing the page. Versioned key
    # keeps favourites bound to the player, never the row index, across re-sorts.
    _ver = st.session_state.get("_fav_ver", 0)
    _h = min(560, 56 + 35 * (len(dv) + 1))
    with st.form(f"{editor_key}_form_{_ver}", border=False):
        edited = st.data_editor(
            data, width="stretch", hide_index=True, height=_h,
            key=f"{editor_key}_{_ver}", column_config=cfg, disabled=disabled,
        )
        _submitted = st.form_submit_button("Save favourites", type="primary", icon=":material/save:")
    if _submitted:
        new_favs = set(favs)
        for _, row in edited.iterrows():
            if row["Fav"]:
                new_favs.add(row[name_col])
            else:
                new_favs.discard(row[name_col])
        if new_favs != favs:
            st.session_state.favorites = new_favs
            save_favorites(new_favs)
            st.session_state._fav_ver = _ver + 1   # rotate editor → drop stale row deltas
            st.session_state._toast_msg = f"{plural(len(new_favs), 'favourite')} saved"
            st.rerun()


def tag_editor(roster_players, editor_key):
    """Render an editable Status column for a list of roster players.
    roster_players: list of dicts with 'name', 'pos', 'value'.
    Persists {player_name: status} to st.session_state.player_tags (per league).
    Uses the same versioned-key trick as fav_grid to avoid positional edit smear."""
    tags = st.session_state.player_tags
    rows = [{
        "Player": p["name"],
        "Pos":    p.get("pos", "—"),
        "Value":  p.get("value"),
        "Status": tags.get(p["name"], ""),
    } for p in roster_players]
    if not rows:
        st.info("No valued players found for this team.")
        return
    df = pd.DataFrame(rows)
    _tver = st.session_state.get("_tag_ver", 0)
    _h = min(560, 56 + 35 * (len(rows) + 1))
    # Form batches all status edits into one save — no per-cell rerun / page jump.
    with st.form(f"{editor_key}_form_{_tver}", border=False):
        edited = st.data_editor(
            df, width="stretch", hide_index=True, height=_h,
            key=f"{editor_key}_{_tver}",
            column_config={
                "Value":  COL_CFG["Value"],
                "Status": st.column_config.SelectboxColumn(
                    "Status", options=TAG_OPTIONS, default="",
                    help="Trade Block = actively shopping (drives Suggestions) · "
                         "Untouchable = never suggested in trades",
                ),
            },
            disabled=["Player", "Pos", "Value"],
        )
        _submitted = st.form_submit_button("Save tags", type="primary", icon=":material/save:")
    if _submitted:
        new_tags = dict(tags)
        for _, r in edited.iterrows():
            nm, stt = r["Player"], (r["Status"] or "")
            if stt:
                new_tags[nm] = stt
            elif nm in new_tags:
                del new_tags[nm]
        if new_tags != tags:
            st.session_state.player_tags = new_tags
            save_player_tags(st.session_state.league_id, new_tags)
            st.session_state._tag_ver = _tver + 1
            # Confirm what landed — the native dropdown can silently no-op on a misclick
            _counts = {}
            for _v in new_tags.values():
                _counts[_v] = _counts.get(_v, 0) + 1
            _summary = ", ".join(f"{_n} {TAG_DISPLAY.get(_k, _k)}"
                                 for _k, _n in _counts.items()) or "none"
            st.session_state._toast_msg = f"Tags saved · {_summary}"
            st.rerun()

# ── Data loading (cached) ─────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_all_data(league_id):
    league, rosters, users, traded_ownership, drafts, slot_map = fetch_league_data(league_id)
    players = fetch_players()
    raw_stats = fetch_season_stats()
    # FC values fetched for THIS league's shape (QB count, PPR, team count)
    num_qbs, ppr, num_teams = derive_league_shape(league)
    fc_values, fc_rookies, fc_picks = fetch_fantasycalc(num_qbs, ppr, num_teams)
    scoring = league.get("scoring_settings") or {}

    player_pts = {}
    all_pts = {}
    for pid, p in players.items():
        pos = p.get("position") or "—"
        pts = compute_fantasy_pts(raw_stats.get(pid), scoring)
        player_pts[pid] = pts
        all_pts[pid] = (pos, pts)

    pos_ranks = build_pos_ranks(all_pts)
    return (league, rosters, users, traded_ownership, drafts, slot_map,
            players, player_pts, pos_ranks, fc_values, fc_rookies, fc_picks, scoring)


@st.cache_data(ttl=1800, show_spinner=False)
def load_trending():
    adds  = get(f"{BASE}/players/nfl/trending/add?lookback_hours={TREND_LOOKBACK}&limit=25")
    drops = get(f"{BASE}/players/nfl/trending/drop?lookback_hours={TREND_LOOKBACK}&limit=25")
    return adds, drops


@st.cache_data(ttl=600, show_spinner=False)
def fetch_user_leagues(handle):
    """Resolve a Sleeper username to their NFL leagues (most recent season with any).
    Returns list of {league_id, name, season, total_rosters}; [] if not found."""
    handle = (handle or "").strip()
    if not handle:
        return []
    try:
        user = get(f"{BASE}/user/{handle}")
        uid  = user.get("user_id") if user else None
        if not uid:
            return []
        for _yr in (datetime.now().year, datetime.now().year - 1):
            lgs = get(f"{BASE}/user/{uid}/leagues/nfl/{_yr}")
            if lgs:
                return [{"league_id": l["league_id"], "name": l.get("name", "League"),
                         "season": l.get("season"), "total_rosters": l.get("total_rosters")}
                        for l in lgs]
        return []
    except Exception as e:
        print(f"[WARN] fetch_user_leagues({handle}): {e}")
        return []


# ── DataFrame builders ────────────────────────────────────────────────────────

def build_rosters_df(rosters, users, players, player_pts, pos_ranks, fc_values, val_maps=None, value_source="FC Dynasty"):
    user_map = {u["user_id"]: u for u in users}
    rows = []
    for roster in sorted(rosters, key=lambda r: r["roster_id"]):
        owner_id  = roster.get("owner_id") or ""
        user      = user_map.get(owner_id, {})
        team_name = (user.get("metadata") or {}).get("team_name") or user.get("display_name") or f"Team {roster['roster_id']}"
        owner_name = user.get("display_name") or "—"
        player_ids = roster.get("players") or []
        starters   = set(roster.get("starters") or [])
        taxi       = set(roster.get("taxi") or [])

        sort_key = lambda pid: (players.get(pid, {}).get("position", "ZZ"), players.get(pid, {}).get("last_name", ""))
        for pid in sorted(player_ids, key=sort_key):
            p    = players.get(pid, {})
            name = player_name(p, fallback=pid)
            pos  = p.get("position") or "—"
            if pos == "K":
                continue
            exp  = p.get("years_exp")
            exp  = "Rookie" if exp == 0 else (str(exp) + "yr" if exp else "—")
            slot = "Starter" if pid in starters else ("Taxi" if pid in taxi else "Bench")
            fc   = fc_values.get(pid, {})
            trend = fc.get("trend30Day")
            trend_disp = format_trend(trend)

            dc_pos   = p.get("depth_chart_position") or ""
            dc_order = p.get("depth_chart_order")
            if dc_pos and dc_order is not None:
                roster_spot = f"{dc_pos}{dc_order}"
            else:
                roster_spot = "—"

            val  = get_active_value(pid, fc_values, val_maps or {}, value_source)
            rank = get_active_rank(pid, fc_values, val_maps or {}, value_source)

            rows.append({
                "Team":          team_name,
                "Owner":         owner_name,
                "Slot":          slot,
                "Player":        name,
                "Pos":           pos,
                "NFL Team":      p.get("team") or "FA",
                "Roster Spot":   roster_spot,
                "Age":           p.get("age") or "—",
                "Exp":           exp,
                "Status":        p.get("injury_status") or p.get("status") or "Active",
                f"{STATS_SEASON} Pts": player_pts.get(pid),
                "Pos Rank":      pos_ranks.get(pid),
                "Value":         val,
                "Rank":          rank,
                "30d Trend":     trend_disp,
                "Tier":          fc.get("tier"),
                # All sources side-by-side (merged in from the old Players page)
                "FC D Value":    get_active_value(pid, fc_values, val_maps or {}, "FC Dynasty"),
                "DN Value":      get_active_value(pid, fc_values, val_maps or {}, "DN Dynasty"),
                "KTC Value":     get_active_value(pid, fc_values, val_maps or {}, "KTC"),
                "DP Value":      get_active_value(pid, fc_values, val_maps or {}, "DP Values"),
                "_cons_avg":     get_active_value(pid, fc_values, val_maps or {}, "Consensus Avg"),
            })
    return pd.DataFrame(rows)


def build_picks_df(rosters, users, traded_ownership, drafts, slot_map, fc_picks):
    num_rounds   = drafts[0].get("settings", {}).get("rounds", 5) if drafts else 5
    current_year = datetime.now().year
    seasons      = [str(current_year + i) for i in range(PICK_SEASONS)]

    ownership = {}
    for r in rosters:
        rid = r["roster_id"]
        for season in seasons:
            for rnd in range(1, num_rounds + 1):
                ownership[(season, rnd, rid)] = rid
    for (season, rnd, orig_rid), current_rid in traded_ownership.items():
        key = (season, rnd, orig_rid)
        if key in ownership:
            ownership[key] = current_rid

    user_map    = {u["user_id"]: u for u in users}
    roster_info = {}
    for r in rosters:
        owner_id  = r.get("owner_id") or ""
        user      = user_map.get(owner_id, {})
        team_name = (user.get("metadata") or {}).get("team_name") or user.get("display_name") or f"Team {r['roster_id']}"
        roster_info[r["roster_id"]] = (team_name, user.get("display_name") or "—")

    rows = []
    for (season, rnd, orig_rid), current_rid in ownership.items():
        orig_team             = roster_info.get(orig_rid, (f"Team {orig_rid}", "—"))[0]
        curr_team, curr_owner = roster_info.get(current_rid, (f"Team {current_rid}", "—"))

        season_slots = slot_map.get(season, {})
        if season_slots and orig_rid in season_slots:
            slot       = season_slots[orig_rid]
            pick_label = f"{rnd}.{slot:02d}"
            fc_key     = f"{season} Pick {rnd}.{slot:02d}"
        else:
            pick_label = f"{season} Round {rnd}"
            fc_key     = None

        fc_val = fc_picks.get(fc_key) if fc_key else None

        rows.append({
            "Team":          curr_team,
            "Owner":         curr_owner,
            "Season":        season,
            "Round":         rnd,
            "Pick":          pick_label,
            "Original Team": orig_team,
            "Via Trade":     "Yes" if orig_rid != current_rid else "No",
            "Value":      fc_val,
        })

    def _pick_slot_sort(v):
        try:
            parts = str(v).split(".")
            return int(parts[1]) if len(parts) >= 2 else 99
        except (ValueError, IndexError):
            return 99

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(
            by=["Team", "Season", "Round", "Pick"],
            key=lambda col: col.apply(_pick_slot_sort) if col.name == "Pick" else col,
        )
    return df


def build_fa_df(rosters, players, player_pts, pos_ranks, fc_values, val_maps=None, value_source="FC Dynasty"):
    rostered = set()
    for r in rosters:
        rostered.update(r.get("players") or [])
        rostered.update(r.get("taxi") or [])

    pos_order = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "K": 4, "DEF": 5, "DL": 6, "LB": 7, "DB": 8}
    rows = []
    for pid, p in players.items():
        if pid in rostered:
            continue
        pos = p.get("position") or ""
        if pos not in DYNASTY_POSITIONS or pos == "K":
            continue
        if p.get("active") is False and not p.get("team"):
            continue

        name  = player_name(p, fallback=pid)
        exp   = p.get("years_exp")
        exp   = "Rookie" if exp == 0 else (str(exp) + "yr" if exp else "—")
        fc    = fc_values.get(pid, {})
        fc_val = fc.get("value") or 0   # keep for sort key
        val    = get_active_value(pid, fc_values, val_maps or {}, value_source) or 0
        trend = fc.get("trend30Day")
        trend_disp = format_trend(trend)

        rows.append({
            "Player":        name,
            "Pos":           pos,
            "NFL Team":      p.get("team") or "FA/UFA",
            "Age":           p.get("age") or None,
            "Exp":           exp,
            "Status":        p.get("injury_status") or p.get("status") or "Active",
            f"{STATS_SEASON} Pts": player_pts.get(pid),
            "Pos Rank":      pos_ranks.get(pid),
            "Value":         val or None,
            "Rank":          get_active_rank(pid, fc_values, val_maps or {}, value_source),
            "30d Trend":     trend_disp,
            "Tier":          fc.get("tier"),
            "Injury Notes":  p.get("injury_notes") or "—",
            "_cons_avg":     get_active_value(pid, fc_values, val_maps or {}, "Consensus Avg"),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(
            by=["Pos", "Value"],
            key=lambda col: col.map(pos_order).fillna(99) if col.name == "Pos"
                            else col.fillna(0),
            ascending=[True, False],
        )
    return df


def build_rookies_df(fc_rookies, rosters, fc_values=None, val_maps=None, value_source="FC Dynasty"):
    rostered = set()
    for r in rosters:
        rostered.update(r.get("players") or [])
        rostered.update(r.get("taxi") or [])

    rows = []
    for r in fc_rookies:
        sid        = r.get("sleeperId")
        trend      = r.get("trend30Day")
        trend_disp = format_trend(trend)
        val  = get_active_value(sid, fc_values or {}, val_maps or {}, value_source) if sid else r.get("value")
        rank = get_active_rank( sid, fc_values or {}, val_maps or {}, value_source) if sid else r.get("overallRank")
        rows.append({
            "Rank":     rank,
            "Player":   r.get("name", ""),
            "Pos":      r.get("position", "—"),
            "NFL Team": r.get("team", "Prospect"),
            "Age":      int(r["age"]) if r.get("age") else None,
            "Value":    val,
            "Pos Rank": r.get("positionRank"),
            "30d Trend":trend_disp,
            "Tier":     r.get("tier"),
            "On Roster":"Yes" if sid in rostered else "No",
        })
    return pd.DataFrame(rows)


def build_scoring_df(scoring):
    cat_order = ["Passing", "Rushing", "Receiving", "Misc Off", "Kicking", "Team DEF", "IDP", "Other"]
    rows = []
    for key, pts in scoring.items():
        if not pts:
            continue
        cat, label = SCORING_LABELS.get(key, ("Other", key))
        rows.append({"Category": cat, "Stat": label, "Points": pts})
    rows.sort(key=lambda r: (cat_order.index(r["Category"]) if r["Category"] in cat_order else 99, r["Stat"]))
    return pd.DataFrame(rows)


def build_trending_df(adds, drops, players, rosters, users, player_pts, fc_values,
                      val_maps=None, value_source="FC Dynasty"):
    user_map    = {u["user_id"]: u for u in users}
    pid_to_team = {}
    for r in rosters:
        oid  = r.get("owner_id") or ""
        u    = user_map.get(oid, {})
        team = (u.get("metadata") or {}).get("team_name") or u.get("display_name") or f"Team {r['roster_id']}"
        for pid in (r.get("players") or []) + (r.get("taxi") or []):
            pid_to_team[pid] = team

    _vm = val_maps or {}
    rows = []
    for entry in adds:
        rows.append(("Add", entry["player_id"], entry["count"]))
    for entry in drops:
        rows.append(("Drop", entry["player_id"], entry["count"]))

    result = []
    for trend, pid, count in rows:
        p    = players.get(pid, {})
        name = player_name(p) or pid
        result.append({
            "Trend":             trend,
            "Player":            name,
            "Pos":               p.get("position") or "—",
            "NFL Team":          p.get("team") or "FA",
            "Age":               int(p["age"]) if p.get("age") is not None else None,
            "Value":             get_active_value(pid, fc_values, _vm, value_source),
            "Rank":              get_active_rank( pid, fc_values, _vm, value_source),
            f"{STATS_SEASON} Pts": player_pts.get(pid),
            "# Added/Dropped":   count,
            "Available":         "No" if pid in pid_to_team else "Yes",
            "Dynasty Team":      pid_to_team.get(pid, "—"),
        })
    return pd.DataFrame(result)


# ── DEF / IDP Analysis ────────────────────────────────────────────────────────

DEF_POSITIONS = {"DL", "LB", "DB", "DEF"}   # pooled; K excluded everywhere

def build_def_analysis(rosters, users, players, player_pts):
    """
    Per-team defensive strength ranked by average 2025 fantasy points.
    Pools DL + LB + DB + DEF positions together; excludes K.
    Returns (team_def, league_def_avg):
      team_def    : {rid: {name, players, avg_pts, player_count}}
      league_def_avg: float
    """
    user_map = {u["user_id"]: u for u in users}
    team_def = {}
    for roster in rosters:
        rid       = roster["roster_id"]
        owner_id  = roster.get("owner_id") or ""
        user      = user_map.get(owner_id, {})
        team_name = (user.get("metadata") or {}).get("team_name") or user.get("display_name") or f"Team {rid}"

        def_players = []
        for pid in (roster.get("players") or []):
            p   = players.get(pid, {})
            pos = p.get("position", "")
            if pos not in DEF_POSITIONS:
                continue
            pts  = player_pts.get(pid)
            name = player_name(p)
            def_players.append({"pid": pid, "name": name, "pos": pos, "pts": pts or 0})

        def_players.sort(key=lambda x: x["pts"], reverse=True)
        scored = [p["pts"] for p in def_players if p["pts"] > 0]
        avg_pts = sum(scored) / len(scored) if scored else 0

        team_def[rid] = {
            "name":         team_name,
            "players":      def_players,
            "avg_pts":      avg_pts,
            "player_count": len(def_players),
        }

    all_avgs = [td["avg_pts"] for td in team_def.values() if td["avg_pts"] > 0]
    league_def_avg = sum(all_avgs) / len(all_avgs) if all_avgs else 0
    return team_def, league_def_avg


# ── Trade Analyzer ────────────────────────────────────────────────────────────

NEED_REACH_LIMIT = 0.15  # max value % sacrificed to fill a need over BPA (15% = reasonable reach)

SKILL_POSITIONS      = ["QB", "RB", "WR", "TE"]
ANALYSIS_DIMENSIONS  = ["QB", "RB", "WR", "TE", "PICK"]  # positions + picks

# Trade Fairness presets — premium the side ACQUIRING the single best player in a deal
# must overpay (× that player's value). "Off" = pure value calculator.
TF_PRESETS = {"Off": 0.0, "Light": 0.10, "Standard": 0.18, "Heavy": 0.28}
TF_NAMES   = list(TF_PRESETS)


# Position colour palette — ONE consistent scheme across every screen (chip / bar /
# pill / score). TE = purple; picks = neutral grey so it never clashes with TE.
POS_PALETTE = {  # dim → (pill-bg token, pill-fg token, accent token)
    "QB":   ("--pill-gold-bg",   "--pill-gold-fg",   "--gold"),
    "RB":   ("--pill-green-bg",  "--pill-green-fg",  "--green-bright"),
    "WR":   ("--pill-blue-bg",   "--pill-blue-fg",   "--blue"),
    "TE":   ("--pill-purple-bg", "--pill-purple-fg", "--purple"),
    "PICK": ("--bg-raised",      "--text-mid",       "--text-mid"),
}
POS_FULLNAME = {"QB": "Quarterback", "RB": "Running Back", "WR": "Wide Receiver",
                "TE": "Tight End", "PICK": "Draft Picks"}
POS_ABBR = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "PICK": "PK"}


def compute_pos_weights(scoring, enabled):
    """Per-position value multipliers derived from league scoring. The value sources
    (FantasyCalc et al.) already price Superflex/2QB and PPR, so the genuine gap they
    DON'T model is TE-premium — `bonus_rec_te` lifts TE value vs WR. Returns all-1.0
    when disabled or standard-scoring. Built as a dict so it can extend later."""
    w = {p: 1.0 for p in ("QB", "RB", "WR", "TE")}
    if not enabled:
        return w
    te_bonus = float((scoring or {}).get("bonus_rec_te") or 0)
    if te_bonus > 0:
        w["TE"] = round(1.0 + min(te_bonus, 1.0) * 0.20, 3)   # 0.5 → ×1.10 · 1.0 → ×1.20
    return w

def build_trade_analysis(rosters, users, players, fc_values, fc_picks, slot_map, traded_ownership, drafts, active_values=None):
    """
    Per-team analysis across QB/RB/WR/TE positions AND draft picks:
      - Average FC value per dimension vs league average
      - Relative surplus / need identification
      - Auto trade suggestions (player-based + pick-based)
    Returns: team_data, league_avgs, all_players_by_pos
    """
    if active_values is None:
        active_values = {pid: (fc_values.get(pid) or {}).get("value") for pid in fc_values}
    user_map = {u["user_id"]: u for u in users}

    # ── Per-team positional player data ──────────────────────────────────────
    team_data = {}
    for roster in rosters:
        rid       = roster["roster_id"]
        owner_id  = roster.get("owner_id") or ""
        user      = user_map.get(owner_id, {})
        team_name = (user.get("metadata") or {}).get("team_name") or user.get("display_name") or f"Team {rid}"

        pos_players = {pos: [] for pos in SKILL_POSITIONS}
        for pid in (roster.get("players") or []):
            p   = players.get(pid, {})
            pos = p.get("position", "")
            if pos not in SKILL_POSITIONS:
                continue
            val = active_values.get(pid)
            if val is None:
                continue
            name = player_name(p)
            pos_players[pos].append({"pid": pid, "name": name, "value": val})

        for pos in SKILL_POSITIONS:
            pos_players[pos].sort(key=lambda x: x["value"], reverse=True)

        pos_avgs = {}
        for pos in SKILL_POSITIONS:
            vals = [p["value"] for p in pos_players[pos]]
            pos_avgs[pos] = sum(vals) / len(vals) if vals else None

        team_data[rid] = {
            "name":        team_name,
            "pos_players": pos_players,
            "pos_avgs":    pos_avgs,
        }

    # ── Build each team's current pick assets ────────────────────────────────
    num_rounds   = drafts[0].get("settings", {}).get("rounds", 5) if drafts else 5
    current_year = datetime.now().year
    seasons      = [str(current_year + i) for i in range(PICK_SEASONS)]

    ownership = {}
    for r in rosters:
        r2id = r["roster_id"]
        for season in seasons:
            for rnd in range(1, num_rounds + 1):
                ownership[(season, rnd, r2id)] = r2id
    for (season, rnd, orig_rid), current_rid in traded_ownership.items():
        key = (season, rnd, orig_rid)
        if key in ownership:
            ownership[key] = current_rid

    for rid in team_data:
        team_picks = []
        for (season, rnd, orig_rid), current_rid in ownership.items():
            if current_rid != rid:
                continue
            season_slots = slot_map.get(season, {})
            if season_slots and orig_rid in season_slots:
                slot       = season_slots[orig_rid]
                pick_label = f"{rnd}.{slot:02d}"
                fc_key     = f"{season} Pick {rnd}.{slot:02d}"
            else:
                pick_label = f"Round {rnd}"
                fc_key     = None
            fc_val = fc_picks.get(fc_key) if fc_key else None
            if fc_val:
                team_picks.append({"label": f"{season} {pick_label}", "value": fc_val, "round": rnd})
        team_picks.sort(key=lambda x: x["value"], reverse=True)
        team_data[rid]["picks"] = team_picks
        # Average pick value for this team
        pick_vals = [p["value"] for p in team_picks]
        team_data[rid]["pos_avgs"]["PICK"] = sum(pick_vals) / len(pick_vals) if pick_vals else None

    # ── League-wide averages + spreads (players + picks) ─────────────────────
    # Spread (best team avg − worst team avg) is used to normalise value gaps
    # in need/surplus scores so cheap positions (TE) and expensive ones (WR)
    # are judged on the same scale — %-of-average inflates gaps at cheap positions.
    league_avgs    = {}
    league_spreads = {}
    for dim in ANALYSIS_DIMENSIONS:
        all_vals = [td["pos_avgs"][dim] for td in team_data.values() if td["pos_avgs"].get(dim) is not None]
        league_avgs[dim]    = sum(all_vals) / len(all_vals) if all_vals else None
        league_spreads[dim] = (max(all_vals) - min(all_vals)) or 1 if all_vals else None

    # ── Relative strength per team ─────────────────────────────────────────────
    for rid, td in team_data.items():
        relative = {}
        for dim in ANALYSIS_DIMENSIONS:
            avg    = td["pos_avgs"].get(dim)
            lg_avg = league_avgs.get(dim)
            if avg is not None and lg_avg is not None and lg_avg > 0:
                relative[dim] = (avg - lg_avg) / lg_avg * 100
            else:
                relative[dim] = None
        td["relative"] = relative

    # ── Per-dimension league rankings (1 = best, N = worst) ──────────────────
    for dim in ANALYSIS_DIMENSIONS:
        ranked = sorted(
            [(rid, td["pos_avgs"][dim]) for rid, td in team_data.items() if td["pos_avgs"].get(dim) is not None],
            key=lambda x: x[1],
            reverse=True,
        )
        for league_rank, (rid, _) in enumerate(ranked, start=1):
            team_data[rid].setdefault("pos_league_rank", {})[dim] = league_rank

    # ── Composite need/surplus score (0–100) per player position ─────────────
    # Combines league rank + value deficit/surplus equally (50/50).
    # need_score  high → genuine priority need (bad rank AND below average in value AND shallow depth)
    # surplus_score high → genuine surplus      (good rank AND above average in value AND strong depth)
    # Weights: rank 40% + value gap 40% + depth 20%
    n_teams = len(team_data)
    for rid, td in team_data.items():
        need_scores    = {}
        surplus_scores = {}
        depth_scores   = {}
        for dim in SKILL_POSITIONS:  # PICK excluded — can't "need" picks as a position
            rank    = td.get("pos_league_rank", {}).get(dim)
            rel     = td["relative"].get(dim)
            _avg    = td["pos_avgs"].get(dim)
            _lg_avg = league_avgs.get(dim)
            _spread = league_spreads.get(dim)
            if rank is None or rel is None or _avg is None or _lg_avg is None or not _spread:
                continue

            # ── Depth component ───────────────────────────────────────────────
            # Measures drop-off from starter to 2nd player (0.0 = great depth, 1.0 = no depth)
            players_at_pos = td["pos_players"].get(dim, [])
            if len(players_at_pos) == 0:
                depth_need = 1.0
            elif len(players_at_pos) == 1:
                depth_need = 0.75
            else:
                p1_val = players_at_pos[0]["value"] or 1
                p2_val = players_at_pos[1]["value"] or 0
                ratio  = min(p2_val / p1_val, 1.0)
                depth_need = 1.0 - ratio   # ratio≈1 (deep) → depth_need≈0; ratio≈0 (shallow) → depth_need≈1
            depth_scores[dim] = depth_need

            rank_component        = (rank - 1) / max(n_teams - 1, 1)   # 0.0 best → 1.0 worst
            # Value gap normalised by the league spread at this position, NOT by the
            # league average — a %-of-average gap systematically over-states need at
            # cheap positions (e.g. TE) and under-states it at expensive ones (WR).
            need_val_component    = max(0.0, _lg_avg - _avg) / _spread  # 0 if above avg, →1 at league-worst
            surplus_val_component = max(0.0, _avg - _lg_avg) / _spread  # 0 if below avg, →1 at league-best

            need_scores[dim]    = (rank_component * 0.4 + need_val_component    * 0.4 + depth_need         * 0.2) * 100
            surplus_scores[dim] = ((1 - rank_component) * 0.4 + surplus_val_component * 0.4 + (1 - depth_need) * 0.2) * 100

        td["need_scores"]    = need_scores
        td["surplus_scores"] = surplus_scores
        td["depth_scores"]   = depth_scores
        td["need_pos"]    = max(need_scores,    key=need_scores.get)    if need_scores    else None
        td["surplus_pos"] = max(surplus_scores, key=surplus_scores.get) if surplus_scores else None

    # ── All-team player pool (for trade matching) ─────────────────────────────
    all_players_by_pos = {pos: [] for pos in SKILL_POSITIONS}
    for rid, td in team_data.items():
        for pos in SKILL_POSITIONS:
            for player in td["pos_players"][pos]:
                all_players_by_pos[pos].append({**player, "on_team_rid": rid, "on_team": td["name"]})

    # ── Auto trade suggestions per team ──────────────────────────────────────
    for rid, td in team_data.items():
        surplus_pos = td["surplus_pos"]
        need_pos    = td["need_pos"]
        # Need must be a player position (can't "get" a pick as a trade target in this model)
        need_pos_player = need_pos if need_pos in SKILL_POSITIONS else None
        suggestions = []

        if surplus_pos and need_pos_player and surplus_pos != need_pos_player:
            if surplus_pos in SKILL_POSITIONS:
                # Player surplus → player targets
                for trade_player in td["pos_players"][surplus_pos][:3]:
                    trade_val = trade_player["value"]
                    targets   = sorted(
                        [p for p in all_players_by_pos[need_pos_player] if p["on_team_rid"] != rid],
                        key=lambda p: abs(p["value"] - trade_val),
                    )
                    suggestions.append({
                        "type":      "player",
                        "asset":     trade_player,
                        "asset_pos": surplus_pos,
                        "want_pos":  need_pos_player,
                        "targets":   targets[:4],
                    })
            # Always offer top picks as assets targeting the need position
            for pick in td["picks"][:3]:
                targets = sorted(
                    [p for p in all_players_by_pos[need_pos_player] if p["on_team_rid"] != rid],
                    key=lambda p: abs(p["value"] - pick["value"]),
                )
                if targets:
                    suggestions.append({
                        "type":      "pick",
                        "asset":     pick,
                        "asset_pos": "PICK",
                        "want_pos":  need_pos_player,
                        "targets":   targets[:4],
                    })

        td["suggestions"] = suggestions

    return team_data, league_avgs, all_players_by_pos


# ── "My Team" dashboard (League Overview) ─────────────────────────────────────

def player_drop_score(value, pts, status, exp, pos_avg, trend_drops=0):
    """Drop priority — higher = more expendable. Pure & reusable so the FA advisor
    and the team dashboard agree. trend_drops = Sleeper league-wide drops (24h)."""
    pos_avg = pos_avg or 1
    val_score   = max(0.0, 1.0 - (value or 0) / pos_avg) * 40
    pts_score   = max(0.0, 1.0 - (pts or 0) / 150.0)     * 30
    inj_score   = (20 if status in ("Out", "IR", "PUP", "Suspended")
                   else 10 if status in ("Questionable", "Doubtful") else 0)
    age_score   = min((exp or 0) / 10.0, 1.0)            * 10
    trend_score = min((trend_drops or 0) / 5000.0, 1.0)  * 25   # mass-dropped across Sleeper
    score = val_score + pts_score + inj_score + age_score + trend_score
    reasons = []
    if (value or 0) < pos_avg * 0.5:             reasons.append("Low value")
    if (pts or 0) < 50:                          reasons.append("Low pts")
    if status in ("Out", "IR", "PUP"):           reasons.append(status)
    elif status in ("Questionable", "Doubtful"): reasons.append(status)
    if (exp or 0) >= 7:                          reasons.append(f"{exp}yr vet")
    if (trend_drops or 0) >= 500:                reasons.append(f"{int(trend_drops):,} Sleeper drops")
    return score, reasons


def _team_value_profile(team_data, players):
    """{rid: (total_value, avg_age_top12, pick_value)} — inputs for the team rating."""
    prof = {}
    for rid, td in team_data.items():
        vals = []
        for pos in SKILL_POSITIONS:
            for p in td.get("pos_players", {}).get(pos, []):
                vals.append((p.get("value") or 0, players.get(p["pid"], {}).get("age")))
        vals.sort(key=lambda t: -t[0])
        total    = sum(v for v, _ in vals)
        ages     = [a for _, a in vals[:12] if a]
        avg_age  = sum(ages) / len(ages) if ages else 26.0
        pick_val = sum(pk.get("value") or 0 for pk in td.get("picks", []))
        prof[rid] = (total, avg_age, pick_val)
    return prof


def team_rating(rid, prof):
    """Win Now / Fading / Rebuilding / Stuck + RAG colour + one-line blurb."""
    totals = [p[0] for p in prof.values()]
    ages   = [p[1] for p in prof.values()]
    picks  = [p[2] for p in prof.values()]
    total, avg_age, pick_val = prof[rid]
    strong = total >= _stats.median(totals)
    young  = (avg_age <= _stats.median(ages)) or (pick_val >= _stats.median(picks))
    if strong and young:
        return ("Win Now", TOKENS["green"],
                "Strong roster with a young core / draft capital — compete now and sustain it.")
    if strong and not young:
        return ("Fading", TOKENS["gold"],
                "Strong now but aging — your window is closing. Cash veterans for youth + picks.")
    if (not strong) and young:
        return ("Rebuilding", TOKENS["blue"],
                "Below average now but young / pick-rich — keep accumulating and ascend.")
    return ("Stuck", TOKENS["red"],
            "Below average and aging with little capital — the hardest spot. Sell veterans for youth & picks.")


def rank_trade_partners(rid, td, team_data, untouchable, my_need, my_surplus):
    """Ranked trade-partner fits for ONE need↔surplus pair. The single source of
    truth shared by the Overview 'Best Trade Partner' tile and the Trade Room
    'Top 3 Suitors' table, so the two never disagree. Sorted by Fit Score desc;
    returns [] when there's no clear need/surplus.

    The sample trade is a *value-balanced* 1-for-1: we anchor on the best chip you
    can realistically move from your surplus (your highest-value, non-Untouchable
    player there), then pick the partner's player at your need position that is
    CLOSEST in value to that chip — not their headline star. This stops the tool
    from proposing your aging QB for their league-winning WR and calling it 'easy'.

    Fit rewards (a) how much they NEED your surplus (they have to want the deal),
    (b) how value-BALANCED the closest swap is, and (c) their depth at your need."""
    if not my_need or not my_surplus or my_need == my_surplus:
        return []
    my_surplus_players = [p for p in td.get("pos_players", {}).get(my_surplus, [])
                          if p["name"] not in untouchable]
    # Your best realistic chip from the surplus position (what you'd actually move)
    my_chip = max(my_surplus_players, key=lambda p: p.get("value") or 0) if my_surplus_players else None
    my_give_val  = (my_chip.get("value") or 0) if my_chip else 0
    my_give_name = my_chip["name"] if my_chip else "—"

    rows = []
    for o_rid, o_td in team_data.items():
        if o_rid == rid:
            continue
        their_supply = o_td.get("surplus_scores", {}).get(my_need, 0)     # they have my need
        their_need   = o_td.get("need_scores", {}).get(my_surplus, 0)     # they need my surplus
        their_cands  = o_td.get("pos_players", {}).get(my_need, [])
        # Their player at my need that is CLOSEST in value to my chip → balanced swap
        if their_cands and my_give_val:
            tm = min(their_cands, key=lambda p: abs((p.get("value") or 0) - my_give_val))
        elif their_cands:
            tm = max(their_cands, key=lambda p: p.get("value") or 0)
        else:
            tm = None
        their_get_val  = (tm.get("value") or 0) if tm else 0
        their_get_name = tm["name"] if tm else "—"

        if my_give_val > 0 and their_get_val > 0:
            _bigger  = max(my_give_val, their_get_val)
            gap_pct  = abs(their_get_val - my_give_val) / _bigger      # 0 = perfectly even
            balance  = (1.0 - gap_pct) * 100
        else:
            gap_pct, balance = 1.0, 0.0
        fit = their_need * 0.45 + balance * 0.35 + min(their_supply, 100) * 0.20

        supply_lbl = "Strong" if their_supply >= 50 else ("Moderate" if their_supply >= 20 else "Weak")
        need_lbl   = "High"   if their_need   >= 50 else ("Medium"   if their_need   >= 20 else "Low")
        rows.append({
            "Team": o_td["name"], "Fit Score": round(fit),
            f"Their {my_need} Supply": supply_lbl,
            f"Their Need for {my_surplus}": need_lbl,
            "Sample: You Give": f"{my_give_name}  ({my_surplus} · {my_give_val:,})" if my_give_val else my_give_name,
            "Sample: You Get":  f"{their_get_name}  ({my_need} · {their_get_val:,})" if their_get_val else their_get_name,
            "Value Diff": f"{their_get_val - my_give_val:+,}" if my_give_val and their_get_val else "—",
            "_give_name": my_give_name, "_give_val": my_give_val,
            "_get_name": their_get_name, "_get_val": their_get_val,
            "_val_diff": (their_get_val - my_give_val) if (my_give_val and their_get_val) else None,
            "_gap_pct": round(gap_pct * 100),
        })
    rows.sort(key=lambda x: x["Fit Score"], reverse=True)
    for i, r in enumerate(rows):
        r["#"] = i + 1
    return rows


def find_top_targets(rid, td, team_data, all_players_by_pos, player_tags, use_trade_block=False):
    """One best target player per weak position, tagged as Good Fit or Hard Get.

    Fit score = avg(their surplus at need_pos, their need for user's chip position).
    Good Fit >= 35, Hard Get < 35.
    use_trade_block=True restricts chips to Trade Block tagged players only.

    When the primary chip's value falls >15% short of the target, suggest_sweetener
    is called to find one or two add-on pieces that close the gap, preferring assets
    the target team also needs.
    """
    untouchable  = {nm for nm, t in player_tags.items() if t == "Untouchable"}
    block_names  = {nm for nm, t in player_tags.items() if t == "Trade Block"}

    if use_trade_block and block_names:
        chip_players = []
        for pos in SKILL_POSITIONS:
            for p in td.get("pos_players", {}).get(pos, []):
                if p["name"] in block_names:
                    chip_players.append({**p, "_pos": pos})
    else:
        surplus_pos  = td.get("surplus_pos")
        chip_players = [{**p, "_pos": surplus_pos}
                        for p in td.get("pos_players", {}).get(surplus_pos or "", [])
                        if p["name"] not in untouchable] if surplus_pos else []

    my_chip     = max(chip_players, key=lambda p: p.get("value") or 0) if chip_players else None
    my_chip_pos = my_chip.get("_pos") if my_chip else td.get("surplus_pos")
    my_chip_val = (my_chip.get("value") or 0) if my_chip else 0

    needs = sorted(
        [(pos, score) for pos, score in td.get("need_scores", {}).items()
         if score and score > 0 and pos in SKILL_POSITIONS],
        key=lambda x: -x[1],
    )[:3]

    results = []
    for need_pos, _ in needs:
        candidates = sorted(
            [p for p in all_players_by_pos.get(need_pos, []) if p["on_team_rid"] != rid],
            key=lambda p: p.get("value") or 0,
            reverse=True,
        )
        best_good, best_any = None, None
        for player in candidates:
            o_td       = team_data.get(player["on_team_rid"], {})
            their_sup  = o_td.get("surplus_scores", {}).get(need_pos, 0)
            their_need = o_td.get("need_scores", {}).get(my_chip_pos, 0) if my_chip_pos else 0
            fit        = (their_sup + their_need) / 2
            if best_any is None:
                best_any = (player, o_td.get("name", ""), player["on_team_rid"], fit)
            if fit >= 35 and best_good is None:
                best_good = (player, o_td.get("name", ""), player["on_team_rid"], fit)
                break

        chosen = best_good or best_any
        if not chosen:
            continue
        player, team_name, o_rid, fit_score = chosen
        target_val = player.get("value") or 0

        # Build offer package — add sweetener(s) when primary chip undershoots by >15%
        chips = [{"name": my_chip["name"], "pos": my_chip_pos, "value": my_chip_val}] if my_chip else []
        package_val = my_chip_val
        o_td = team_data.get(o_rid, {})
        their_needs = o_td.get("need_scores", {}) if o_td else {}

        if target_val > 0 and package_val < target_val * 0.85:
            shortfall = target_val - package_val
            exclude   = {my_chip["name"]} if my_chip else set()
            sw = suggest_sweetener(team_data, rid, their_needs, shortfall,
                                   exclude_names=exclude, untouchable=untouchable)
            if sw:
                chips.append({"name": sw["name"], "pos": sw["pos"], "value": sw["value"]})
                package_val += sw["value"]
                # If still >15% short after first sweetener, try one more
                if package_val < target_val * 0.85:
                    shortfall2 = target_val - package_val
                    exclude2   = exclude | {sw["name"]}
                    sw2 = suggest_sweetener(team_data, rid, their_needs, shortfall2,
                                            exclude_names=exclude2, untouchable=untouchable)
                    if sw2:
                        chips.append({"name": sw2["name"], "pos": sw2["pos"], "value": sw2["value"]})
                        package_val += sw2["value"]

        results.append({
            "pos":         need_pos,
            "player":      player,
            "team_name":   team_name,
            "fit_tag":     "Good Fit" if fit_score >= 35 else "Hard Get",
            "fit_score":   round(fit_score),
            "chips":       chips,
            "package_val": package_val,
            "target_val":  target_val,
        })
    return results


def suggest_sweetener(team_data, from_rid, target_needs, shortfall, exclude_names=(),
                      untouchable=()):
    """The single best balancing asset on `from_rid`'s roster: fills `target_needs`
    (pos→score) and is value-matched to `shortfall`, skipping anything in
    `exclude_names`/`untouchable`. Shared by the Trade Calculator and the Overview
    Best-Trade-Partner tile so 'the piece that evens the deal' is computed one way.
    Returns {name, pos, value, is_pick, why} or None."""
    if not from_rid or from_rid not in team_data or shortfall <= 0:
        return None
    td = team_data[from_rid]
    exclude, untouch = set(exclude_names), set(untouchable)
    cands = []
    for _pos in SKILL_POSITIONS:
        for _p in td.get("pos_players", {}).get(_pos, []):
            _v = _p.get("value") or 0
            if _v <= 0 or _p["name"] in exclude or _p["name"] in untouch:
                continue
            cands.append((_p["name"], _pos, _v, False, target_needs.get(_pos, 0) / 100.0))
    for _pk in td.get("picks", []):
        _v = round((_pk.get("value") or 0) / 10282 * 10000)
        if _v <= 0 or _pk["label"] in exclude:
            continue
        cands.append((_pk["label"], "PICK", _v, True, 0.5))
    best, best_score = None, -1.0
    for _name, _pos, _v, _is_pick, _nfit in cands:
        _vfit  = max(0.0, 1.0 - abs(_v - shortfall) / max(shortfall, 1))
        _score = _nfit * 0.5 + _vfit * 0.5
        if _v > shortfall * 1.9:
            _score *= 0.35
        if _score > best_score:
            best, best_score = (_name, _pos, _v, _is_pick), _score
    if not best:
        return None
    _name, _pos, _v, _is_pick = best
    _why = ("a pick to build with" if _is_pick else
            (f"fills the {_pos} need" if target_needs.get(_pos, 0) >= 20 else f"{_pos} depth"))
    return {"name": _name, "pos": _pos, "value": _v, "is_pick": _is_pick, "why": _why}


# ── Insight facts: derive win-now / future / power ranks for every team from
#    values the app ALREADY computes (no re-fetch), then hand to insight_text. ──
def _league_ranks_for_facts(team_data, players, prof=None):
    """{rid: (season_rank, dynasty_rank, power_rank)} — win-now = roster value,
    future = youth + pick-capital blend, power = mean positional league rank
    (same ordering as the Power Rankings table). All from existing computations."""
    prof = prof or _team_value_profile(team_data, players)
    rids = list(team_data)
    n = len(rids) or 1
    season  = {r: i + 1 for i, r in enumerate(sorted(rids, key=lambda r: -prof[r][0]))}
    youth   = {r: i + 1 for i, r in enumerate(sorted(rids, key=lambda r: prof[r][1]))}
    picks   = {r: i + 1 for i, r in enumerate(sorted(rids, key=lambda r: -prof[r][2]))}
    fut     = {r: (youth[r] + picks[r]) / 2 for r in rids}
    dynasty = {r: i + 1 for i, r in enumerate(sorted(rids, key=lambda r: fut[r]))}

    def _avg_pos_rank(r):
        rk = [v for v in (team_data[r].get("pos_league_rank") or {}).values() if v]
        return sum(rk) / len(rk) if rk else n
    power = {r: i + 1 for i, r in enumerate(sorted(rids, key=_avg_pos_rank))}
    return {r: (season[r], dynasty[r], power[r]) for r in rids}


def power_ranks(team_data, def_analysis):
    """League power ranks {rid: rank} computed the SAME way as the Power Rankings
    table (default view): mean NORMALISED positional rank across QB/RB/WR/TE/Picks/DEF.
    Lower rank = stronger. Distinct from roster-value rank (that's win-now/season)."""
    rids = list(team_data)
    n = len(rids) or 1
    _dv = {r: ((def_analysis or {}).get(r) or {}).get("avg_pts") for r in rids}
    _do = sorted([x for x in _dv.items() if x[1] is not None], key=lambda x: x[1], reverse=True)
    _drank = {r: i + 1 for i, (r, _) in enumerate(_do)}
    _dims = ["QB", "RB", "WR", "TE", "PICK", "DEF"]

    def _score(r):
        lr = {**(team_data[r].get("pos_league_rank") or {}), "DEF": _drank.get(r)}
        norm = [(1 - (lr[d] - 1) / max(n - 1, 1)) * 100 for d in _dims if lr.get(d) is not None]
        return sum(norm) / len(norm) if norm else 0
    return {r: i + 1 for i, r in enumerate(sorted(rids, key=_score, reverse=True))}


def build_my_team_facts(my_team, team_name_to_rid, team_data, players, value_source=None):
    """Assemble the fact object for the user's team, or None if not selectable."""
    if not my_team or my_team not in team_name_to_rid:
        return None
    rid  = team_name_to_rid[my_team]
    prof = _team_value_profile(team_data, players)
    s_rank, d_rank, p_rank = _league_ranks_for_facts(team_data, players, prof)[rid]
    positions = {k: v for k, v in (team_data[rid].get("pos_league_rank") or {}).items() if v}
    if not any(p in positions for p in ("QB", "RB", "WR", "TE")):
        return None
    total, avg_age, _pick = prof[rid]
    return it.build_team_facts(
        team=my_team, teams_in_league=len(team_data), power_rank=p_rank,
        positions=positions, season_rank=s_rank, dynasty_rank=d_rank,
        roster_value=total, avg_age=avg_age, value_source=value_source,
        priority_need=team_data[rid].get("need_pos"))


def _insight_week() -> str:
    """ISO year+week bucket so insight calls are cached one-per-week."""
    y, w, _ = datetime.now(timezone.utc).isocalendar()
    return f"{y}W{w:02d}"


def render_bottom_line(facts, cache_key):
    """Gold-accent verdict banner (concept-2). bottom_line comes from the insight
    engine — real Claude phrasing if a key is set, deterministic templates otherwise."""
    bl = it.generate_team_insights(facts, cache_key)["bottom_line"]
    st.markdown(
        '<div class="dlh-card" style="border-left:4px solid var(--gold);margin-bottom:18px;">'
        '<div class="eyebrow" style="color:var(--gold);">Bottom line</div>'
        f'<div style="font-size:20px;font-weight:500;color:var(--text-hi);'
        f'margin-top:8px;line-height:1.4;">{_html.escape(bl)}</div>'
        '<div style="font-size:13px;color:var(--text-mid);margin-top:8px;">'
        'Based on starter quality, roster age, and pick capital.</div>'
        '</div>', unsafe_allow_html=True)


def render_team_dashboard(my_team, team_name_to_rid, team_data, league_avgs,
                          players, player_pts, rosters, pos_ranks,
                          fc_values, val_maps, value_source, val_col):
    """Live 4-panel snapshot for the selected team, shown on League Overview."""
    if not my_team or my_team not in team_name_to_rid:
        st.info("Pick **My Team** in the sidebar to unlock your live dashboard — team rating, "
                "trade needs, best trade partner, and cut/add suggestions.")
        return
    rid  = team_name_to_rid[my_team]
    td   = team_data[rid]
    prof = _team_value_profile(team_data, players)

    # ── Team identity row + status pills (right) ──────────────────────────────
    _owner    = globals().get("team_owner_user", {}).get(my_team)
    _owner_nm = (_owner or {}).get("display_name")
    rating, _rcol, _blurb = team_rating(rid, prof)
    _n    = len(team_data)
    _sr, _dr, _ = _league_ranks_for_facts(team_data, players, prof)[rid]
    _pwr = power_ranks(team_data, globals().get("def_analysis") or {}).get(rid, _n)
    _sea, _dyn  = it.season_status(_sr, _n), it.dynasty_status(_dr, _n)
    _sea_c  = {"contender": "green", "in the mix": "gold", "long shot": "red"}[_sea]
    _dyn_c  = {"ascending": "green", "stable": "blue", "aging": "red"}[_dyn]
    _rate_c = {"Win Now": "green", "Fading": "gold", "Rebuilding": "blue", "Stuck": "red"}.get(rating, "gold")
    _handle = (f'<div style="font-size:.8rem;color:var(--text-mid);">@{_html.escape(_owner_nm)}</div>'
               if _owner_nm else '')
    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;'
        f'flex-wrap:wrap;margin:2px 0 16px;">'
        f'<div style="display:flex;align-items:center;gap:12px;">'
        f'{user_avatar_tag(_owner, my_team, px=46, radius=12)}'
        f'<div><div style="font-size:1.2rem;font-weight:700;color:var(--text-hi);line-height:1.15;">'
        f'{_html.escape(my_team)}</div>{_handle}</div></div>'
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;">'
        f'<span class="pill {_rate_c}">{rating}</span>'
        f'<span class="pill {_sea_c}">{_sea.capitalize()} · {_sr}/{_n}</span>'
        f'<span class="pill {_dyn_c}">Dynasty · {_dyn.capitalize()} · {_dr}/{_n}</span>'
        f'</div></div>', unsafe_allow_html=True)

    # ── 3 KPI cards: Power rank · Win-now · Dynasty (three DISTINCT metrics) ────
    # Power rank = mean positional league rank (same ordering as the Power Rankings
    # table) — NOT roster value (that's what Win-now/season already reflects).
    _tier_lbl, _tier_c = ("Elite", "green") if _pwr <= _n / 4 else \
                         (("Solid", "gold") if _pwr <= _n / 2 else ("Weak", "red"))
    _kpis = [
        ("Power rank",
         f'#{_pwr}<span style="font-size:.5em;color:var(--text-mid);">/{_n}</span>', _tier_lbl, _tier_c),
        ("Win-now", _sea.capitalize(), f"{_sr} of {_n}", _sea_c),
        ("Dynasty", _dyn.capitalize(), f"{_dr} of {_n}", _dyn_c),
    ]
    for _col, (_eb, _val, _pill, _pc) in zip(st.columns(3), _kpis):
        _col.markdown(
            f'<div class="dlh-card" style="border-left:4px solid var(--{_pc});padding:16px 18px;">'
            f'<div class="eyebrow">{_eb}</div>'
            f'<div style="font-family:\'Space Grotesk\',sans-serif;font-size:34px;font-weight:700;'
            f'color:var(--text-hi);line-height:1;margin:8px 0 12px;">{_val}</div>'
            f'<span class="pill {_pc}">{_pill}</span></div>', unsafe_allow_html=True)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    # Panel 2 — Trade Needs
    with c1.container(border=True):
        st.markdown('<div class="eyebrow" style="margin-bottom:10px;">Top Trade Needs</div>', unsafe_allow_html=True)
        needs = [(p, s) for p, s in sorted(td.get("need_scores", {}).items(), key=lambda x: -x[1])[:3]
                 if s and s > 0]
        if needs:
            n_teams = len(team_data)
            _cards = []
            for pos, score in needs:
                _pbg, _pfg, _acc = POS_PALETTE.get(pos, ("--pill-blue-bg", "--pill-blue-fg", "--blue"))
                _your = round(td.get("pos_avgs", {}).get(pos) or 0)
                _lg   = round(league_avgs.get(pos) or 0)
                _rel  = td.get("relative", {}).get(pos)
                _rank = td.get("pos_league_rank", {}).get(pos)
                _meta = f"{_your:,} vs {_lg:,}" + (f" · {_rel:+.0f}%" if _rel is not None else "")
                _rk   = f" #{_rank}/{n_teams}" if _rank else ""
                _cards.append(
                    f'<div style="display:flex;align-items:center;gap:11px;background:var(--bg-surface);'
                    f'border:1px solid var(--border);border-radius:10px;padding:10px 12px;margin-bottom:7px;">'
                    f'<div style="flex:0 0 auto;width:32px;height:32px;border-radius:8px;background:var({_pbg});'
                    f'color:var({_pfg});display:flex;align-items:center;justify-content:center;font-weight:700;'
                    f'font-size:.76rem;">{POS_ABBR.get(pos, pos)}</div>'
                    f'<div style="flex:1;min-width:0;">'
                    f'<div style="font-size:.86rem;color:var(--text-hi);margin-bottom:5px;">'
                    f'<strong>{POS_FULLNAME.get(pos, pos)}</strong> '
                    f'<span style="font-size:.74rem;color:var(--text-mid);">{_meta}</span></div>'
                    f'<div style="height:6px;border-radius:3px;background:var(--bg-hover);overflow:hidden;">'
                    f'<div style="height:6px;width:{min(100, round(score))}%;background:var({_acc});border-radius:3px;"></div></div></div>'
                    f'<div style="flex:0 0 auto;"><span style="background:var(--pill-red-bg);color:var(--pill-red-fg);'
                    f'font-size:.68rem;font-weight:600;padding:2px 8px;border-radius:999px;white-space:nowrap;">Need{_rk}</span></div>'
                    f'</div>')
            st.markdown("".join(_cards), unsafe_allow_html=True)
        else:
            st.caption("No clear needs — roster is balanced.")

    # Panel 3 — Best Trade Partner (same ranking as Trade Room > Best Trade Partners)
    with c2.container(border=True):
        st.markdown('<div class="eyebrow" style="margin-bottom:10px;">Best Trade Partner</div>', unsafe_allow_html=True)
        _bp_need    = td.get("need_pos")
        _bp_surplus = td.get("surplus_pos")
        _untouch    = {nm for nm, t in st.session_state.get("player_tags", {}).items()
                       if t == "Untouchable"}
        _partners = rank_trade_partners(rid, td, team_data, _untouch, _bp_need, _bp_surplus)
        if _partners and _partners[0]["_give_val"] and _partners[0]["_get_val"]:
            bp = _partners[0]
            _gv, _tv = bp["_give_val"], bp["_get_val"]
            _bp_rid  = team_name_to_rid.get(bp["Team"])
            send_pieces = [(bp["_give_name"], _bp_surplus, _gv)]
            get_pieces  = [(bp["_get_name"],  _bp_need,    _tv)]
            # Premium Curve -> balancing sweetener on the lighter side (same engine as the calc)
            _pc_name = st.session_state.get("trade_fairness", "Off")
            _pc_frac = TF_PRESETS.get(_pc_name, 0.0)
            _prem    = round(_pc_frac * max(_gv, _tv))
            _eff_you = _gv + (_prem if _gv >= _tv else 0)
            _eff_them = _tv + (_prem if _tv > _gv else 0)
            _short   = abs(_eff_you - _eff_them)
            if _short > 0.05 * (max(_eff_you, _eff_them) or 1):
                if _eff_you > _eff_them:
                    _sw = suggest_sweetener(team_data, _bp_rid, td.get("need_scores", {}),
                                            _short, exclude_names={bp["_get_name"]})
                    if _sw: get_pieces.append((_sw["name"], _sw["pos"], _sw["value"]))
                else:
                    _tn = team_data[_bp_rid].get("need_scores", {}) if _bp_rid else {}
                    _sw = suggest_sweetener(team_data, rid, _tn, _short,
                                            exclude_names={bp["_give_name"]}, untouchable=_untouch)
                    if _sw: send_pieces.append((_sw["name"], _sw["pos"], _sw["value"]))
            _send_tot = sum(p[2] for p in send_pieces)
            _get_tot  = sum(p[2] for p in get_pieces)
            _diff = _get_tot - _send_tot
            _pa   = round(_send_tot / ((_send_tot + _get_tot) or 1) * 100)
            if abs(_diff) <= 0.05 * max(_send_tot, _get_tot, 1):
                _vbg, _vfg, _verdict = "var(--pill-green-bg)", "var(--pill-green-fg)", f"Fair . ±{abs(_diff):,}"
            else:
                _vbg, _vfg = "var(--pill-gold-bg)", "var(--pill-gold-fg)"
                _verdict = (f"Favours you . +{_diff:,}" if _diff > 0 else f"Favours them . {_diff:,}")

            st.markdown(f"**{_html.escape(bp['Team'])}** — they need your **{_bp_surplus}**, "
                        f"you want a **{_bp_need}**", unsafe_allow_html=True)

            def _piece_rows(pieces):
                _h = ""
                for _nm, _ps, _vl in pieces:
                    _b, _f, _a = POS_PALETTE.get(_ps, ("--pill-blue-bg", "--pill-blue-fg", "--blue"))
                    _h += (f'<div style="display:flex;align-items:center;gap:8px;margin-top:7px;">'
                           f'<span style="flex:0 0 auto;width:28px;height:20px;border-radius:6px;background:var({_b});'
                           f'color:var({_f});display:flex;align-items:center;justify-content:center;font-size:.62rem;font-weight:700;">'
                           f'{POS_ABBR.get(_ps, _ps)}</span>'
                           f'<span style="flex:1;min-width:0;font-size:.82rem;color:var(--text-hi);overflow:hidden;'
                           f'text-overflow:ellipsis;white-space:nowrap;">{_html.escape(_nm)}</span>'
                           f'<span style="flex:0 0 auto;font-size:.78rem;color:var(--text-mid);">{_vl:,}</span></div>')
                return _h

            _scA, _scB = st.columns(2)
            _scA.markdown(
                f'<div style="border:1px solid var(--border);border-radius:10px;padding:11px 12px;">'
                f'<div class="eyebrow" style="color:var(--pill-red-fg);">You send</div>'
                f'<div style="font-size:1.25rem;font-weight:700;color:var(--text-hi);">{_send_tot:,}</div>'
                f'{_piece_rows(send_pieces)}</div>', unsafe_allow_html=True)
            _scB.markdown(
                f'<div style="border:1px solid var(--border);border-radius:10px;padding:11px 12px;">'
                f'<div class="eyebrow" style="color:var(--pill-green-fg);">You get</div>'
                f'<div style="font-size:1.25rem;font-weight:700;color:var(--text-hi);">{_get_tot:,}</div>'
                f'{_piece_rows(get_pieces)}</div>', unsafe_allow_html=True)

            st.markdown(
                f'<div style="margin-top:9px;"><div style="display:flex;height:16px;border-radius:5px;overflow:hidden;'
                f'font-size:.66rem;font-weight:600;">'
                f'<div style="width:{_pa}%;background:var(--red);color:#2a0a0a;display:flex;align-items:center;justify-content:center;">{_pa}%</div>'
                f'<div style="width:{100 - _pa}%;background:var(--green);color:#04210F;display:flex;align-items:center;justify-content:center;">{100 - _pa}%</div></div>'
                f'<div style="text-align:center;margin-top:7px;"><span style="background:{_vbg};color:{_vfg};'
                f'font-size:.74rem;font-weight:600;padding:3px 12px;border-radius:999px;">{_verdict}</span></div></div>',
                unsafe_allow_html=True)

            if st.button("Refine in Trade Room →", key="bp_refine", type="primary", width="stretch"):
                def _lbl(nm, ps, vl): return f"{nm}  ({'Pick' if ps == 'PICK' else ps}) — {vl:,}"
                st.session_state["_tb_preload"] = {
                    "team_a": my_team, "team_b": bp["Team"],
                    "side_a": [_lbl(*p) for p in send_pieces],
                    "side_b": [_lbl(*p) for p in get_pieces],
                }
                st.session_state.nav_page = "Trade Room"
                st.rerun()
            if _pc_frac > 0:
                st.caption(f"Premium Curve **{_pc_name}** applied to the balance.")
        else:
            st.caption("No clean value-matched partner right now — see the Trade Room for options.")

    # Panel 4 — Top Targets
    with st.container(border=True):
        _tt_hdr, _tt_tog = st.columns([3, 2])
        _tt_hdr.markdown('<div class="eyebrow" style="margin-bottom:2px;">Top Targets</div>', unsafe_allow_html=True)
        _tt_hdr.markdown(
            '<div style="font-size:.74rem;color:var(--text-mid);">Best player to chase per weak position</div>',
            unsafe_allow_html=True)
        _use_block = _tt_tog.toggle(
            "Trade block chips only", value=False, key="targets_use_block",
            help="ON = only your Trade Block players used as chips when scoring fit")

        _targets = find_top_targets(
            rid, td, team_data, all_players_by_pos,
            st.session_state.get("player_tags", {}),
            use_trade_block=_use_block,
        )
        if _targets:
            _t_cards = []
            for t in _targets:
                _pos      = t["pos"]
                _pl       = t["player"]
                _pbg, _pfg, _acc = POS_PALETTE.get(_pos, ("--pill-blue-bg", "--pill-blue-fg", "--blue"))
                _tval     = t["target_val"]
                _pval     = t["package_val"]
                _nm       = _html.escape(_pl.get("name") or "—")
                _team     = _html.escape(t["team_name"])
                _is_fit   = t["fit_tag"] == "Good Fit"
                _tag_bg   = "var(--pill-green-bg)" if _is_fit else "var(--pill-gold-bg)"
                _tag_fg   = "var(--pill-green-fg)" if _is_fit else "var(--pill-gold-fg)"
                _tag_lbl  = "Good Fit" if _is_fit else "Hard Get"

                # Build offer string: "Jordan Love (QB) + 2025 1st (PICK)"
                _chip_parts = []
                for _ch in t.get("chips", []):
                    _cp = _html.escape(_ch.get("pos") or "")
                    _cn = _html.escape(_ch.get("name") or "")
                    _chip_parts.append(f'<strong style="color:var(--text-body);">{_cn}</strong>'
                                       f'<span style="color:var(--text-low);"> ({_cp})</span>')
                _offer_str  = ' <span style="color:var(--text-faint);">+</span> '.join(_chip_parts) if _chip_parts else "—"

                # Value gap indicator
                _gap_pct  = round((_tval - _pval) / _tval * 100) if _tval > 0 else 0
                if abs(_gap_pct) <= 10:
                    _gap_col, _gap_txt = "var(--green)", f"±{abs(_gap_pct)}% value"
                elif _gap_pct > 0:
                    _gap_col, _gap_txt = "var(--gold)", f"You send {_gap_pct}% less"
                else:
                    _gap_col, _gap_txt = "var(--pill-red-fg)", f"You send {abs(_gap_pct)}% more"

                _t_cards.append(
                    f'<div style="display:flex;align-items:center;gap:11px;background:var(--bg-surface);'
                    f'border:1px solid var(--border);border-radius:10px;padding:10px 12px;margin-bottom:7px;">'
                    f'<div style="flex:0 0 auto;width:32px;height:32px;border-radius:8px;background:var({_pbg});'
                    f'color:var({_pfg});display:flex;align-items:center;justify-content:center;'
                    f'font-weight:700;font-size:.76rem;">{POS_ABBR.get(_pos, _pos)}</div>'
                    f'<div style="flex:1;min-width:0;">'
                    f'<div style="font-size:.86rem;color:var(--text-hi);">'
                    f'<strong>{_nm}</strong> '
                    f'<span style="font-size:.74rem;color:var(--text-mid);">{_tval:,}</span></div>'
                    f'<div style="font-size:.74rem;color:var(--text-mid);margin:2px 0 1px;">{_team}</div>'
                    f'<div style="font-size:.72rem;color:var(--text-mid);">Offer: {_offer_str}</div>'
                    f'<div style="font-size:.68rem;color:{_gap_col};margin-top:2px;">{_gap_txt} · package {_pval:,}</div>'
                    f'</div>'
                    f'<div style="flex:0 0 auto;">'
                    f'<span style="background:{_tag_bg};color:{_tag_fg};font-size:.68rem;font-weight:600;'
                    f'padding:2px 8px;border-radius:999px;white-space:nowrap;">{_tag_lbl}</span>'
                    f'</div></div>'
                )
            st.markdown("".join(_t_cards), unsafe_allow_html=True)
        else:
            st.caption("No clear targets found — roster may be balanced or no trade fits exist.")

    # Panel 5 — Cut-for-Pickup
    st.markdown("#### :material/autorenew: Cut-for-Pickup")
    _, _drops = load_trending()
    drop_counts = {str(d["player_id"]): d.get("count", 0) for d in (_drops or [])}
    cuts = []
    for pos in SKILL_POSITIONS:
        pavg = td.get("pos_avgs", {}).get(pos) or 1
        for pp in td.get("pos_players", {}).get(pos, []):
            pid, pobj = pp["pid"], players.get(pp["pid"], {})
            sc, reasons = player_drop_score(
                pp.get("value") or 0, player_pts.get(pid) or 0,
                pobj.get("injury_status") or pobj.get("status") or "Active",
                pobj.get("years_exp") or 0, pavg,
                trend_drops=drop_counts.get(str(pid), 0))
            cuts.append({"Player": pp["name"], "Pos": pos, val_col: pp.get("value") or 0,
                         "Why": " · ".join(reasons) if reasons else "depth", "_s": sc})
    cuts.sort(key=lambda x: -x["_s"])
    cuts3 = [{k: v for k, v in c.items() if k != "_s"} for c in cuts[:3]]

    p1, p2 = st.columns(2)
    with p1:
        st.markdown("**Consider cutting**")
        # Spacer matches the Exclude-rookies checkbox height in p2 so both tables align
        st.markdown("<div style='height:38px'></div>", unsafe_allow_html=True)
        if cuts3:
            st.dataframe(pd.DataFrame(cuts3), hide_index=True, width="stretch",
                         column_config={val_col: COL_CFG["Value"]})
        else:
            st.caption("Roster looks lean.")
    with p2:
        st.markdown("**Consider adding** *(free agents)*")
        # Checkbox return value drives the filter directly — no session-state lag.
        _excl_rookies_add = st.checkbox(
            "Exclude rookies", key="dash_excl_rookies_add",
            help="Hide rookies from these free-agent suggestions.")
        df_fa = build_fa_df(rosters, players, player_pts, pos_ranks, fc_values, val_maps, value_source)
        df_fa = df_fa.rename(columns={"Value": val_col})
        if _excl_rookies_add and "Exp" in df_fa.columns:
            df_fa = df_fa[df_fa["Exp"] != "Rookie"]
        # Adds fill skill needs — never suggest IDP/DEF/K free agents here.
        df_fa = df_fa[df_fa["Pos"].isin(SKILL_POSITIONS)]
        fa_sorted = df_fa.sort_values(val_col, ascending=False, na_position="last")
        need_pos = [p for p, _ in sorted(td.get("need_scores", {}).items(), key=lambda x: -x[1])]
        picks_rows, seen = [], set()
        for pos in need_pos[:2]:
            row = fa_sorted[fa_sorted["Pos"] == pos].head(1)
            if not row.empty and row.iloc[0]["Player"] not in seen:
                picks_rows.append(row.iloc[0]); seen.add(row.iloc[0]["Player"])
        for _, r0 in fa_sorted.iterrows():
            if len(picks_rows) >= 3:
                break
            if r0["Player"] not in seen:
                picks_rows.append(r0); seen.add(r0["Player"])
        if picks_rows:
            _cols = [c for c in ["Player", "Pos", "NFL Team", val_col] if c in df_fa.columns]
            st.dataframe(pd.DataFrame(picks_rows)[_cols], hide_index=True, width="stretch",
                         column_config={val_col: COL_CFG["Value"]})
        else:
            st.caption("No standout free agents available.")
    st.caption("Cuts weigh value vs positional average, production, injury, age — and "
               "**Sleeper league-wide drops** (a high drop count = many managers dropping this player).")


# ── Fantasy News ─────────────────────────────────────────────────────────────

NEWS_FEEDS = {
    "ProFootballTalk": "https://profootballtalk.nbcsports.com/feed/",
    "ESPN NFL":        "https://www.espn.com/espn/rss/nfl/news",
    "NFL Trade Rumors":"https://www.nfltraderumors.co/feed/",
}

def _parse_dt(entry):
    """Return a timezone-aware datetime from an RSS entry, or epoch if missing.
    feedparser normalises published_parsed to UTC, so use calendar.timegm
    (interprets the struct as UTC) — NOT time.mktime (which assumes local time
    and skews every timestamp, pushing many into the 'future')."""
    pt = entry.get("published_parsed") or entry.get("updated_parsed")
    if pt:
        import calendar as _cal
        return datetime.fromtimestamp(_cal.timegm(pt), tz=timezone.utc)
    return datetime.fromtimestamp(0, tz=timezone.utc)

@st.cache_data(ttl=1800, show_spinner=False)   # 30-min cache
def fetch_rss_news():
    """Fetch all configured RSS feeds. Returns list of story dicts."""
    stories = []
    for source, url in NEWS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.get("entries", []):
                summary = entry.get("summary") or ""
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                stories.append({
                    "source":    source,
                    "title":     entry.get("title", "").strip(),
                    "summary":   summary[:300] + ("…" if len(summary) > 300 else ""),
                    "link":      entry.get("link", ""),
                    "published": _parse_dt(entry),
                    "published_str": entry.get("published", ""),
                })
        except Exception as e:
            print(f"[WARNING] RSS feed '{source}' failed to load: {e}")
    # Sort newest first
    stories.sort(key=lambda s: s["published"], reverse=True)
    return stories


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_sleeper_player_news(players_data):
    """
    Use Sleeper trending adds (last 24h) as a proxy for breaking player news.
    Returns list of dicts with player name, team, pos, add count, and a note.
    """
    try:
        adds  = get(f"{BASE}/players/nfl/trending/add?lookback_hours=24&limit=20")
        drops = get(f"{BASE}/players/nfl/trending/drop?lookback_hours=24&limit=10")
    except Exception as e:
        print(f"[WARNING] Sleeper player news fetch failed: {e}")
        return []

    items = []
    for entry in adds:
        pid  = entry.get("player_id", "")
        p    = players_data.get(pid, {})
        name = player_name(p, fallback=pid)
        items.append({
            "source":    "Sleeper Transactions",
            "title":     f"{name} trending up — {entry['count']:,} adds in last 24h",
            "summary":   (
                f"{name} ({p.get('position','?')} · {p.get('team','FA')}) "
                f"is being added in {entry['count']:,} leagues. "
                f"Injury status: {p.get('injury_status') or p.get('status') or 'Active'}."
            ),
            "link":      "",
            "published": datetime.now(tz=timezone.utc),
            "published_str": "Last 24h",
        })
    for entry in drops:
        pid  = entry.get("player_id", "")
        p    = players_data.get(pid, {})
        name = player_name(p, fallback=pid)
        items.append({
            "source":    "Sleeper Transactions",
            "title":     f"{name} trending down — {entry['count']:,} drops in last 24h",
            "summary":   (
                f"{name} ({p.get('position','?')} · {p.get('team','FA')}) "
                f"is being dropped in {entry['count']:,} leagues. "
                f"Injury status: {p.get('injury_status') or p.get('status') or 'Active'}."
            ),
            "link":      "",
            "published": datetime.now(tz=timezone.utc),
            "published_str": "Last 24h",
        })
    return items


# ── Radar normalization helper ────────────────────────────────────────────────

def normalize_dim(values_dict):
    """Given {rid: value_or_None}, return {rid: 0-100 score}."""
    valid = {rid: v for rid, v in values_dict.items() if v is not None}
    if not valid: return {rid: 50 for rid in values_dict}
    mn, mx = min(valid.values()), max(valid.values())
    if mn == mx: return {rid: 50 for rid in values_dict}
    return {rid: (v - mn) / (mx - mn) * 100 if v is not None else 50 for rid, v in values_dict.items()}


# ── App layout ────────────────────────────────────────────────────────────────

# ── Step 1 · Entry / login screen ─────────────────────────────────────────────
if "league_id" not in st.session_state:
    st.session_state.league_id = None   # login-first: always start at the entry screen

if not st.session_state.get("league_id"):
    _LSIDE, _RSIDE = st.columns([1, 1.05], gap="large")

    with _LSIDE:
        _hero = _LOGO_STACKED or _LOGO_HORIZONTAL or ""
        # Scale SVG to fit the card without overflowing (SVG has fixed width="300")
        _hero_disp = (_hero.replace('<svg ', '<svg style="max-width:190px;height:auto;display:block;margin:0 auto;" ', 1)
                      if _hero else "")

        def _ck(txt):
            return (f'<div style="display:flex;align-items:center;gap:10px;margin:10px 0;'
                    f'color:var(--text-body);font-size:.92rem;">'
                    f'<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--green-bright)" '
                    f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex:0 0 auto;">'
                    f'<path d="M21.801 10A10 10 0 1 1 17 3.335"/><path d="m9 11 3 3L22 4"/></svg>'
                    f'<span>{txt}</span></div>')

        st.markdown(
            f'<div style="background:repeating-linear-gradient(90deg, rgba(255,255,255,.018) 0 1px, '
            f'transparent 1px 46px), var(--bg-page); border:1px solid var(--border); border-radius:16px; '
            f'padding:44px 34px; min-height:440px; display:flex; flex-direction:column; justify-content:center; align-items:center;">'
            f'<div style="width:100%; text-align:center; margin-bottom:4px;">{_hero_disp}</div>'
            f'<div style="text-align:center; color:var(--text-body); font-size:1.05rem; margin:10px 0 24px;">'
            f'Your dynasty command center</div>'
            f'<div style="max-width:310px; margin:0 auto; width:100%;">'
            f'{_ck("Trade analysis · 4 value sources")}'
            f'{_ck("Rookie draft simulator + 2026 big board")}'
            f'{_ck("AI insights for Sleeper leagues")}'
            f'</div></div>', unsafe_allow_html=True)

    with _RSIDE:
        st.markdown('<div class="eyebrow" style="margin-top:10px;">Get started — it’s free</div>',
                    unsafe_allow_html=True)
        st.markdown('<h1 style="margin:.25rem 0 .35rem;">Find your league</h1>', unsafe_allow_html=True)
        st.markdown('<p style="color:var(--text-mid); margin:0 0 1.1rem;">Enter your Sleeper username to '
                    'connect your leagues — or paste a league ID directly.</p>', unsafe_allow_html=True)
        if st.session_state.get("auth_email"):
            st.success(f"Signed in as **{st.session_state.auth_email}** — pick your league below to get started.")

        st.markdown('<div class="eyebrow">Sleeper username or league ID</div>', unsafe_allow_html=True)
        _fc1, _fc2 = st.columns([3, 1], vertical_alignment="bottom")
        _in = _fc1.text_input("Sleeper username or league ID", key="entry_input",
                              placeholder="your Sleeper username…", label_visibility="collapsed")
        if _fc2.button("Find →", type="primary", key="entry_find", width="stretch"):
            _q = (_in or "").strip()
            st.session_state.pop("_entry_err", None)
            if _q.isdigit() and len(_q) >= 15:
                _lg = None
                try: _lg = get(f"{BASE}/league/{_q}")
                except Exception: _lg = None
                if _lg and _lg.get("league_id"):
                    st.session_state._found_leagues = [{
                        "league_id": _lg["league_id"], "name": _lg.get("name", "League"),
                        "season": _lg.get("season"), "total_rosters": _lg.get("total_rosters")}]
                else:
                    st.session_state._found_leagues = []
                    st.session_state._entry_err = "No league found with that ID."
            else:
                _lgs = fetch_user_leagues(_q)
                st.session_state._found_leagues = _lgs
                if not _lgs:
                    st.session_state._entry_err = f"No NFL leagues found for '{_q}'. Check the username, or paste a league ID."
            st.rerun()

        if st.session_state.get("_entry_err"):
            st.error(st.session_state._entry_err)
        _found = st.session_state.get("_found_leagues") or []
        if _found:
            _labels = {f"{l['name']}  ·  {l.get('season','')}  ·  {l.get('total_rosters','?')} teams": l["league_id"]
                       for l in _found}
            _pick = st.selectbox("Pick your league", list(_labels.keys()), key="entry_pick")
            if st.button("Next →", type="primary", key="entry_open", width="stretch"):
                st.session_state.league_id = _labels[_pick]
                save_last_league(_labels[_pick])
                st.session_state.pop("_found_leagues", None)
                st.session_state.pop("_entry_err", None)
                st.rerun()

        st.markdown('<div style="text-align:center; color:var(--text-low); font-size:.8rem; '
                    'border-top:1px solid var(--divider); margin:18px 0 12px; line-height:.1;">'
                    '<span style="background:var(--bg-page); padding:0 12px;">already have an account?</span></div>',
                    unsafe_allow_html=True)

        if not st.session_state.get("_show_signin"):
            if st.button("Sign in", key="entry_show_signin", width="stretch"):
                st.session_state._show_signin = True
                st.rerun()
        elif not auth_available():
            st.info("Sign-in isn’t available right now — use **Find your league** above.")
        elif not st.session_state.get("_auth_code_sent"):
            _ae = st.text_input("Email", key="entry_auth_email", placeholder="you@email.com")
            _ac1, _ac2 = st.columns(2)
            if _ac1.button("Send code", type="primary", key="entry_auth_send", width="stretch"):
                ok, err = auth_send_code(_ae)
                if ok:
                    st.session_state._auth_code_sent = True
                    st.session_state._auth_pending_email = (_ae or "").strip()
                    st.rerun()
                else:
                    st.error(f"Couldn't send code: {err}")
            if _ac2.button("Back", key="entry_auth_back", width="stretch"):
                st.session_state._show_signin = False
                st.rerun()
        else:
            st.caption(f"Code sent to **{st.session_state.get('_auth_pending_email','')}** — check your email.")
            _code = st.text_input("6-digit code", key="entry_auth_code")
            _ec1, _ec2 = st.columns(2)
            if _ec1.button("Verify & sign in", type="primary", key="entry_auth_verify", width="stretch"):
                _em = auth_verify_code(st.session_state.get("_auth_pending_email", ""), _code)
                if _em:
                    st.session_state.auth_email = _em
                    st.session_state.pop("_auth_code_sent", None)
                    _ll = load_last_league()
                    if _ll:
                        st.session_state.league_id = _ll
                    st.session_state._toast_msg = f"Signed in as {_em}"
                    st.rerun()
                else:
                    st.error("Invalid or expired code — try again.")
            if _ec2.button("Cancel", key="entry_auth_cancel", width="stretch"):
                st.session_state.pop("_auth_code_sent", None)
                st.rerun()

        st.markdown('<div style="margin-top:16px;"><span class="pill gold">BETA</span> '
                    '<span style="color:var(--text-mid); font-size:.82rem; margin-left:6px;">'
                    'Free access · No credit card needed</span></div>', unsafe_allow_html=True)
    st.stop()

league_id = st.session_state.league_id

# Show the loading spinner ONLY on a genuine cold load (first visit, league switch,
# or manual Refresh). On warm reruns the data is cached and returns instantly — a
# spinner element flashing in/out at the top of the page is what makes the main
# content "jump", so we suppress it entirely when the league is already warmed.
_cold_load = st.session_state.get("_data_warmed_for") != league_id
_load_spin = st.spinner("Loading your league…") if _cold_load else contextlib.nullcontext()
with _load_spin:
    try:
        (league, rosters, users, traded_ownership, drafts, slot_map,
         players, player_pts, pos_ranks, fc_values, fc_rookies, fc_picks, scoring) = load_all_data(league_id)
    except Exception as e:
        st.error(f"Failed to load league {league_id}: {e}")
        if st.button("Try a different league", key="landing_retry"):
            st.session_state.league_id = None
            st.rerun()
        st.stop()
    num_qbs      = derive_league_shape(league)[0]        # 1 = single-QB, 2 = superflex/2QB
    owner_view   = _is_owner()                           # owner sees the held-back KTC/DN sources
    dn_map       = fetch_dn_values()
    ktc_by_id    = fetch_ktc_values()
    dp_map, cw_ktc = fetch_dp_values(num_qbs)            # DP reads its 1QB column when 1-QB
    ktc_map      = build_ktc_sleeper_map(ktc_by_id, cw_ktc, players)
    # KTC & DynastyNerds are held back (legality) AND SuperFlex-only. Drop their
    # maps entirely for the public, and for everyone in 1-QB leagues — emptying the
    # maps both removes them as options and auto-excludes them from Consensus Avg.
    # The plumbing (fetch + crosswalk) stays so owner view / future re-enable is trivial.
    if (not owner_view) or num_qbs < 2:
        dn_map = {}
        ktc_map = {}
    val_maps     = {"dn": dn_map, "ktc": ktc_map, "dp": dp_map}
st.session_state._data_warmed_for = league_id

# ── Step 2 · Setup (My Team + Value Source) — skipped for returning signed-in users ──
if st.session_state.get("_onboarded_for") != league_id:
    _lp0 = load_league_prefs(league_id)
    if _signed_in() and _lp0.get("team"):
        st.session_state._onboarded_for = league_id   # returning member → straight in
    else:
        _umap0 = {u["user_id"]: u for u in users}
        _teams0 = sorted({
            ((_umap0.get(r.get("owner_id") or "", {}).get("metadata") or {}).get("team_name")
             or _umap0.get(r.get("owner_id") or "", {}).get("display_name")
             or f"Team {r['roster_id']}") for r in rosters
        })

        # Per-source blurb shown under the value-source selectbox on setup.
        _VS_INFO = {
            "FC Dynasty":    ("Dynasty-specific values updated daily by FantasyCalc — the most widely used "
                              "public dynasty ranker. Accounts for age, positional scarcity, and dynasty outlook.",
                              "https://dynasty.fantasycalc.com"),
            "FC Redraft":    ("Win-now, single-season values with no dynasty youth premium. Best for "
                              "redraft leagues or evaluating year-by-year output.",
                              "https://fantasycalc.com"),
            "DP Values":     ("Open-source dynasty rankings from an analytics-first team. Strong "
                              "Superflex / 2QB support and transparent methodology.",
                              "https://dynastyprocess.com"),
            "Consensus Avg": ("Blends all available dynasty sources for your league format. Reduces "
                              "ranker bias — a reliable default for most leagues.", None),
            "KTC":           ("Community-voted dynasty rankings from KeepTradeCut — the original "
                              "dynasty trade calculator. SuperFlex / 2QB leagues only.",
                              "https://keeptradecut.com"),
            "DN Dynasty":    ("Analytics-heavy dynasty rankings from DynastyNerds with detailed "
                              "positional projections. SuperFlex / 2QB leagues only.",
                              "https://dynastynerds.com"),
        }

        # Auto-detect the user's team from the Sleeper username entered on Page 1.
        _entry_q   = st.session_state.get("entry_input", "").strip()
        _is_lid    = _entry_q.isdigit() and len(_entry_q) >= 15
        _default_team_idx = 0
        # First preference: previously saved team
        _lp0_team = _lp0.get("team")
        if _lp0_team and _lp0_team in _teams0:
            _default_team_idx = _teams0.index(_lp0_team)
        elif not _is_lid and _entry_q:
            # Username was entered: find which team in this league belongs to them.
            for _u in _umap0.values():
                if _u.get("display_name", "").lower() == _entry_q.lower():
                    _uid = _u.get("user_id")
                    for _r in rosters:
                        if _r.get("owner_id") == _uid:
                            _tname = ((_umap0.get(_uid, {}).get("metadata") or {}).get("team_name")
                                      or _umap0.get(_uid, {}).get("display_name")
                                      or f"Team {_r['roster_id']}")
                            if _tname in _teams0:
                                _default_team_idx = _teams0.index(_tname)
                            break
                    break

        # The whole setup lives in one st.empty() slot so Streamlit can clear it
        # atomically before the Continue rerun (prevents leftover widget ghosts).
        _setup_ph = st.empty()
        with _setup_ph.container():
            _su_l, _su_r = st.columns([1, 1.05], gap="large")

            # ── Left panel — league identity card ────────────────────────────
            with _su_l:
                _lname      = _html.escape(league.get("name", "Dynasty League"))
                _avatar_html = league_avatar_tag(league, px=72, radius=16)
                _badge_html  = "".join(
                    f'<span style="display:inline-block;background:#1b212c;border:1px solid #2a3344;'
                    f'border-radius:6px;padding:2px 8px;margin:3px 3px 0;font-size:.72rem;color:#c7cdd6;">'
                    f'{_html.escape(str(b))}</span>'
                    for b in league_format_badges(league)
                )
                st.markdown(
                    f'<div style="background:repeating-linear-gradient(90deg,rgba(255,255,255,.018) 0 1px,'
                    f'transparent 1px 46px),var(--bg-page);border:1px solid var(--border);border-radius:16px;'
                    f'padding:44px 34px;min-height:440px;display:flex;flex-direction:column;'
                    f'justify-content:center;align-items:center;text-align:center;">'
                    f'<div style="margin-bottom:14px;">{_avatar_html}</div>'
                    f'<div style="font:700 1.45rem/1 \'Space Grotesk\',sans-serif;color:var(--text-hi);margin-bottom:10px;">'
                    f'{_lname}</div>'
                    f'<div style="margin-bottom:16px;">{_badge_html}</div>'
                    f'<div style="color:var(--text-mid);font-size:.9rem;line-height:1.5;">'
                    f'One quick setup to personalise<br>your dynasty command centre.</div>'
                    f'</div>', unsafe_allow_html=True)

            # ── Right panel — team + value source form ────────────────────────
            with _su_r:
                st.markdown('<div class="eyebrow" style="margin-top:10px;">Quick setup</div>',
                            unsafe_allow_html=True)
                st.markdown('<h2 style="margin:.25rem 0 .6rem;">Your team &amp; preferences</h2>',
                            unsafe_allow_html=True)
                st.caption("You can change these anytime from Settings.")

                st.markdown('<div class="eyebrow" style="margin-top:14px;">Your team</div>',
                            unsafe_allow_html=True)
                _setup_team_sel = st.selectbox(
                    "Your team", _teams0, index=_default_team_idx,
                    key="setup_team", label_visibility="collapsed")

                _vs_options = available_value_sources(num_qbs, owner_view)
                st.markdown('<div class="eyebrow" style="margin-top:14px;">Value source</div>',
                            unsafe_allow_html=True)
                _setup_vs_sel = st.selectbox(
                    "Value source", _vs_options,
                    index=(_vs_options.index(_lp0.get("value_source", "FC Dynasty"))
                           if _lp0.get("value_source") in _vs_options else 0),
                    key="setup_vs", format_func=vs_label, label_visibility="collapsed")

                # Dynamic per-source description + link
                _vs_blurb, _vs_url = _VS_INFO.get(_setup_vs_sel, ("", None))
                if _vs_blurb:
                    _link_md = f" [Visit site →]({_vs_url})" if _vs_url else ""
                    st.caption(f"{_vs_blurb}{_link_md}")

                st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
                if st.button("Continue →", type="primary", key="setup_go", width="stretch"):
                    _setup_ph.empty()
                    save_league_prefs(league_id, value_source=_setup_vs_sel, team=_setup_team_sel)
                    st.session_state.pop("_prefs_seeded_for", None)
                    st.session_state._onboarded_for = league_id
                    st.rerun()
                if st.button("← Back", key="setup_switch", width="stretch"):
                    st.session_state.league_id = None
                    st.rerun()
        st.stop()

# Initialise session-state defaults once (must happen before any widget with these keys)
st.session_state.setdefault("app_theme", "System Default")

# Re-hydrate per-user data whenever IDENTITY changes (sign in / out) — favourites
# are global, tags per league. The signed-in store is Supabase; guest is session.
_identity = st.session_state.get("auth_email") or "guest"
if st.session_state.get("_loaded_identity") != _identity:
    st.session_state._loaded_identity = _identity
    st.session_state.favorites = load_favorites()
    st.session_state.player_tags = load_player_tags(league_id)
    st.session_state._player_tags_league = league_id
    st.session_state.pop("_prefs_seeded_for", None)   # re-seed My Team / value source from store

# Reseed tags when the league changes within the same identity
if st.session_state.get("_player_tags_league") != league_id:
    st.session_state.player_tags = load_player_tags(league_id)
    st.session_state._player_tags_league = league_id

# ── Sidebar: identity + value source (rendered early — value_source drives the
#    data pipeline below; team names derive straight from rosters/users) ───────
_user_map_sb = {u["user_id"]: u for u in users}
def _roster_team_name(r):
    _u = _user_map_sb.get(r.get("owner_id") or "", {})
    return ((_u.get("metadata") or {}).get("team_name")
            or _u.get("display_name") or f"Team {r['roster_id']}")
_sb_team_names = sorted({_roster_team_name(r) for r in rosters})
# team name → owner Sleeper user (drives owner avatars across the app)
team_owner_user = {_roster_team_name(r): _user_map_sb.get(r.get("owner_id") or "", {})
                   for r in rosters}

with st.sidebar:
    # Brand logo IS the Home button: a full-width button painted with the logo
    # SVG as its background, label hidden. Clicking it returns to League Overview.
    if _LOGO_HORIZONTAL:
        _logo_uri = "data:image/svg+xml;base64," + base64.b64encode(
            _LOGO_HORIZONTAL.encode("utf-8")).decode("ascii")
        st.markdown(f"""
        <style>
        [data-testid="stSidebar"] .st-key-nav_home button{{
          height:60px; padding:0 !important; font-size:0 !important;
          border:none !important; background-color:transparent !important;
          background-image:url("{_logo_uri}");
          background-size:contain; background-repeat:no-repeat; background-position:center;
        }}
        [data-testid="stSidebar"] .st-key-nav_home button:hover{{
          background-color:transparent !important; filter:brightness(1.12);
        }}
        /* keep the label in the DOM for screen readers, but invisible */
        [data-testid="stSidebar"] .st-key-nav_home button p{{ opacity:0; }}
        </style>
        """, unsafe_allow_html=True)
    _home_label = "Dynasty FF Lil' Helper — Home" if _LOGO_HORIZONTAL else "Home"
    if st.button(_home_label, width="stretch", key="nav_home"):
        st.session_state.nav_page = "Overview"
        st.rerun()

    # ── Account: optional email sign-in (saves settings across devices) ───────
    if auth_available():
        if st.session_state.get("auth_email"):
            st.caption(f"Signed in · {st.session_state.auth_email}")
            if st.button("Sign out", width="stretch", key="auth_signout"):
                for _k in ("auth_email", "_auth_code_sent", "_auth_pending_email", "_onboarded_for"):
                    st.session_state.pop(_k, None)
                st.session_state.league_id = None              # back to the entry screen
                st.session_state.nav_page   = "Overview"  # land on Overview next time
                st.rerun()
        else:
            with st.expander("Sign in to save", expanded=False):
                if not st.session_state.get("_auth_code_sent"):
                    _ae = st.text_input("Email", key="auth_email_input", placeholder="you@email.com")
                    if st.button("Send code", width="stretch", key="auth_send"):
                        ok, err = auth_send_code(_ae)
                        if ok:
                            st.session_state._auth_code_sent = True
                            st.session_state._auth_pending_email = (_ae or "").strip()
                            st.rerun()
                        else:
                            st.error(f"Couldn't send code: {err}")
                else:
                    st.caption(f"Code sent to **{st.session_state.get('_auth_pending_email','')}** — check your email.")
                    _code = st.text_input("6-digit code", key="auth_code_input")
                    _c1, _c2 = st.columns(2)
                    if _c1.button("Verify", width="stretch", key="auth_verify"):
                        _em = auth_verify_code(st.session_state.get("_auth_pending_email", ""), _code)
                        if _em:
                            st.session_state.auth_email = _em
                            st.session_state.pop("_auth_code_sent", None)
                            st.session_state._toast_msg = f"Signed in as {_em}"
                            st.rerun()
                        else:
                            st.error("Invalid or expired code — try again.")
                    if _c2.button("Cancel", width="stretch", key="auth_cancel"):
                        st.session_state.pop("_auth_code_sent", None)
                        st.rerun()

    st.divider()
    render_league_header(league)
    render_league_badges(league)
    st.caption(f"Sleeper · {league.get('season', '')}")

    # My Team + Value Source are now chosen in Settings. Their state is still seeded
    # and persisted HERE (value_source must resolve before the data pipeline below),
    # and the selected team shows as a read-only identity badge under the league data.
    _team_opts = ["—"] + _sb_team_names
    if st.session_state.get("_prefs_seeded_for") != league_id:
        st.session_state._prefs_seeded_for = league_id
        _prefs = load_league_prefs(league_id)
        _saved_team = _prefs.get("team")
        st.session_state.my_team_pick = _saved_team if _saved_team in _team_opts else "—"
        _saved_vs = _prefs.get("value_source")
        _vs_opts_boot = available_value_sources(num_qbs, owner_view)
        st.session_state.value_source = _saved_vs if _saved_vs in _vs_opts_boot else "FC Dynasty"
        _saved_tf = _prefs.get("trade_fairness")
        st.session_state.trade_fairness = _saved_tf if _saved_tf in TF_PRESETS else "Off"
        st.session_state.pos_weighting = bool(_prefs.get("positional_weighting", True))
        # New league context → page-level sticky team choices no longer apply
        for _sk in [k for k in list(st.session_state.keys()) if str(k).startswith("_sticky_")]:
            st.session_state.pop(_sk, None)
        st.session_state.pop("_last_my_team", None)
        st.session_state.pop("_last_value_source", None)
        st.session_state.pop("_last_trade_fairness", None)
        st.session_state.pop("_last_pos_weighting", None)
    # Coerce any stale persisted choices into the currently-allowed sets
    _vs_options_sb = available_value_sources(num_qbs, owner_view)
    if st.session_state.get("value_source") not in _vs_options_sb:
        st.session_state.value_source = "FC Dynasty"
    if st.session_state.get("my_team_pick", "—") not in _team_opts:
        st.session_state.my_team_pick = "—"
    if st.session_state.get("trade_fairness") not in TF_PRESETS:
        st.session_state.trade_fairness = "Off"
    st.session_state.setdefault("pos_weighting", True)
    # The My Team / Value-source / Trade-fairness / Positional-weighting widgets live
    # only on Settings (+ the calculator for fairness). Streamlit drops widget-keyed
    # state on reruns where the widget isn't rendered, so re-assert each run.
    st.session_state.value_source = st.session_state.value_source
    st.session_state.my_team_pick = st.session_state.my_team_pick
    st.session_state.trade_fairness = st.session_state.trade_fairness
    st.session_state.pos_weighting = bool(st.session_state.pos_weighting)
    my_team = None if st.session_state.get("my_team_pick", "—") == "—" else st.session_state.my_team_pick

    # Read-only identity badge: owner avatar + team name + @handle, under the league data
    if my_team:
        _own    = team_owner_user.get(my_team)
        _own_nm = (_own or {}).get("display_name")
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:11px;margin:8px 0 2px;">'
            f'{user_avatar_tag(_own, my_team, px=40, radius=10)}'
            f'<div style="line-height:1.25;"><div style="font-size:.95rem;font-weight:700;color:var(--text-hi);">'
            f'{_html.escape(my_team)}</div>'
            + (f'<div style="font-size:.76rem;color:var(--text-mid);">@{_html.escape(_own_nm)}</div>'
               if _own_nm else '')
            + '</div></div>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size:.8rem;color:var(--text-mid);margin:3px 0 -2px;">'
            f'<strong style="color:var(--text-hi);">{vs_label(st.session_state.value_source)}</strong></div>',
            unsafe_allow_html=True)
        st.markdown(
            "<style>[data-testid='stSidebar'] .st-key-vs_change button{background:transparent!important;"
            "border:none!important;box-shadow:none!important;color:var(--gold)!important;padding:0!important;"
            "min-height:auto!important;height:auto!important;font-size:.76rem!important;font-weight:600!important;}"
            "[data-testid='stSidebar'] .st-key-vs_change button:hover{color:var(--green-bright)!important;}</style>",
            unsafe_allow_html=True)
        if st.button("change value source →", key="vs_change"):
            st.session_state.nav_page = "Settings"
            st.rerun()
    else:
        st.caption("No team selected — choose yours in **Settings**.")

    # Persist on change (the selectors that drive these now live in Settings)
    if st.session_state.get("_last_my_team", "__unset__") != my_team:
        save_league_prefs(league_id, team=my_team)
        for _sk in [k for k in list(st.session_state.keys()) if str(k).startswith("_sticky_")]:
            st.session_state.pop(_sk, None)
        st.session_state._last_my_team = my_team
    if st.session_state.get("_last_value_source") != st.session_state.value_source:
        save_league_prefs(league_id, value_source=st.session_state.value_source)
        st.session_state._last_value_source = st.session_state.value_source
    if st.session_state.get("_last_trade_fairness", "__unset__") != st.session_state.trade_fairness:
        save_league_prefs(league_id, trade_fairness=st.session_state.trade_fairness)
        st.session_state._last_trade_fairness = st.session_state.trade_fairness
    if st.session_state.get("_last_pos_weighting", "__unset__") != st.session_state.pos_weighting:
        save_league_prefs(league_id, positional_weighting=st.session_state.pos_weighting)
        st.session_state._last_pos_weighting = st.session_state.pos_weighting

# Positional Weighting — set the module globals get_active_value reads so the league's
# scoring tilt (e.g. TE-premium) flows into EVERY value/rank-derived number app-wide.
_PID_POS     = {pid: (p.get("position") or "") for pid, p in players.items()}
_POS_WEIGHTS = compute_pos_weights(scoring, st.session_state.pos_weighting)
_pw_tag      = "pw" + "_".join(f"{k}{v}" for k, v in sorted(_POS_WEIGHTS.items()) if v != 1.0)

value_source = st.session_state["value_source"]
val_col      = value_col_label(value_source)   # dynamic column header e.g. "FC D Value"
active_values = {
    pid: get_active_value(pid, fc_values, val_maps, value_source)
    for pid in set(list(fc_values.keys()) + list(dn_map.keys()) + list(ktc_map.keys()) + list(dp_map.keys()))
}


# ── Dark theme (single source of truth) ───────────────────────────────────────
# Dark-only by design: several hand-built elements (Power Rankings table, chart
# colours) are styled for dark. "System Default" shipped a broken light view to
# light-mode users, so it was removed. Light can return once those are tokenised.
_theme = "Dark"   # drives Plotly chart templates; surfaces/colours now via config.toml + top CSS

# Trade/DEF analysis — cached in session_state; only recomputes when value_source changes or Refresh is clicked
_trade_cache_key = f"trade_data_{league_id}_{value_source}_{_pw_tag}"
if st.session_state.get("_trade_cache_key") != _trade_cache_key:
    team_data, league_avgs, all_players_by_pos = build_trade_analysis(
        rosters, users, players, fc_values, fc_picks, slot_map, traded_ownership, drafts,
        active_values=active_values,
    )
    def_analysis, league_def_avg = build_def_analysis(rosters, users, players, player_pts)
    team_name_to_rid = {td["name"]: rid for rid, td in team_data.items()}
    st.session_state._trade_cache_key    = _trade_cache_key
    st.session_state._team_data          = team_data
    st.session_state._league_avgs        = league_avgs
    st.session_state._all_players_by_pos = all_players_by_pos
    st.session_state._team_name_to_rid   = team_name_to_rid
    st.session_state._def_analysis       = def_analysis
    st.session_state._league_def_avg     = league_def_avg
else:
    team_data          = st.session_state._team_data
    league_avgs        = st.session_state._league_avgs
    all_players_by_pos = st.session_state._all_players_by_pos
    team_name_to_rid   = st.session_state._team_name_to_rid
    def_analysis       = st.session_state._def_analysis
    league_def_avg     = st.session_state._league_def_avg

# ── Sidebar navigation ────────────────────────────────────────────────────────
# Page keys are the plain display names (no emoji). format_func prepends a
# monochrome Material Symbols icon that inherits the label's text colour (→ green
# when active). Trending and Rookie Class now live inside Front Office; the Batch-2
# rebuild lifts these same labels into a top menu, so keep the names as-is here.
_NAV_ICONS = {
    "Overview":         "home",
    "Players & Picks":  "list_alt",
    "Front Office":     "person_search",
    "Fantasy News":     "newspaper",
    "Trade Room":       "swap_horiz",
    "Draft Room":       "dashboard",
    "Settings":         "settings",
}


def _nav_label(page_key: str) -> str:
    """page key → ':material/icon: Label' (icon prepended to the plain name)."""
    return f":material/{_NAV_ICONS.get(page_key, 'circle')}: {page_key}"


with st.sidebar:
    st.divider()
    page = st.radio("Navigation", list(_NAV_ICONS.keys()), format_func=_nav_label,
                    label_visibility="collapsed", key="nav_page")


def _refresh_all_data():
    """Clear every cached source so the next run re-fetches fresh data."""
    load_all_data.clear()
    fetch_dn_values.clear()
    fetch_ktc_values.clear()
    fetch_dp_values.clear()
    load_trending.clear()
    fetch_rss_news.clear()
    for _k in ["_trade_cache_key", "_team_data", "_league_avgs",
               "_all_players_by_pos", "_team_name_to_rid", "_def_analysis", "_league_def_avg",
               "_data_warmed_for"]:   # re-show the loading spinner during the real re-fetch
        st.session_state.pop(_k, None)

# Flush any pending save confirmation (set before a st.rerun on the previous run)
if st.session_state.get("_toast_msg"):
    st.toast(st.session_state.pop("_toast_msg"), icon=":material/save:")

def _render_trending_section():
    with st.spinner("Loading trending data..."):
        try:
            adds, drops = load_trending()
        except Exception as e:
            st.error(f"Failed to load trending: {e}")
            adds, drops = [], []

    df_tr = build_trending_df(adds, drops, players, rosters, users, player_pts, fc_values,
                              val_maps=val_maps, value_source=value_source)
    df_tr = df_tr.rename(columns={"Value": val_col})

    col_a, col_b, col_c = st.columns([2, 2, 3])
    sel_tr_type  = col_a.selectbox("Trend Type",   ["All", "Add", "Drop"],        key="tr_type")
    sel_tr_avail = col_b.selectbox("Availability", ["All", "Available", "Taken"], key="tr_avail")
    tr_srch      = col_c.text_input("Search player name", key="tr_name",           placeholder="e.g. Brock Purdy")

    mask = pd.Series(True, index=df_tr.index)
    if sel_tr_type  == "Add":       mask &= df_tr["Trend"]     == "Add"
    elif sel_tr_type == "Drop":     mask &= df_tr["Trend"]     == "Drop"
    if sel_tr_avail == "Available": mask &= df_tr["Available"] == "Yes"
    elif sel_tr_avail == "Taken":   mask &= df_tr["Available"] == "No"
    if tr_srch:                     mask &= df_tr["Player"].str.contains(tr_srch, case=False, na=False)
    dv = df_tr[mask]

    _tr_col_cfg = {
        val_col:               COL_CFG["Value"],
        "Rank":                COL_CFG["Rank"],
        f"{STATS_SEASON} Pts": COL_CFG[f"{STATS_SEASON} Pts"],
    }
    dv = dash_na(dv)
    if my_team and "Dynasty Team" in dv.columns and (dv["Dynasty Team"] == my_team).any():
        _tr_hl = "background-color: rgba(255, 196, 0, 0.18)"
        _tr_styled = dv.style.apply(
            lambda row: [_tr_hl if row["Dynasty Team"] == my_team else "" for _ in row], axis=1
        )
        st.dataframe(_tr_styled, width="stretch", hide_index=True, column_config=_tr_col_cfg)
        _tr_note = f" · highlighted = {my_team}"
    else:
        st.dataframe(dv, width="stretch", hide_index=True, column_config=_tr_col_cfg)
        _tr_note = ""
    st.caption(f"Top adds + drops across all Sleeper leagues (last {TREND_LOOKBACK}h) · {len(dv)} shown · Value source: **{value_source}**{_tr_note}")


def _render_rookie_class_section():
    df_rk = build_rookies_df(fc_rookies, rosters, fc_values=fc_values, val_maps=val_maps, value_source=value_source)
    df_rk = df_rk.rename(columns={"Value": val_col, "Rank": "Overall Rank"})

    col_a, col_b, col_c, col_d = st.columns([2, 2, 3, 1])
    sel_rk_pos  = col_a.multiselect("Positions",    sorted(df_rk["Pos"].unique().tolist()), key="rk_pos",
                                    placeholder="All positions")
    sel_rk_rost = col_b.selectbox("Roster Status",  ["All", "On Roster", "Not Rostered"],   key="rk_rost")
    rk_srch     = col_c.text_input("Search player name", key="rk_name", placeholder="e.g. Ashton Jeanty")
    col_d.markdown('<div style="padding-top: 1.75rem;"></div>', unsafe_allow_html=True)
    rk_fav_only = col_d.checkbox("Only", key="rk_fav_only")

    mask = pd.Series(True, index=df_rk.index)
    if sel_rk_pos:                      mask &= df_rk["Pos"].isin(sel_rk_pos)
    if sel_rk_rost == "On Roster":      mask &= df_rk["On Roster"] == "Yes"
    elif sel_rk_rost == "Not Rostered": mask &= df_rk["On Roster"] == "No"
    if rk_srch:                         mask &= df_rk["Player"].str.contains(rk_srch, case=False, na=False)
    if rk_fav_only:                     mask &= df_rk["Player"].isin(st.session_state.favorites)
    dv = df_rk[mask]

    fav_grid(dv, "Player", "rk_fav_grid",
             col_cfg={val_col: COL_CFG["Value"], "Overall Rank": COL_CFG["Rank"]})
    st.caption(f"{plural(len(dv), 'rookie')} shown (sorted by rookie value) · \"Overall Rank\" = dynasty rank across all players · Value source: **{value_source}** · tick the Fav box to favourite")


# ── Page: Overview ─────────────────────────────────────────────────────
if page == "Overview":
    @st.fragment
    def _frag_league_overview():
        _hc1, _hc2 = st.columns([4, 1], vertical_alignment="center")
        with _hc1:
            render_league_title(league)
        with _hc2:
            if st.button(":material/sync: Switch league", key="ov_switch_league", width="stretch"):
                st.session_state.league_id = None
                st.rerun()
        _ov_tabs = st.tabs(["My Team Dashboard", "Positional Strength & Rebuild"])

        with _ov_tabs[0]:
            # ── My Team dashboard (rating · needs · best partner · cut-for-pickup) ────
            render_team_dashboard(my_team, team_name_to_rid, team_data, league_avgs,
                                  players, player_pts, rosters, pos_ranks,
                                  fc_values, val_maps, value_source, val_col)

            st.markdown("---")
            # ── League Power Rankings table ───────────────────────────────────────────
            st.subheader("League Power Rankings")

            _cb1, _cb2, _ = st.columns([1, 1, 4])
            _excl_def   = _cb1.checkbox("Exclude DEF",   key="pr_excl_def")
            _excl_picks = _cb2.checkbox("Exclude Picks", key="pr_excl_picks")

            _active_dims = ["QB", "RB", "WR", "TE"]
            if not _excl_picks: _active_dims.append("PICK")
            if not _excl_def:   _active_dims.append("DEF")
            _dim_count = len(_active_dims)
            st.caption(f"Score = average normalised rank across {_dim_count} dimension{'s' if _dim_count != 1 else ''}: {', '.join(_active_dims).replace('PICK','Picks')}")

            _n = len(team_data)

            # DEF ranks — sort teams by avg def pts descending
            _def_vals  = {rid: (def_analysis.get(rid) or {}).get("avg_pts") for rid in team_data}
            _def_order = sorted([x for x in _def_vals.items() if x[1] is not None], key=lambda x: x[1], reverse=True)
            _def_rank_map = {rid: i + 1 for i, (rid, _) in enumerate(_def_order)}

            # Build one row per team
            _pr_rows = []
            for rid, _td in team_data.items():
                _lr = {**_td.get("pos_league_rank", {}), "DEF": _def_rank_map.get(rid)}
                _norm = []
                for _d in _active_dims:
                    r = _lr.get(_d)
                    if r is not None:
                        _norm.append((1 - (r - 1) / max(_n - 1, 1)) * 100)
                _overall = round(sum(_norm) / len(_norm)) if _norm else 0
                _pr_rows.append({
                    "team": _td["name"], "QB": _lr.get("QB"), "RB": _lr.get("RB"),
                    "WR": _lr.get("WR"), "TE": _lr.get("TE"),
                    "Picks": _lr.get("PICK"), "DEF": _lr.get("DEF"), "score": _overall,
                })
            _pr_rows.sort(key=lambda x: x["score"], reverse=True)

            # Per-position mini-rank: compact "#n" coloured by quality tier (token
            # colours), struck-through + faint when excluded from the score.
            def _pr_rank(rank, n, excluded=False, hl=""):
                if rank is None:
                    return f'<td style="text-align:center;padding:6px 4px;{hl}"><span style="color:var(--text-faint)">—</span></td>'
                if excluded:
                    return (f'<td style="text-align:center;padding:6px 4px;{hl}">'
                            f'<span style="color:var(--text-faint);text-decoration:line-through;'
                            f'font-size:0.82rem">#{rank}</span></td>')
                pct = 1 - (rank - 1) / max(n - 1, 1)
                if   pct >= 0.75: c = "var(--green-bright)"
                elif pct >= 0.5:  c = "var(--text-body)"
                elif pct >= 0.25: c = "var(--text-mid)"
                else:             c = "var(--pill-red-fg)"
                return (f'<td style="text-align:center;padding:6px 4px;{hl}">'
                        f'<span style="color:{c};font-weight:600;font-size:0.84rem">#{rank}</span></td>')

            def _pr_th(label, align="center", excluded=False):
                deco = "text-decoration:line-through;" if excluded else ""
                return (f'<th style="text-align:{align};padding:6px 8px 10px;color:var(--text-faint);'
                        f'font-weight:600;font-size:11px;letter-spacing:1px;text-transform:uppercase;'
                        f'{deco}">{label}</th>')

            _tbl_html = (
                '<table style="width:100%;border-collapse:separate;border-spacing:0 4px;font-size:0.88rem;margin-top:6px">'
                '<thead><tr>'
                + _pr_th("#") + _pr_th("Team", "left")
                + _pr_th("QB") + _pr_th("RB") + _pr_th("WR") + _pr_th("TE")
                + _pr_th("Picks", excluded=_excl_picks) + _pr_th("DEF", excluded=_excl_def)
                + _pr_th("Score", "left")
                + '</tr></thead><tbody>'
            )

            for i, row in enumerate(_pr_rows):
                _is_mine = my_team and row["team"] == my_team
                _sc = row["score"]
                # User row reads as a rounded highlighted pill (--row-you-*); others
                # sit transparently on the card.
                if _is_mine:
                    _hl   = ("background:var(--row-you-bg);border-top:1px solid var(--row-you-border);"
                             "border-bottom:1px solid var(--row-you-border);")
                    _hl_l = _hl + ("border-left:1px solid var(--row-you-border);"
                                   "border-top-left-radius:10px;border-bottom-left-radius:10px;")
                    _hl_r = _hl + ("border-right:1px solid var(--row-you-border);"
                                   "border-top-right-radius:10px;border-bottom-right-radius:10px;")
                    _chip_bg, _chip_fg = "var(--pill-green-bg)", "var(--green-bright)"
                    _name_c, _name_w   = "var(--text-hi)", 700
                    _fill, _sc_c, _sc_w = "var(--green-bright)", "var(--text-hi)", 700
                    _you = ('<span class="pill green" style="padding:2px 9px;font-size:11px;'
                            'margin-left:8px;vertical-align:middle">YOU</span>')
                else:
                    _hl = _hl_l = _hl_r = ""
                    _chip_bg, _chip_fg = "var(--bg-raised)", "var(--text-body)"
                    _name_c, _name_w   = "var(--text-body)", 500
                    _fill, _sc_c, _sc_w = "var(--green)", "var(--text-body)", 600
                    _you = ""

                _chip = (f'<span style="display:inline-flex;align-items:center;justify-content:center;'
                         f'width:28px;height:28px;border-radius:8px;background:{_chip_bg};color:{_chip_fg};'
                         f'font-weight:700;font-size:0.84rem">{i+1}</span>')

                _pr_av = user_avatar_tag(globals().get("team_owner_user", {}).get(row["team"]),
                                         row["team"], px=22, radius=6)
                _tbl_html += '<tr>'
                _tbl_html += f'<td style="text-align:center;padding:6px 4px;{_hl_l}">{_chip}</td>'
                _tbl_html += (f'<td style="padding:6px 12px;color:{_name_c};font-weight:{_name_w};{_hl}">'
                              f'<div style="display:flex;align-items:center;gap:8px;">{_pr_av}'
                              f'<span>{row["team"]}{_you}</span></div></td>')
                for _dim, _excl in [("QB", False), ("RB", False), ("WR", False), ("TE", False),
                                    ("Picks", _excl_picks), ("DEF", _excl_def)]:
                    _tbl_html += _pr_rank(row[_dim], _n, excluded=_excl, hl=_hl)
                _tbl_html += (f'<td style="padding:6px 14px 6px 8px;{_hl_r}">'
                              f'<div style="display:flex;align-items:center;gap:10px">'
                              f'<div style="background:var(--bg-hover);border-radius:4px;height:8px;flex:1;min-width:60px">'
                              f'<div style="background:{_fill};width:{_sc}%;height:8px;border-radius:4px"></div></div>'
                              f'<span style="font-size:0.84rem;color:{_sc_c};font-weight:{_sc_w};'
                              f'min-width:24px;text-align:right">{_sc}</span>'
                              f'</div></td></tr>')

            _tbl_html += "</tbody></table>"
            st.markdown(_tbl_html, unsafe_allow_html=True)

        with _ov_tabs[1]:
            # ── Chart A: Radar / Positional Strength ──────────────────────────────────
            with st.container():
                st.subheader("Positional Strength")
                st.caption("Radar chart — each dimension normalised 0–100 across teams (0 = weakest, 100 = strongest)")

                # Build per-team values for each radar axis
                radar_dims = ["QB", "RB", "WR", "TE", "PICK", "DEF"]

                # Skill positions from team_data pos_avgs
                raw_radar = {dim: {} for dim in radar_dims}
                for rid, td in team_data.items():
                    for dim in ["QB", "RB", "WR", "TE", "PICK"]:
                        raw_radar[dim][rid] = td["pos_avgs"].get(dim)
                # DEF from def_analysis
                for rid in team_data:
                    de = def_analysis.get(rid, {})
                    raw_radar["DEF"][rid] = de.get("avg_pts")

                # Normalise each dimension
                norm_radar = {dim: normalize_dim(raw_radar[dim]) for dim in radar_dims}

                # Team name lookup
                rid_to_name = {rid: td["name"] for rid, td in team_data.items()}
                all_team_names_sorted = sorted(rid_to_name.values())

                default_sel = st.session_state.get("_sticky_radar_sel")
                if default_sel is None:   # no choice this session → default to My Team
                    if my_team in all_team_names_sorted:
                        default_sel = [my_team]
                    else:
                        default_sel = [all_team_names_sorted[0]] if all_team_names_sorted else []
                default_sel = [t for t in default_sel if t in all_team_names_sorted]
                selected_teams = st.multiselect(
                    "Highlight teams (1–3)",
                    options=all_team_names_sorted,
                    default=default_sel,
                    max_selections=3,
                    key="radar_sel",
                )
                st.session_state._sticky_radar_sel = selected_teams

                HIGHLIGHT_COLORS = ["#2196F3", "#F44336", "#4CAF50"]
                _chart_template = "plotly_dark" if _theme == "Dark" else "plotly_white"
                _bg_trace_color = "rgba(180,180,180,0.10)"   # faint so selected teams pop
                name_to_rid = {td["name"]: rid for rid, td in team_data.items()}
                _sel_rids = {name_to_rid.get(t) for t in selected_teams}

                fig_radar = go.Figure()

                # Faded background traces for NON-selected teams only (context, not clutter)
                for rid, td in team_data.items():
                    if rid in _sel_rids:
                        continue
                    r_vals = [norm_radar[dim][rid] for dim in radar_dims]
                    r_vals += [r_vals[0]]  # close polygon
                    dims_closed = radar_dims + [radar_dims[0]]
                    fig_radar.add_trace(go.Scatterpolar(
                        r=r_vals,
                        theta=dims_closed,
                        line=dict(color=_bg_trace_color, width=1),
                        opacity=0.5,
                        showlegend=False,
                        hoverinfo="skip",
                    ))

                # Coloured traces for selected teams
                for i, team_name in enumerate(selected_teams):
                    sel_rid = name_to_rid.get(team_name)
                    if sel_rid is None:
                        continue
                    r_vals = [norm_radar[dim][sel_rid] for dim in radar_dims]
                    r_vals += [r_vals[0]]
                    dims_closed = radar_dims + [radar_dims[0]]
                    fig_radar.add_trace(go.Scatterpolar(
                        r=r_vals,
                        theta=dims_closed,
                        line=dict(color=HIGHLIGHT_COLORS[i], width=2.5),
                        name=team_name,
                    ))

                fig_radar.update_layout(
                    polar=dict(
                        radialaxis=dict(visible=True, range=[0, 100]),
                        bgcolor="rgba(0,0,0,0)",
                    ),
                    showlegend=True,
                    height=500,
                    margin=dict(t=60, b=40, l=60, r=60),   # padding so axis labels (QB) don't clip
                    template=_chart_template,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_radar, use_container_width=True)

            # ── Chart C: Rebuild vs Contend Scatter ───────────────────────────────────
            with st.container():
                st.subheader("Rebuild vs. Contend")
                st.caption("X = average roster age · Y = total FC value. Quadrant lines at league medians.")

                scatter_rows = []
                for rid, td in team_data.items():
                    # Collect ages of all rostered players
                    ages = []
                    for pos in ["QB", "RB", "WR", "TE"]:
                        for player_entry in td["pos_players"].get(pos, []):
                            pid = player_entry.get("pid")
                            if pid:
                                age = players.get(pid, {}).get("age")
                                if age:
                                    ages.append(age)
                    avg_age = sum(ages) / len(ages) if ages else None
                    total_val = sum(
                        p["value"]
                        for pos in ["QB", "RB", "WR", "TE"]
                        for p in td["pos_players"].get(pos, [])
                    )
                    if avg_age is not None:
                        scatter_rows.append({
                            "Team": td["name"],
                            "Avg Age": round(avg_age, 1),
                            "Total Value": total_val,
                        })

                if scatter_rows:
                    df_scatter = pd.DataFrame(scatter_rows)
                    median_age   = df_scatter["Avg Age"].median()
                    median_value = df_scatter["Total Value"].median()
                    min_age      = df_scatter["Avg Age"].min()
                    max_age      = df_scatter["Avg Age"].max()
                    min_val      = df_scatter["Total Value"].min()
                    max_val      = df_scatter["Total Value"].max()

                    fig_scatter = px.scatter(
                        df_scatter,
                        x="Avg Age",
                        y="Total Value",
                        text="Team",
                        height=450,
                    )
                    # Highlight My Team in gold, everyone else blue
                    _mk_colors = ["#ffc400" if t == my_team else "#2196F3" for t in df_scatter["Team"]]
                    _mk_sizes  = [17 if t == my_team else 12 for t in df_scatter["Team"]]
                    fig_scatter.update_traces(
                        textposition="top center",
                        textfont=dict(size=10),
                        marker=dict(size=_mk_sizes, color=_mk_colors,
                                    line=dict(width=1, color="rgba(0,0,0,0.3)")),
                        cliponaxis=False,
                    )

                    # Quadrant lines
                    _qline_color = "rgba(200,200,200,0.6)" if _theme == "Dark" else "rgba(100,100,100,0.4)"
                    fig_scatter.add_hline(y=median_value, line_dash="dot", line_color=_qline_color)
                    fig_scatter.add_vline(x=median_age,   line_dash="dot", line_color=_qline_color)

                    # Quadrant labels
                    pad_x = (max_age - min_age) * 0.05
                    pad_y = (max_val - min_val) * 0.05
                    quadrant_labels = [
                        (min_age + pad_x, max_val - pad_y, "Win Now"),
                        (max_age - pad_x, max_val - pad_y, "Fading"),
                        (min_age + pad_x, min_val + pad_y, "Rebuilding"),
                        (max_age - pad_x, min_val + pad_y, "Stuck"),
                    ]
                    for qx, qy, qtxt in quadrant_labels:
                        fig_scatter.add_annotation(
                            x=qx, y=qy, text=qtxt,
                            showarrow=False,
                            font=dict(size=11, color="grey"),
                            opacity=0.7,
                        )

                    # Expand axis ranges so corner quadrant labels and team names don't clip
                    _xr = (max_age - min_age) or 1
                    _yr = (max_val - min_val) or 1
                    fig_scatter.update_layout(
                        margin=dict(t=20, b=40, l=10, r=10),
                        template=_chart_template,
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(range=[min_age - _xr * 0.15, max_age + _xr * 0.15]),
                        yaxis=dict(range=[min_val - _yr * 0.18, max_val + _yr * 0.18]),
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)
                    if my_team:
                        st.caption(f"Gold dot = {my_team}")
                else:
                    st.info("Not enough roster age data to generate scatter chart.")

    # ── Page: Rosters ─────────────────────────────────────────────────────────────
    _frag_league_overview()
elif page == "Players & Picks":
    df_r = build_rosters_df(rosters, users, players, player_pts, pos_ranks, fc_values,
                            val_maps=val_maps, value_source=value_source)
    # All four sources are shown side-by-side now (Players page merged in), so the
    # single dynamic active-value column is redundant — drop it.
    df_r = df_r.drop(columns=["Value"]).rename(columns={"_cons_avg": "Cons. Avg"})

    _pp_tabs = st.tabs(["Players", "Trade Block", "Draft Picks"])

    with _pp_tabs[0]:
        st.header(":material/groups: Players")
        col_a, col_b, col_c, col_d = st.columns([2, 2, 2, 3])
        _r_team_opts = sorted(df_r["Team"].unique().tolist())
        _r_default = st.session_state.get("_sticky_r_team")
        if _r_default is None:   # no choice made this session → default to My Team
            _r_default = [my_team] if my_team in _r_team_opts else []
        _r_default = [t for t in _r_default if t in _r_team_opts]
        sel_teams = col_a.multiselect("Teams", _r_team_opts, default=_r_default, key="r_team",
                                      placeholder="All teams")
        st.session_state._sticky_r_team = sel_teams
        sel_pos   = col_b.multiselect("Positions", sorted(df_r["Pos"].unique().tolist()),   key="r_pos",
                                      placeholder="All positions")
        sel_slots = col_c.multiselect("Slot",      ["Starter", "Bench", "Taxi"],            key="r_slot",
                                      placeholder="All slots")
        name_srch = col_d.text_input("Search player name", key="r_name", placeholder="e.g. Ja'Marr Chase")
        r_fav_only = st.checkbox("Favourites only", key="r_fav_only")

        mask = pd.Series(True, index=df_r.index)
        if sel_teams: mask &= df_r["Team"].isin(sel_teams)
        if sel_pos:   mask &= df_r["Pos"].isin(sel_pos)
        if sel_slots: mask &= df_r["Slot"].isin(sel_slots)
        if name_srch: mask &= df_r["Player"].str.contains(name_srch, case=False, na=False)
        if r_fav_only: mask &= df_r["Player"].isin(st.session_state.favorites)
        dv = df_r[mask]

        # All four sources side-by-side (merged from the old Players page) + Cons. Avg
        # Only show the value columns that are actually available for this league/viewer
        # (KTC/DN are hidden for the public and in 1-QB), so no empty columns appear.
        _src_cols = [value_col_label(s) for s in available_value_sources(num_qbs, owner_view)]
        _src_cols = [c for c in _src_cols if c in dv.columns]
        display_cols = (["Team", "Owner", "Slot", "Player", "Pos", "NFL Team", "Roster Spot",
                         "Age", "Exp", "Status", f"{STATS_SEASON} Pts", "Pos Rank"]
                        + _src_cols + ["Rank", "30d Trend", "Tier"])

        _num = {c: st.column_config.NumberColumn(format="%d") for c in _src_cols}
        col_cfg = {
            **_num,
            **{k: COL_CFG[k] for k in [f"{STATS_SEASON} Pts", "Rank", "Pos Rank"] if k in dv.columns},
            "Roster Spot": st.column_config.Column(
                "Roster Spot",
                help="NFL depth-chart position from Sleeper (e.g. RB1 = first-string RB, "
                     "LWR/RWR/SWR = left/right/slot WR, NT/DL = defensive line). Not your fantasy lineup slot — "
                     "that's the 'Slot' column.",
            ),
        }

        # Default sort: position order (QB→RB→WR→TE→…) then overall Rank (best first, unranked last)
        _r_pos_order = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "K": 4, "DEF": 5, "DL": 6, "LB": 7, "DB": 8}
        dv = dv.sort_values(
            by=["Pos", "Rank"],
            key=lambda col: col.map(_r_pos_order).fillna(99) if col.name == "Pos"
                            else pd.to_numeric(col, errors="coerce").fillna(999999),
        ).reset_index(drop=True)

        fav_grid(dv[display_cols], "Player", "r_fav_grid", col_cfg=col_cfg)
        st.caption(f"{plural(len(dv), 'player')} shown · all sources normalised to 0–10K · tick the Fav box to favourite")

        st.divider()
        rid_to_name = {rid: _td2["name"] for rid, _td2 in team_data.items()}
        _chart_template = "plotly_dark" if _theme == "Dark" else "plotly_white"
        # ── Chart B: Roster Value Stacked Bar ────────────────────────────────────
        with st.container():
            st.subheader("Roster Value by Position")
            st.caption("Total FC value per team, stacked by position (skill positions only). Sorted descending.")

            POS_COLORS = {"QB": "#3B82F6", "RB": "#10B981", "WR": "#F59E0B", "TE": "#EF4444"}

            # Compute total value per team and sort descending
            total_vals = {}
            for rid, td in team_data.items():
                total = sum(
                    p["value"]
                    for pos in ["QB", "RB", "WR", "TE"]
                    for p in td["pos_players"].get(pos, [])
                )
                total_vals[rid] = total

            sorted_rids = sorted(total_vals.keys(), key=lambda r: total_vals[r])
            team_names_bar = [rid_to_name[rid] for rid in sorted_rids]

            fig_bar = go.Figure()
            for pos, color in POS_COLORS.items():
                values = [
                    sum(p["value"] for p in team_data[rid]["pos_players"].get(pos, []))
                    for rid in sorted_rids
                ]
                _seg_ranks = []
                for rid in sorted_rids:
                    _rk = team_data[rid].get("pos_league_rank", {}).get(pos)
                    _seg_ranks.append(f"#{_rk}" if _rk else "")
                fig_bar.add_trace(go.Bar(
                    name=pos,
                    y=team_names_bar,
                    x=values,
                    orientation="h",
                    marker_color=color,
                    text=_seg_ranks,
                    textposition="inside",
                    insidetextanchor="middle",
                    textfont=dict(size=11, color="white"),
                ))

            fig_bar.update_layout(
                barmode="stack",
                height=420,
                xaxis_title="Total FC Value",
                yaxis_title="",
                margin=dict(t=20, b=40, l=160),
                template=_chart_template,
                uniformtext_minsize=9,
                uniformtext_mode="show",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.caption("#N inside each segment = that team's league rank at the position (by avg value).")
            st.plotly_chart(fig_bar, use_container_width=True)

    with _pp_tabs[1]:
        # ── Trade Block (My Team) — players you are shopping ──────────────────────
        st.header(":material/sell: Trade Block")
        if not my_team:
            st.info("Set **My Team** in the sidebar to tag your players.")
        else:
            _my_rid = team_name_to_rid.get(my_team)
            _my_pp  = team_data.get(_my_rid, {}).get("pos_players", {}) if _my_rid else {}
            _my_players = [
                {"name": p["name"], "pos": _pos, "value": p["value"]}
                for _pos in SKILL_POSITIONS for p in _my_pp.get(_pos, [])
            ]
            _my_players.sort(key=lambda x: x["value"] or 0, reverse=True)
            _r_block = [p for p in _my_players if st.session_state.player_tags.get(p["name"]) == "Trade Block"]
            if _r_block:
                st.markdown("**Your Trade Block:** " + " · ".join(f"{p['name']} ({p['pos']})" for p in _r_block))
            st.caption(f"Tagging **{my_team.strip()}** · Untouchable players are never suggested in trades · shared with the Trade Room")
            tag_editor(_my_players, "tags_rosters")

    with _pp_tabs[2]:
        # ── Draft Picks ───────────────────────────────────────────────────────────
        st.header(":material/sports_football: Draft Picks")
        df_p = build_picks_df(rosters, users, traded_ownership, drafts, slot_map, fc_picks)

        _curr_year   = str(datetime.now().year)
        _all_seasons = sorted(df_p["Season"].unique().tolist())

        col_a, col_b = st.columns(2)
        sel_teams_p = col_a.multiselect("Teams",   sorted(df_p["Team"].unique().tolist()),   key="p_team",
                                        placeholder="All teams")
        sel_seasons = col_b.multiselect(
            "Season",
            options=_all_seasons,
            default=[_curr_year] if _curr_year in _all_seasons else _all_seasons[:1],
            key="p_season",
        )

        mask = pd.Series(True, index=df_p.index)
        if sel_teams_p: mask &= df_p["Team"].isin(sel_teams_p)
        if sel_seasons: mask &= df_p["Season"].isin(sel_seasons)
        dv = df_p[mask]

        # Enrich with trade context: owning team's pick status + biggest positional need
        def _pick_pos_status(team_name):
            _rid = team_name_to_rid.get(team_name)
            if not _rid: return "—"
            _td  = team_data.get(_rid, {})
            rel  = _td.get("relative", {}).get("PICK")
            if rel is None: return "—"
            if rel >= 10:  return "Surplus"
            if rel <= -10: return "Deficit"
            return "Average"

        def _team_biggest_need(team_name):
            _rid = team_name_to_rid.get(team_name)
            if not _rid: return "—"
            _td  = team_data.get(_rid, {})
            np   = _td.get("need_pos")
            ns   = _td.get("need_scores", {}).get(np)
            if not np: return "—"
            return f"{np}  ({ns:.0f}/100)" if ns is not None else np

        dv = dv.copy()
        dv["Owner's Pick Status"] = dv["Team"].apply(_pick_pos_status)
        dv["Owner's Biggest Need"] = dv["Team"].apply(_team_biggest_need)

        # Sort by Season → Round → slot number within the pick (1.01, 1.02 … 5.12)
        def _slot_key(v):
            try:    return int(str(v).split(".")[1])
            except: return 99
        dv = dv.sort_values(
            by=["Season", "Round", "Pick"],
            key=lambda col: col.apply(_slot_key) if col.name == "Pick" else col,
        ).reset_index(drop=True)

        # Highlight My Team's picks (semi-transparent gold works on dark + light themes)
        if my_team and (dv["Team"] == my_team).any():
            _hl = "background-color: rgba(255, 196, 0, 0.18)"
            _styled = dv.style.apply(
                lambda row: [_hl if row["Team"] == my_team else "" for _ in row], axis=1
            )
            st.dataframe(
                _styled, width="stretch", hide_index=True,
                column_config={"Value": COL_CFG["Value"]},
            )
        else:
            st.dataframe(
                dv, width="stretch", hide_index=True,
                column_config={"Value": COL_CFG["Value"]},
            )
        _hl_note = f" · highlighted = {my_team}" if my_team and (dv["Team"] == my_team).any() else ""
        st.caption(f"{plural(len(dv), 'pick')} shown · Surplus = pick-rich · Average · Deficit = pick-poor{_hl_note}")

# ── Page: Free Agents ────────────────────────────────────────────────────────
elif page == "Front Office":
    df_fa = build_fa_df(rosters, players, player_pts, pos_ranks, fc_values,
                        val_maps=val_maps, value_source=value_source)
    df_fa = df_fa.rename(columns={"Value": val_col})

    # Resolve _cons_avg column
    if value_source != "Consensus Avg":
        df_fa = df_fa.rename(columns={"_cons_avg": "Cons. Avg"})
    else:
        df_fa = df_fa.drop(columns=["_cons_avg"])

    st.title("Front Office")
    _fo_tabs = st.tabs(["Trending on Sleeper", "League Free Agents", "Pickup & Drop Advisor", "Rookie Class"])

    with _fo_tabs[0]:
        _render_trending_section()

    with _fo_tabs[1]:
        st.header(":material/person_search: League Current Free Agents")
        col_a, col_b, col_c, col_d = st.columns([2, 2, 2, 3])

        sel_fa_pos    = col_a.multiselect("Positions", sorted(df_fa["Pos"].unique().tolist()), key="fa_pos",
                                          placeholder="All positions")
        col_b.markdown('<div style="padding-top: 1.75rem;"></div>', unsafe_allow_html=True)
        incl_rookies  = col_b.checkbox("Include Rookies", value=False, key="fa_rookies")
        fa_fav_only   = col_b.checkbox("Favourites only", key="fa_fav_only")
        min_val       = col_c.number_input("Min Value", min_value=0, value=0, step=100, key="fa_min",
                                           help="0 shows every unrostered player. Raise to hide deep-bench noise.")
        fa_srch       = col_d.text_input("Search player name", key="fa_name", placeholder="e.g. Austin Ekeler")

        mask = pd.Series(True, index=df_fa.index)
        if sel_fa_pos:       mask &= df_fa["Pos"].isin(sel_fa_pos)
        if not incl_rookies: mask &= df_fa["Exp"] != "Rookie"
        if min_val > 0:      mask &= df_fa[val_col].notna() & (df_fa[val_col] >= min_val)
        if fa_srch:          mask &= df_fa["Player"].str.contains(fa_srch, case=False, na=False)
        if fa_fav_only:      mask &= df_fa["Player"].isin(st.session_state.favorites)
        # Sort by the ACTIVE VALUE (the number users see) descending — Tier as tiebreaker.
        # The source "Rank" field is missing/unreliable for fringe FAs, so it floated
        # low-value players to the top; value-first ordering fixes that. No-value rows last.
        dv = df_fa[mask].copy()
        dv["_vsort"] = pd.to_numeric(dv[val_col], errors="coerce")
        dv["_tsort"] = pd.to_numeric(dv["Tier"], errors="coerce")
        dv = dv.sort_values(by=["_vsort", "_tsort"], ascending=[False, True],
                            na_position="last").reset_index(drop=True)
        # Derive Rank from the value ordering so Rank and value never disagree
        dv["Rank"] = dv["_vsort"].rank(method="min", ascending=False).astype("Int64")
        dv = dv.drop(columns=["_vsort", "_tsort"])

        # Build display columns dynamically based on selected source
        fa_display_cols = ["Player", "Pos", "NFL Team", "Age", "Exp", "Status",
                           f"{STATS_SEASON} Pts", "Pos Rank", val_col]
        if value_source != "Consensus Avg":
            fa_display_cols.append("Cons. Avg")   # side-by-side comparison
        fa_display_cols += ["Rank", "30d Trend", "Tier", "Injury Notes"]

        fa_col_cfg = {
            **{k: COL_CFG[k] for k in [f"{STATS_SEASON} Pts", "Rank", "Cons. Avg", "Pos Rank"] if k in dv.columns},
            val_col: COL_CFG["Value"],
        }

        fav_grid(dv[fa_display_cols], "Player", "fa_fav_grid", col_cfg=fa_col_cfg)
        st.caption(f"{plural(len(dv), 'free agent')} shown · sorted by {value_source} value (best first) · tick the Fav box to favourite")

    with _fo_tabs[2]:
        # ── Pickup & Drop Advisor ─────────────────────────────────────────────────
        st.divider()
        st.subheader(":material/swap_vert: Pickup & Drop Advisor")
        st.caption("Personalised free-agent targets and roster-trim candidates for the team "
                   "you've selected in the sidebar.")

        _adv_team = my_team   # always the user's selected team — no separate picker here (B3)
        if not _adv_team:
            st.info("Choose a team in the sidebar (**Choose Team you want to View**) to get "
                    "personalised pickup & drop advice.")
        else:
            # Respect the "Include Rookies" checkbox from the filters above
            _fa_pool = df_fa if incl_rookies else df_fa[df_fa["Exp"] != "Rookie"]

            _rid         = team_name_to_rid[_adv_team]
            _td          = team_data[_rid]
            _need_scores = _td.get("need_scores", {})
            _pos_players = _td.get("pos_players", {})
            _pos_avgs    = _td.get("pos_avgs", {})
            _pos_ranks   = _td.get("pos_league_rank", {})
            _n_teams     = len(team_data)

            # ── Positional need summary table ─────────────────────────────────────
            st.markdown("#### :material/bar_chart: Positional Needs")
            _sorted_needs = sorted(_need_scores.items(), key=lambda x: x[1], reverse=True)
            _need_rows = []
            for _pos, _score in _sorted_needs:
                _your_avg = round(_pos_avgs.get(_pos) or 0)
                _lg_avg   = round(league_avgs.get(_pos) or 0)
                _rank     = _pos_ranks.get(_pos)
                _gap_pct  = round((_your_avg - _lg_avg) / max(_lg_avg, 1) * 100)
                _need_rows.append({
                    "Position":        _pos,
                    "Need Score":      f"{_score:.0f} / 100",
                    "Your Avg Value":  _your_avg,
                    "League Avg":      _lg_avg,
                    "vs League":       f"{_gap_pct:+d}%",
                    "League Rank":     f"{_rank} / {_n_teams}" if _rank else "—",
                })
            st.dataframe(pd.DataFrame(_need_rows), width="stretch", hide_index=True)

            # One-line focus pointer — the biggest gap to address first.
            if _sorted_needs:
                _focus_pos, _focus_score = _sorted_needs[0]
                _focus_lbl = "draft picks" if _focus_pos == "PICK" else _focus_pos
                st.markdown(f"**Where to focus:** your biggest positional gap is **{_focus_lbl}** "
                            f"(need score {_focus_score:.0f}/100) — prioritise it in the pickups "
                            "and trades below.")

            st.divider()

            # ── Recommended pickups — tabbed by top 2 needs + Best Available ──────
            st.markdown("#### :material/recommend: Recommended Pickups")
            _top_need_positions = [p for p, _ in _sorted_needs[:2]]
            _tab_labels = [f"{p} (Need: {_need_scores[p]:.0f})" for p in _top_need_positions] + ["Best Available"]
            _pickup_tabs = st.tabs(_tab_labels)

            # Helper: columns to show in pickup tables
            def _pickup_display_cols(df):
                cols = ["Player", "NFL Team", "Age", "Status", val_col]
                if "Cons. Avg" in df.columns and value_source != "Consensus Avg":
                    cols.append("Cons. Avg")
                cols += [f"{STATS_SEASON} Pts", "Tier", "Injury Notes"]
                return [c for c in cols if c in df.columns]

            _pickup_col_cfg = {
                val_col:               COL_CFG["Value"],
                "Cons. Avg":           COL_CFG["Cons. Avg"],
                f"{STATS_SEASON} Pts": COL_CFG[f"{STATS_SEASON} Pts"],
            }

            for _i, _pos in enumerate(_top_need_positions):
                with _pickup_tabs[_i]:
                    _fa_for_pos = (
                        _fa_pool[_fa_pool["Pos"] == _pos]
                        .sort_values(val_col, ascending=False, na_position="last")
                        .head(8)
                    )
                    _your_avg = round(_pos_avgs.get(_pos) or 0)
                    _lg_avg   = round(league_avgs.get(_pos) or 0)
                    _rank     = _pos_ranks.get(_pos)
                    st.caption(
                        f"Need score **{_need_scores[_pos]:.0f}/100** · "
                        f"Your avg {_pos} value: **{_your_avg:,}** · "
                        f"League avg: **{_lg_avg:,}** · "
                        f"Ranked **{_rank}/{_n_teams}** in league"
                    )
                    if _fa_for_pos.empty:
                        st.info(f"No free agent {_pos}s currently available.")
                    else:
                        fav_grid(_fa_for_pos[_pickup_display_cols(_fa_for_pos)], "Player",
                                 f"pickup_fav_{_pos}", col_cfg=_pickup_col_cfg)

            with _pickup_tabs[-1]:
                _fa_best = (
                    _fa_pool
                    .sort_values(val_col, ascending=False, na_position="last")
                    .head(10)
                )
                _best_cols = ["Player", "Pos", "NFL Team", "Age", "Status", val_col]
                if "Cons. Avg" in _fa_best.columns and value_source != "Consensus Avg":
                    _best_cols.append("Cons. Avg")
                _best_cols += [f"{STATS_SEASON} Pts", "Tier"]
                _best_cols = [c for c in _best_cols if c in _fa_best.columns]
                st.caption("Top 10 free agents by value across all positions.")
                fav_grid(_fa_best[_best_cols], "Player", "pickup_fav_best", col_cfg=_pickup_col_cfg)

            st.divider()

            # ── Drop candidates ───────────────────────────────────────────────────
            st.markdown("#### :material/content_cut: Drop Candidates *(if you need a roster spot)*")
            st.caption("Rostered players ranked by drop priority — weighs value vs positional average, recent points, injury status, experience, and **Sleeper league-wide drops**.")

            _, _fa_drops = load_trending()
            _drop_counts = {str(d["player_id"]): d.get("count", 0) for d in (_fa_drops or [])}
            _drop_rows = []
            for _pos in SKILL_POSITIONS:
                _pos_avg_val = _pos_avgs.get(_pos) or 1
                for _pp in _pos_players.get(_pos, []):
                    _pid    = _pp["pid"]
                    _pobj   = players.get(_pid, {})
                    _val    = _pp["value"] or 0
                    _pts    = player_pts.get(_pid) or 0
                    _status = _pobj.get("injury_status") or _pobj.get("status") or "Active"
                    _exp    = _pobj.get("years_exp") or 0

                    _drop_score, _reasons = player_drop_score(
                        _val, _pts, _status, _exp, _pos_avg_val,
                        trend_drops=_drop_counts.get(str(_pid), 0))

                    _drop_rows.append({
                        "Player":              _pp["name"],
                        "Pos":                 _pos,
                        val_col:              _val,
                        f"{STATS_SEASON} Pts": round(_pts, 1) if _pts else None,
                        "Status":              _status,
                        "Exp":                 f"{_exp}yr" if _exp else "Rookie",
                        "Reason":              " · ".join(_reasons) if _reasons else "—",
                        "_score":              _drop_score,
                    })

            _drop_rows.sort(key=lambda x: x["_score"], reverse=True)
            for _r in _drop_rows:
                del _r["_score"]

            _drop_df   = pd.DataFrame(_drop_rows).head(8)
            _drop_cols = ["Player", "Pos", val_col, f"{STATS_SEASON} Pts", "Status", "Exp", "Reason"]
            _drop_cols = [c for c in _drop_cols if c in _drop_df.columns]

            if _drop_df.empty:
                st.info("No drop candidates found — roster looks healthy.")
            else:
                st.dataframe(
                    _drop_df[_drop_cols],
                    width="stretch", hide_index=True,
                    column_config={
                        val_col:               COL_CFG["Value"],
                        f"{STATS_SEASON} Pts": COL_CFG[f"{STATS_SEASON} Pts"],
                    },
                )
                st.caption("Ranked by drop priority — value vs positional average, production, "
                           "injury, age, and Sleeper league-wide drops.")

    with _fo_tabs[3]:
        _render_rookie_class_section()

# ── Page: Settings (includes Scoring Rules section) ──────────────────────────
elif page == "Settings":
    st.title("Settings")
    if _signed_in():
        st.caption(f"Signed in as **{st.session_state.auth_email}** — your team, value source, favourites and tags are saved to your account.")
    else:
        st.caption("Browsing as a guest — settings last for this session. **Sign in** (sidebar) to save them to your account.")

    # ── Data & League controls (moved off the sidebar) ───────────────────────
    st.subheader("Data & League")
    _dc1, _dc2, _dc3 = st.columns([2, 1, 1])
    _dc1.markdown(
        f"**League:** {league.get('name', '—')}  \n"
        f"**Sleeper league ID:** `{league_id}`  \n"
        f"**Value source:** {value_source}  \n"
        f"<span style='color:grey'>Last loaded: {datetime.now().strftime('%H:%M')}</span>",
        unsafe_allow_html=True,
    )
    _dc2.markdown('<div style="padding-top:0.5rem;"></div>', unsafe_allow_html=True)
    if _dc2.button("Refresh data", width="stretch",
                   help="Re-fetch all values, stats and news from the sources"):
        _refresh_all_data()
        st.rerun()
    _dc3.markdown('<div style="padding-top:0.5rem;"></div>', unsafe_allow_html=True)
    if _dc3.button("Switch league", width="stretch"):
        st.session_state.league_id = None
        st.rerun()

    # ── Data Loaded — counts + value sources (moved off the Overview page) ─────
    st.markdown("##### Data Loaded")
    st.caption("What's currently loaded for this league.")
    _kpis = [
        ("Teams",          f"{len(rosters)}"),
        ("Players valued", f"{len(fc_values):,}"),
        ("Rookies ranked", f"{len(fc_rookies)}"),
        ("Pick values",    f"{len(fc_picks)}"),
        ("Stats season",   f"{STATS_SEASON}"),
    ]
    for _kc, (_keb, _kval) in zip(st.columns(5), _kpis):
        _kc.markdown(
            f'<div class="dlh-card" style="position:relative;overflow:hidden;'
            f'padding:16px 18px 16px 20px;">'
            f'<div style="position:absolute;left:0;top:0;bottom:0;width:4px;'
            f'background:linear-gradient(180deg,var(--green),var(--gold));"></div>'
            f'<div class="eyebrow">{_keb}</div>'
            f'<div style="font-family:\'Space Grotesk\',sans-serif;font-size:40px;'
            f'font-weight:700;color:var(--text-hi);line-height:1.15;'
            f'margin-top:6px;">{_kval}</div></div>',
            unsafe_allow_html=True)
    _src_counts = {"FC Dynasty": len(fc_values), "DN Dynasty": len(dn_map),
                   "KTC": len(ktc_map), "DP Values": len(dp_map)}
    _loaded = [f"{vs_label(s)} {_src_counts[s]:,}"
               for s in available_value_sources(num_qbs, owner_view) if s in _src_counts]
    st.caption("Value sources loaded — " + " · ".join(_loaded))

    st.divider()

    col_s1, col_s2 = st.columns(2)

    with col_s1:
        st.subheader("My Team & Value Source")
        # Team — persisted as your saved team for this league (avatar shown below)
        st.selectbox("Choose Team you want to View", ["—"] + _sb_team_names, key="my_team_pick")
        _set_team = None if st.session_state.get("my_team_pick", "—") == "—" else st.session_state.my_team_pick
        if _set_team:
            _s_own    = team_owner_user.get(_set_team)
            _s_own_nm = (_s_own or {}).get("display_name")
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:11px;margin:-2px 0 12px;">'
                f'{user_avatar_tag(_s_own, _set_team, px=42, radius=11)}'
                f'<div style="line-height:1.25;"><div style="font-weight:700;color:var(--text-hi);">'
                f'{_html.escape(_set_team)}</div>'
                + (f'<div style="font-size:.78rem;color:var(--text-mid);">@{_html.escape(_s_own_nm)}</div>'
                   if _s_own_nm else '')
                + '</div></div>', unsafe_allow_html=True)
        # Value source — drives the Value/Rank columns everywhere
        st.selectbox("Value source to use", available_value_sources(num_qbs, owner_view),
                     key="value_source", format_func=vs_label,
                     help="Dynasty rankings power player values. **FantasyCalc (Redraft)** is a "
                          "win-now/seasonal lens — pick it for redraft or brand-new leagues.")
        _rd_note = redraft_note(st.session_state.value_source)
        if _rd_note:
            st.caption(_rd_note)
        if owner_view and num_qbs < 2:
            st.caption("Owner view: KeepTradeCut & DynastyNerds are SuperFlex-only — hidden for this 1-QB league.")
        st.caption(
            "Value source drives the **Value** and **Rank** columns across Players & Picks, "
            "Front Office, and the Trade Room. Picks always use FC values."
        )
        _vs_sel = st.session_state.get("value_source", "FC Dynasty")
        source_info = {
            "FC Dynasty":    "FantasyCalc dynasty SuperFlex value. Normalised to 0–10K. Default.",
            "DN Dynasty":    "DynastyNerds dynasty SuperFlex — ranker consensus (~330 players). 0–10K.",
            "KTC":           "KeepTradeCut dynasty SuperFlex — scraped from dynasty-rankings page. Normalised to 0–10K.",
            "DP Values":     "DynastyProcess (FantasyPros ECR-derived) — weekly GitHub CSV. Normalised to 0–10K.",
            "Consensus Avg": "Normalised average of FC Dynasty + DN Dynasty + KTC + DP Values. Most balanced view.",
        }
        st.info(source_info.get(_vs_sel, ""))

        missing = [name for name, m in [("DN", dn_map), ("KTC", ktc_map), ("DP", dp_map)] if not m]
        if missing:
            st.warning(f"Could not load: {', '.join(missing)}. Those sources will be skipped in Consensus Avg.")

        st.markdown("**Positional Weighting**")
        st.checkbox(
            "Auto-weight by league scoring", key="pos_weighting",
            help="Tilts player values for scoring your value source can't model — mainly TE-premium "
                 "(TEs worth more vs WR). Off = raw value-source numbers. Applies to every value & rank "
                 "across the app and the trade tools.")
        _pw_now    = compute_pos_weights(scoring, st.session_state.pos_weighting)
        _pw_active = [f"{k} ×{v}" for k, v in _pw_now.items() if v != 1.0]
        if _pw_active:
            st.caption("Active tilt: **" + " · ".join(_pw_active) + "** (TE-premium league). Your value "
                       "source already prices Superflex / 2QB and PPR, so those aren't re-weighted.")
        elif st.session_state.pos_weighting:
            st.caption("This league's scoring needs no positional tilt (standard TE). Superflex / PPR are "
                       "already baked into your value source.")

    with col_s2:
        st.subheader("Theme")
        st.info("**Dark theme** — Dynasty FF Lil' Helper is dark-only for now. A polished light theme is on the roadmap.")

    st.divider()
    st.subheader("Draft Room")
    st.caption("**Need Reach Limit** — how far a team reaches for positional need over Best Player "
               "Available in the draft simulation. 0% = pure BPA · 40% = heavily need-driven. "
               "Also adjustable on the Draft Room page.")
    st.slider(
        "Need Reach Limit", min_value=0, max_value=40, value=15, step=5, format="%d%%",
        key="reach_limit_pct",
        help="How far simulated teams reach for positional need over Best Player Available "
             "in the Draft Room. 0% = pure BPA, 40% = heavily need-driven. (Also on the Draft Room page.)",
    )

    st.divider()
    st.subheader("Trade Room")
    st.caption("**Premium Curve** — your **Value source** scores raw market value (an even-value trade). "
               "The Premium Curve layers real dynasty behaviour on top: the best player usually wins a "
               "trade, so landing the single most valuable player costs extra. Off = pure value. When a "
               "side comes short, the Trade Room suggests a balancing piece. Also on the Trade Calculator.")
    st.selectbox(
        "Trade Fairness", TF_NAMES, key="trade_fairness",
        help="Off = even on raw value · Light / Standard / Heavy add a 10 / 18 / 28% premium on the "
             "best player in the deal, then suggest a sweetener to even it up.")

    # ════════ Scoring Rules (merged in — will become a sub-menu) ═════════════
    st.divider()
    st.header(":material/rule: Scoring Rules")
    df_sc = build_scoring_df(scoring)
    _sc1, _sc2 = st.columns([2, 3])
    sel_cats  = _sc1.multiselect("Categories", sorted(df_sc["Category"].unique().tolist()), key="sc_cat",
                                 placeholder="All categories")
    stat_srch = _sc2.text_input("Search stat name", key="sc_stat", placeholder="e.g. Passing TD")
    _sc_mask = pd.Series(True, index=df_sc.index)
    if sel_cats:  _sc_mask &= df_sc["Category"].isin(sel_cats)
    if stat_srch: _sc_mask &= df_sc["Stat"].str.contains(stat_srch, case=False, na=False)
    _sc_dv = df_sc[_sc_mask]
    st.dataframe(_sc_dv, width="stretch", hide_index=True,
                 column_config={"Points": COL_CFG["Points"]})
    st.caption(plural(len(_sc_dv), "active scoring rule"))

# ── Page: Trade Room ─────────────────────────────────────────────────────
elif page == "Trade Room":
    @st.fragment
    def _frag_trade_analyzer():
        # team_data / league_avgs / all_players_by_pos already computed above tabs
        # ── Team: follows the sidebar-selected team (no separate picker here) ──────
        if not my_team or my_team not in team_name_to_rid:
            st.info("Choose a team in the sidebar (**Choose Team you want to View**) to use the Trade Room.")
            return
        sel_ta_team = my_team
        rid = team_name_to_rid[sel_ta_team]
        td  = team_data[rid]

        # Consume an Overview "Refine in Trade Room" deep-link → preload the Trade Builder
        _pl = st.session_state.pop("_tb_preload", None)
        if _pl:
            st.session_state["calc_team_a"] = _pl["team_a"]
            st.session_state["calc_team_b"] = _pl["team_b"]
            st.session_state[f"calc_side_a_{_pl['team_a']}"] = _pl["side_a"]
            st.session_state[f"calc_side_b_{_pl['team_b']}"] = _pl["side_b"]
            st.success("Trade loaded into **Trade Builder** — open that tab to refine the pieces.")

        # Set of Untouchable player names for THIS team — excluded from all trade-away lists
        _player_tags = st.session_state.player_tags
        _untouchable = {
            p["name"] for _pos in SKILL_POSITIONS for p in td["pos_players"].get(_pos, [])
            if _player_tags.get(p["name"]) == "Untouchable"
        }

        # ── Player status tags ────────────────────────────────────────────────────
        with st.expander("Tag players (Trade Block / Untouchable)", expanded=False):
            _ta_players = [
                {"name": p["name"], "pos": _pos, "value": p["value"]}
                for _pos in SKILL_POSITIONS for p in td["pos_players"].get(_pos, [])
            ]
            _ta_players.sort(key=lambda x: x["value"] or 0, reverse=True)
            st.caption(f"Tagging **{sel_ta_team.strip()}** · Untouchable players are excluded from trade suggestions below · shared with Players & Picks")
            tag_editor(_ta_players, "tags_trade")

        # ── Your trade block (players tagged Trade) ────────────────────────────
        _trade_block = [
            {"name": p["name"], "pos": _pos, "value": p["value"]}
            for _pos in SKILL_POSITIONS for p in td["pos_players"].get(_pos, [])
            if _player_tags.get(p["name"]) == "Trade Block"
        ]
        if _trade_block:
            _trade_block.sort(key=lambda x: x["value"] or 0, reverse=True)
            st.markdown("**Your Trade Block**")
            st.dataframe(
                pd.DataFrame([{"Player": p["name"], "Pos": p["pos"], val_col: p["value"]} for p in _trade_block]),
                width="stretch", hide_index=True,
                column_config={val_col: COL_CFG["Value"]},
            )

        _tr_tabs = st.tabs(["Roster Strength", "Trade Partners", "Trade Builder", "Suggestions"])

        with _tr_tabs[0]:
            # ── Positional strength — summary banner + detail table ──────────────────
            st.subheader("Positional Strength vs League Average")
            st.caption(f"Score (0–100) = league rank (40%) + value gap (40%) + depth drop-off (20%) · "
                       f"based on value source: **{value_source}** (change in sidebar)")

            # Bottom Line verdict for the analysed team — above the Need/Surplus tiles
            _tr_bl_facts = build_my_team_facts(sel_ta_team, team_name_to_rid, team_data, players, value_source)
            if _tr_bl_facts:
                render_bottom_line(_tr_bl_facts,
                                   (st.session_state.get("league_id"), sel_ta_team, value_source, _insight_week()))

            _n_teams   = len(team_data)
            _need_pos  = td.get("need_pos")
            _surp_pos  = td.get("surplus_pos")
            _need_sc   = td.get("need_scores",    {}).get(_need_pos)
            _surp_sc   = td.get("surplus_scores", {}).get(_surp_pos)
            _need_rank = td.get("pos_league_rank",{}).get(_need_pos)
            _surp_rank = td.get("pos_league_rank",{}).get(_surp_pos)
            _need_lbl  = "Draft Picks" if _need_pos == "PICK" else (_need_pos or "—")
            _surp_lbl  = "Draft Picks" if _surp_pos == "PICK" else (_surp_pos or "—")

            # ── Summary banner ────────────────────────────────────────────────────────
            ban_l, ban_r = st.columns(2)
            ban_l.markdown(
                f"""<div style="background:linear-gradient(135deg,#3d0c0c,#5c1a1a);
                    border:1px solid #c0392b; border-radius:10px; padding:16px 20px;">
                    <div style="font-size:0.72rem; color:#e88; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:6px;">
                        ▼ Priority Need
                    </div>
                    <div style="font-size:1.6rem; font-weight:700; color:#fff; margin-bottom:4px;">{_need_lbl}</div>
                    <div style="font-size:0.9rem; color:#f5a5a5;">
                        Score <strong>{f'{_need_sc:.0f}' if _need_sc is not None else '—'}/100</strong>
                        &nbsp;·&nbsp; Rank <strong>#{_need_rank}/{_n_teams}</strong>
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )
            ban_r.markdown(
                f"""<div style="background:linear-gradient(135deg,#0c2e1a,#134d29);
                    border:1px solid #27ae60; border-radius:10px; padding:16px 20px;">
                    <div style="font-size:0.72rem; color:#7ec; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:6px;">
                        ▲ Biggest Surplus
                    </div>
                    <div style="font-size:1.6rem; font-weight:700; color:#fff; margin-bottom:4px;">{_surp_lbl}</div>
                    <div style="font-size:0.9rem; color:#a8efc8;">
                        Score <strong>{f'{_surp_sc:.0f}' if _surp_sc is not None else '—'}/100</strong>
                        &nbsp;·&nbsp; Rank <strong>#{_surp_rank}/{_n_teams}</strong>
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )

            st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)

            # ── Detail table — all positions ──────────────────────────────────────────
            _tbl_rows = []
            for dim in ANALYSIS_DIMENSIONS:
                avg       = td["pos_avgs"].get(dim)
                rel       = td["relative"].get(dim)
                lg_avg    = league_avgs.get(dim)
                rank      = td.get("pos_league_rank", {}).get(dim)
                depth_raw = td.get("depth_scores",    {}).get(dim)
                ns        = td.get("need_scores",     {}).get(dim)
                ss        = td.get("surplus_scores",  {}).get(dim)
                lbl       = "Draft Picks" if dim == "PICK" else dim
                if ns is not None and ss is not None:
                    if ns >= ss and ns >= 20:   status = f"▼ Need"
                    elif ss > ns and ss >= 20:  status = f"▲ Surplus"
                    else:                        status = "~ Average"
                    score = ns if (ns >= ss) else ss
                else:
                    status = "—"; score = None
                depth_lbl = "—"
                if depth_raw is not None and dim in SKILL_POSITIONS:
                    depth_lbl = "Shallow" if depth_raw >= 0.6 else ("Moderate" if depth_raw >= 0.3 else "Deep")
                _tbl_rows.append({
                    "Position":   lbl,
                    "Your Avg":   int(avg)    if avg    is not None else None,
                    "League Avg": int(lg_avg) if lg_avg is not None else None,
                    "vs Avg":     f"{rel:+.1f}%" if rel is not None else "—",
                    "Rank":       f"#{rank}/{_n_teams}" if rank else "—",
                    "Score":      round(score) if score is not None else None,
                    "Depth":      depth_lbl,
                    "Status":     status,
                    "_dim":       dim,
                })

            # Sort: needs first (by score desc), then average, then surpluses (by score desc)
            def _tbl_sort(r):
                s = r["Score"] or 0
                if "Need" in r["Status"]:    return (0, -s)
                if "Average" in r["Status"]: return (1, 0)
                return (2, -s)
            _tbl_rows.sort(key=_tbl_sort)

            # Colored position row-cards (chip · name · your-vs-lg · track bar · pill · score).
            # "Table view" toggle keeps the raw grid for power users.
            if st.toggle("Table view", value=False, key="rs_table_view"):
                st.dataframe(
                    pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in _tbl_rows]),
                    width="stretch", hide_index=True,
                    column_config={
                        "Your Avg":   st.column_config.NumberColumn("Your Avg",   format="%d"),
                        "League Avg": st.column_config.NumberColumn("League Avg", format="%d"),
                        "Score":      st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
                    },
                )
            else:
                _cards = []
                for r in _tbl_rows:
                    _name = POS_FULLNAME.get(r["_dim"], r["Position"])
                    _abbr = POS_ABBR.get(r["_dim"], r["_dim"])
                    _pbg, _pfg, _acc = POS_PALETTE.get(r["_dim"], ("--pill-blue-bg", "--pill-blue-fg", "--blue"))
                    _sc = r["Score"] or 0
                    _sw = ("Need" if "Need" in r["Status"] else "Surplus" if "Surplus" in r["Status"] else "Average")
                    _pill = (f"{r['Rank']} · {r['Depth']} · {_sw}"
                             if r["Depth"] and r["Depth"] != "—" else f"{r['Rank']} · {_sw}")
                    _meta = (f"{r['Your Avg']:,} vs {r['League Avg']:,} · {r['vs Avg']}"
                             if r["Your Avg"] is not None and r["League Avg"] is not None else r["vs Avg"])
                    _cards.append(
                        f'<div style="display:flex;align-items:center;gap:14px;background:var(--bg-surface);'
                        f'border:1px solid var(--border);border-radius:12px;padding:11px 16px;margin-bottom:8px;">'
                        f'<div style="flex:0 0 auto;width:38px;height:38px;border-radius:9px;background:var({_pbg});'
                        f'color:var({_pfg});display:flex;align-items:center;justify-content:center;font-weight:700;'
                        f'font-size:.82rem;">{_abbr}</div>'
                        f'<div style="flex:1;min-width:0;">'
                        f'<div style="font-size:.95rem;color:var(--text-hi);margin-bottom:6px;">'
                        f'<strong>{_name}</strong>&nbsp;&nbsp;'
                        f'<span style="font-size:.8rem;color:var(--text-mid);">{_meta}</span></div>'
                        f'<div style="height:8px;border-radius:4px;background:var(--bg-hover);overflow:hidden;">'
                        f'<div style="height:8px;width:{_sc}%;background:var({_acc});border-radius:4px;"></div></div></div>'
                        f'<div style="flex:0 0 auto;"><span style="background:var({_pbg});color:var({_pfg});'
                        f'font-size:.72rem;font-weight:600;padding:3px 10px;border-radius:999px;white-space:nowrap;">{_pill}</span></div>'
                        f'<div style="flex:0 0 auto;min-width:34px;text-align:right;font-family:\'Space Grotesk\',sans-serif;'
                        f'font-weight:700;font-size:1.4rem;color:var({_acc});">{_sc}</div>'
                        f'</div>')
                st.markdown("".join(_cards), unsafe_allow_html=True)

            # ── Full breakdown table ───────────────────────────────────────────────────
            with st.expander("Full positional breakdown (players + picks)", expanded=False):
                breakdown_rows = []

                def _player_status(rel):
                    if rel is None:   return "—"
                    if rel >= 15:     return "Well Above Avg"
                    if rel >= 5:      return "Above Avg"
                    if rel >= -5:     return "Near Avg"
                    if rel >= -15:    return "Below Avg"
                    return "Well Below Avg"

                # Players by position — each player vs league avg for that position
                for pos in SKILL_POSITIONS:
                    lg_avg = league_avgs.get(pos, 0)
                    for player in td["pos_players"][pos]:
                        pval = player["value"]
                        prel = (pval - lg_avg) / lg_avg * 100 if lg_avg else None
                        breakdown_rows.append({
                            "Type":        pos,
                            "Asset":       player["name"],
                            val_col:       pval,
                            "League Avg":  int(lg_avg) if lg_avg else 0,
                            "vs Lg Avg":   f"{prel:+.1f}%" if prel is not None else "—",
                            "Status":      _player_status(prel),
                        })

                # Picks — each pick vs league avg pick value
                lg_pick = league_avgs.get("PICK", 0)
                for pick in td["picks"]:
                    pval = pick["value"]
                    prel = (pval - lg_pick) / lg_pick * 100 if lg_pick else None
                    breakdown_rows.append({
                        "Type":        "PICK",
                        "Asset":       pick["label"],
                        val_col:       pval,
                        "League Avg":  int(lg_pick) if lg_pick else 0,
                        "vs Lg Avg":   f"{prel:+.1f}%" if prel is not None else "—",
                        "Status":      _player_status(prel),
                    })

                st.dataframe(
                    pd.DataFrame(breakdown_rows), width="stretch", hide_index=True,
                    column_config={
                        val_col:      COL_CFG["Value"],
                        "League Avg": COL_CFG["League Avg"],
                    },
                )

            st.divider()
            # ── Section B: Defensive Strength (IDP/DEF) ───────────────────────────────
            st.subheader("Defensive Strength (IDP / DEF)")
            st.caption(
                "Pools DL + LB + DB + DEF positions. Ranked by average 2025 fantasy points "
                "(league scoring), compared to the league average. Kickers excluded."
            )

            team_def_entry = def_analysis.get(rid, {})
            def_avg_pts    = team_def_entry.get("avg_pts", 0)
            def_count      = team_def_entry.get("player_count", 0)
            def_rel        = (def_avg_pts - league_def_avg) / league_def_avg * 100 if league_def_avg else 0
            def_suffix     = "▲ Surplus" if def_rel >= 5 else ("▼ Need" if def_rel <= -5 else "~ Average")

            d1, d2, d3 = st.columns(3)
            d1.metric(
                label=f"DEF Avg Pts  ({def_suffix})",
                value=f"{def_avg_pts:.1f}",
                delta=f"{def_rel:+.1f}% vs league avg ({league_def_avg:.1f})",
                delta_color="normal",
            )
            d2.metric("IDP/DEF Players on Roster", def_count)
            d3.metric("League DEF Avg Pts", f"{league_def_avg:.1f}")

            # League-wide DEF ranking table
            with st.expander("Full league DEF ranking", expanded=True):
                def_rows = []
                for r2id, de in def_analysis.items():
                    r2_rel = (de["avg_pts"] - league_def_avg) / league_def_avg * 100 if league_def_avg else 0
                    def_rows.append({
                        "Team":       de["name"],
                        "Avg Pts":    round(de["avg_pts"], 1),
                        "Players":    de["player_count"],
                        "vs League":  f"{r2_rel:+.1f}%",
                    })
                def_rows.sort(key=lambda r: r["Avg Pts"], reverse=True)
                for i, row in enumerate(def_rows):
                    row["Rank"] = i + 1
                df_def_rank = pd.DataFrame(def_rows)[["Rank", "Team", "Avg Pts", "Players", "vs League"]]
                st.dataframe(df_def_rank, width="stretch", hide_index=True,
                             height=(len(df_def_rank) + 1) * 35 + 3,
                             column_config={"Avg Pts": COL_CFG["Avg Pts"]})

            # Individual DEF players for selected team
            def_players = team_def_entry.get("players", [])
            if def_players:
                with st.expander(f"{sel_ta_team} — individual DEF/IDP players", expanded=True):
                    st.dataframe(
                        pd.DataFrame([{
                            "Player": p["name"], "Pos": p["pos"],
                            f"{STATS_SEASON} Pts": round(p["pts"], 1),
                        } for p in def_players]),
                        width="stretch", hide_index=True,
                        height=(len(def_players) + 1) * 35 + 3,
                        column_config={f"{STATS_SEASON} Pts": COL_CFG[f"{STATS_SEASON} Pts"]},
                    )

        with _tr_tabs[1]:
            # ── Best Trade Partners ───────────────────────────────────────────────────
            st.subheader(":material/handshake: Best Trade Partners")
            st.caption(
                "Ranked by realistic fit: how much they need what you offer (45%) + how "
                "value-balanced the closest 1-for-1 is (35%) + their depth at your need (20%). "
                "The sample pairs your best movable surplus chip with their closest-value player "
                "at your need — a balanced starting point, not their franchise star."
            )

            _auto_need    = td.get("need_pos")
            _auto_surplus = td.get("surplus_pos")

            _tp_col_a, _tp_col_b = st.columns(2)
            _need_override = _tp_col_a.selectbox(
                "I need (position)",
                options=["Auto — " + (_auto_need or "none")] + SKILL_POSITIONS,
                index=0,
                key="tp_need_override",
            )
            _surplus_override = _tp_col_b.selectbox(
                "I can offer (position)",
                options=["Auto — " + (_auto_surplus or "none")] + SKILL_POSITIONS,
                index=0,
                key="tp_surplus_override",
            )

            _my_need    = _auto_need    if _need_override.startswith("Auto")    else _need_override
            _my_surplus = _auto_surplus if _surplus_override.startswith("Auto") else _surplus_override

            if not _my_need or not _my_surplus or _my_need == _my_surplus:
                st.info("No clear positional imbalance — trade partner ranking requires at least one need and one surplus position.")
            else:
                # Shared ranking — identical to the Overview "Best Trade Partner" tile
                _partner_rows = rank_trade_partners(rid, td, team_data, _untouchable, _my_need, _my_surplus)

                # Show top 3 highlighted, full table in expander
                _top3 = _partner_rows[:3]
                _cols_show = ["#", "Team", "Fit Score", f"Their {_my_need} Supply",
                              f"Their Need for {_my_surplus}", "Sample: You Give", "Sample: You Get", "Value Diff"]
                st.markdown("**Top 3 Suitors**")
                st.dataframe(
                    pd.DataFrame(_top3)[_cols_show],
                    width="stretch", hide_index=True,
                    column_config={"Fit Score": st.column_config.ProgressColumn(
                        "Fit Score", min_value=0, max_value=100, format="%d"
                    )},
                )
                with st.expander("Full league ranking", expanded=False):
                    st.dataframe(
                        pd.DataFrame(_partner_rows)[_cols_show],
                        width="stretch", hide_index=True,
                        column_config={"Fit Score": st.column_config.ProgressColumn(
                            "Fit Score", min_value=0, max_value=100, format="%d"
                        )},
                    )

        with _tr_tabs[2]:
            # ── Section C: Manual Trade Analyzer ─────────────────────────────────────
            st.subheader("Manual Trade Analyzer")
            st.caption("Pick any player or pick from this team's roster, choose your target position, and see closest-value options across the league.")

            # Build asset options: all players with FC values + all valued picks
            # (Untouchable players stay selectable here — this is manual exploration —
            #  but get a [U] marker so the intent is visible.)
            asset_options = []
            for pos in SKILL_POSITIONS:
                for player in td["pos_players"][pos]:
                    _lock = "[U] " if player["name"] in _untouchable else ""
                    asset_options.append({
                        "label":     f"{_lock}{player['name']}  ({pos})  —  {player['value']:,}",
                        "value":     player["value"],
                        "type":      "player",
                        "pos":       pos,
                        "name":      player["name"],
                    })
            for pick in td["picks"]:
                asset_options.append({
                    "label":  f"{pick['label']}  —  {pick['value']:,}",
                    "value":  pick["value"],
                    "type":   "pick",
                    "pos":    "PICK",
                    "name":   pick["label"],
                })

            if not asset_options:
                st.info("No FC-valued assets found for this team.")
            else:
                col_a, col_b = st.columns([3, 1])
                sel_asset_label = col_a.selectbox(
                    "Asset to trade away (player or pick)",
                    options=[a["label"] for a in asset_options],
                    key="man_asset",
                )
                # Default Target to the team's priority need; if that equals the default
                # asset's position, fall back to the next-biggest need (never QB-for-QB).
                _needs_ranked = [p for p, _ in sorted(td.get("need_scores", {}).items(),
                                                      key=lambda x: x[1], reverse=True)]
                _default_asset_pos = asset_options[0]["pos"] if asset_options else None
                _target_default = next((p for p in _needs_ranked if p != _default_asset_pos), None)
                _target_idx = SKILL_POSITIONS.index(_target_default) if _target_default in SKILL_POSITIONS else 0
                sel_target_pos = col_b.selectbox(
                    "Target position",
                    options=SKILL_POSITIONS,
                    index=_target_idx,
                    key="man_target_pos",
                )

                # Find the selected asset
                sel_asset = next((a for a in asset_options if a["label"] == sel_asset_label), None)

                if sel_asset:
                    asset_val = sel_asset["value"]
                    # Find all players in target position on OTHER teams
                    pool = [
                        p for p in all_players_by_pos[sel_target_pos]
                        if p["on_team_rid"] != rid
                    ]
                    pool.sort(key=lambda p: abs(p["value"] - asset_val))

                    if not pool:
                        st.info(f"No {sel_target_pos}s with FC values found on other rosters.")
                    else:
                        st.markdown(
                            f"Trading **{sel_asset['name']}** ({val_col}: **{asset_val:,}**) — "
                            f"closest-value **{sel_target_pos}s** on other rosters:"
                        )
                        def _man_pos_status(target_rid, pos):
                            owner_td = team_data.get(target_rid, {})
                            ns = owner_td.get("need_scores",    {}).get(pos)
                            ss = owner_td.get("surplus_scores", {}).get(pos)
                            if ns is None or ss is None:
                                return "—"
                            if ss > ns and ss >= 20:  return "Surplus"
                            if ns > ss and ns >= 20:  return "Deficit"
                            return "Average"

                        # Score each candidate: fit (mutual benefit) first, then closest value
                        scored_pool = []
                        for p in pool:
                            diff      = p["value"] - asset_val
                            supply    = _man_pos_status(p["on_team_rid"], sel_target_pos)
                            asset_need = _man_pos_status(p["on_team_rid"], sel_asset["pos"])
                            fit = (2 if "Surplus" in supply   else 0) + \
                                  (2 if "Deficit" in asset_need else 0)
                            scored_pool.append((p, diff, supply, asset_need, fit))
                        scored_pool.sort(key=lambda x: (-x[4], abs(x[1])))

                        rows = []
                        for p, diff, supply, asset_need, _ in scored_pool[:10]:
                            rows.append({
                                "Player":              p["name"],
                                "Currently On":        p["on_team"],
                                val_col:               p["value"],
                                "Value Diff":          f"{diff:+,}",
                                "Their Target Supply": supply,
                                "Need for Your Asset": asset_need,
                            })
                        st.dataframe(
                            pd.DataFrame(rows),
                            width="stretch", hide_index=True,
                            key="man_results",
                            column_config={val_col: COL_CFG["Value"]},
                        )

            st.divider()
            # ── Section D: Trade Calculator ──────────────────────────────────────────
            st.subheader("Trade Calculator")
            st.caption(
                f"Weighed on **{value_source}** values — FantasyCalc already reflects your league's "
                "Superflex / PPR / team-count scoring. Pick the two teams, add players & picks, "
                "and the fairness read updates live."
            )

            _tf_name = st.selectbox(
                "Premium Curve", TF_NAMES, key="trade_fairness",
                help="The best player usually wins a trade. Off = pure value · Light/Standard/Heavy add a "
                     "10/18/28% premium on the best player, then suggest a sweetener the other team needs.")
            _tf_frac = TF_PRESETS.get(_tf_name, 0.0)
            if _tf_frac > 0:
                st.caption(f"The **{value_source}** totals below are raw market value. The **Premium Curve "
                           f"({_tf_name})** layers a {int(_tf_frac*100)}% premium on the best player on top — "
                           "so a value-even deal can still come up short, and we suggest the piece to close it.")
            else:
                st.caption(f"The **{value_source}** totals below are raw market value — a pure even-value read. "
                           "Turn the **Premium Curve** on to weigh the best player heavier and get a balancing "
                           "suggestion.")

            # Per-team asset universe (normalised to 0–10K) + metadata for the sweetener engine
            _calc_untouch = {nm for nm, t in st.session_state.get("player_tags", {}).items()
                             if t == "Untouchable"}
            _team_assets, _team_meta = {}, {}
            for _r2, _t2 in team_data.items():
                _d, _m = {}, {}
                for _p2 in SKILL_POSITIONS:
                    for _pl in _t2["pos_players"].get(_p2, []):
                        _v = _pl["value"] or 0
                        if _v:
                            _lbl = f"{_pl['name']}  ({_p2}) — {_v:,}"
                            _d[_lbl] = _v
                            _m[_lbl] = {"value": _v, "pos": _p2, "name": _pl["name"],
                                        "is_pick": False, "untouchable": _pl["name"] in _calc_untouch}
                for _pk in _t2.get("picks", []):
                    _v = round((_pk["value"] or 0) / 10282 * 10000)
                    if _v:
                        _lbl = f"{_pk['label']}  (Pick) — {_v:,}"
                        _d[_lbl] = _v
                        _m[_lbl] = {"value": _v, "pos": "PICK", "name": _pk["label"],
                                    "is_pick": True, "untouchable": False}
                _team_assets[_t2["name"]] = _d
                _team_meta[_t2["name"]]   = _m

            _all_teams = sorted(_team_assets.keys())
            _a_default = my_team if my_team in _all_teams else _all_teams[0]
            _b_default = next((t for t in _all_teams if t != _a_default), _all_teams[0])
            # Seed via session_state (no index=) so the Overview deep-link can preload teams
            if st.session_state.get("calc_team_a") not in _all_teams:
                st.session_state.calc_team_a = _a_default
            if st.session_state.get("calc_team_b") not in _all_teams:
                st.session_state.calc_team_b = _b_default

            _cc1, _cc2 = st.columns(2)
            with _cc1:
                st.markdown("<span style='color:var(--blue); font-weight:600;'>◀ Side A sends</span>", unsafe_allow_html=True)
                _team_a = st.selectbox("Team A", _all_teams,
                                       key="calc_team_a", label_visibility="collapsed")
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:9px;margin:2px 0 8px;">'
                    f'{user_avatar_tag(globals().get("team_owner_user", {}).get(_team_a), _team_a, px=30, radius=8)}'
                    f'<span style="font-size:.86rem;font-weight:600;color:var(--text-hi);">{_html.escape(_team_a)}</span>'
                    f'</div>', unsafe_allow_html=True)
                # Key includes the team so switching teams never carries stale options
                _ka = f"calc_side_a_{_team_a}"
                _add_a = st.session_state.pop("_calc_add_a", None)   # one-click sweetener add
                if _add_a and _add_a in _team_assets[_team_a] and _add_a not in st.session_state.get(_ka, []):
                    st.session_state[_ka] = st.session_state.get(_ka, []) + [_add_a]
                _side_a = st.multiselect("Players & picks", sorted(_team_assets[_team_a].keys()),
                                         key=_ka, placeholder=f"Add from {_team_a}…",
                                         label_visibility="collapsed")
            with _cc2:
                st.markdown("<span style='color:var(--purple); font-weight:600;'>Side B sends ▶</span>", unsafe_allow_html=True)
                _team_b = st.selectbox("Team B", _all_teams,
                                       key="calc_team_b", label_visibility="collapsed")
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:9px;margin:2px 0 8px;">'
                    f'{user_avatar_tag(globals().get("team_owner_user", {}).get(_team_b), _team_b, px=30, radius=8)}'
                    f'<span style="font-size:.86rem;font-weight:600;color:var(--text-hi);">{_html.escape(_team_b)}</span>'
                    f'</div>', unsafe_allow_html=True)
                _kb = f"calc_side_b_{_team_b}"
                _add_b = st.session_state.pop("_calc_add_b", None)   # one-click sweetener add
                if _add_b and _add_b in _team_assets[_team_b] and _add_b not in st.session_state.get(_kb, []):
                    st.session_state[_kb] = st.session_state.get(_kb, []) + [_add_b]
                _side_b = st.multiselect("Players & picks", sorted(_team_assets[_team_b].keys()),
                                         key=_kb, placeholder=f"Add from {_team_b}…",
                                         label_visibility="collapsed")

            _tot_a = sum(_team_assets[_team_a].get(x, 0) for x in _side_a)
            _tot_b = sum(_team_assets[_team_b].get(x, 0) for x in _side_b)

            if not _side_a or not _side_b:
                st.info("Add at least one asset to **each** side to weigh the trade.")
            else:
                _gap     = _tot_b - _tot_a
                _bigger  = max(_tot_a, _tot_b) or 1
                _gap_pct = abs(_gap) / _bigger * 100
                _sum     = (_tot_a + _tot_b) or 1
                _pa      = round(_tot_a / _sum * 100)
                if _gap_pct <= 5:
                    _badge_bg, _badge_tx = "var(--pill-green-bg)", "var(--pill-green-fg)"
                    _verdict = f"Even trade — within {_gap_pct:.0f}% ({abs(_gap):,} apart)"
                else:
                    _badge_bg, _badge_tx = "var(--pill-gold-bg)", "var(--pill-gold-fg)"
                    # _gap = B − A; the side that SENT MORE overpays, so the OTHER side is favoured
                    _winner = _team_a if _gap > 0 else _team_b
                    _arrow  = "◀" if _gap > 0 else "▶"   # point at the favoured (left=A / right=B) side
                    _verdict = f"{_arrow} Favours {_winner} by {abs(_gap):,} ({_gap_pct:.0f}%)"
                st.markdown(
                    f"""<div style="border:1px solid var(--border); border-radius:12px; padding:16px 18px; margin-top:4px;">
                      <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                        <div><div style="font-size:0.72rem; color:var(--pill-blue-fg); text-transform:uppercase; letter-spacing:.06em;">{_team_a}</div>
                             <div style="font-size:1.5rem; font-weight:700; color:var(--text-hi);">{_tot_a:,}</div></div>
                        <div style="text-align:center; align-self:center;">
                             <span style="background:{_badge_bg}; color:{_badge_tx}; padding:5px 12px; border-radius:14px; font-size:0.82rem; font-weight:600;">{_verdict}</span></div>
                        <div style="text-align:right;"><div style="font-size:0.72rem; color:var(--pill-purple-fg); text-transform:uppercase; letter-spacing:.06em;">{_team_b}</div>
                             <div style="font-size:1.5rem; font-weight:700; color:var(--text-hi);">{_tot_b:,}</div></div>
                      </div>
                      <div style="display:flex; height:20px; border-radius:6px; overflow:hidden; font-size:0.74rem; font-weight:600;">
                        <div style="width:{_pa}%; background:var(--blue); color:#04210F; display:flex; align-items:center; justify-content:center;">{_pa}%</div>
                        <div style="width:{100 - _pa}%; background:var(--purple); color:#04210F; display:flex; align-items:center; justify-content:center;">{100 - _pa}%</div>
                      </div>
                    </div>""",
                    unsafe_allow_html=True,
                )

                # ── Trade Fairness: best-player premium + sweetener engine ──────────
                if _tf_frac > 0:
                    _sel = ([(_l, _team_meta[_team_a][_l], "a") for _l in _side_a]
                            + [(_l, _team_meta[_team_b][_l], "b") for _l in _side_b])
                    _players = [s for s in _sel if not s[1]["is_pick"]]
                    _pz_l, _pz_m, _pz_side = max(_players or _sel, key=lambda x: x[1]["value"])
                    _premium = round(_tf_frac * _pz_m["value"])
                    _eff_a = _tot_a + (_premium if _pz_side == "a" else 0)
                    _eff_b = _tot_b + (_premium if _pz_side == "b" else 0)
                    _short = abs(_eff_a - _eff_b)
                    _light_side = "a" if _eff_a < _eff_b else "b"
                    _light_team = _team_a if _light_side == "a" else _team_b
                    _other_team = _team_b if _light_side == "a" else _team_a

                    st.markdown(
                        f"<div style='margin-top:12px;font-size:.86rem;color:var(--text-mid);'>"
                        f"<strong style='color:var(--text-hi);'>Premium Curve · {_tf_name}</strong> — "
                        f"<strong>{_html.escape(_pz_m['name'])}</strong> ({_pz_m['value']:,}) is the best "
                        f"player; a {int(_tf_frac*100)}% premium (~{_premium:,}) applies for landing it."
                        f"</div>", unsafe_allow_html=True)

                    if _short <= 0.04 * (max(_eff_a, _eff_b) or 1):
                        st.success(f"Fair even with the premium — within ~{_short:,} of even.")
                    else:
                        st.warning(f"**{_light_team}** is ~**{_short:,}** light — add a piece **{_other_team}** wants.")
                        _o_rid   = team_name_to_rid.get(_other_team)
                        _o_needs = team_data[_o_rid]["need_scores"] if _o_rid else {}
                        _used    = set(_side_a if _light_side == "a" else _side_b)
                        _cands   = []
                        for _cl, _cm in _team_meta[_light_team].items():
                            if _cl in _used or _cm["untouchable"] or _cm["value"] <= 0:
                                continue
                            _nfit  = 0.5 if _cm["is_pick"] else (_o_needs.get(_cm["pos"], 0) / 100.0)
                            _vfit  = max(0.0, 1.0 - abs(_cm["value"] - _short) / max(_short, 1))
                            _score = _nfit * 0.5 + _vfit * 0.5
                            if _cm["value"] > _short * 1.9:
                                _score *= 0.35
                            _cands.append((_score, _cl, _cm))
                        _cands.sort(key=lambda x: x[0], reverse=True)
                        if _cands:
                            st.caption(f"Suggested sweeteners from **{_light_team}** — fills {_other_team}'s "
                                       "needs, value-matched to close the gap:")
                            for _sc, _cl, _cm in _cands[:2]:
                                _why = ("a pick they can build with" if _cm["is_pick"]
                                        else (f"fills their {_cm['pos']} need"
                                              if _o_needs.get(_cm["pos"], 0) >= 20 else f"{_cm['pos']} depth"))
                                _bc1, _bc2 = st.columns([3, 1])
                                _bc1.markdown(
                                    f"<div style='font-size:.86rem;padding-top:5px;'>"
                                    f"<strong>{_html.escape(_cm['name'])}</strong> "
                                    f"({_cm['pos']} · {_cm['value']:,}) — {_why}</div>", unsafe_allow_html=True)
                                if _bc2.button("Add", key=f"sw_{_light_side}_{_cl}", width="stretch"):
                                    st.session_state[f"_calc_add_{_light_side}"] = _cl
                                    st.rerun()
                        else:
                            st.caption(f"No clean sweetener on {_light_team} — adjust the pieces manually.")

        with _tr_tabs[3]:
            # ── Section A: Auto Trade Suggestions ────────────────────────────────────
            st.subheader("Dynasty Little Helper Suggestions")

            surplus_pos = td["surplus_pos"]
            need_pos    = td["need_pos"]

            def _pos_status(target_rid, pos):
                """Surplus / Deficit / Average for a team at a given position (handles PICK via relative%)."""
                owner_td = team_data.get(target_rid, {})
                if pos == "PICK":
                    rel = owner_td.get("relative", {}).get("PICK")
                    if rel is None: return "—"
                    if rel >= 10:   return "Surplus"
                    if rel <= -10:  return "Deficit"
                    return "Average"
                ns = owner_td.get("need_scores",    {}).get(pos)
                ss = owner_td.get("surplus_scores", {}).get(pos)
                if ns is None or ss is None: return "—"
                if ss > ns and ss >= 20:  return "Surplus"
                if ns > ss and ns >= 20:  return "Deficit"
                return "Average"

            # Two toggles: shop the explicit Trade Block, and whether to include Untouchables
            _sa_c1, _sa_c2 = st.columns(2)
            _shop_block = _sa_c1.checkbox(
                "Shop my Trade Block", value=bool(_trade_block),
                help="Drive suggestions from players you tagged Trade, instead of auto-detected surplus.",
                key="ta_shop_block",
            )
            _incl_untouch = _sa_c2.checkbox(
                "Include Untouchables", value=False,
                help="Also include players tagged Untouchable in the suggestions.",
                key="ta_incl_untouch",
            )
            _need_for_targets = need_pos if need_pos in SKILL_POSITIONS else None

            if (not _shop_block or not _trade_block) and (not surplus_pos or not need_pos or surplus_pos == need_pos):
                st.info("No clear trade opportunities identified — positional values are well-balanced. Tag players Trade to shop them directly.")
            else:
                if _shop_block and _trade_block:
                    # Suggestions driven by YOUR trade block: shop each tagged player for your need
                    suggestions = []
                    for _bp in _trade_block:
                        _tg = sorted(
                            [p for p in all_players_by_pos.get(_need_for_targets, []) if p["on_team_rid"] != rid],
                            key=lambda p: abs((p["value"] or 0) - (_bp["value"] or 0)),
                        )[:3] if _need_for_targets else []
                        suggestions.append({
                            "type": "player",
                            "asset": {"name": _bp["name"], "value": _bp["value"]},
                            "asset_pos": _bp["pos"],
                            "want_pos": _need_for_targets or "—",
                            "targets": _tg,
                        })
                else:
                    suggestions = td.get("suggestions", [])
                    if not _incl_untouch:   # default: never offer an Untouchable player
                        suggestions = [s for s in suggestions
                                       if not (s.get("type") == "player" and s.get("asset", {}).get("name") in _untouchable)]
                if not suggestions or not any(s.get("targets") for s in suggestions):
                    st.info("Not enough data to generate suggestions — tag players Trade, or check you have a clear positional need.")
                else:
                    # ── Top 5 ideal player-for-player targets ─────────────────────────
                    # Score each candidate: +2 if target has surplus of need_pos,
                    # +2 if target team needs the asset_pos, then sort by score desc,
                    # value proximity asc within each score tier.
                    _candidates = []
                    for sug in suggestions:
                        if sug["type"] != "player":
                            continue
                        _asset    = sug["asset"]
                        _want_pos = sug["want_pos"]
                        _apos     = sug["asset_pos"]
                        for t in sug["targets"]:
                            _tpn  = _pos_status(t["on_team_rid"], _want_pos)
                            _ttpn = _pos_status(t["on_team_rid"], _apos)
                            _fit  = (2 if "Surplus" in _tpn  else 0) + \
                                    (2 if "Deficit" in _ttpn else 0)
                            _vdiff = abs(t["value"] - _asset["value"])
                            _candidates.append({
                                "Trade Away":                f"{_asset['name']}  ({_apos})",
                                "Target Player":             f"{t['name']}  ({_want_pos})",
                                "Currently On":              t["on_team"],
                                val_col:                  t["value"],
                                "Value Diff":                f"{t['value'] - _asset['value']:+,}",
                                "Their Target Supply":      _tpn,
                                "Need for Your Asset": _ttpn,
                                "_fit":   _fit,
                                "_vdiff": _vdiff,
                            })

                    if _candidates:
                        _candidates.sort(key=lambda x: (-x["_fit"], x["_vdiff"]))
                        _top5 = [{k: v for k, v in c.items() if not k.startswith("_")}
                                 for c in _candidates[:5]]
                        st.markdown("**Top 5 Ideal Player-for-Player Targets**")
                        st.caption("Ranked by trade fit (both teams benefit) then closest value.")
                        st.dataframe(
                            pd.DataFrame(_top5),
                            width="stretch", hide_index=True,
                            key="sug_top5",
                            column_config={val_col: COL_CFG["Value"]},
                        )
                        st.markdown("---")

                    st.caption("Full suggestion details by asset:")
                    for sug in suggestions:
                        asset    = sug["asset"]
                        want_pos = sug["want_pos"]
                        targets  = sug["targets"]

                        if sug["type"] == "player":
                            header = (
                                f"**Trade away** — {sug['asset_pos']}: **{asset['name']}** "
                                f"&nbsp;·&nbsp; {val_col}: **{asset['value']:,}** → get **{want_pos}**"
                            )
                        else:
                            header = (
                                f"**Use pick** — **{asset['label']}** "
                                f"&nbsp;·&nbsp; {val_col}: **{asset['value']:,}** → get **{want_pos}**"
                            )

                        st.markdown(header)
                        if not targets:
                            st.caption("No matching targets found on other rosters.")
                        else:
                            asset_val  = asset["value"]
                            asset_pos  = sug["asset_pos"]

                            st.dataframe(
                                pd.DataFrame([{
                                    "Player":                    f"{t['name']}  ({want_pos})",
                                    "Currently On":              t["on_team"],
                                    val_col:                  t["value"],
                                    "Value Diff":                f"{t['value'] - asset_val:+,}",
                                    "Their Target Supply":      _pos_status(t["on_team_rid"], want_pos),
                                    "Need for Your Asset": _pos_status(t["on_team_rid"], asset_pos),
                                } for t in targets]),
                                width="stretch", hide_index=True,
                                key=f"sug_{asset.get('pid', asset.get('label', ''))}",
                                column_config={val_col: COL_CFG["Value"]},
                            )
                        st.markdown("---")

    # ── Page: Draft Room ─────────────────────────────────────────────────────────
    _frag_trade_analyzer()
elif page == "Draft Room":
    curr_year = str(datetime.now().year)

    # ── Session state + persistence (per league) ──────────────────────────────
    if st.session_state.get("_draft_confirmed_league") != league_id:
        st.session_state.draft_confirmed = load_draft_selections(league_id)
        st.session_state._draft_confirmed_league = league_id

    confirmed    = st.session_state.draft_confirmed   # {pick_label: rookie_name}
    rookie_names = sorted([r["name"] for r in fc_rookies if r.get("name")])

    # ── Simulation control: Need Reach Limit (shared with Settings) ───────────
    # Read the persisted value up front so the simulation below uses it; the actual
    # slider widget renders inside the "Edit settings" strip after the sim (so it
    # doesn't dominate the top of the war room). Same session key as the Settings page.
    _reach_pct       = int(st.session_state.get("reach_limit_pct", 15))
    need_reach_limit = _reach_pct / 100
    _mode = ("Strict" if need_reach_limit < 0.10
             else "Balanced" if need_reach_limit <= 0.20
             else "Need-heavy")

    # ── Build sorted picks list for current year ──────────────────────────────
    df_all_picks = build_picks_df(rosters, users, traded_ownership, drafts, slot_map, fc_picks)
    df_cur = df_all_picks[
        (df_all_picks["Season"] == curr_year) &
        df_all_picks["Pick"].str.contains(r"\.", na=False)
    ].copy()

    # Sort ascending by (round, slot) — baked into the df, never depends on UI sort
    def _pick_sort_key(pick_str):
        try:
            rnd, slot = str(pick_str).split(".")
            return (int(rnd), int(slot))
        except Exception:
            return (99, 99)

    df_cur = df_cur.sort_values("Pick", key=lambda col: col.apply(_pick_sort_key)).reset_index(drop=True)

    # Normalise FC pick values to 0-10K so they're on the same scale as all active sources.
    # We use the same 10282 anchor as get_active_value for FC Dynasty.
    def _norm_pick(v):
        return round(v / 10282 * 10000) if v else 0

    picks_for_sim = []
    for _, row in df_cur.iterrows():
        rid      = team_name_to_rid.get(row["Team"])
        raw_pick = row["Value"]   # raw FC pick value from fc_picks
        if rid and pd.notna(raw_pick):
            try:
                rnd, slot = str(row["Pick"]).split(".")
                picks_for_sim.append((int(rnd), int(slot), row["Pick"], rid, _norm_pick(raw_pick)))
            except (ValueError, TypeError):
                pass  # skip picks with unparseable labels or non-numeric values

    # Pre-compute active-source value for every rookie in the pool.
    # Falls back to normalised FC dynasty value if the active source has no data for that player.
    def _rookie_active_val(r):
        sid = r.get("sleeperId")
        if sid:
            v = get_active_value(sid, fc_values, val_maps, value_source)
            if v is not None and v > 0:
                return v
        # Fallback: normalise the raw FC value stored on the rookie record
        return _norm_pick(r.get("value")) or 0

    # ── Simulation function ────────────────────────────────────────────────────
    def run_simulation(picks_sorted, confirmed_map):
        confirmed_names = set(confirmed_map.values())
        # Build pool enriched with _active_val — the value used for ALL comparisons
        available = []
        for r in fc_rookies:
            if r.get("position") not in SKILL_POSITIONS:
                continue
            if r.get("name") in confirmed_names:
                continue
            av = _rookie_active_val(r)
            if av > 0:
                available.append({**r, "_active_val": av})
        available.sort(key=lambda r: r["_active_val"], reverse=True)

        # ── Live need scores — copy per team, decay as picks are made ────────
        # Each pick at position P divides that team's need score for P by (1 + picks_at_P).
        # Original scores are kept as the baseline so decay is always relative to the start.
        orig_need = {rid: dict(td2.get("need_scores", {})) for rid, td2 in team_data.items()}
        live_need = {rid: dict(scores) for rid, scores in orig_need.items()}
        pick_counts = {rid: {pos: 0 for pos in SKILL_POSITIONS} for rid in team_data}

        def _apply_pick(team_rid, pos):
            """Decay need score for pos after a pick is assigned to team_rid."""
            if team_rid not in pick_counts or pos not in SKILL_POSITIONS:
                return
            pick_counts[team_rid][pos] += 1
            cnt = pick_counts[team_rid][pos]
            orig = orig_need.get(team_rid, {}).get(pos, 0)
            live_need[team_rid][pos] = orig / (1 + cnt)

        selections = {}

        # Seed confirmed picks first — count them so they influence later need scores
        for pick_label, rk_name in confirmed_map.items():
            match = next((r for r in fc_rookies if r.get("name") == rk_name), None)
            if match is None:
                st.warning(f'Confirmed pick "{rk_name}" is no longer in the rookie rankings — value may be unavailable.', icon=":material/warning:")
            pos = match.get("position", "—") if match else "—"
            owner = next((p[3] for p in picks_sorted if p[2] == pick_label), None)
            if owner:
                _apply_pick(owner, pos)
            selections[pick_label] = {
                "name":   rk_name,
                "pos":    pos,
                "value":  match.get("value") if match else None,  # raw FC value for display
                "reason": "Confirmed",
            }

        # Simulate remaining
        for rnd, slot, pick_label, team_rid, pick_value in picks_sorted:
            if pick_label in selections:
                continue
            if not available:
                selections[pick_label] = {"name": "—", "pos": "—", "value": None, "reason": "Pool empty"}
                continue

            # Use live (decayed) need scores — reflects picks already made this draft
            ns       = live_need.get(team_rid, {})
            need_pos = max(ns, key=ns.get) if ns else None
            by_pos   = {}
            for r in available:
                by_pos.setdefault(r.get("position", ""), []).append(r)

            best_overall = available[0]   # already sorted descending by _active_val
            need_best    = by_pos.get(need_pos, [None])[0] if need_pos else None

            if need_best and need_best is not best_overall:
                # How much value are we sacrificing to fill the need over BPA?
                reach_pct = (best_overall["_active_val"] - need_best["_active_val"]) / max(best_overall["_active_val"], 1)
                if reach_pct <= need_reach_limit:
                    # Small sacrifice — worth taking the need position
                    selected = need_best
                    reason   = f"Need ({need_pos})"
                else:
                    # BPA is too valuable to pass — take best available regardless of need
                    selected = best_overall
                    reason   = f"Best Available (+{reach_pct:.0%} over need)"
            elif need_best:
                # Need player IS the best available — easy call
                selected = need_best
                reason   = f"Need ({need_pos})"
            else:
                selected = best_overall
                reason   = "Best Available"

            sel_pos  = selected.get("position", "—")
            sel_name = selected.get("name")
            _apply_pick(team_rid, sel_pos)
            available = [r for r in available if r.get("name") != sel_name]
            selections[pick_label] = {
                "name":   sel_name or "—",
                "pos":    sel_pos,
                "value":  selected.get("value"),     # raw FC value for display (Rookie FC Val column)
                "reason": reason,
            }
        return selections

    rookie_sels = run_simulation(picks_for_sim, confirmed)

    # One-shot toast after a live-data refresh (the rerun clears the inline toast).
    if st.session_state.pop("_dr_refreshed", False):
        st.toast("Live data refreshed — rosters, trades & values re-fetched.", icon=":material/sync:")

    # ── War-room header — title + pill (left) · stacked Refresh / Clear (right) ──
    _hdr_l, _hdr_r = st.columns([4, 1.25], vertical_alignment="center")
    _hdr_l.markdown(
        f'<div style="display:flex;align-items:center;gap:13px;flex-wrap:wrap;">'
        f'<span style="font-family:\'Space Grotesk\',sans-serif;font-size:30px;font-weight:700;'
        f'color:var(--text-hi);line-height:1;">{curr_year} Draft Room</span>'
        f'<span class="pill green dlh-live-pill" style="display:inline-flex;align-items:center;gap:6px;">'
        f'<span class="dlh-dot green"></span>War Room Active</span></div>',
        unsafe_allow_html=True)
    ordered_picks = list(df_cur["Pick"])
    with _hdr_r:
        if st.button("Refresh Live Data", key="dr_refresh", width="stretch", type="primary",
                     help="Re-fetch rosters, trades and rookie values from Sleeper/FantasyCalc, then "
                          "re-estimate the board. Use it when a trade happens mid-draft (it can change "
                          "who owns a pick and what each team needs)."):
            _refresh_all_data()                   # clear league + value caches → fresh fetch
            st.session_state["_dr_refreshed"] = True
            st.rerun()
        if st.button("Clear board", key="dr_clear", width="stretch",
                     help="Unlock every pick and reset the whole board back to estimates."):
            for pick in ordered_picks:
                st.session_state[f"dr_sel_{pick.replace('.', '_')}"] = ""
            st.session_state.draft_confirmed = {}
            clear_draft_selections(league_id)
            st.rerun()

    # Shared position-chip helper (used by both tabs)
    def _pos_chip(pos):
        _pbg, _pfg, _ = POS_PALETTE.get(pos if pos in POS_PALETTE else "PICK",
                                        ("--pill-blue-bg", "--pill-blue-fg", "--blue"))
        _label = POS_ABBR.get(pos, pos) if pos and pos != "—" else "—"
        return (f'<span style="display:inline-block;min-width:30px;text-align:center;background:var({_pbg});'
                f'color:var({_pfg});font-weight:700;font-size:.66rem;padding:3px 6px;border-radius:6px;">{_label}</span>')

    # Compact, borderless star buttons for the rookie-pool favourite toggles.
    st.markdown(
        "<style>[class*='st-key-dr_poolfav_'] button{border:0!important;background:transparent!important;"
        "padding:0!important;min-height:0!important;color:var(--gold)!important;font-size:1.05rem!important;"
        "box-shadow:none!important;}[class*='st-key-dr_poolfav_'] button:hover{transform:scale(1.2);}</style>",
        unsafe_allow_html=True)

    tab_board, tab_pool = st.tabs([f"{curr_year} Draft Board", "Available Rookie Pool"])

    # ── Tab 1: Draft board ────────────────────────────────────────────────────────
    with tab_board:
        # Settings strip (slider tucked behind "Edit settings")
        st.markdown(
            f'<div style="margin:4px 0 2px;color:var(--text-mid);font-size:.86rem;">'
            f'Mode: <strong style="color:var(--text-hi);">{_mode}</strong>'
            f'&nbsp;·&nbsp; Need Reach: <strong style="color:var(--text-hi);">{_reach_pct}%</strong>'
            f'&nbsp;·&nbsp; Value source: <strong style="color:var(--text-hi);">{vs_label(value_source)}</strong></div>',
            unsafe_allow_html=True)
        with st.expander("Edit settings"):
            st.caption("**Need Reach Limit** — how far a team reaches for positional need over Best "
                       "Player Available. 0% = pure BPA · 40% = heavily need-driven. Shared with Settings.")
            st.slider("Need Reach Limit", min_value=0, max_value=40, value=15, step=5,
                      format="%d%%", key="reach_limit_pct", label_visibility="collapsed")

        # Live on-the-clock alert
        _pick_team    = dict(zip(df_cur["Pick"], df_cur["Team"]))
        _unconfirmed  = [p for p in ordered_picks if p not in confirmed]
        on_clock_pick = _unconfirmed[0] if _unconfirmed else None
        on_deck_pick  = _unconfirmed[1] if len(_unconfirmed) > 1 else None
        my_next_pick  = next((p for p in _unconfirmed if _pick_team.get(p) == my_team), None) if my_team else None

        if not _unconfirmed:
            st.success("Every pick on the board is locked — draft complete.", icon=":material/check_circle:")
        elif not my_team:
            st.info("Pick your team in Settings to get a live on-the-clock alert for your picks.",
                    icon=":material/sports_football:")
        else:
            on_clock_team = _pick_team.get(on_clock_pick, "").strip()
            on_deck_team  = _pick_team.get(on_deck_pick, "").strip() if on_deck_pick else ""
            _you_on_clock = (my_next_pick == on_clock_pick)
            if _you_on_clock:
                _accent, _fg = "var(--green-bright)", "var(--pill-green-fg)"
                _bg = "var(--row-you-bg)"
                _dot = '<span class="dlh-dot green"></span>'
                _head = f"You're on the clock — make pick <strong>{my_next_pick}</strong>"
                _sub  = f"{on_deck_team} is on deck" if on_deck_team else ""
            else:
                _accent, _fg = "var(--gold)", "var(--pill-gold-fg)"
                _bg = "var(--pill-gold-bg)"
                _dot = '<span class="dlh-dot"></span>'
                _head = f"<strong>{on_clock_team}</strong> is on the clock — {on_clock_pick}"
                if my_next_pick:
                    _n   = _unconfirmed.index(my_next_pick)
                    _sub = f"Your pick (<strong>{my_next_pick}</strong>) is {plural(_n, 'pick')} away"
                    if on_deck_team:
                        _sub += f" · {on_deck_team} on deck"
                else:
                    _sub = (f"{on_deck_team} is on deck" if on_deck_team else "")
            _sub_html = (f'<div style="color:var(--text-mid);font-size:.82rem;margin-top:3px;">{_sub}</div>'
                         if _sub else "")
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;margin:14px 0 8px;background:{_bg};'
                f'border:1px solid {_accent};border-left:4px solid {_accent};border-radius:10px;padding:12px 16px;">'
                f'{_dot}<div><div style="color:{_fg};font-size:.95rem;">{_head}</div>{_sub_html}</div></div>',
                unsafe_allow_html=True)

        st.caption("Use **Select** on any upcoming pick to lock the rookie taken — the board saves and "
                   "re-estimates the remaining picks automatically (no full reload). Your picks carry a "
                   "green rail so they're easy to find.")

        # Board lives in a fragment: rookie selection reruns only the fragment (B5 fix preserved).
        @st.fragment
        def _draft_board_fragment():
            # Column headers use the same [6, 1.15] layout as the data rows — guarantees alignment.
            _hdr_info, _hdr_act = st.columns([6, 1.15])
            _hdr_info.markdown(
                '<div style="display:flex;align-items:center;gap:10px;padding:2px 14px 4px 17px;'
                'font:600 11px/1 \'Inter\',sans-serif;letter-spacing:1px;text-transform:uppercase;'
                'color:var(--text-low);">'
                '<span style="flex:0 0 50px;">Pick</span>'
                '<span style="flex:0 0 150px;">Team</span>'
                '<span style="flex:1;">Est. Rookie</span>'
                '<span style="flex:0 0 46px;text-align:center;">Pos</span>'
                '<span style="flex:0 0 64px;text-align:right;">FC Val</span>'
                '<span style="flex:1.3;padding-left:12px;">Logic</span>'
                '</div>', unsafe_allow_html=True)
            _hdr_act.markdown(
                '<div style="font:600 11px/1 \'Inter\',sans-serif;letter-spacing:1px;text-transform:uppercase;'
                'color:var(--text-low);text-align:center;padding-top:4px;">Select</div>',
                unsafe_allow_html=True)

            _opts = [""] + rookie_names
            with st.container(height=520):
                for _, row in df_cur.iterrows():
                    pick   = row["Pick"]
                    team   = (row["Team"] or "").strip()
                    sel    = rookie_sels.get(pick, {})
                    locked = pick in confirmed
                    is_you = bool(my_team) and row["Team"] == my_team
                    is_clk = (pick == on_clock_pick)

                    est_name = (confirmed.get(pick) if locked else sel.get("name")) or "—"
                    pos      = sel.get("pos", "—")
                    fcval    = sel.get("value")
                    logic    = sel.get("reason", "—") if not locked else "Confirmed"

                    if locked:
                        _bg, _rail = "var(--bg-inset)", "transparent"
                        _team_col, _txt, _pick_col = "var(--text-mid)", "var(--text-mid)", "var(--text-low)"
                        _state = '<span class="pill green" style="font-size:.64rem;padding:2px 9px;">&#10003; Locked</span>'
                    elif is_clk:
                        _bg, _rail = "var(--pill-gold-bg)", "var(--gold)"
                        _team_col, _txt, _pick_col = "var(--pill-gold-fg)", "var(--text-hi)", "var(--pill-gold-fg)"
                        _state = ('<span class="pill gold dlh-live-pill" style="font-size:.64rem;padding:2px 9px;'
                                  'display:inline-flex;align-items:center;gap:5px;"><span class="dlh-dot"></span>On Clock</span>')
                    elif is_you:
                        _bg, _rail = "var(--row-you-bg)", "var(--green-bright)"
                        _team_col, _txt, _pick_col = "var(--green-bright)", "var(--text-hi)", "var(--green-bright)"
                        _state = ''
                    else:
                        _bg, _rail = "var(--bg-surface)", "transparent"
                        _team_col, _txt, _pick_col = "var(--text-body)", "var(--text-hi)", "var(--text-mid)"
                        _state = ''

                    _fcval_s = f"{int(fcval):,}" if (fcval is not None and pd.notna(fcval)) else "—"

                    c_info, c_sel = st.columns([6, 1.15], vertical_alignment="center")
                    c_info.markdown(
                        f'<div style="display:flex;align-items:center;gap:10px;padding:9px 14px;margin:3px 0;'
                        f'border-radius:8px;background:{_bg};border-left:3px solid {_rail};">'
                        f'<span style="flex:0 0 50px;font-weight:700;color:{_pick_col};">{pick}</span>'
                        f'<span style="flex:0 0 150px;font-weight:600;color:{_team_col};overflow:hidden;'
                        f'text-overflow:ellipsis;white-space:nowrap;">{team}</span>'
                        f'<span style="flex:1;color:{_txt};overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{est_name}</span>'
                        f'<span style="flex:0 0 46px;text-align:center;">{_pos_chip(pos)}</span>'
                        f'<span style="flex:0 0 64px;text-align:right;color:var(--text-mid);font-variant-numeric:tabular-nums;">{_fcval_s}</span>'
                        f'<span style="flex:1.3;padding-left:12px;color:var(--text-mid);font-size:.82rem;'
                        f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{logic}</span>'
                        f'<span style="flex:0 0 auto;">{_state}</span>'
                        f'</div>', unsafe_allow_html=True)

                    _safe = pick.replace(".", "_")
                    _idx  = _opts.index(confirmed[pick]) if (locked and confirmed.get(pick) in _opts) else 0
                    c_sel.selectbox(
                        f"Select rookie for pick {pick}", _opts, index=_idx,
                        key=f"dr_sel_{_safe}", label_visibility="collapsed",
                        format_func=lambda x: "Select" if x == "" else x,
                    )

            # Confirmed picks are driven by the per-row selectboxes alone.
            _new_confirmed = {}
            for pick in ordered_picks:
                _v = st.session_state.get(f"dr_sel_{pick.replace('.', '_')}")
                if _v:
                    _new_confirmed[pick] = _v

            if _new_confirmed != st.session_state.draft_confirmed:
                # A rookie was selected/changed → persist + recompute the downstream board
                st.session_state.draft_confirmed = _new_confirmed
                save_draft_selections(league_id, _new_confirmed)
                st.rerun()

            st.caption(f"{len(_new_confirmed)} confirmed · {len(df_cur) - len(_new_confirmed)} estimated · "
                       "your draft is saved automatically")

        _draft_board_fragment()

        # Trade Block — a link to where it's managed, not a repeated table here.
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        _tb_c1, _tb_c2 = st.columns([3, 1], vertical_alignment="center")
        _tb_c1.caption("**Trade Block** — your shopped players live in the Trade Room, handy when "
                       "weighing pick-for-player swaps mid-draft.")
        def _goto_trade_room():
            st.session_state.nav_page = "Trade Room"
        _tb_c2.button("Open Trade Block →", key="dr_tradeblock", width="stretch",
                      on_click=_goto_trade_room)

    # ── Tab 2: Available Rookie Pool ──────────────────────────────────────────────
    with tab_pool:
        taken_names = set(confirmed.values())
        pool_src = sorted(
            [r for r in fc_rookies
             if r.get("position") in SKILL_POSITIONS and r.get("value")
             and r.get("name") not in taken_names],
            key=lambda r: r.get("value", 0), reverse=True,
        )
        pool_ranked = list(enumerate(pool_src, 1))

        pc1, pc2, pc3 = st.columns([2, 3, 1])
        pool_pos  = pc1.multiselect("Filter by position", SKILL_POSITIONS, key="dr_pool_pos")
        pool_srch = pc2.text_input("Search pool", key="dr_pool_srch", placeholder="e.g. Jeanty")
        pc3.markdown('<div style="padding-top:1.75rem;"></div>', unsafe_allow_html=True)
        pool_fav  = pc3.checkbox("★ only", key="dr_pool_fav")

        @st.fragment
        def _pool_fragment():
            favs = st.session_state.favorites
            rows = []
            for rank, r in pool_ranked:
                nm = r["name"]
                if pool_srch and pool_srch.lower() not in nm.lower():
                    continue
                if pool_pos and r.get("position") not in pool_pos:
                    continue
                if pool_fav and nm not in favs:
                    continue
                rows.append((rank, r))

            if not rows:
                st.info("No rookies match the current filters.")
                return

            # Column headers use the same [7, 0.7] layout as the data rows.
            _ph_ci, _ph_cf = st.columns([7, 0.7])
            _ph_ci.markdown(
                '<div style="display:flex;align-items:center;gap:10px;padding:2px 14px 4px 17px;'
                'font:600 11px/1 \'Inter\',sans-serif;letter-spacing:1px;text-transform:uppercase;'
                'color:var(--text-low);">'
                '<span style="flex:0 0 40px;">#</span>'
                '<span style="flex:1;">Rookie</span>'
                '<span style="flex:0 0 46px;text-align:center;">Pos</span>'
                '<span style="flex:0 0 70px;text-align:right;">FC Val</span>'
                '<span style="flex:0 0 70px;text-align:right;">Tier</span>'
                '</div>', unsafe_allow_html=True)
            _ph_cf.markdown(
                '<div style="font:600 11px/1 \'Inter\',sans-serif;letter-spacing:1px;text-transform:uppercase;'
                'color:var(--text-low);text-align:center;padding-top:4px;">Fav</div>',
                unsafe_allow_html=True)

            with st.container(height=460):
                for rank, r in rows:
                    nm   = r["name"]
                    pos  = r.get("position", "—")
                    val  = r.get("value")
                    tier = r.get("tier")
                    is_fav = nm in favs
                    _val_s  = f"{int(val):,}" if val else "—"
                    _tier_s = f"Tier {int(tier)}" if tier else "—"
                    _rail   = "var(--gold)" if is_fav else "transparent"

                    ci, cf = st.columns([7, 0.7], vertical_alignment="center")
                    ci.markdown(
                        f'<div style="display:flex;align-items:center;gap:10px;padding:8px 14px;margin:3px 0;'
                        f'border-radius:8px;background:var(--bg-surface);border-left:3px solid {_rail};">'
                        f'<span style="flex:0 0 40px;font-weight:700;color:var(--text-mid);">{rank}</span>'
                        f'<span style="flex:1;color:var(--text-hi);overflow:hidden;text-overflow:ellipsis;'
                        f'white-space:nowrap;">{nm}</span>'
                        f'<span style="flex:0 0 46px;text-align:center;">{_pos_chip(pos)}</span>'
                        f'<span style="flex:0 0 70px;text-align:right;color:var(--text-mid);'
                        f'font-variant-numeric:tabular-nums;">{_val_s}</span>'
                        f'<span style="flex:0 0 70px;text-align:right;color:var(--text-low);font-size:.8rem;">{_tier_s}</span>'
                        f'</div>', unsafe_allow_html=True)
                    if cf.button("★" if is_fav else "☆", key=f"dr_poolfav_{rank}",
                                 help="Remove favourite" if is_fav else "Add favourite"):
                        _new = set(favs)
                        _new.discard(nm) if is_fav else _new.add(nm)
                        st.session_state.favorites = _new
                        save_favorites(_new)
                        st.rerun()

            st.caption(f"{plural(len(rows), 'rookie')} available · tap ★ to favourite")

        _pool_fragment()

# ── Page: Fantasy News ───────────────────────────────────────────────────────
elif page == "Fantasy News":
    st.caption("NFL & fantasy news from ProFootballTalk, ESPN, NFL Trade Rumors + Sleeper transaction alerts · auto-refreshes every 30 minutes")

    with st.spinner("Loading news..."):
        try:
            rss_stories    = fetch_rss_news()
            sleeper_alerts = fetch_sleeper_player_news(players)
        except Exception as e:
            st.error(f"Failed to load news: {e}")
            rss_stories, sleeper_alerts = [], []

    all_stories = rss_stories + sleeper_alerts

    if not all_stories:
        st.info("No stories loaded — check your internet connection.")
    else:
        # ── Filters ───────────────────────────────────────────────────────────
        all_sources = sorted({s["source"] for s in all_stories})
        col_a, col_b = st.columns([2, 3])
        sel_sources = col_a.multiselect(
            "Sources", all_sources, default=all_sources, key="news_src"
        )
        news_search = col_b.text_input(
            "Search headlines & summaries", key="news_srch",
            placeholder="e.g. trade, injury, rookie, Josh Allen…"
        )

        filtered = [
            s for s in all_stories
            if s["source"] in sel_sources
            and (
                not news_search
                or news_search.lower() in s["title"].lower()
                or news_search.lower() in s["summary"].lower()
            )
        ]

        st.caption(f"{plural(len(filtered), 'story', 'stories')} shown · Last fetched: {datetime.now().strftime('%H:%M')}")
        st.divider()

        # ── Source colour badges — use border+text colour (theme-neutral) ────────
        SOURCE_COLORS = {
            "ProFootballTalk":      "#4A9EDB",
            "ESPN NFL":             "#E53935",
            "NFL Trade Rumors":     "#43A047",
            "Sleeper Transactions": "#FB8C00",
        }

        # ── Render stories ────────────────────────────────────────────────────
        for story in filtered:
            color = SOURCE_COLORS.get(story["source"], "#888888")
            with st.container():
                if story["link"]:
                    st.markdown(
                        f'<a href="{story["link"]}" target="_blank" style="font-size:1.05em; font-weight:600; text-decoration:none;">'
                        f'{story["title"]}</a>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"**{story['title']}**")

                col_src, col_time = st.columns([2, 3])
                col_src.markdown(
                    f'<span style="color:{color}; border:1px solid {color}; padding:2px 8px; '
                    f'border-radius:4px; font-size:0.82em; font-weight:600;">'
                    f'{story["source"]}</span>',
                    unsafe_allow_html=True,
                )
                # Format timestamp — guard against future/negative diffs (timezone skew)
                pub = story["published"]
                now = datetime.now(tz=timezone.utc)
                diff_h = (now - pub).total_seconds() / 3600 if pub.timestamp() > 0 else None
                if diff_h is None or diff_h < 0:
                    time_str = "Recent"   # keep format consistent — no raw RSS date strings
                elif diff_h < 1:
                    time_str = f"{max(1, int(diff_h * 60))}m ago"
                elif diff_h < 24:
                    time_str = f"{int(diff_h)}h ago"
                else:
                    time_str = pub.strftime("%b %d")
                col_time.caption(time_str)

                if story["summary"]:
                    st.caption(story["summary"])

                st.divider()
