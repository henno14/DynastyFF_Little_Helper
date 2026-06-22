"""
insight_text.py — Dynasty Little Helper's natural-language insight engine.

Pattern (see redesign/CODE-PROMPT-theme-and-insights.md §2): the app computes
all the numbers, this module only turns them into prose, safely.

    facts (computed by the app) ─► generate_team_insights() ─► {bottom_line, ...}
                                          │
                                          ├─ Claude (claude-haiku-4-5)  ← phrasing only
                                          ├─ JSON parse + number guard  ← rejects hallucinated stats
                                          └─ deterministic templates    ← always works, no key needed

The model NEVER computes numbers; it only writes the sentence. Everything here
falls back to f-string templates so the app runs fine with no API key.

Key:   read from st.secrets["ANTHROPIC_API_KEY"] (works on Streamlit Cloud);
       falls back to the ANTHROPIC_API_KEY env var for local dev. Absent → templates.
Model: claude-haiku-4-5 (~$0.002/call; cached one-per-team-per-source-per-week).

Adapted from redesign/insights.py — reconciled to read facts the app already
computes rather than re-fetching from Sleeper/FantasyCalc.
"""

from __future__ import annotations

import json
import os
import re

import streamlit as st

MODEL = "claude-haiku-4-5"

TEAM_SYSTEM = """You are "Dynasty Little Helper," a sharp, friendly fantasy-football dynasty analyst.
You write SHORT, punchy, plain-English takes for a superflex dynasty manager.

RULES
- Use ONLY the numbers in the JSON. Never invent stats, player names, ranks, or values
  that aren't provided. If a field is missing, don't reference it.
- Voice: confident, a little witty, never cheesy. Talk like a smart league-mate.
- Be specific and directive — tell them what to DO, not just what is.
- Hard length limits below. No emoji. Max one exclamation. Sentence case.
- Don't restate the JSON; interpret it.

OUTPUT strict JSON, no prose around it:
{
  "bottom_line":    "1-2 sentences: the key takeaway + the one move to make.",
  "this_season":    "1 sentence on win-now outlook.",
  "dynasty_outlook":"1 sentence on long-term trajectory.",
  "helper_suggests":"1-2 sentences proposing a concrete roster move."
}"""

TRADE_SYSTEM = """You are "Dynasty Little Helper," a fantasy dynasty trade analyst.
Use ONLY the numbers provided. No invented players/values. Sentence case, no emoji.

OUTPUT strict JSON:
{
  "verdict_label": "you win | fair | you lose",
  "verdict_pill":  "green | gold | red",
  "headline":      "<=6 words",
  "rationale":     "2 sentences citing the value edge and roster fit.",
  "risk_check":    "1 sentence naming the main risk, or empty string."
}"""


# --------------------------------------------------------------------------- #
# Rule-based labels (thresholds) — predictable, computed here so prose and the
# UI pills stay consistent. Mirrors team_context.py / CODE-PROMPT §2.1.
# --------------------------------------------------------------------------- #
def pos_tag(rank: int, n: int) -> str:
    q = rank / n
    if q <= 0.25:
        return "elite"
    if q <= 0.5:
        return "solid"
    if q <= 0.75:
        return "thin"
    return "weak"


def season_status(rank: int, n: int) -> str:
    if rank <= max(2, n // 3):
        return "contender"
    if rank <= max(4, 2 * n // 3):
        return "in the mix"
    return "long shot"


def dynasty_status(rank: int, n: int) -> str:
    if rank <= max(2, n // 3):
        return "ascending"
    if rank <= max(4, 2 * n // 3):
        return "stable"
    return "aging"


def quadrant(season: str, dyn: str) -> str:
    win_now = season in ("contender", "in the mix")
    bright = dyn in ("ascending", "stable")
    if win_now and bright:
        return "contend"
    if not win_now and bright:
        return "reload"
    if win_now and not bright:
        return "win-now fading"
    return "rebuild"


def build_team_facts(*, team: str, teams_in_league: int, power_rank: int,
                     positions: dict[str, int], season_rank: int, dynasty_rank: int,
                     roster_value: int | None = None, avg_age: float | None = None,
                     value_source: str | None = None,
                     value_change_pct_7d: float | None = None,
                     priority_need: str | None = None) -> dict:
    """Assemble the fact object from values the app already computes, and derive
    the rule-based labels. `positions` maps QB/RB/WR/TE (+ picks/DEF) -> league rank.
    `priority_need`, when given, is the app's computed need position (need_scores) —
    used as the 'biggest hole' so the Bottom Line never disagrees with the Priority
    Need tile. No numbers are computed beyond min/derivation + labels."""
    n = teams_in_league
    skill = [p for p in ("QB", "RB", "WR", "TE") if p in positions]
    ranked = sorted(skill, key=lambda p: positions[p])
    strongest, weakest = ranked[0], ranked[-1]
    # Align the "biggest hole" with the app's priority-need computation when supplied
    if priority_need and priority_need in positions:
        weakest = priority_need
    s_status = season_status(season_rank, n)
    d_status = dynasty_status(dynasty_rank, n)

    facts: dict = {
        "team": team,
        "teams_in_league": n,
        "power_rank": power_rank,
        "positions": positions,
        "position_tags": {p: pos_tag(positions[p], n) for p in skill},
        "strongest": {"pos": strongest, "rank": positions[strongest]},
        "weakest": {"pos": weakest, "rank": positions[weakest]},
        "season_status": s_status, "season_rank": season_rank,
        "dynasty_status": d_status, "dynasty_rank": dynasty_rank,
        "quadrant": quadrant(s_status, d_status),
    }
    if roster_value is not None:
        facts["roster_value"] = round(roster_value)
    if avg_age is not None:
        facts["avg_age"] = round(avg_age, 1)
    if value_source:
        facts["value_source"] = value_source
    if value_change_pct_7d is not None:
        facts["value_change_pct_7d"] = value_change_pct_7d
    return facts


# --------------------------------------------------------------------------- #
# Number guard — reject any large integer the model didn't get from the facts
# --------------------------------------------------------------------------- #
def _allowed_big_numbers(facts: dict) -> set[int]:
    allowed: set[int] = set()

    def walk(v):
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            allowed.add(int(round(v)))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(facts)
    return {a for a in allowed if a >= 100}


def _passes_number_guard(text: str, facts: dict) -> bool:
    allowed = _allowed_big_numbers(facts)
    for tok in re.findall(r"\d[\d,]{2,}", text):           # 3+ digit numbers only
        n = int(tok.replace(",", ""))
        if n >= 100 and not any(abs(n - a) <= 2 for a in allowed):
            return False
    return True


# --------------------------------------------------------------------------- #
# Deterministic template fallback (always correct, no API needed)
# --------------------------------------------------------------------------- #
def team_templates(f: dict) -> dict:
    n = f["teams_in_league"]
    w, s = f["weakest"], f["strongest"]
    age = f.get("avg_age")
    return {
        "bottom_line": (
            f"You're a {f['season_status']} this season ({f['season_rank']}/{n}), "
            f"but {f['dynasty_status']} long-term ({f['dynasty_rank']}/{n}). "
            f"Biggest hole: {w['pos']} — address it now."
        ),
        "this_season": (
            f"Win-now strength ranks {f['season_rank']} of {n} — "
            f"{'in contention' if f['season_rank'] <= n // 3 else 'an uphill road'} this year."
        ),
        "dynasty_outlook": (
            f"Roster trajectory is {f['dynasty_status']} ({f['dynasty_rank']}/{n})"
            + (f", avg age {age}." if age is not None else ".")
        ),
        "helper_suggests": (
            f"Trade from your {s['pos']} strength (#{s['rank']}) to fix {w['pos']} "
            f"(#{w['rank']}) — you have the surplus to upgrade without gutting the core."
        ),
    }


def trade_templates(t: dict) -> dict:
    pill = {"you win": "green", "fair": "gold", "you lose": "red"}[t["verdict_label"]]
    return {
        "verdict_label": t["verdict_label"],
        "verdict_pill": pill,
        "headline": {"you win": "You win this one.", "fair": "A fair deal.",
                     "you lose": "You're paying up."}[t["verdict_label"]],
        "rationale": (
            f"You give {t['give_value']} to get {t['get_value']} "
            f"({'+' if t['delta'] >= 0 else ''}{t['delta']} value)"
            + (", and it fixes your biggest hole." if t.get("fixes_biggest_hole")
               else ", trading from a position of strength." if t.get("trades_from_strength")
               else ".")
        ),
        "risk_check": (t["risk_notes"][0] if t.get("risk_notes") else ""),
    }


# --------------------------------------------------------------------------- #
# Claude call — phrasing only. Key from st.secrets (Cloud) or env (local dev).
# --------------------------------------------------------------------------- #
def _api_key() -> str:
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY", "")  # raises if no secrets file
    except Exception:
        key = ""
    return (key or os.environ.get("ANTHROPIC_API_KEY", "") or "").strip()


def ai_available() -> bool:
    """True when a key is present AND smart insights aren't toggled off in Settings."""
    if st.session_state.get("smart_insights_off"):
        return False
    return bool(_api_key())


def _call_claude(system: str, facts: dict) -> dict | None:
    key = _api_key()
    if not key or st.session_state.get("smart_insights_off"):
        return None
    try:
        import anthropic  # imported lazily so templates work without the dep
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model=MODEL, max_tokens=500, system=system,
            messages=[{"role": "user", "content": json.dumps(facts)}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        data = json.loads(text)
        if not _passes_number_guard(json.dumps(data), facts):
            return None                                   # hallucinated stat → fall back
        return data
    except Exception:
        return None                                       # no key, timeout, bad JSON → fall back


# --------------------------------------------------------------------------- #
# Public API — cached so we pay at most one call per (league, team, source, week)
# `_facts`/`_trade` are excluded from the cache key (leading underscore); the
# explicit cache_key tuple drives caching.
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def generate_team_insights(_facts: dict, cache_key: tuple) -> dict:
    """Claude phrasing when available + valid, else deterministic templates.
    Returns {bottom_line, this_season, dynasty_outlook, helper_suggests}."""
    out = _call_claude(TEAM_SYSTEM, _facts)
    return out if out else team_templates(_facts)


def build_trade_context(my_facts: dict, give: list[dict], get: list[dict],
                        fairness_band: float = 0.05) -> dict:
    """give/get are [{name, pos, value, age?}] rows already valued by the app."""
    gv = sum(p["value"] for p in give)
    rv = sum(p["value"] for p in get)
    delta = rv - gv
    pct = (delta / gv * 100) if gv else 0.0
    if abs(pct) <= fairness_band * 100:
        label = "fair"
    elif delta > 0:
        label = "you win"
    else:
        label = "you lose"
    hole = my_facts["weakest"]["pos"]
    strength = my_facts["strongest"]["pos"]
    risks: list[str] = []
    if any(p.get("age", 0) and p["age"] >= 28 for p in get):
        risks.append("You're taking on an aging asset — watch the cliff.")
    if len([p for p in get if p["pos"] == hole]) and len(give) >= 2:
        risks.append(f"Going thin elsewhere to fix {hole}; keep depth in mind.")
    return {
        "give": give, "get": get,
        "give_value": gv, "get_value": rv, "delta": delta, "pct_delta": round(pct, 1),
        "verdict_label": label,
        "fixes_biggest_hole": any(p["pos"] == hole for p in get),
        "trades_from_strength": any(p["pos"] == strength for p in give),
        "risk_notes": risks,
    }


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def generate_trade_verdict(_trade: dict, cache_key: tuple) -> dict:
    """Claude verdict when available + valid, else deterministic templates."""
    out = _call_claude(TRADE_SYSTEM, _trade)
    return out if out else trade_templates(_trade)
