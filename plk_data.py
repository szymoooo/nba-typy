"""
PLK data layer - PulsBasketu primary source.

Public API endpoints (no auth required, polish service):
  /api/v1/league-seasons/plk/games-list?season=2026
  /api/v1/league-seasons/plk/table?season=2026
  /api/v1/season-teams/{team_id}?season=2026&league_id=plk
  /api/v1/league-seasons/plk/stats/players/stat-lines/leaders?season=2026

Cache: w pamieci modulu, zerowane przy kazdym uruchomieniu skryptu.
Wszystkie odpowiedzi dumpowane do plk/_debug/pb_*.json.
"""

import os
import json
from datetime import datetime, timezone, timedelta

import requests


# ============================================================
# KONFIGURACJA
# ============================================================
PB_BASE = "https://api.pulsbasketu.com/api/v1"
PB_LEAGUE = "plk"
PB_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl,en-US;q=0.9,en;q=0.8",
    "Origin": "https://pulsbasketu.com",
    "Referer": "https://pulsbasketu.com/",
}

DEBUG_DIR = "plk/_debug"
CET = timezone(timedelta(hours=2))  # CEST uproszczone (UTC+2)

# In-memory cache - tylko w obrebie jednego runa skryptu
_cache = {
    "games_list": None,
    "table": None,
    "season_teams": {},   # team_id -> raw response
    "leaders": None,
}


# ============================================================
# HTTP helpers
# ============================================================

def _save_debug(name, data):
    """Zapisuje JSON do plk/_debug/pb_{name}.json (debug)."""
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        path = os.path.join(DEBUG_DIR, f"pb_{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    except Exception:
        pass


def _fetch_json(url, label, timeout=15):
    """Bezpieczne pobranie JSON. Zwraca None jak coś sie sypie."""
    try:
        r = requests.get(url, headers=PB_HEADERS, timeout=timeout)
    except Exception as e:
        print(f"   [pulsbasketu-EXC] {label}: {type(e).__name__}: {e}")
        return None
    if r.status_code != 200:
        print(f"   [pulsbasketu-FAIL] {label} -> HTTP {r.status_code}: {r.text[:200]}")
        return None
    try:
        return r.json()
    except Exception as e:
        print(f"   [pulsbasketu-JSON] {label}: {e}")
        return None


def default_season(today=None):
    """PLK sezon 2025/26 jest etykietowany w API jako 'season=2026'.
    Logika: od lipca przelaczamy sie na nowy sezon (rozpoczyna sie w pazdzierniku,
    ale wszystkie endpointy 'znaja' nowy sezon juz w lipcu/sierpniu)."""
    today = today or datetime.now()
    return today.year + 1 if today.month >= 7 else today.year


# ============================================================
# 3 GLOWNE FETCHE
# ============================================================

def fetch_games_list(season=None):
    """Lista wszystkich meczow w sezonie (cached). Zwraca list[dict]."""
    season = season or default_season()
    if _cache["games_list"] is not None:
        return _cache["games_list"]

    url = f"{PB_BASE}/league-seasons/{PB_LEAGUE}/games-list?season={season}"
    data = _fetch_json(url, "games-list")
    if data is None:
        return []

    # Format: {games: [...]} albo bezposrednio [...]
    games = (data.get("games") if isinstance(data, dict) else None) or \
            (data.get("data") if isinstance(data, dict) else None) or \
            (data if isinstance(data, list) else [])
    if not isinstance(games, list):
        games = []

    print(f"   [pulsbasketu] /games-list -> {len(games)} meczow (sezon {season})")
    _save_debug("games_list", data)
    _cache["games_list"] = games
    return games


def fetch_table(season=None):
    """Tabela ligowa: {team_id: row}. Każdy row ma wins/losses, streak, games_list."""
    season = season or default_season()
    if _cache["table"] is not None:
        return _cache["table"]

    url = f"{PB_BASE}/league-seasons/{PB_LEAGUE}/table?season={season}"
    data = _fetch_json(url, "table")
    if data is None:
        return {}

    rows = data.get("table") if isinstance(data, dict) else (data if isinstance(data, list) else [])
    if not isinstance(rows, list):
        rows = []

    table_by_id = {r.get("team_id"): r for r in rows if isinstance(r, dict)}
    print(f"   [pulsbasketu] /table -> {len(table_by_id)} druzyn")
    _save_debug("table", data)
    _cache["table"] = table_by_id
    return table_by_id


def fetch_season_team(team_id, season=None):
    """Per-team rich data: advanced_stat_line, opponent_stat_line, players[].
    Cached per team_id w obrebie runa."""
    season = season or default_season()
    if team_id in _cache["season_teams"]:
        return _cache["season_teams"][team_id]

    url = f"{PB_BASE}/season-teams/{team_id}?season={season}&league_id={PB_LEAGUE}"
    data = _fetch_json(url, f"season-team-{team_id}")
    _cache["season_teams"][team_id] = data
    if data:
        _save_debug(f"season_team_{team_id}", data)
    return data


def fetch_leaders(season=None, limit=20, sort_by="avg"):
    """Top N strzelcow ligi (z PPG)."""
    season = season or default_season()
    if _cache["leaders"] is not None:
        return _cache["leaders"]

    url = (f"{PB_BASE}/league-seasons/{PB_LEAGUE}/stats/players/stat-lines/leaders"
           f"?season={season}&limit={limit}&sort_by={sort_by}")
    data = _fetch_json(url, "leaders")
    if data is None:
        return []

    leaders = (data.get("data") if isinstance(data, dict) else None) or \
              (data.get("leaders") if isinstance(data, dict) else None) or \
              (data if isinstance(data, list) else [])
    if not isinstance(leaders, list):
        leaders = []

    print(f"   [pulsbasketu] /leaders -> {len(leaders)} graczy")
    _save_debug("leaders", data)
    _cache["leaders"] = leaders
    return leaders


# ============================================================
# Helpers - data parsing & filtering
# ============================================================

def parse_game_date(game):
    """PulsBasketu 'date': '2026-05-23T19:00:00' (lokalny CET, bez TZ).
    Zwraca aware datetime w CET. None jak parse padnie."""
    s = game.get("date") or ""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=CET)
        return dt
    except Exception:
        return None


def filter_games_for_date(games, date_str):
    """Filtruje liste meczow po YYYY-MM-DD (lokalny PL)."""
    out = []
    for g in games:
        dt = parse_game_date(g)
        if dt and dt.strftime("%Y-%m-%d") == date_str:
            out.append(g)
    # sortuj chronologicznie po godzinie
    out.sort(key=lambda g: parse_game_date(g) or datetime.now(CET))
    return out


def game_status(game):
    """Zwraca 'pre' | 'in' | 'post' na bazie 'finished' i czasu startu."""
    if game.get("finished"):
        return "post"
    dt = parse_game_date(game)
    if dt is None:
        return "pre"
    now = datetime.now(CET)
    if dt > now:
        return "pre"
    # po starcie ale nie 'finished' -> live
    return "in"


def fmt_game_time(game):
    """'19:00 CET' albo pusty."""
    dt = parse_game_date(game)
    return dt.strftime("%H:%M") + " CET" if dt else ""


# ============================================================
# Helpers - per-team aggregates from /table
# ============================================================

def get_team_record(table_by_id, team_id):
    """Wyciąga bilans z tabeli: W-L overall + dom + wyjazd + rating."""
    row = table_by_id.get(team_id) or {}
    games = row.get("games") or 0
    scored = row.get("small_points_scored") or 0
    lost = row.get("small_points_lost") or 0
    return {
        "wins": row.get("wins", 0),
        "losses": row.get("losses", 0),
        "wins_home": row.get("wins_home", 0),
        "losses_home": row.get("losses_home", 0),
        "wins_away": row.get("wins_away", 0),
        "losses_away": row.get("losses_away", 0),
        "real_position": row.get("real_position"),
        "games": games,
        "ppg": round(scored / games, 1) if games else 0.0,
        "papg": round(lost / games, 1) if games else 0.0,
        "net_rating_simple": round((scored - lost) / games, 1) if games else 0.0,
        "pace": row.get("pace"),
    }


def get_streak_last_n(table_by_id, team_id, n=15):
    """Ostatnie n liter z pola streak (W=wygrana, L=porazka)."""
    row = table_by_id.get(team_id) or {}
    streak = row.get("streak") or ""
    return streak[-n:] if streak else ""


def get_recent_games_for_team(table_by_id, team_id, n=5):
    """N ostatnich meczow z table.games_list (najnowsze pierwsze)."""
    row = table_by_id.get(team_id) or {}
    games_list = row.get("games_list") or []
    return games_list[:n]


# ============================================================
# Helpers - per-team rich (from /season-teams/{id})
# ============================================================

def get_advanced_stats(season_team_data):
    """ortg, drtg, net_rtg, ts, efg, pace, polish_pts_perc, etc."""
    if not season_team_data:
        return {}
    return season_team_data.get("advanced_stat_line") or {}


def get_avg_stats(season_team_data):
    """Srednie per mecz: points, fgp, f3p, ftp, rebounds, assists, fouls, etc."""
    if not season_team_data:
        return {}
    return season_team_data.get("avg_stat_line") or {}


def get_opponent_avg_stats(season_team_data):
    """Co RYWALE robia przeciwko tej druzynie (sygnal slabosci defensywnych)."""
    if not season_team_data:
        return {}
    return season_team_data.get("opponent_avg_stat_line") or {}


def get_top_scorers_for_team(season_team_data, n=3):
    """Top N graczy zespolu po srednim PPG (avg_stat_line.points)."""
    if not season_team_data:
        return []
    players = season_team_data.get("players") or []
    if not isinstance(players, list):
        return []

    def player_ppg(p):
        avg = (p.get("avg_stat_line") if isinstance(p, dict) else None) or {}
        return avg.get("points") or 0

    sorted_players = sorted(players, key=player_ppg, reverse=True)
    out = []
    for p in sorted_players[:n]:
        if not isinstance(p, dict):
            continue
        avg = p.get("avg_stat_line") or {}
        # Roznice w nazwach pol miedzy odpowiedziami - probujemy kilka
        first = p.get("first_name") or (p.get("player") or {}).get("first_name") or ""
        last = p.get("last_name") or (p.get("player") or {}).get("last_name") or ""
        full_name = (first + " " + last).strip() or p.get("name") or "?"
        out.append({
            "name": full_name,
            "player_id": p.get("player_id") or (p.get("player") or {}).get("player_id"),
            "ppg": round(avg.get("points", 0) or 0, 1),
            "mpg": _seconds_to_min(avg.get("seconds")),
            "apg": round(avg.get("assists", 0) or 0, 1),
            "rpg": round(avg.get("rebounds", 0) or 0, 1),
            "fgp": avg.get("fgp"),
            "f3p": avg.get("f3p"),
            "fouls": round(avg.get("fouls", 0) or 0, 1),
            "games_played": p.get("games_played") or avg.get("games_played"),
        })
    return out


def _seconds_to_min(s):
    if s is None:
        return None
    try:
        return round(float(s) / 60, 1)
    except Exception:
        return None


# ============================================================
# Helpers - cross-team / H2H / playoff series
# ============================================================

def get_h2h_in_season(games, team_a_id, team_b_id):
    """Mecze pomiedzy dwiema druzynami w sezonie (zakonczone), chronologicznie."""
    if not team_a_id or not team_b_id:
        return []
    h2h = []
    for g in games:
        h_id = (g.get("home_team") or {}).get("team_id")
        a_id = (g.get("away_team") or {}).get("team_id")
        if {h_id, a_id} == {team_a_id, team_b_id} and g.get("finished"):
            h2h.append(g)
    h2h.sort(key=lambda g: g.get("date") or "")
    return h2h


def summarize_h2h(h2h_games, team_a_id, team_a_name, team_b_id, team_b_name):
    """Zlicza wins/losses oraz tworzy chronologiczna liste."""
    if not h2h_games:
        return {"summary": "brak rozegranych spotkan w tym sezonie", "games": []}

    a_wins = b_wins = 0
    games_str = []
    for g in h2h_games:
        h = g.get("home_team") or {}
        a = g.get("away_team") or {}
        h_score = h.get("score", 0) or 0
        a_score = a.get("score", 0) or 0
        winner_id = h.get("team_id") if h_score > a_score else a.get("team_id")
        if winner_id == team_a_id:
            a_wins += 1
        elif winner_id == team_b_id:
            b_wins += 1
        date = g.get("day") or (g.get("date") or "")[:10]
        stage = g.get("stage_name") or ""
        games_str.append(f"{date} ({stage}): {a.get('name','?')} {a_score}-{h_score} {h.get('name','?')}")

    summary = f"{team_a_name} {a_wins}-{b_wins} {team_b_name} (w sezonie 2025/26)"
    return {"summary": summary, "games": games_str, "a_wins": a_wins, "b_wins": b_wins}


def get_implied_probabilities(odds_home, odds_away):
    """Z kursow bukmacherskich -> implied % (znormalizowane, bez vigorish)."""
    if not odds_home or not odds_away:
        return None
    try:
        h_inv = 1.0 / float(odds_home)
        a_inv = 1.0 / float(odds_away)
        total = h_inv + a_inv
        return {
            "home_pct": round(100 * h_inv / total, 1),
            "away_pct": round(100 * a_inv / total, 1),
        }
    except Exception:
        return None



# ============================================================
# PLAYOFF SERIES (dodane w fix/plk-audit-context)
# ============================================================
# Dodatkowe endpointy (z DevTools eksploracji 23/05/2026):
#   /playoff-series/{id}                    - szczegoly serii (kto vs kto, stan)
#   /playoff-series/{id}/players/stat-lines - per-player stats W TEJ SERII
#   /playoff-series/{id}/teams/stat-lines   - per-team stats W TEJ SERII
#   /playoff-series?league_id=plk&season=X  - lista wszystkich serii w sezonie

_cache["playoff_series_list"] = None
_cache["playoff_series"] = {}      # series_id -> data
_cache["series_player_stats"] = {}  # (series_id, stat_type) -> data


def fetch_playoff_series_list(season=None):
    """Lista wszystkich serii playoff w sezonie. Cached."""
    season = season or default_season()
    if _cache["playoff_series_list"] is not None:
        return _cache["playoff_series_list"]

    url = f"{PB_BASE}/playoff-series?league_id={PB_LEAGUE}&season={season}"
    data = _fetch_json(url, "playoff-series-list")
    if data is None:
        _cache["playoff_series_list"] = []
        return []

    series = data if isinstance(data, list) else (
        data.get("series") or data.get("data") or []
    )
    if not isinstance(series, list):
        series = []
    print(f"   [pulsbasketu] /playoff-series -> {len(series)} serii")
    _save_debug("playoff_series_list", data)
    _cache["playoff_series_list"] = series
    return series


def fetch_playoff_series(series_id):
    """Szczegoly konkretnej serii. Cached per series_id."""
    if not series_id:
        return None
    if series_id in _cache["playoff_series"]:
        return _cache["playoff_series"][series_id]

    url = f"{PB_BASE}/playoff-series/{series_id}"
    data = _fetch_json(url, f"playoff-series-{series_id}")
    _cache["playoff_series"][series_id] = data
    if data:
        _save_debug(f"playoff_series_{series_id}", data)
    return data


def fetch_series_player_stats(series_id, season=None, stat_type="avg"):
    """Per-player stats W KONKRETNEJ SERII (avg lub total).
    Najwazniejsze dla audytu - mowi kto sie rozkreca, kto wypadl."""
    if not series_id:
        return None
    season = season or default_season()
    cache_key = (series_id, stat_type)
    if cache_key in _cache["series_player_stats"]:
        return _cache["series_player_stats"][cache_key]

    url = (f"{PB_BASE}/playoff-series/{series_id}/players/stat-lines"
           f"?season={season}&stat_line_type={stat_type}&series_id={series_id}")
    data = _fetch_json(url, f"series-{series_id}-players-{stat_type}")
    _cache["series_player_stats"][cache_key] = data
    if data:
        _save_debug(f"series_{series_id}_players_{stat_type}", data)
    return data


# Mapowanie stage z PulsBasketu na polskie nazwy uzywane w prompcie/UI.
STAGE_PL = {
    "quarter_finals": "Cwiercfinaly",
    "semi_finals": "Polfinaly",
    "finals": "Final",
    "third_place": "Mecz o 3 miejsce",
    "fifth_place": "Mecz o 5 miejsce",
    "play_in": "Play-in",
}


def get_stage_pl(stage_code):
    """'semi_finals' -> 'Polfinaly'. Fallback na sam kod jak nie znamy."""
    if not stage_code:
        return "?"
    return STAGE_PL.get(stage_code, stage_code.replace("_", " ").title())


def find_series_for_match(game, all_series=None):
    """Znajduje (series_id, series_meta) dla danego meczu po team_ids obu druzyn.
    Format z PulsBasketu /playoff-series:
        {id: 851, stage: "semi_finals", finished: false,
         teams: [{data: {team_id: 37, ...}, wins: 2, seed: "1", higher_seed: true},
                 {data: {team_id: 40, ...}, wins: 1, seed: "5", higher_seed: false}]}
    Zwraca (None, None) gdy mapping niemozliwy."""
    if not game:
        return None, None
    h_id = (game.get("home_team") or {}).get("team_id")
    a_id = (game.get("away_team") or {}).get("team_id")
    if not h_id or not a_id:
        return None, None

    if all_series is None:
        all_series = fetch_playoff_series_list()
    if not all_series:
        return None, None

    target_pair = {h_id, a_id}
    for s in all_series:
        if not isinstance(s, dict):
            continue
        teams = s.get("teams") or []
        team_ids = set()
        for t in teams:
            if not isinstance(t, dict):
                continue
            tdata = t.get("data") or {}
            tid = tdata.get("team_id") or t.get("team_id")
            if tid:
                team_ids.add(tid)
        if team_ids == target_pair:
            return s.get("id") or s.get("playoff_series_id") or s.get("series_id"), s
    return None, None


def get_series_state(series_meta):
    """Wyciaga stan serii: {team_id: {name, wins, seed, higher_seed}}.
    Zwraca None jak format nieznany."""
    if not series_meta:
        return None
    teams = series_meta.get("teams") or []
    if len(teams) != 2:
        return None
    out = {}
    for t in teams:
        if not isinstance(t, dict):
            continue
        data = t.get("data") or {}
        tid = data.get("team_id")
        if not tid:
            continue
        out[tid] = {
            "name": data.get("team") or "?",
            "abbr": data.get("abbr"),
            "wins": int(t.get("wins", 0) or 0),
            "seed": t.get("seed"),
            "higher_seed": bool(t.get("higher_seed", False)),
        }
    return out or None


def format_series_state_short(series_state, h_id, a_id, h_name, a_name):
    """'WKS Slask Wroclaw 2-2 AMW Arka Gdynia' albo pusty string."""
    if not series_state:
        return ""
    h_wins = (series_state.get(h_id) or {}).get("wins", "?")
    a_wins = (series_state.get(a_id) or {}).get("wins", "?")
    return f"{h_name} {h_wins}-{a_wins} {a_name}"


def get_top_scorers_in_series(series_player_stats, team_id, n=3):
    """Z odpowiedzi /playoff-series/{id}/players/stat-lines wyciaga top N
    scorerow danej druzyny w tej serii.

    Format odpowiedzi (PulsBasketu, fix #10 - podstawowa struktura):
      {
        "team_id": 9, "team_name": "AMW Arka Gdynia",
        "full_name": "Luke Barrett", "position": "SF", "player_id": 7161,
        "games": 4,                    # mecze w serii
        "total_games_played": 34,      # mecze w sezonie
        "stat_line": {points: 18.8, ... }   # SREDNIE (mimo ze 'stat_line' a nie 'avg')
      }
    """
    if not series_player_stats:
        return []
    # Lista moze byc plain albo {data: [...]} / {players: [...]}
    players = series_player_stats if isinstance(series_player_stats, list) else (
        (series_player_stats.get("data") if isinstance(series_player_stats, dict) else None) or
        (series_player_stats.get("players") if isinstance(series_player_stats, dict) else None) or
        []
    )
    if not isinstance(players, list):
        return []

    def player_team(p):
        if not isinstance(p, dict):
            return None
        # team_id na top-level, fallback na zagniezdzone
        return (p.get("team_id") or
                (p.get("team") or {}).get("team_id") or
                (p.get("player_data") or {}).get("team_id"))

    def player_name(p):
        """Najpierw full_name (tak zwraca PulsBasketu), potem first+last fallbacki."""
        if not isinstance(p, dict):
            return "?"
        full = p.get("full_name")
        if full:
            return full.strip()
        pdata = p.get("player_data") or p.get("player") or {}
        full = pdata.get("full_name")
        if full:
            return full.strip()
        first = p.get("first_name") or pdata.get("first_name") or ""
        last = p.get("last_name") or pdata.get("last_name") or ""
        joined = (first + " " + last).strip()
        return joined or pdata.get("name") or "?"

    def player_stats(p):
        """Zwraca slownik srednich (PulsBasketu nazywa to 'stat_line' chociaz to srednie).
        Fallback na 'avg_stat_line' jak format kiedys sie zmieni."""
        if not isinstance(p, dict):
            return {}
        return p.get("stat_line") or p.get("avg_stat_line") or {}

    def player_ppg(p):
        return player_stats(p).get("points") or 0

    team_players = [p for p in players if player_team(p) == team_id]
    # Wykluczamy "is_total_player" (sumaryczne wirtualne wpisy zespolu)
    team_players = [p for p in team_players if not p.get("is_total_player")]
    team_players.sort(key=player_ppg, reverse=True)

    out = []
    for p in team_players[:n]:
        sl = player_stats(p)
        out.append({
            "name": player_name(p),
            "position": p.get("position"),
            "player_id": p.get("player_id") or (p.get("player_data") or {}).get("player_id"),
            "ppg": round(sl.get("points", 0) or 0, 1),
            "apg": round(sl.get("assists", 0) or 0, 1),
            "rpg": round(sl.get("rebounds", 0) or 0, 1),
            "fgp": sl.get("fgp"),
            "f3p": sl.get("f3p"),
            "fouls": round(sl.get("fouls", 0) or 0, 1),
            "games_in_series": p.get("games"),  # ile meczow zagral w tej serii
        })
    return out
