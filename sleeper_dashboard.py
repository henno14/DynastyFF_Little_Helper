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

st.markdown("""
<style>
/* ── Modern type (loaded from Google Fonts; config.toml names them too) ─────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');

/* Brand tokens — single source of truth. Light values live alongside as a
   future flip (see config.toml note); dark is forced for the beta. */
:root{
  --brand-coral:#ff5a5f; --brand-coral-hi:#ff7a7e; --brand-coral-deep:#e23d42;
  --brand-gold:#e6b422;  --brand-gold-hi:#f2c94c;  --brand-green:#157a3d;
  --surface:#171c26; --surface-2:#1b212c; --border:#262d3a;
  --text:#fafafa; --muted:#9aa4b2;
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

/* ── Metric cards — branded: gradient surface + coral→gold accent rail ──────── */
[data-testid="stMetric"]{
  position:relative; overflow:hidden;
  background:linear-gradient(180deg,#1a2130 0%, #141a25 100%);
  border:1px solid #2a3344; border-radius:16px;
  padding:15px 18px 13px 21px; box-shadow:0 2px 10px rgba(0,0,0,.28);
  transition:border-color .15s ease, transform .1s ease;
}
[data-testid="stMetric"]::after{
  content:""; position:absolute; left:0; top:0; bottom:0; width:4px;
  background:linear-gradient(180deg,var(--brand-coral),var(--brand-gold));
}
[data-testid="stMetric"]:hover{ border-color:#3a4658; transform:translateY(-1px); }
[data-testid="stMetricLabel"]{
  color:var(--muted) !important; font-weight:600;
  text-transform:uppercase; letter-spacing:.05em; font-size:.72rem;
}
[data-testid="stMetricValue"]{ color:var(--text) !important; font-weight:600; }

/* ── Buttons ────────────────────────────────────────────────────────────────── */
.stButton>button, .stDownloadButton>button{
  border-radius:10px; font-weight:600;
  transition:transform .04s ease, box-shadow .15s ease, border-color .15s ease;
}
.stButton>button:hover{ border-color:var(--brand-coral); }
.stButton>button:active{ transform:translateY(1px); }
button[kind="primary"]{ box-shadow:0 2px 8px rgba(255,90,95,.22); }
button[kind="primary"]:hover{ box-shadow:0 5px 18px rgba(255,90,95,.4); transform:translateY(-1px); }

/* ── Tabs — coral selected state ────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"]{ gap:6px; }
.stTabs [aria-selected="true"]{ color:var(--brand-coral) !important; }
.stTabs [data-baseweb="tab-highlight"]{ background:var(--brand-coral) !important; }

/* ── Sidebar nav: radio → pill list with a coral active rail ────────────────── */
[data-testid="stSidebar"] [role="radiogroup"]{ gap:1px; }
[data-testid="stSidebar"] [role="radiogroup"] label{
  border-radius:9px; padding:7px 11px; margin:1px 0; width:100%;
  cursor:pointer; transition:background .12s ease;
}
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child{ display:none; } /* hide radio dot */
[data-testid="stSidebar"] [role="radiogroup"] label:hover{ background:rgba(255,255,255,.05); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){
  background:rgba(255,90,95,.14); box-shadow:inset 3px 0 0 var(--brand-coral);
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p{
  color:var(--brand-coral-hi) !important; font-weight:700;
}

/* ── Surfaces: dataframes / expanders / inputs get the rounded, bordered look ── */
[data-testid="stDataFrame"]{ border-radius:12px; overflow:hidden; }
[data-testid="stExpander"]{ border-radius:12px; }
hr{ border-color:var(--border); }
</style>
""", unsafe_allow_html=True)

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

# ── Player status tags (Untouchable / Keep / Trade / Cut) — per league ────────
TAG_OPTIONS = ["", "Untouchable", "Keep", "Trade", "Cut"]
TAG_DISPLAY = {
    "Untouchable": "🔒 Untouchable",
    "Keep":        "✅ Keep",
    "Trade":       "🔄 Trade Block",
    "Cut":         "✂️ Cut",
}

def load_player_tags(league_id):
    return _store_get(f"tags:{league_id}", {})

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
def fetch_dp_values():
    """Fetch DynastyProcess values.csv (weekly) and player-ID crosswalk.
    Returns (dp_map, cw_ktc_to_sid):
      dp_map        : {sleeper_id: {value, rank, ecr}}
      cw_ktc_to_sid : {ktc_id_str: sleeper_id_str}
    """
    import csv as _csv, io as _io, json as _json

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
        raw_vals = [float(r.get("value_2qb") or 0) for r in rows]
        max_val  = max(raw_vals) if raw_vals else 1
        ranked   = sorted(rows, key=lambda r: float(r.get("value_2qb") or 0), reverse=True)
        for rank_i, row in enumerate(ranked, 1):
            fp_id = str(row.get("fp_id") or "").strip()
            raw   = row.get("value_2qb")
            ecr   = row.get("ecr_2qb")
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
        with open(DP_CACHE, "w") as f:
            _json.dump(dp_map, f)
    except Exception as e:
        print(f"[WARNING] DP values fetch failed: {e}")
        if os.path.exists(DP_CACHE):
            age_h = (datetime.now().timestamp() - os.path.getmtime(DP_CACHE)) / 3600
            if age_h < 168:
                with open(DP_CACHE) as f:
                    dp_map = _json.load(f)

    return dp_map, cw_ktc_to_sid


@st.cache_data(ttl=3600, show_spinner=False)
def build_ktc_sleeper_map(ktc_by_ktcid, cw_ktc_to_sid, players):
    """Map KTC data to Sleeper player IDs.
    Strategy (in order):
      1. Name match: build a KTC name→data lookup, then scan the Sleeper players dict.
         This covers ~490 of ~500 KTC players and is the most reliable method.
      2. Crosswalk supplement: use dynastyprocess ktc_id→sleeper_id for any remaining gaps.
    """
    # Build name→data lookup from KTC (lower-case, suffix-stripped)
    ktc_by_name    = {}
    ktc_by_name_lc = {}
    for kid, d in ktc_by_ktcid.items():
        name = (d.get("name") or "").strip()
        if not name:
            continue
        ktc_by_name[name] = d
        ktc_by_name_lc[name.lower()] = d

    result = {}
    # Pass 1 — name matching against Sleeper players dict
    for pid, p in players.items():
        name = player_name(p)
        if not name:
            continue
        if name in ktc_by_name:
            result[pid] = ktc_by_name[name]
        elif name.lower() in ktc_by_name_lc:
            result[pid] = ktc_by_name_lc[name.lower()]
        else:
            # Strip common suffixes (Jr., Sr., II, III, IV)
            base = re.sub(r'\s+(Jr\.?|Sr\.?|II|III|IV)$', '', name, flags=re.IGNORECASE).strip()
            if base.lower() in ktc_by_name_lc:
                result[pid] = ktc_by_name_lc[base.lower()]

    # Pass 2 — crosswalk supplement for any KTC player still unmapped
    for kid, d in ktc_by_ktcid.items():
        sid = cw_ktc_to_sid.get(str(kid))
        if sid and sid not in result:
            result[sid] = d

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
        return _norm_fc(fc.get("value"))
    elif source == "DN Dynasty":
        return dn.get("value")
    elif source == "KTC":
        return ktc.get("value")
    elif source == "DP Values":
        return dp.get("value")
    else:  # Consensus Avg
        vals = [v for v in [
            _norm_fc(fc.get("value")),
            dn.get("value"),
            ktc.get("value"),
            dp.get("value"),
        ] if v is not None and v > 0]
        return int(sum(vals) / len(vals)) if vals else None


def get_active_rank(pid, fc_values, val_maps, source):
    """Return player rank for the active source, or None."""
    fc  = fc_values.get(pid, {})
    dn  = (val_maps or {}).get("dn",  {}).get(pid, {})
    ktc = (val_maps or {}).get("ktc", {}).get(pid, {})
    dp  = (val_maps or {}).get("dp",  {}).get(pid, {})

    if source == "FC Dynasty":
        return fc.get("overallRank")
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
        "DN Dynasty":    "DN Value",
        "KTC":           "KTC Value",
        "DP Values":     "DP Value",
        "Consensus Avg": "Cons. Avg",
    }.get(source, "Value")


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
    """Render a grid with a clickable ⭐ favourites column (first column).
    Favourites are keyed by player display name, shared across all grids,
    and persisted to favorites.json. Only the ⭐ column is editable.
    styler_fn: optional fn(df) -> Styler for row highlighting (applies to
    non-editable columns only, per st.data_editor behaviour)."""
    favs = st.session_state.favorites
    dv = dv.copy().reset_index(drop=True)
    if dv.empty:
        st.info("No players match your filters. Try clearing the search or changing position.")
        return
    dv = dash_na(dv)   # object-column None/NaN → '—' (no literal 'None')
    dv.insert(0, "⭐", dv[name_col].map(lambda n: n in favs))
    cfg = {**(col_cfg or {}), "⭐": st.column_config.CheckboxColumn("⭐", default=False)}
    disabled = [c for c in dv.columns if c != "⭐"]
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
        _submitted = st.form_submit_button("💾 Save favourites", type="primary")
    if _submitted:
        new_favs = set(favs)
        for _, row in edited.iterrows():
            if row["⭐"]:
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
                    help="🔒 Untouchable = never suggested in trades · ✅ Keep · "
                         "🔄 Trade Block = actively shopping · ✂️ Cut candidate",
                ),
            },
            disabled=["Player", "Pos", "Value"],
        )
        _submitted = st.form_submit_button("💾 Save tags", type="primary")
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
            _summary = ", ".join(f"{_n} {TAG_DISPLAY.get(_k, _k).split(' ', 1)[-1]}"
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
            "title":     f"📈 {name} trending up — {entry['count']:,} adds in last 24h",
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
            "title":     f"📉 {name} trending down — {entry['count']:,} drops in last 24h",
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
    # Centre + constrain the entry form so it reads like an intentional login card
    _el, _ec, _er = st.columns([1, 1.4, 1])
    with _ec:
        if _LOGO_HORIZONTAL:
            st.markdown(
                f'<div style="display:flex; justify-content:center; margin:0.5rem 0 0.25rem;">'
                f'<div style="width:min(440px,80%);">{_LOGO_HORIZONTAL}</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.title("🏈 Dynasty FF Lil' Helper")
        st.markdown(
            '<p style="text-align:center; color:#9aa4b2; max-width:620px; margin:0 auto 0.5rem;">'
            "Your dynasty trade brain — FantasyCalc + DynastyNerds + KeepTradeCut + DynastyProcess "
            "in one, plus trade analysis, draft tools, and a free-agent advisor.</p>",
            unsafe_allow_html=True,
        )
        # Signed in but no saved league yet (first sign-in) → guide them to pick one
        if st.session_state.get("auth_email"):
            st.success(f"✅ Signed in as **{st.session_state.auth_email}** — pick your league below "
                       "to get started (your settings will save automatically from now on).")
        _tab_find, _tab_signin = st.tabs(["🔎 Find my league", "🔑 Sign in"])

        with _tab_signin:
            if not auth_available():
                st.info("Sign-in isn't available right now — use **Find my league**.")
            else:
                st.caption("Signed-in members jump straight back to their league and saved settings.")
                if not st.session_state.get("_auth_code_sent"):
                    _ae = st.text_input("Email", key="entry_auth_email", placeholder="you@email.com")
                    if st.button("Send code", key="entry_auth_send"):
                        ok, err = auth_send_code(_ae)
                        if ok:
                            st.session_state._auth_code_sent = True
                            st.session_state._auth_pending_email = (_ae or "").strip()
                            st.rerun()
                        else:
                            st.error(f"Couldn't send code: {err}")
                else:
                    st.caption(f"Code sent to **{st.session_state.get('_auth_pending_email','')}** — check your email.")
                    _code = st.text_input("6-digit code", key="entry_auth_code")
                    _ec1, _ec2 = st.columns(2)
                    if _ec1.button("Verify & sign in", type="primary", key="entry_auth_verify"):
                        _em = auth_verify_code(st.session_state.get("_auth_pending_email", ""), _code)
                        if _em:
                            st.session_state.auth_email = _em
                            st.session_state.pop("_auth_code_sent", None)
                            _ll = load_last_league()      # jump straight in if they have a saved league
                            if _ll:
                                st.session_state.league_id = _ll
                            st.session_state._toast_msg = f"Signed in as {_em}"
                            st.rerun()
                        else:
                            st.error("Invalid or expired code — try again.")
                    if _ec2.button("Cancel", key="entry_auth_cancel"):
                        st.session_state.pop("_auth_code_sent", None)
                        st.rerun()

        with _tab_find:
            st.caption("Enter your **Sleeper username** (we'll find your leagues) — or paste a **league ID** directly.")
            _in = st.text_input("Sleeper username or league ID", key="entry_input",
                                placeholder="your Sleeper username — or paste a league ID")
            if st.button("Find →", type="primary", key="entry_find"):
                _q = (_in or "").strip()
                st.session_state.pop("_entry_err", None)
                if _q.isdigit() and len(_q) >= 15:        # looks like a league ID
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
                else:                                      # treat as a Sleeper username
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
                if st.button("Open league →", type="primary", key="entry_open"):
                    st.session_state.league_id = _labels[_pick]
                    save_last_league(_labels[_pick])
                    st.session_state.pop("_found_leagues", None)
                    st.session_state.pop("_entry_err", None)
                    st.rerun()
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
    dn_map       = fetch_dn_values()
    ktc_by_id    = fetch_ktc_values()
    dp_map, cw_ktc = fetch_dp_values()
    ktc_map      = build_ktc_sleeper_map(ktc_by_id, cw_ktc, players)
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
        # Centre + constrain so it matches the login card and reads intentionally
        _su_l, _su_c, _su_r = st.columns([1, 1.6, 1])
        with _su_c:
            st.title(f"🏈 {league.get('name', 'Your league')}")
            st.caption("Quick setup — you can change either of these anytime from the sidebar.")
            # st.form batches the dropdowns: picking a team / value source no longer
            # triggers a rerun on every change — nothing saves until "Continue".
            with st.form("setup_form", border=False):
                _setup_team = st.selectbox("Which team is yours?", ["—"] + _teams0, key="setup_team")
                _setup_vs = st.selectbox(
                    "Value source", ["FC Dynasty", "DN Dynasty", "KTC", "DP Values", "Consensus Avg"],
                    key="setup_vs",
                )
                st.caption(
                    "**Value source** sets which dynasty ranking powers every player's value & rank "
                    "across the app — FantasyCalc, DynastyNerds, KeepTradeCut, DynastyProcess, or a "
                    "consensus average of them. You can switch it anytime from the sidebar."
                )
                _setup_go = st.form_submit_button("Continue →", type="primary")
            if _setup_go:
                save_league_prefs(league_id, value_source=_setup_vs,
                                  team=(_setup_team if _setup_team != "—" else None))
                st.session_state.pop("_prefs_seeded_for", None)   # sidebar re-seeds from these
                st.session_state._onboarded_for = league_id
                st.rerun()
            if st.button("Switch league", key="setup_switch"):
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
    st.session_state._auto_cut_done = set()
    st.session_state.pop("_prefs_seeded_for", None)   # re-seed My Team / value source from store

# Reseed tags when the league changes within the same identity
if st.session_state.get("_player_tags_league") != league_id:
    st.session_state.player_tags = load_player_tags(league_id)
    st.session_state._player_tags_league = league_id
    st.session_state._auto_cut_done = set()

# ── Sidebar: identity + value source (rendered early — value_source drives the
#    data pipeline below; team names derive straight from rosters/users) ───────
_user_map_sb = {u["user_id"]: u for u in users}
_sb_team_names = sorted({
    (( _user_map_sb.get(r.get("owner_id") or "", {}) ).get("metadata") or {}).get("team_name")
    or _user_map_sb.get(r.get("owner_id") or "", {}).get("display_name")
    or f"Team {r['roster_id']}"
    for r in rosters
})

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
    _home_label = "Dynasty FF Lil' Helper — Home" if _LOGO_HORIZONTAL else "🏠 Home"
    if st.button(_home_label, width="stretch", key="nav_home"):
        st.session_state.nav_page = "🏠 League Overview"
        st.rerun()

    # ── Account: optional email sign-in (saves settings across devices) ───────
    if auth_available():
        if st.session_state.get("auth_email"):
            st.caption(f"✅ Signed in · {st.session_state.auth_email}")
            if st.button("Sign out", width="stretch", key="auth_signout"):
                for _k in ("auth_email", "_auth_code_sent", "_auth_pending_email", "_onboarded_for"):
                    st.session_state.pop(_k, None)
                st.session_state.league_id = None              # back to the entry screen
                st.session_state.nav_page   = "🏠 League Overview"  # land on Overview next time
                st.rerun()
        else:
            with st.expander("🔑 Sign in to save", expanded=False):
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
    st.subheader(f"🏈 {league.get('name', 'Dynasty League')}")
    st.caption(f"Sleeper · {league.get('season', '')} · {league.get('total_rosters', '?')} teams")

    # My Team + Value Source — persisted per league; re-seeded when league changes
    _team_opts = ["—"] + _sb_team_names
    if st.session_state.get("_prefs_seeded_for") != league_id:
        st.session_state._prefs_seeded_for = league_id
        _prefs = load_league_prefs(league_id)
        _saved_team = _prefs.get("team")
        st.session_state.my_team_pick = _saved_team if _saved_team in _team_opts else "—"
        _saved_vs = _prefs.get("value_source")
        _vs_opts_boot = ["FC Dynasty", "DN Dynasty", "KTC", "DP Values", "Consensus Avg"]
        st.session_state.value_source = _saved_vs if _saved_vs in _vs_opts_boot else "FC Dynasty"
        # New league context → page-level sticky team choices no longer apply
        for _sk in [k for k in list(st.session_state.keys()) if str(k).startswith("_sticky_")]:
            st.session_state.pop(_sk, None)
        st.session_state.pop("_last_my_team", None)
        st.session_state.pop("_last_value_source", None)
    _my_team_sel = st.selectbox("My Team", _team_opts, key="my_team_pick")
    my_team = None if _my_team_sel == "—" else _my_team_sel
    if st.session_state.get("_last_my_team", "__unset__") != my_team:
        save_league_prefs(league_id, team=my_team)
        # Identity changed → reset page-level sticky team choices so the
        # new team becomes the default everywhere on next visit
        for _sk in [k for k in list(st.session_state.keys()) if str(k).startswith("_sticky_")]:
            st.session_state.pop(_sk, None)
        st.session_state._last_my_team = my_team

    # Value source — drives every Value/Rank column; persisted per league
    _vs_options_sb = ["FC Dynasty", "DN Dynasty", "KTC", "DP Values", "Consensus Avg"]
    st.selectbox("Value Source", _vs_options_sb, key="value_source")
    if st.session_state.get("_last_value_source") != st.session_state.value_source:
        save_league_prefs(league_id, value_source=st.session_state.value_source)
        st.session_state._last_value_source = st.session_state.value_source

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
_trade_cache_key = f"trade_data_{league_id}_{value_source}"
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
with st.sidebar:
    st.divider()
    page = st.radio("", [
        "🏠 League Overview",
        "📋 Rosters & Draft Picks",
        "🔍 Free Agents",
        "📈 Trending",
        "📰 Fantasy News",
        "🔄 Trade Analyzer",
        "🌟 2026 Rookies",
        "🏟️ Draft Room",
        "⚙️ Settings",
    ], label_visibility="collapsed", key="nav_page")


def _refresh_all_data():
    """Clear every cached source so the next run re-fetches fresh data."""
    load_all_data.clear()
    fetch_dn_values.clear()
    fetch_ktc_values.clear()
    fetch_dp_values.clear()
    build_ktc_sleeper_map.clear()
    load_trending.clear()
    fetch_rss_news.clear()
    for _k in ["_trade_cache_key", "_team_data", "_league_avgs",
               "_all_players_by_pos", "_team_name_to_rid", "_def_analysis", "_league_def_avg",
               "_data_warmed_for"]:   # re-show the loading spinner during the real re-fetch
        st.session_state.pop(_k, None)

# Flush any pending save confirmation (set before a st.rerun on the previous run)
if st.session_state.get("_toast_msg"):
    st.toast(st.session_state.pop("_toast_msg"), icon="💾")

# ── Page: League Overview ─────────────────────────────────────────────────────
if page == "🏠 League Overview":
    @st.fragment
    def _frag_league_overview():
        st.title(league.get("name", "Dynasty League"))

        # Top metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Teams",          len(rosters))
        col2.metric("Players Valued", f"{len(fc_values):,}")
        col3.metric("Rookies Ranked", len(fc_rookies))
        col4.metric("Pick Values",    len(fc_picks))
        col5.metric("Stats Season",   STATS_SEASON)
        st.caption(
            f"Value sources loaded — FantasyCalc {len(fc_values):,} · DynastyNerds {len(dn_map):,} · "
            f"KeepTradeCut {len(ktc_map):,} · DynastyProcess {len(dp_map):,}"
        )

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

        def _badge(rank, n, excluded=False):
            if rank is None:
                return '<td style="text-align:center;color:#555">—</td>'
            if excluded:
                return (f'<td style="text-align:center;padding:6px 4px">'
                        f'<span style="background:#1a1d24;color:#444;padding:3px 10px;'
                        f'border-radius:12px;font-size:0.82rem;font-weight:600;text-decoration:line-through">#{rank}</span></td>')
            pct = 1 - (rank - 1) / max(n - 1, 1)
            if   pct >= 0.75: bg, fg = "#0d3320", "#4ade80"
            elif pct >= 0.5:  bg, fg = "#2d2500", "#fbbf24"
            elif pct >= 0.25: bg, fg = "#2d1400", "#fb923c"
            else:             bg, fg = "#2d0a0a", "#f87171"
            return (f'<td style="text-align:center;padding:6px 4px">'
                    f'<span style="background:{bg};color:{fg};padding:3px 10px;'
                    f'border-radius:12px;font-size:0.82rem;font-weight:600">#{rank}</span></td>')

        # Header — greyed label for excluded columns
        def _th(label, excluded=False):
            _style = "text-align:center;padding:10px 8px;font-weight:500;"
            _style += "color:#444;text-decoration:line-through" if excluded else "color:#888"
            return f'<th style="{_style}">{label}</th>'

        _tbl_html = (
            '<table style="width:100%;border-collapse:collapse;font-size:0.88rem;margin-top:6px">'
            '<thead><tr style="border-bottom:2px solid #2d3140">'
            '<th style="text-align:left;padding:10px 14px;color:#888;font-weight:500;width:28%">#&nbsp; Team</th>'
            + _th("QB") + _th("RB") + _th("WR") + _th("TE")
            + _th("Picks", _excl_picks) + _th("DEF", _excl_def)
            + '<th style="text-align:left;padding:10px 14px;color:#888;font-weight:500;min-width:110px">Score</th>'
            '</tr></thead><tbody>'
        )

        for i, row in enumerate(_pr_rows):
            _is_mine = my_team and row["team"] == my_team
            _bg  = "rgba(255,196,0,0.12)" if _is_mine else ("#16191f" if i % 2 == 0 else "#11141a")
            _sc  = row["score"]
            _bc  = "#4ade80" if _sc >= 60 else ("#fbbf24" if _sc >= 40 else "#f87171")
            _row_border = "border-left:3px solid #ffc400;" if _is_mine else ""
            _star = "⭐ " if _is_mine else ""
            _tbl_html += f'<tr style="background:{_bg};{_row_border}border-bottom:1px solid #1e2130">'
            _tbl_html += (f'<td style="padding:10px 14px;font-weight:500;color:#e0e0e0">'
                          f'<span style="color:#555;margin-right:8px">{i+1}</span>{_star}{row["team"]}</td>')
            # Always show all 6 position badges — greyed out if excluded from score
            for _dim, _excl in [("QB",False),("RB",False),("WR",False),("TE",False),
                                 ("Picks",_excl_picks),("DEF",_excl_def)]:
                _tbl_html += _badge(row[_dim], _n, excluded=_excl)
            _tbl_html += (f'<td style="padding:10px 14px">'
                          f'<div style="display:flex;align-items:center;gap:8px">'
                          f'<div style="background:#1e2130;border-radius:4px;height:7px;flex:1;min-width:60px">'
                          f'<div style="background:{_bc};width:{_sc}%;height:7px;border-radius:4px"></div></div>'
                          f'<span style="font-size:0.82rem;color:#ccc;min-width:26px;text-align:right">{_sc}</span>'
                          f'</div></td></tr>')

        _tbl_html += "</tbody></table>"
        st.markdown(_tbl_html, unsafe_allow_html=True)

        st.markdown("---")

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
            st.plotly_chart(fig_radar, width="stretch")

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
            st.plotly_chart(fig_bar, width="stretch")

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
                st.plotly_chart(fig_scatter, width="stretch")
                if my_team:
                    st.caption(f"⭐ Gold dot = {my_team}")
            else:
                st.info("Not enough roster age data to generate scatter chart.")

    # ── Page: Rosters ─────────────────────────────────────────────────────────────
    _frag_league_overview()
elif page == "📋 Rosters & Draft Picks":
    df_r = build_rosters_df(rosters, users, players, player_pts, pos_ranks, fc_values,
                            val_maps=val_maps, value_source=value_source)
    # All four sources are shown side-by-side now (Players page merged in), so the
    # single dynamic active-value column is redundant — drop it.
    df_r = df_r.drop(columns=["Value"]).rename(columns={"_cons_avg": "Cons. Avg"})

    st.header("👥 Players")
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
    r_fav_only = st.checkbox("⭐ Favourites only", key="r_fav_only")

    mask = pd.Series(True, index=df_r.index)
    if sel_teams: mask &= df_r["Team"].isin(sel_teams)
    if sel_pos:   mask &= df_r["Pos"].isin(sel_pos)
    if sel_slots: mask &= df_r["Slot"].isin(sel_slots)
    if name_srch: mask &= df_r["Player"].str.contains(name_srch, case=False, na=False)
    if r_fav_only: mask &= df_r["Player"].isin(st.session_state.favorites)
    dv = df_r[mask]

    # All four sources side-by-side (merged from the old Players page) + Cons. Avg
    _src_cols = ["FC D Value", "DN Value", "KTC Value", "DP Value", "Cons. Avg"]
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
    st.caption(f"{plural(len(dv), 'player')} shown · all sources normalised to 0–10K · tick the ⭐ box to favourite")

    # ── Player Tags (My Team) — its own section (future sub-menu) ─────────────
    st.divider()
    st.header("🏷️ Player Tags")
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
        _r_block = [p for p in _my_players if st.session_state.player_tags.get(p["name"]) == "Trade"]
        if _r_block:
            st.markdown("**🔄 Your Trade Block:** " + " · ".join(f"{p['name']} ({p['pos']})" for p in _r_block))
        st.caption(f"Tagging **{my_team.strip()}** · 🔒 Untouchable players are never suggested in trades · shared with Trade Analyzer")
        tag_editor(_my_players, "tags_rosters")

    # ════════ Draft Picks (merged in — will become a sub-menu) ═══════════════
    st.divider()
    st.header("🎯 Draft Picks")
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
        if rel >= 10:  return "🟢 Surplus"
        if rel <= -10: return "🔴 Deficit"
        return "🟡 Average"

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
    _hl_note = f" · ⭐ highlighted = {my_team}" if my_team and (dv["Team"] == my_team).any() else ""
    st.caption(f"{plural(len(dv), 'pick')} shown · 🟢 Surplus = pick-rich · 🟡 Average · 🔴 Deficit = pick-poor{_hl_note}")

# ── Page: Free Agents ────────────────────────────────────────────────────────
elif page == "🔍 Free Agents":
    df_fa = build_fa_df(rosters, players, player_pts, pos_ranks, fc_values,
                        val_maps=val_maps, value_source=value_source)
    df_fa = df_fa.rename(columns={"Value": val_col})

    # Resolve _cons_avg column
    if value_source != "Consensus Avg":
        df_fa = df_fa.rename(columns={"_cons_avg": "Cons. Avg"})
    else:
        df_fa = df_fa.drop(columns=["_cons_avg"])

    st.header("🔍 League Current Free Agents")
    col_a, col_b, col_c, col_d = st.columns([2, 2, 2, 3])

    sel_fa_pos    = col_a.multiselect("Positions", sorted(df_fa["Pos"].unique().tolist()), key="fa_pos",
                                      placeholder="All positions")
    col_b.markdown('<div style="padding-top: 1.75rem;"></div>', unsafe_allow_html=True)
    incl_rookies  = col_b.checkbox("Include Rookies", value=False, key="fa_rookies")
    fa_fav_only   = col_b.checkbox("⭐ Favourites only", key="fa_fav_only")
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
    st.caption(f"{plural(len(dv), 'free agent')} shown · sorted by {value_source} value (best first) · tick the ⭐ box to favourite")

    # ── Pickup & Drop Advisor ─────────────────────────────────────────────────
    st.divider()
    st.subheader("🔄 Pickup & Drop Advisor")
    st.caption("Select your team to see personalised free agent targets and roster trim candidates.")

    _adv_opts    = sorted(team_name_to_rid.keys())
    _adv_default = st.session_state.get("_sticky_fa_adv")
    if _adv_default not in _adv_opts:   # no choice this session → default to My Team
        _adv_default = my_team if my_team in _adv_opts else None
    _adv_team = st.selectbox(
        "Team to advise", _adv_opts,
        index=_adv_opts.index(_adv_default) if _adv_default else None,
        placeholder="Select a team…", key="fa_advisor_team",
        help="Defaults to your sidebar 'My Team'. Change it here to get pickup/drop advice "
             "for a different team without switching your global selection.",
    )
    if _adv_team:
        st.session_state._sticky_fa_adv = _adv_team

    if _adv_team:
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
        st.markdown("#### 📊 Positional Needs")
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

        st.divider()

        # ── Recommended pickups — tabbed by top 2 needs + Best Available ──────
        st.markdown("#### 🎯 Recommended Pickups")
        _top_need_positions = [p for p, _ in _sorted_needs[:2]]
        _tab_labels = [f"📍 {p} (Need: {_need_scores[p]:.0f})" for p in _top_need_positions] + ["⭐ Best Available"]
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
        st.markdown("#### ✂️ Drop Candidates *(if you need a roster spot)*")
        st.caption("Rostered players ranked by drop priority — weighs value vs positional average, recent points, injury status, and experience.")

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

                # Drop score — higher = more expendable
                _val_score  = max(0.0, 1.0 - _val / _pos_avg_val) * 40   # below pos avg → +score
                _pts_score  = max(0.0, 1.0 - _pts / 150.0)       * 30   # low pts → +score
                _inj_score  = (20 if _status in ("Out", "IR", "PUP", "Suspended")
                               else 10 if _status in ("Questionable", "Doubtful") else 0)
                _age_score  = min(_exp / 10.0, 1.0)               * 10   # veterans → +score
                _drop_score = _val_score + _pts_score + _inj_score + _age_score

                _reasons = []
                # Players you've tagged ✂️ Cut always surface at the top of the list
                if st.session_state.player_tags.get(_pp["name"]) == "Cut":
                    _drop_score += 1000
                    _reasons.append("✂️ Tagged Cut")
                if _val < _pos_avg_val * 0.5:             _reasons.append("Low value")
                if _pts < 50:                             _reasons.append("Low pts")
                if _status in ("Out", "IR", "PUP"):       _reasons.append(_status)
                elif _status in ("Questionable","Doubtful"): _reasons.append(_status)
                if _exp >= 7:                             _reasons.append(f"{_exp}yr vet")

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

        # Auto-tag genuine drop candidates (score ≥ 50: clearly below positional value
        # AND low production) as ✂️ Cut — but only for YOUR team, once per session, and
        # never overwriting a tag you've set or cleared yourself.
        _auto_cut_n = 0
        if my_team and _adv_team == my_team:
            _auto_done = st.session_state.setdefault("_auto_cut_done", set())
            for _r in _drop_rows:
                _nm = _r["Player"]
                if _r["_score"] >= 50 and _nm not in st.session_state.player_tags and _nm not in _auto_done:
                    st.session_state.player_tags[_nm] = "Cut"
                    _auto_done.add(_nm)
                    _auto_cut_n += 1
            if _auto_cut_n:
                save_player_tags(league_id, st.session_state.player_tags)

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
            if my_team and _adv_team == my_team:
                _cut_note = (f" · auto-tagged {plural(_auto_cut_n, 'player')} ✂️ Cut this session"
                             if _auto_cut_n else "")
                st.caption("Strong drop candidates are auto-tagged ✂️ Cut on your roster — "
                           f"edit anytime on Rosters / Trade Analyzer; your changes are kept.{_cut_note}")

# ── Page: 2026 Rookies ───────────────────────────────────────────────────────
elif page == "🌟 2026 Rookies":
    df_rk = build_rookies_df(fc_rookies, rosters, fc_values=fc_values, val_maps=val_maps, value_source=value_source)
    df_rk = df_rk.rename(columns={"Value": val_col, "Rank": "Overall Rank"})

    col_a, col_b, col_c, col_d = st.columns([2, 2, 3, 1])
    sel_rk_pos  = col_a.multiselect("Positions",    sorted(df_rk["Pos"].unique().tolist()), key="rk_pos",
                                    placeholder="All positions")
    sel_rk_rost = col_b.selectbox("Roster Status",  ["All", "On Roster", "Not Rostered"],   key="rk_rost")
    rk_srch     = col_c.text_input("Search player name", key="rk_name", placeholder="e.g. Ashton Jeanty")
    col_d.markdown('<div style="padding-top: 1.75rem;"></div>', unsafe_allow_html=True)
    rk_fav_only = col_d.checkbox("⭐ Only", key="rk_fav_only")

    mask = pd.Series(True, index=df_rk.index)
    if sel_rk_pos:                      mask &= df_rk["Pos"].isin(sel_rk_pos)
    if sel_rk_rost == "On Roster":      mask &= df_rk["On Roster"] == "Yes"
    elif sel_rk_rost == "Not Rostered": mask &= df_rk["On Roster"] == "No"
    if rk_srch:                         mask &= df_rk["Player"].str.contains(rk_srch, case=False, na=False)
    if rk_fav_only:                     mask &= df_rk["Player"].isin(st.session_state.favorites)
    dv = df_rk[mask]

    fav_grid(dv, "Player", "rk_fav_grid",
             col_cfg={val_col: COL_CFG["Value"], "Overall Rank": COL_CFG["Rank"]})
    st.caption(f"{plural(len(dv), 'rookie')} shown (sorted by rookie value) · \"Overall Rank\" = dynasty rank across all players · Value source: **{value_source}** · tick the ⭐ box to favourite")

# ── Page: Settings (includes Scoring Rules section) ──────────────────────────
elif page == "⚙️ Settings":
    st.title("Settings")
    if _signed_in():
        st.caption(f"✅ Signed in as **{st.session_state.auth_email}** — your team, value source, favourites and tags are saved to your account.")
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
    if _dc2.button("🔄 Refresh data", width="stretch",
                   help="Re-fetch all values, stats and news from the sources"):
        _refresh_all_data()
        st.rerun()
    _dc3.markdown('<div style="padding-top:0.5rem;"></div>', unsafe_allow_html=True)
    if _dc3.button("🔁 Switch league", width="stretch"):
        st.session_state.league_id = None
        st.rerun()
    st.divider()

    col_s1, col_s2 = st.columns(2)

    with col_s1:
        st.subheader("Value Source")
        st.caption(
            "Controls which data source drives the **Value** and **Rank** columns "
            "across Rosters, Free Agents, and Trade Analyzer. Picks always use FC values."
        )
        _vs_sel = st.session_state.get("value_source", "FC Dynasty")
        st.success(f"Current source: **{_vs_sel}** — change it anytime from the **sidebar** (under My Team).")
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

    with col_s2:
        st.subheader("Theme")
        st.info("🌙 **Dark theme** — Dynasty FF Lil' Helper is dark-only for now. A polished light theme is on the roadmap.")

    st.divider()
    st.subheader("Draft Room")
    st.slider(
        "Need Reach Limit", min_value=0, max_value=40, value=15, step=5, format="%d%%",
        key="reach_limit_pct",
        help="How far simulated teams reach for positional need over Best Player Available "
             "in the Draft Room. 0% = pure BPA, 40% = heavily need-driven. (Also on the Draft Room page.)",
    )

    # ════════ Scoring Rules (merged in — will become a sub-menu) ═════════════
    st.divider()
    st.header("📊 Scoring Rules")
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

# ── Page: Trending ───────────────────────────────────────────────────────────
elif page == "📈 Trending":
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
        _tr_note = f" · ⭐ highlighted = {my_team}"
    else:
        st.dataframe(dv, width="stretch", hide_index=True, column_config=_tr_col_cfg)
        _tr_note = ""
    st.caption(f"Top adds + drops across all Sleeper leagues (last {TREND_LOOKBACK}h) · {len(dv)} shown · Value source: **{value_source}**{_tr_note}")

# ── Page: Trade Analyzer ─────────────────────────────────────────────────────
elif page == "🔄 Trade Analyzer":
    @st.fragment
    def _frag_trade_analyzer():
        # team_data / league_avgs / all_players_by_pos already computed above tabs
        # ── Team selector ─────────────────────────────────────────────────────────
        _ta_opts    = sorted(team_name_to_rid.keys())
        _ta_default = st.session_state.get("_sticky_ta_team")
        if _ta_default not in _ta_opts:   # no choice this session → default to My Team
            _ta_default = my_team if my_team in _ta_opts else _ta_opts[0]
        sel_ta_team = st.selectbox(
            "Select team to analyze",
            _ta_opts,
            index=_ta_opts.index(_ta_default),
            key="ta_team",
        )
        st.session_state._sticky_ta_team = sel_ta_team
        rid = team_name_to_rid[sel_ta_team]
        td  = team_data[rid]

        # Set of Untouchable player names for THIS team — excluded from all trade-away lists
        _player_tags = st.session_state.player_tags
        _untouchable = {
            p["name"] for _pos in SKILL_POSITIONS for p in td["pos_players"].get(_pos, [])
            if _player_tags.get(p["name"]) == "Untouchable"
        }

        # ── Player status tags ────────────────────────────────────────────────────
        with st.expander("🏷️ Tag players (Untouchable / Keep / Trade / Cut)", expanded=False):
            _ta_players = [
                {"name": p["name"], "pos": _pos, "value": p["value"]}
                for _pos in SKILL_POSITIONS for p in td["pos_players"].get(_pos, [])
            ]
            _ta_players.sort(key=lambda x: x["value"] or 0, reverse=True)
            st.caption(f"Tagging **{sel_ta_team.strip()}** · 🔒 Untouchable players are excluded from trade suggestions below · shared with the Rosters page")
            tag_editor(_ta_players, "tags_trade")

        # ── Your trade block (players tagged 🔄 Trade) ────────────────────────────
        _trade_block = [
            {"name": p["name"], "pos": _pos, "value": p["value"]}
            for _pos in SKILL_POSITIONS for p in td["pos_players"].get(_pos, [])
            if _player_tags.get(p["name"]) == "Trade"
        ]
        if _trade_block:
            _trade_block.sort(key=lambda x: x["value"] or 0, reverse=True)
            st.markdown("**🔄 Your Trade Block**")
            st.dataframe(
                pd.DataFrame([{"Player": p["name"], "Pos": p["pos"], val_col: p["value"]} for p in _trade_block]),
                width="stretch", hide_index=True,
                column_config={val_col: COL_CFG["Value"]},
            )

        st.divider()

        # ── Positional strength — summary banner + detail table ──────────────────
        st.subheader("Positional Strength vs League Average")
        st.caption(f"Score (0–100) = league rank (40%) + value gap (40%) + depth drop-off (20%) · "
                   f"based on value source: **{value_source}** (change in sidebar)")

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
            })

        # Sort: needs first (by score desc), then average, then surpluses (by score desc)
        def _tbl_sort(r):
            s = r["Score"] or 0
            if "Need" in r["Status"]:    return (0, -s)
            if "Average" in r["Status"]: return (1, 0)
            return (2, -s)
        _tbl_rows.sort(key=_tbl_sort)

        st.dataframe(
            pd.DataFrame(_tbl_rows),
            width="stretch",
            hide_index=True,
            column_config={
                "Your Avg":   st.column_config.NumberColumn("Your Avg",   format="%d"),
                "League Avg": st.column_config.NumberColumn("League Avg", format="%d"),
                "Score":      st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
            },
        )

        # ── Full breakdown table ───────────────────────────────────────────────────
        with st.expander("Full positional breakdown (players + picks)", expanded=False):
            breakdown_rows = []

            def _player_status(rel):
                if rel is None:   return "—"
                if rel >= 15:     return "🟢 Well Above Avg"
                if rel >= 5:      return "🟡 Above Avg"
                if rel >= -5:     return "⚪ Near Avg"
                if rel >= -15:    return "🟠 Below Avg"
                return "🔴 Well Below Avg"

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

        # ── Best Trade Partners ───────────────────────────────────────────────────
        st.subheader("🤝 Best Trade Partners")
        st.caption(
            "Ranked by mutual trade fit: how much they have what you need (40%) + "
            "how much they need what you have (40%) + value proximity (20%). "
            "Sample trades pair their target with your closest-value surplus piece — a balanced starting point, not your franchise asset."
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
            _my_surplus_players = [p for p in td.get("pos_players", {}).get(_my_surplus, [])
                                   if p["name"] not in _untouchable]

            _partner_rows = []
            for _o_rid, _o_td in team_data.items():
                if _o_rid == rid:
                    continue

                # How much does the other team have what I need?
                _their_supply = _o_td.get("surplus_scores", {}).get(_my_need, 0)
                # How much does the other team need what I have?
                _their_need   = _o_td.get("need_scores", {}).get(_my_surplus, 0)

                # Their headline asset at my need position (the appealing target)
                _their_candidates = _o_td.get("pos_players", {}).get(_my_need, [])
                _their_give_val   = _their_candidates[0]["value"] if _their_candidates else 0
                _their_give_name  = _their_candidates[0]["name"]  if _their_candidates else "—"

                # Value-match MY side: offer the surplus player closest in value to what I'd get,
                # not my franchise asset — produces a realistic, balanced 1-for-1 sample.
                if _my_surplus_players and _their_give_val > 0:
                    _match = min(_my_surplus_players, key=lambda p: abs((p["value"] or 0) - _their_give_val))
                    _my_give_val, _my_give_name = _match["value"] or 0, _match["name"]
                elif _my_surplus_players:
                    _my_give_val, _my_give_name = _my_surplus_players[0]["value"] or 0, _my_surplus_players[0]["name"]
                else:
                    _my_give_val, _my_give_name = 0, "—"

                if _my_give_val > 0 and _their_give_val > 0:
                    _val_gap   = abs(_my_give_val - _their_give_val)
                    _proximity = max(0.0, 1.0 - _val_gap / max(_my_give_val, _their_give_val)) * 100
                else:
                    _proximity = 50.0  # neutral when no data

                _fit = _their_supply * 0.4 + _their_need * 0.4 + _proximity * 0.2

                _supply_lbl = ("🟢 Strong" if _their_supply >= 50 else
                               "🟡 Moderate" if _their_supply >= 20 else "🔴 Weak")
                _need_lbl   = ("🔴 High"   if _their_need   >= 50 else
                               "🟡 Medium" if _their_need   >= 20 else "🟢 Low")
                _vdiff_str  = f"{_their_give_val - _my_give_val:+,}" if _my_give_val and _their_give_val else "—"

                _partner_rows.append({
                    "Team":                   _o_td["name"],
                    "Fit Score":              round(_fit),
                    f"Their {_my_need} Supply": _supply_lbl,
                    f"Their Need for {_my_surplus}": _need_lbl,
                    "Sample: You Give":       f"{_my_give_name}  ({_my_surplus} · {_my_give_val:,})" if _my_give_val else _my_give_name,
                    "Sample: You Get":        f"{_their_give_name}  ({_my_need} · {_their_give_val:,})" if _their_give_val else _their_give_name,
                    "Value Diff":             _vdiff_str,
                })

            _partner_rows.sort(key=lambda x: x["Fit Score"], reverse=True)
            # Add rank
            for _i, _row in enumerate(_partner_rows):
                _row["#"] = _i + 1

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

        st.divider()

        # ── Section A: Auto Trade Suggestions ────────────────────────────────────
        st.subheader("A · Auto Suggestions")

        surplus_pos = td["surplus_pos"]
        need_pos    = td["need_pos"]

        def _pos_status(target_rid, pos):
            """Surplus / Deficit / Average for a team at a given position (handles PICK via relative%)."""
            owner_td = team_data.get(target_rid, {})
            if pos == "PICK":
                rel = owner_td.get("relative", {}).get("PICK")
                if rel is None: return "—"
                if rel >= 10:   return "🟢 Surplus"
                if rel <= -10:  return "🔴 Deficit"
                return "🟡 Average"
            ns = owner_td.get("need_scores",    {}).get(pos)
            ss = owner_td.get("surplus_scores", {}).get(pos)
            if ns is None or ss is None: return "—"
            if ss > ns and ss >= 20:  return "🟢 Surplus"
            if ns > ss and ns >= 20:  return "🔴 Deficit"
            return "🟡 Average"

        # Two toggles: shop the explicit Trade Block, and whether to include Untouchables
        _sa_c1, _sa_c2 = st.columns(2)
        _shop_block = _sa_c1.checkbox(
            "🔄 Shop my Trade Block", value=bool(_trade_block),
            help="Drive suggestions from players you tagged 🔄 Trade, instead of auto-detected surplus.",
            key="ta_shop_block",
        )
        _incl_untouch = _sa_c2.checkbox(
            "Include Untouchables", value=False,
            help="Also include players tagged 🔒 Untouchable in the suggestions.",
            key="ta_incl_untouch",
        )
        _need_for_targets = need_pos if need_pos in SKILL_POSITIONS else None

        if (not _shop_block or not _trade_block) and (not surplus_pos or not need_pos or surplus_pos == need_pos):
            st.info("No clear trade opportunities identified — positional values are well-balanced. Tag players 🔄 Trade to shop them directly.")
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
                st.info("Not enough data to generate suggestions — tag players 🔄 Trade, or check you have a clear positional need.")
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
                    st.markdown("**🏆 Top 5 Ideal Player-for-Player Targets**")
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

        st.divider()

        # ── Section B: Defensive Strength (IDP/DEF) ───────────────────────────────
        st.subheader("B · Defensive Strength (IDP / DEF)")
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
        with st.expander("Full league DEF ranking", expanded=False):
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
                         column_config={"Avg Pts": COL_CFG["Avg Pts"]})

        # Individual DEF players for selected team
        def_players = team_def_entry.get("players", [])
        if def_players:
            with st.expander(f"{sel_ta_team} — individual DEF/IDP players", expanded=False):
                st.dataframe(
                    pd.DataFrame([{
                        "Player": p["name"], "Pos": p["pos"],
                        f"{STATS_SEASON} Pts": round(p["pts"], 1),
                    } for p in def_players]),
                    width="stretch", hide_index=True,
                    column_config={f"{STATS_SEASON} Pts": COL_CFG[f"{STATS_SEASON} Pts"]},
                )

        st.divider()

        # ── Section C: Manual Trade Analyzer ─────────────────────────────────────
        st.subheader("C · Manual Trade Analyzer")
        st.caption("Pick any player or pick from this team's roster, choose your target position, and see closest-value options across the league.")

        # Build asset options: all players with FC values + all valued picks
        # (Untouchable players stay selectable here — this is manual exploration —
        #  but get a 🔒 marker so the intent is visible.)
        asset_options = []
        for pos in SKILL_POSITIONS:
            for player in td["pos_players"][pos]:
                _lock = "🔒 " if player["name"] in _untouchable else ""
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
                        if ss > ns and ss >= 20:  return "🟢 Surplus"
                        if ns > ss and ns >= 20:  return "🔴 Deficit"
                        return "🟡 Average"

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
        st.subheader("D · Trade Calculator")
        st.caption(
            f"Weighed on **{value_source}** values — FantasyCalc already reflects your league's "
            "Superflex / PPR / team-count scoring. Pick the two teams, add players & picks, "
            "and the fairness read updates live."
        )

        # Per-team asset universe (normalised to 0–10K), so each side filters to its team
        _team_assets = {}
        for _r2, _t2 in team_data.items():
            _d = {}
            for _p2 in SKILL_POSITIONS:
                for _pl in _t2["pos_players"].get(_p2, []):
                    _v = _pl["value"] or 0
                    if _v:
                        _d[f"{_pl['name']}  ({_p2}) — {_v:,}"] = _v
            for _pk in _t2.get("picks", []):
                _v = round((_pk["value"] or 0) / 10282 * 10000)
                if _v:
                    _d[f"{_pk['label']}  (Pick) — {_v:,}"] = _v
            _team_assets[_t2["name"]] = _d

        _all_teams = sorted(_team_assets.keys())
        _a_default = my_team if my_team in _all_teams else _all_teams[0]
        _b_default = next((t for t in _all_teams if t != _a_default), _all_teams[0])

        _cc1, _cc2 = st.columns(2)
        with _cc1:
            st.markdown("<span style='color:#2196F3; font-weight:600;'>◀ Side A sends</span>", unsafe_allow_html=True)
            _team_a = st.selectbox("Team A", _all_teams, index=_all_teams.index(_a_default),
                                   key="calc_team_a", label_visibility="collapsed")
            # Key includes the team so switching teams never carries stale options
            _side_a = st.multiselect("Players & picks", sorted(_team_assets[_team_a].keys()),
                                     key=f"calc_side_a_{_team_a}", placeholder=f"Add from {_team_a}…",
                                     label_visibility="collapsed")
        with _cc2:
            st.markdown("<span style='color:#ff5a5f; font-weight:600;'>Side B sends ▶</span>", unsafe_allow_html=True)
            _team_b = st.selectbox("Team B", _all_teams, index=_all_teams.index(_b_default),
                                   key="calc_team_b", label_visibility="collapsed")
            _side_b = st.multiselect("Players & picks", sorted(_team_assets[_team_b].keys()),
                                     key=f"calc_side_b_{_team_b}", placeholder=f"Add from {_team_b}…",
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
                _badge_bg, _badge_tx = "#0c2e1a", "#7ee2a8"
                _verdict = f"⚖️ Even trade — within {_gap_pct:.0f}% ({abs(_gap):,} apart)"
            else:
                _badge_bg, _badge_tx = "#3a2e0c", "#f5d27a"
                _winner = _team_b if _gap > 0 else _team_a
                _verdict = f"↘ Favours {_winner} by {abs(_gap):,} ({_gap_pct:.0f}%)"
            st.markdown(
                f"""<div style="border:1px solid #2d3140; border-radius:12px; padding:16px 18px; margin-top:4px;">
                  <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                    <div><div style="font-size:0.72rem; color:#7ab4f0; text-transform:uppercase; letter-spacing:.06em;">{_team_a}</div>
                         <div style="font-size:1.5rem; font-weight:700; color:#fff;">{_tot_a:,}</div></div>
                    <div style="text-align:center; align-self:center;">
                         <span style="background:{_badge_bg}; color:{_badge_tx}; padding:5px 12px; border-radius:14px; font-size:0.82rem; font-weight:600;">{_verdict}</span></div>
                    <div style="text-align:right;"><div style="font-size:0.72rem; color:#f0a0a3; text-transform:uppercase; letter-spacing:.06em;">{_team_b}</div>
                         <div style="font-size:1.5rem; font-weight:700; color:#fff;">{_tot_b:,}</div></div>
                  </div>
                  <div style="display:flex; height:20px; border-radius:6px; overflow:hidden; font-size:0.74rem; font-weight:600;">
                    <div style="width:{_pa}%; background:#2196F3; color:#fff; display:flex; align-items:center; justify-content:center;">{_pa}%</div>
                    <div style="width:{100 - _pa}%; background:#ff5a5f; color:#fff; display:flex; align-items:center; justify-content:center;">{100 - _pa}%</div>
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )

    # ── Page: Draft Room ─────────────────────────────────────────────────────────
    _frag_trade_analyzer()
elif page == "🏟️ Draft Room":
    curr_year = str(datetime.now().year)

    # ── Session state + persistence (per league) ──────────────────────────────
    if st.session_state.get("_draft_confirmed_league") != league_id:
        st.session_state.draft_confirmed = load_draft_selections(league_id)
        st.session_state._draft_confirmed_league = league_id

    confirmed    = st.session_state.draft_confirmed   # {pick_label: rookie_name}
    rookie_names = sorted([r["name"] for r in fc_rookies if r.get("name")])

    # ── Simulation control: Need Reach Limit (shared with Settings) ───────────
    st.caption("**Need Reach Limit** — how far a team reaches for positional need over Best Player "
               "Available. 0% = pure BPA · 40% = heavily need-driven. Also adjustable in Settings.")
    need_reach_limit = st.slider(
        "Need Reach Limit", min_value=0, max_value=40, value=15, step=5,
        format="%d%%", key="reach_limit_pct",
    ) / 100
    _mode = "Strict (near-BPA)" if need_reach_limit < 0.10 else ("Balanced" if need_reach_limit <= 0.20 else "Need-heavy (aggressive reaches)")
    st.caption(f"Mode: **{_mode}** at {int(need_reach_limit * 100)}%")

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
                st.warning(f'Confirmed pick "{rk_name}" is no longer in the rookie rankings — value may be unavailable.', icon="⚠️")
            pos = match.get("position", "—") if match else "—"
            owner = next((p[3] for p in picks_sorted if p[2] == pick_label), None)
            if owner:
                _apply_pick(owner, pos)
            selections[pick_label] = {
                "name":   rk_name,
                "pos":    pos,
                "value":  match.get("value") if match else None,  # raw FC value for display
                "reason": "✅ Confirmed",
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
                    reason   = f"📊 Need ({need_pos})"
                else:
                    # BPA is too valuable to pass — take best available regardless of need
                    selected = best_overall
                    reason   = f"💰 Best Available (+{reach_pct:.0%} over need)"
            elif need_best:
                # Need player IS the best available — easy call
                selected = need_best
                reason   = f"📊 Need ({need_pos})"
            else:
                selected = best_overall
                reason   = "💰 Best Available"

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

    # ── Build editable draft board df (always sorted 1.01 → N.12) ────────────
    draft_rows = []
    for _, row in df_cur.iterrows():
        pick   = row["Pick"]
        sel    = rookie_sels.get(pick, {})
        is_confirmed = pick in confirmed
        draft_rows.append({
            "Pick":            pick,
            "Team":            f"⭐ {row['Team']}" if my_team and row["Team"] == my_team else row["Team"],
            "Pick FC Value":   row["Value"],
            "Est. Rookie":     sel.get("name", "—"),
            "Pos":             sel.get("pos",  "—"),
            "Rookie FC Val":   sel.get("value"),
            "Logic":           sel.get("reason", "—"),
            "Pick Made":       is_confirmed,
            "Rookie Selected": confirmed.get(pick, ""),
        })

    df_board = pd.DataFrame(draft_rows)

    # ── Draft board ───────────────────────────────────────────────────────────
    st.subheader(f"{curr_year} Draft Board")

    # Highlight My Team's picks (Styler applies to the non-editable columns)
    _board_data = df_board
    if my_team and (df_board["Team"] == f"⭐ {my_team}").any():
        _dr_hl = "background-color: rgba(255, 196, 0, 0.18)"
        _board_data = df_board.style.apply(
            lambda row: [_dr_hl if row["Team"] == f"⭐ {my_team}" else "" for _ in row], axis=1
        )

    edited = st.data_editor(
        _board_data,
        width="stretch",
        hide_index=True,
        key="draft_board_editor",
        column_config={
            "Pick Made":       st.column_config.CheckboxColumn("Pick Made",       default=False),
            "Rookie Selected": st.column_config.SelectboxColumn(
                "Rookie Selected",
                options=[""] + rookie_names,
                default="",
            ),
            "Pick FC Value":   COL_CFG["Pick FC Value"],
            "Rookie FC Val":   COL_CFG["Rookie FC Val"],
        },
        disabled=["Pick", "Team", "Pick FC Value", "Est. Rookie", "Pos", "Rookie FC Val", "Logic"],
    )

    btn_c1, btn_c2, _ = st.columns([1, 1, 4])
    if btn_c1.button("🔄 Update Estimates", key="dr_update", width="stretch"):
        new_confirmed = {}
        for _, row in edited.iterrows():
            if row.get("Pick Made") and row.get("Rookie Selected"):
                new_confirmed[row["Pick"]] = row["Rookie Selected"]
        st.session_state.draft_confirmed = new_confirmed
        save_draft_selections(league_id, new_confirmed)
        st.rerun()

    if btn_c2.button("🗑️ Clear All", key="dr_clear", width="stretch"):
        st.session_state.draft_confirmed = {}
        clear_draft_selections(league_id)
        st.rerun()

    st.caption(f"{len(confirmed)} confirmed · {len(df_board) - len(confirmed)} estimated · your draft is saved automatically")

    st.divider()

    # ── Available Rookie Pool (below the board) ───────────────────────────────
    st.subheader("Available Rookie Pool")
    st.caption("Rookies not yet confirmed as picked. Sorted by FC value.")

    # Only exclude rookies that are confirmed — estimated picks stay in the pool
    taken_names = set(confirmed.values())

    pool_rows = [
        {
            "Rank":     i + 1,
            "Rookie":   r["name"],
            "Pos":      r.get("position", "—"),
            "Value": r.get("value"),
            "Tier":     r.get("tier"),
        }
        for i, r in enumerate(
            sorted(
                [r for r in fc_rookies
                 if r.get("position") in SKILL_POSITIONS
                 and r.get("value")
                 and r.get("name") not in taken_names],
                key=lambda r: r.get("value", 0), reverse=True,
            )
        )
    ]

    pool_col1, pool_col2, pool_col3 = st.columns([2, 3, 1])
    pool_pos  = pool_col1.multiselect("Filter by position", SKILL_POSITIONS, key="dr_pool_pos")
    pool_srch = pool_col2.text_input("Search pool", key="dr_pool_srch", placeholder="e.g. Jeanty")
    pool_col3.markdown('<div style="padding-top: 1.75rem;"></div>', unsafe_allow_html=True)
    pool_fav  = pool_col3.checkbox("⭐ Only", key="dr_pool_fav")

    df_pool = pd.DataFrame(pool_rows)
    if not df_pool.empty:
        if pool_srch: df_pool = df_pool[df_pool["Rookie"].str.contains(pool_srch, case=False, na=False)]
        if pool_pos:  df_pool = df_pool[df_pool["Pos"].isin(pool_pos)]
        if pool_fav:  df_pool = df_pool[df_pool["Rookie"].isin(st.session_state.favorites)]

    if df_pool.empty:
        st.info("No rookies match the current filters.")
    else:
        fav_grid(df_pool, "Rookie", "dr_pool_fav_grid",
                 col_cfg={"Value": COL_CFG["Value"]})
    st.caption(f"{plural(len(df_pool), 'rookie')} still available · tick the ⭐ box to favourite")

# ── Page: Fantasy News ───────────────────────────────────────────────────────
elif page == "📰 Fantasy News":
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
