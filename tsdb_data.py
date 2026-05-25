"""
TheSportsDB data layer - wspolna biblioteka dla ACB i BBL.
Klucz publiczny '123', brak auth, nie blokuje GitHub Actions.

Endpointy uzywane:
  /eventsnextleague.php?id={league_id}    -> nastepne 15 meczow
  /eventspastleague.php?id={league_id}    -> ostatnie 15 meczow
  /eventsseason.php?id={league_id}&s={s}  -> pelny sezon (do formy/H2H)
  /lookuptable.php?l={league_id}&s={s}    -> tabela (fallback win%)

Funkcje publiczne:
  fetch_season_events(league_id, season)  -> lista wszystkich meczow sezonu
  fetch_games_today(league_id, today)     -> mecze na dzis (next+past)
  fetch_table(league_id, season)          -> {team_name: {wins,losses,...}}
  build_table_from_events(events)         -> buduje tabele z eventow (dokladniejsze)
  get_streak(table, team, n)              -> 'WWLWWL...'
  get_recent_games(table, team, n)        -> lista ostatnich n meczow
  get_home_away_record(table, team)       -> {wins_home, losses_home, ...}
  get_h2h(table, h_name, a_name)         -> lista meczow H2H
  format_recent_games(results)            -> tekst dla promptu
  format_h2h(h2h, h_name, a_name)        -> tekst dla promptu
  get_ppg_papg(table, team)              -> (ppg, papg, net_rtg)
  game_status(ev)                         -> 'pre'|'in'|'post'
  fmt_time_cet(ev)                        -> '20:30 CET'
  score(ev, side)                         -> int
  team_logo(ev, side)                     -> url
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta

TSDB_API_KEY = "123"
TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{TSDB_API_KEY}"
CET = timezone(timedelta(hours=2))

TSDB_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/123.0.0.0 Safari/537.36"),
    "Accept": "application/json",
}

_cache = {}  # url -> data


# ============================================================
# HTTP
# ============================================================

def _fetch(url, debug_name=None, debug_dir=None):
    if url in _cache:
        return _cache[url]
    try:
        r = requests.get(url, headers=TSDB_HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"   [tsdb] HTTP {r.status_code}: {url}")
            _cache[url] = None
            return None
        data = r.json()
        _cache[url] = data
        if debug_name and debug_dir:
            try:
                os.makedirs(debug_dir, exist_ok=True)
                with open(os.path.join(debug_dir, f"tsdb_{debug_name}.json"),
                          "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
        return data
    except Exception as e:
        print(f"   [tsdb-EXC] {type(e).__name__}: {e}")
        _cache[url] = None
        return None


# ============================================================
# Pobieranie meczow
# ============================================================

def fetch_season_events(league_id, season="2025-2026", debug_dir=None):
    """Pobiera pelny kalendarz sezonu. Kluczowe dla formy i H2H.
    season format: '2025-2026'"""
    url = f"{TSDB_BASE}/eventsseason.php?id={league_id}&s={season}"
    data = _fetch(url, f"season_{league_id}", debug_dir)
    if not data:
        return []
    events = data.get("events") or []
    print(f"   [tsdb] /eventsseason {league_id} s={season} -> {len(events)} meczow")
    return events


def fetch_games_today(league_id, today_slug, debug_dir=None):
    """Pobiera mecze na dzis lacząc next+past 15."""
    games = []
    seen = set()
    for endpoint in ("eventsnextleague", "eventspastleague"):
        url = f"{TSDB_BASE}/{endpoint}.php?id={league_id}"
        data = _fetch(url, f"{endpoint}_{league_id}", debug_dir)
        if not data:
            continue
        for ev in data.get("events") or []:
            eid = ev.get("idEvent")
            if eid in seen:
                continue
            seen.add(eid)
            if ev.get("dateEvent") == today_slug:
                games.append(ev)
    print(f"   [tsdb] mecze na {today_slug} (league {league_id}): {len(games)}")
    return games


def fetch_table(league_id, season="2025-2026", debug_dir=None):
    """Pobiera oficjalną tabelę z TSDB (fallback gdy brak eventów sezonu).
    Zwraca {team_name: {wins, losses, played, win_pct}}"""
    url = f"{TSDB_BASE}/lookuptable.php?l={league_id}&s={season}"
    data = _fetch(url, f"table_{league_id}", debug_dir)
    if not data:
        return {}
    table = {}
    for row in data.get("table") or []:
        name = row.get("strTeam") or ""
        played = int(row.get("intPlayed") or 0)
        wins = int(row.get("intWin") or 0)
        losses = int(row.get("intLoss") or 0)
        if name:
            table[name] = {
                "wins": wins,
                "losses": losses,
                "played": played,
                "win_pct": wins / played if played > 0 else 0.0,
                "pts_for": 0, "pts_against": 0,
                "wins_home": 0, "losses_home": 0,
                "wins_away": 0, "losses_away": 0,
                "results": [],
            }
    print(f"   [tsdb] /lookuptable {league_id} -> {len(table)} druzyn")
    return table


# ============================================================
# Budowanie tabeli z eventow (dokladniejsze niz lookuptable)
# ============================================================

def build_table_from_events(events):
    """Buduje pelna tabele z listy eventow sezonu.
    Kluczowe: liczy dom/wyjazd, wyniki, ppg/papg, results[] do formy.
    Zwraca {team_name: {...}}"""
    table = {}

    # Sortuj chronologicznie
    def _key(ev):
        return (ev.get("dateEvent") or "") + (ev.get("strTime") or "")

    finished = []
    for ev in sorted(events, key=_key):
        # Tylko zakonczone mecze (maja wyniki)
        hs = ev.get("intHomeScore")
        as_ = ev.get("intAwayScore")
        if hs is None or as_ is None:
            continue
        try:
            hs = int(hs)
            as_ = int(as_)
        except (TypeError, ValueError):
            continue
        if hs == 0 and as_ == 0:
            # Moze byc mecz bez wyniku lub naprawde 0-0 (rzadkie w koszykowce)
            status = (ev.get("strStatus") or "").lower()
            if status not in ("match finished", "ft", "aet", "finished"):
                continue

        h_name = ev.get("strHomeTeam") or "?"
        a_name = ev.get("strAwayTeam") or "?"
        date = ev.get("dateEvent") or ""
        round_no = ev.get("intRound") or ""

        for tname, opp_name, my_score, opp_score, is_home in [
            (h_name, a_name, hs, as_, True),
            (a_name, h_name, as_, hs, False),
        ]:
            if tname not in table:
                table[tname] = {
                    "wins": 0, "losses": 0,
                    "wins_home": 0, "losses_home": 0,
                    "wins_away": 0, "losses_away": 0,
                    "pts_for": 0, "pts_against": 0,
                    "results": [],  # [{date, opponent, score, win, home, round}]
                }
            won = my_score > opp_score
            t = table[tname]
            t["pts_for"] += my_score
            t["pts_against"] += opp_score
            if won:
                t["wins"] += 1
                if is_home:
                    t["wins_home"] += 1
                else:
                    t["wins_away"] += 1
            else:
                t["losses"] += 1
                if is_home:
                    t["losses_home"] += 1
                else:
                    t["losses_away"] += 1
            t["results"].append({
                "date": date,
                "round": str(round_no),
                "opponent": opp_name,
                "score": f"{my_score}-{opp_score}",
                "win": won,
                "home": is_home,
            })

    # Uzupelnij win_pct
    for t in table.values():
        g = t["wins"] + t["losses"]
        t["played"] = g
        t["win_pct"] = t["wins"] / g if g > 0 else 0.0

    print(f"   [tsdb] build_table_from_events -> {len(table)} druzyn")
    return table


# ============================================================
# Funkcje analityczne (identyczne jak lba_data)
# ============================================================

def get_team_row(table, team_name):
    """Zwraca row dla druzyny. Probuje dokladne dopasowanie, potem fuzzy."""
    if not team_name or not table:
        return {}
    if team_name in table:
        return table[team_name]
    tl = team_name.lower()
    for k, v in table.items():
        if k.lower() == tl or k.lower() in tl or tl in k.lower():
            return v
    return {}


def get_win_pct(table, team_name):
    row = get_team_row(table, team_name)
    return row.get("win_pct", 0.0)


def get_ppg_papg(table, team_name):
    """Zwraca (ppg, papg, net_rtg)."""
    row = get_team_row(table, team_name)
    g = row.get("played", 0)
    if g == 0:
        return 0.0, 0.0, 0.0
    ppg = round(row.get("pts_for", 0) / g, 1)
    papg = round(row.get("pts_against", 0) / g, 1)
    return ppg, papg, round(ppg - papg, 1)


def get_home_away_record(table, team_name):
    row = get_team_row(table, team_name)
    return {
        "wins_home":   row.get("wins_home", 0),
        "losses_home": row.get("losses_home", 0),
        "wins_away":   row.get("wins_away", 0),
        "losses_away": row.get("losses_away", 0),
    }


def get_streak(table, team_name, n=15):
    """Streak ostatnich n meczow 'WWLWWL...' (najnowszy z prawej)."""
    row = get_team_row(table, team_name)
    results = row.get("results") or []
    recent = results[-n:] if len(results) >= n else results[:]
    return "".join("W" if r["win"] else "L" for r in recent) or "-"


def get_recent_games(table, team_name, n=5):
    """Ostatnie n zakończonych meczow, chronologicznie (najnowszy ostatni)."""
    row = get_team_row(table, team_name)
    results = row.get("results") or []
    return results[-n:] if len(results) >= n else results[:]


def get_h2h(events, h_name, a_name):
    """Mecze H2H z listy wszystkich eventow sezonu (zakonczone)."""
    h2h = []
    for ev in events:
        hs = ev.get("intHomeScore")
        as_ = ev.get("intAwayScore")
        if hs is None or as_ is None:
            continue
        teams = {ev.get("strHomeTeam"), ev.get("strAwayTeam")}
        if h_name in teams and a_name in teams:
            h2h.append(ev)
    h2h.sort(key=lambda e: e.get("dateEvent") or "")
    return h2h


# ============================================================
# Formatery dla promptu
# ============================================================

def format_recent_games(results):
    if not results:
        return "  - brak danych"
    lines = []
    for r in results:
        where = "dom" if r.get("home") else "wyj"
        wl = "W" if r.get("win") else "L"
        rnd = f" (r.{r['round']})" if r.get("round") else ""
        lines.append(f"  - {r['date']}{rnd} [{where}] vs {r['opponent']}: {r['score']} -> {wl}")
    return "\n".join(lines)


def format_h2h(h2h, h_name, a_name):
    if not h2h:
        return "brak rozegranych spotkan w tym sezonie"
    h_wins = a_wins = 0
    lines = []
    for ev in h2h:
        hs = int(ev.get("intHomeScore") or 0)
        as_ = int(ev.get("intAwayScore") or 0)
        home = ev.get("strHomeTeam") or "?"
        away = ev.get("strAwayTeam") or "?"
        winner = home if hs > as_ else away
        if winner == h_name:
            h_wins += 1
        else:
            a_wins += 1
        date = ev.get("dateEvent") or ""
        rnd = ev.get("intRound") or ""
        lines.append(f"  - {date} (r.{rnd}): {away} {as_}-{hs} {home} -> {winner}")
    return f"{h_name} {h_wins}-{a_wins} {a_name}\n" + "\n".join(lines)


# ============================================================
# Helpers - event
# ============================================================

def game_status(ev):
    """Zwraca 'pre'|'in'|'post'."""
    status = (ev.get("strStatus") or ev.get("strProgress") or "").lower()
    if status in ("match finished", "ft", "aet", "finished"):
        return "post"
    if status in ("", "not started", "ns"):
        # Sprawdz czy wyniki juz sa
        hs = ev.get("intHomeScore")
        as_ = ev.get("intAwayScore")
        if hs is not None and as_ is not None:
            try:
                if int(hs) > 0 or int(as_) > 0:
                    return "post"
            except (TypeError, ValueError):
                pass
        return "pre"
    return "in"


def fmt_time_cet(ev):
    """Godzina CET z pola strTimeLocal '16:30:00' -> '16:30 CET'."""
    t = ev.get("strTimeLocal") or ev.get("strTime") or ""
    if t and len(t) >= 5:
        return t[:5] + " CET"
    return ""


def score(ev, side):
    key = "intHomeScore" if side == "home" else "intAwayScore"
    val = ev.get(key)
    try:
        return int(val) if val is not None else 0
    except (TypeError, ValueError):
        return 0


def team_logo(ev, side, default=""):
    key = "strHomeTeamBadge" if side == "home" else "strAwayTeamBadge"
    return ev.get(key) or default
