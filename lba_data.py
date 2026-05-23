"""
LBA (Lega Basket Serie A) data layer - legabasket.it public API.

Endpointy odkryte przez DevTools (23/05/2026):
  /api/championships/get-championships?current=1&items=1000
  /api/championships/get-championships-calendar-by-id?id={c_id}
  /api/statistics/get-players-statistics?c_id={c_id}&round=last
  /api/teams/get-teams?items=50

IDs kluczowych sezonów (year=2025 = sezon 2025/26):
  595 = Playoff Serie A 2025/26
  596 = Regular Season A 2025/26

Wszystkie endpointy: brak auth, brak CORS issues, czysty JSON.
Dumpy do lba/_debug/lb_*.json.
"""

import os
import json
import time
from datetime import datetime, timezone, timedelta

import requests

LBA_BASE = "https://www.legabasket.it/api"
LBA_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8",
    "Referer": "https://www.legabasket.it/",
    "Origin": "https://www.legabasket.it",
}

DEBUG_DIR = "lba/_debug"
CET = timezone(timedelta(hours=2))

_cache = {
    "championships": None,   # lista mistrzostwa w sezonie
    "calendar": {},          # c_id -> {competition, matches, ...}
    "stats": {},             # c_id -> lista graczy
    "teams": None,
    "table": {},             # c_id -> {team_id: {wins, losses, ...}}
}


# ============================================================
# HTTP helpers
# ============================================================

def _save_debug(name, data):
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        with open(os.path.join(DEBUG_DIR, f"lb_{name}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    except Exception:
        pass


def _fetch_json(url, label, timeout=15):
    try:
        r = requests.get(url, headers=LBA_HEADERS, timeout=timeout)
    except Exception as e:
        print(f"   [lba-EXC] {label}: {type(e).__name__}: {e}")
        return None
    if r.status_code != 200:
        print(f"   [lba-FAIL] {label} -> HTTP {r.status_code}: {r.text[:150]}")
        return None
    ct = r.headers.get("content-type", "")
    if "html" in ct or r.text.lstrip().startswith("<!"):
        print(f"   [lba-HTML] {label} -> zwrocil HTML zamiast JSON (redirect?)")
        return None
    try:
        return r.json()
    except Exception as e:
        print(f"   [lba-JSON] {label}: {e}")
        return None


# ============================================================
# Season detection
# ============================================================

def get_season_ids(year=None):
    """Zwraca {regular: c_id, playoff: c_id} dla danego sezonu (rok=2025 -> 2025/26).
    Jeśli year=None, bierze rok startowy sezonu (przed lipcem -> rok-1, od lipca -> rok bieżący).
    API legabasket.it przechowuje year=2025 dla sezonu 2025/26."""
    if year is None:
        now = datetime.now()
        # Sezon 2025/26 startuje jesienią 2025; rok startowy = bieżący rok jeśli >= lipiec,
        # w przeciwnym razie rok poprzedni (np. maj 2026 -> sezon 2025/26 -> year=2025)
        year = now.year if now.month >= 7 else now.year - 1

    if _cache["championships"] is None:
        url = f"{LBA_BASE}/championships/get-championships?current=1&items=1000"
        data = _fetch_json(url, "championships")
        if data:
            # API zwraca klucz "competitions" (nie "championships")
            arr = data if isinstance(data, list) else (
                data.get("competitions") or data.get("championships") or
                data.get("data") or []
            )
            _cache["championships"] = arr if isinstance(arr, list) else []
            _save_debug("championships", data)
            print(f"   [lba] /championships -> {len(_cache['championships'])} wpisow")
        else:
            _cache["championships"] = []

    championships = _cache["championships"]
    regular_id = playoff_id = None
    for c in championships:
        if c.get("year") != year:
            continue
        code = c.get("code", "").lower()
        ctype = (c.get("ctype_code") or "").lower()
        ctype_name = (c.get("ctype_name") or "").lower()
        if ctype == "rs" or "regular" in code or "regular" in ctype_name:
            regular_id = c.get("id")
        elif ctype in ("po", "pf") or "playoff" in code or "playoff" in ctype_name:
            playoff_id = c.get("id")

    print(f"   [lba] sezon {year}: regular={regular_id} playoff={playoff_id}")
    return {"regular": regular_id, "playoff": playoff_id, "year": year}


# ============================================================
# Core fetches
# ============================================================

def fetch_calendar(c_id):
    """Pełny kalendarz dla danego championship_id. Cached."""
    if not c_id:
        return {}
    if c_id in _cache["calendar"]:
        return _cache["calendar"][c_id]

    url = f"{LBA_BASE}/championships/get-championships-calendar-by-id?id={c_id}"
    data = _fetch_json(url, f"calendar-{c_id}")
    if data is None:
        _cache["calendar"][c_id] = {}
        return {}
    _save_debug(f"calendar_{c_id}", data)
    _cache["calendar"][c_id] = data
    matches = data.get("matches") or []
    print(f"   [lba] /calendar/{c_id} -> {len(matches)} mecz(y)")
    return data


def fetch_player_stats(c_id, round_type="last"):
    """Statystyki graczy. Cached."""
    if not c_id:
        return []
    key = (c_id, round_type)
    if key in _cache["stats"]:
        return _cache["stats"][key]

    url = f"{LBA_BASE}/statistics/get-players-statistics?c_id={c_id}&round={round_type}"
    data = _fetch_json(url, f"stats-{c_id}-{round_type}")
    if data is None:
        _cache["stats"][key] = []
        return []
    _save_debug(f"stats_{c_id}_{round_type}", data)
    # Odpowiedź: {"stats": [...], "filters": ..., "cache_key": ..., "cdn_url": ...}
    players = data.get("stats") or (data if isinstance(data, list) else [])
    if not isinstance(players, list):
        players = []
    _cache["stats"][key] = players
    print(f"   [lba] /stats/{c_id} -> {len(players)} graczy")
    return players


def build_table_from_matches(c_id):
    """Buduje bilans W-L dla każdej drużyny z wyników meczów Regular Season.
    Używane zamiast brakującego /api/standings."""
    if c_id in _cache["table"]:
        return _cache["table"][c_id]

    cal = fetch_calendar(c_id)
    matches = cal.get("matches") or []
    table = {}  # team_id -> {name, wins, losses, pts_for, pts_against}

    for m in matches:
        status = str(m.get("game_status") or "0")
        if status not in ("2", "3"):  # 2=played, 3=finished (guessing - sprawdź)
            # Fallback: mecz jest zakończony jeśli ma wynik != 0-0 i datę w przeszłości
            h_score = int(m.get("home_final_score") or 0)
            v_score = int(m.get("visitor_final_score") or 0)
            if h_score == 0 and v_score == 0:
                continue

        h_id = m.get("h_team_id")
        v_id = m.get("v_team_id")
        h_name = m.get("h_team_name") or "?"
        v_name = m.get("v_team_name") or "?"
        h_score = int(m.get("home_final_score") or 0)
        v_score = int(m.get("visitor_final_score") or 0)

        if h_id not in table:
            table[h_id] = {"name": h_name, "team_id": h_id, "wins": 0, "losses": 0,
                           "pts_for": 0, "pts_against": 0}
        if v_id not in table:
            table[v_id] = {"name": v_name, "team_id": v_id, "wins": 0, "losses": 0,
                           "pts_for": 0, "pts_against": 0}

        table[h_id]["pts_for"] += h_score
        table[h_id]["pts_against"] += v_score
        table[v_id]["pts_for"] += v_score
        table[v_id]["pts_against"] += h_score

        if h_score > v_score:
            table[h_id]["wins"] += 1
            table[v_id]["losses"] += 1
        elif v_score > h_score:
            table[v_id]["wins"] += 1
            table[h_id]["losses"] += 1

    _cache["table"][c_id] = table
    print(f"   [lba] table/{c_id} obliczona z meczow -> {len(table)} druzyn")
    return table


def get_win_pct(table, team_id):
    """Zwraca float 0.0-1.0 dla danej drużyny."""
    row = table.get(team_id) or {}
    w = row.get("wins", 0)
    l = row.get("losses", 0)
    return w / (w + l) if (w + l) > 0 else 0.0


def get_net_rating_simple(table, team_id):
    """Prosty net rating: (pts_for - pts_against) / gry."""
    row = table.get(team_id) or {}
    pf = row.get("pts_for", 0)
    pa = row.get("pts_against", 0)
    g = row.get("wins", 0) + row.get("losses", 0)
    return round((pf - pa) / g, 1) if g > 0 else 0.0


# ============================================================
# Helpers - mecze
# ============================================================

def parse_match_dt(match):
    """LBA 'match_datetime': '2026-05-23T20:00:00.000+02:00'. Zwraca aware datetime."""
    s = match.get("match_datetime") or ""
    if not s:
        return None
    try:
        # Python 3.10 fromisoformat nie obsługuje .000+02:00 na wszystkich wersjach
        s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        try:
            # strip miliseconds
            s2 = s[:19] + s[19+4:]  # usuń .000
            return datetime.fromisoformat(s2)
        except Exception:
            return None


def match_status(match):
    """Zwraca 'pre' | 'in' | 'post'."""
    status = str(match.get("game_status") or "0")
    if status in ("2", "3"):
        return "post"
    h_score = int(match.get("home_final_score") or 0)
    v_score = int(match.get("visitor_final_score") or 0)
    if h_score > 0 or v_score > 0:
        # są wyniki ale status może być numerycznym live
        dt = parse_match_dt(match)
        if dt and dt <= datetime.now(CET):
            # mogło się skończyć
            return "post" if status == "2" else "in"
    dt = parse_match_dt(match)
    if dt is None:
        return "pre"
    now = datetime.now(CET)
    if dt > now:
        return "pre"
    return "in"


def filter_matches_for_date(matches, date_str):
    """Filtruje listę meczów po dacie PL."""
    out = []
    for m in (matches or []):
        dt = parse_match_dt(m)
        if dt and dt.strftime("%Y-%m-%d") == date_str:
            out.append(m)
    out.sort(key=lambda m: parse_match_dt(m) or datetime.now(CET))
    return out


def fmt_match_time(match):
    """'20:00 CET' albo ''."""
    dt = parse_match_dt(match)
    return dt.strftime("%H:%M") + " CET" if dt else ""


def logo_url(logo_key, cdn_url=None):
    """logo_key -> pełny URL logo drużyny."""
    if not logo_key:
        return ""
    base = cdn_url or "https://lba-media.s3.eu-south-1.amazonaws.com/variants"
    return f"{base}/{logo_key}/thumb"


# ============================================================
# Helpers - gracze
# ============================================================

def get_top_scorers_by_team(players, team_id, n=3):
    """Top N strzelców danej drużyny z listy statystyk."""
    team = [p for p in (players or []) if p.get("team_id") == team_id]
    team.sort(key=lambda p: float(p.get("score") or 0), reverse=True)
    out = []
    for p in team[:n]:
        out.append({
            "name": f"{p.get('name', '')} {p.get('surname', '')}".strip(),
            "player_id": p.get("player_id"),
            "ppg": round(float(p.get("score") or 0), 1),
            "mpg": round(float(p.get("minutes") or 0), 1),
            "presences": p.get("presences"),
        })
    return out


def get_h2h_in_season(matches, h_id, v_id):
    """Mecze head-to-head w sezonie (zakończone), chronologicznie."""
    h2h = []
    for m in (matches or []):
        mh = m.get("h_team_id")
        mv = m.get("v_team_id")
        if {mh, mv} != {h_id, v_id}:
            continue
        if match_status(m) != "post":
            continue
        h2h.append(m)
    h2h.sort(key=lambda m: m.get("match_datetime") or "")
    return h2h


def format_h2h(h2h, h_id, h_name, v_id, v_name):
    """Zwraca tekstowe podsumowanie H2H."""
    if not h2h:
        return "brak rozegranych spotkan w tym sezonie"
    h_wins = v_wins = 0
    lines = []
    for m in h2h:
        hs = int(m.get("home_final_score") or 0)
        vs = int(m.get("visitor_final_score") or 0)
        mh = m.get("h_team_id")
        winner = m.get("h_team_name") if hs > vs else m.get("v_team_name")
        if mh == h_id and hs > vs:
            h_wins += 1
        elif mh != h_id and vs > hs:
            h_wins += 1
        elif mh == v_id and hs > vs:
            v_wins += 1
        elif mh != v_id and vs > hs:
            v_wins += 1
        date = (m.get("match_datetime") or "")[:10]
        day = m.get("day_name") or ""
        lines.append(
            f"  - {date} ({day}): {m.get('v_team_name')} {vs}-{hs} {m.get('h_team_name')} -> {winner}"
        )
    return f"{h_name} {h_wins}-{v_wins} {v_name}\n" + "\n".join(lines)


def get_series_state(matches, h_id, v_id, h_name, v_name):
    """Stan aktualnej serii playoff między parą drużyn."""
    h2h = get_h2h_in_season(matches, h_id, v_id)
    if not h2h:
        return None
    h_wins = v_wins = 0
    for m in h2h:
        hs = int(m.get("home_final_score") or 0)
        vs = int(m.get("visitor_final_score") or 0)
        mh = m.get("h_team_id")
        if (mh == h_id and hs > vs) or (mh == v_id and vs > hs):
            h_wins += 1
        else:
            v_wins += 1
    return {"h_name": h_name, "v_name": v_name, "h_wins": h_wins, "v_wins": v_wins,
            "total": h_wins + v_wins}
