"""
run_mode.py - Wykrywa tryb uruchomienia na podstawie czasu i meczów.

Używane przez daily_update.yml do decydowania co robić w danym cronie:

TRYBY:
  full     - pełna analiza AI (rano, lub gdy brak aktualnego picka)
  pre-game - "last check" przed meczem (kontuzje), tylko 1h-30min przed startem
  live     - tylko aktualizacja wyników (w trakcie meczu), zero Gemini
  post     - zaktualizuj wyniki po meczu, zero Gemini
  idle     - brak meczów dziś, nic do roboty

Logika PLK/EuroLeague:
  - Jeśli `plk/ai_analyses.json` istnieje i pick jest na DZIŚ -> skip full AI
  - Jeśli mecz zaczyna się za 30-90 minut -> pre-game audit (kontuzje!)
  - Jeśli mecz trwa (started ale nie finished) -> live updates
  - Jeśli mecz skończony i nie ma checkmark w HTML -> post update

Wyjście: pisze plik `.run_mode` z trybem, odczytywany przez workflow.
"""

import os
import sys
import json
from datetime import datetime, timezone, timedelta

CET = timezone(timedelta(hours=2))

def today_str():
    return datetime.now(CET).strftime("%Y-%m-%d")

def now_cet():
    return datetime.now(CET)

def load_json_safe(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def get_plk_games_today():
    """Czyta z PulsBasketu games-list (lokalny cache) albo odpala mini-fetch."""
    import requests
    try:
        season = now_cet().year + 1 if now_cet().month >= 7 else now_cet().year
        url = (f"https://api.pulsbasketu.com/api/v1/league-seasons/plk/"
               f"games-list?season={season}")
        print(f"  [run_mode] GET {url}")
        r = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Origin": "https://pulsbasketu.com",
            "Referer": "https://pulsbasketu.com/",
        }, timeout=10)
        print(f"  [run_mode] HTTP {r.status_code}, len={len(r.text)}")
        if r.status_code != 200:
            print(f"  [run_mode] Odpowiedz: {r.text[:200]}")
            return []
        data = r.json()
        games = (data.get("games") if isinstance(data, dict) else None) or \
                (data if isinstance(data, list) else [])
        today = today_str()
        result = []
        for g in (games or []):
            d = (g.get("date") or "")[:10]
            if d == today:
                result.append(g)
        print(f"  [run_mode] Lacznie meczow w sezonie: {len(games)}, dzis ({today}): {len(result)}")
        return result
    except Exception as e:
        print(f"  [run_mode] Blad: {e}")
        return []

def get_plk_pick_date():
    """Zwraca datę ostatniego wygenerowanego picka PLK."""
    data = load_json_safe("plk/ai_analyses.json")
    if data and data.get("date"):
        return data["date"]
    # fallback: sprawdź propozycje_typow.txt
    try:
        with open("plk/propozycje_typow.txt", encoding="utf-8") as f:
            first_line = f.readline()
        if today_str() in first_line:
            return today_str()
    except Exception:
        pass
    return None

def determine_plk_mode(games_today):
    """Zwraca tryb dla PLK na podstawie meczów i czasu."""
    now = now_cet()

    if not games_today:
        return "idle", "brak meczow PLK dzisiaj"

    # Sprawdź czy pick już istnieje na dziś
    pick_date = get_plk_pick_date()
    has_pick_today = (pick_date == today_str())

    modes = []
    for g in games_today:
        date_str = g.get("date") or ""
        try:
            game_dt = datetime.fromisoformat(date_str)
            if game_dt.tzinfo is None:
                game_dt = game_dt.replace(tzinfo=CET)
        except Exception:
            continue

        finished = g.get("finished", False)
        mins_to_start = (game_dt - now).total_seconds() / 60

        h = g.get("home_team") or {}
        a = g.get("away_team") or {}
        matchup = f"{a.get('name','?')} @ {h.get('name','?')}"

        if finished:
            h_score = int(h.get("score", 0) or 0)
            a_score = int(a.get("score", 0) or 0)
            modes.append(("post", f"{matchup} skończony {a_score}-{h_score}"))
        elif mins_to_start <= 0:
            # Mecz powinien trwać
            modes.append(("live", f"{matchup} w trakcie (start był {-mins_to_start:.0f} min temu)"))
        elif 30 <= mins_to_start <= 90:
            # Okno "last check before game" - 30-90 minut przed
            modes.append(("pre-game", f"{matchup} za {mins_to_start:.0f} min - PRE-GAME CHECK"))
        elif not has_pick_today:
            modes.append(("full", f"{matchup} za {mins_to_start:.0f} min - brak picka, potrzebny full run"))
        else:
            modes.append(("skip", f"{matchup} za {mins_to_start:.0f} min - pick już jest, czekaj"))

    if not modes:
        return "idle", "brak aktywnych meczow"

    # Priorytet: live > pre-game > full > post > skip > idle
    priority = {"live": 0, "pre-game": 1, "full": 2, "post": 3, "skip": 4, "idle": 5}
    modes.sort(key=lambda x: priority.get(x[0], 99))
    return modes[0]


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "plk"
    now = now_cet()
    print(f"run_mode.py: {now.strftime('%Y-%m-%d %H:%M %Z')}, target={target}")

    if target == "plk":
        games = get_plk_games_today()
        print(f"  Mecze PLK dziś: {len(games)}")
        mode, reason = determine_plk_mode(games)
        print(f"  Tryb: {mode} ({reason})")

        # Zapisz do .run_mode_plk żeby workflow mógł podjąć decyzję
        with open(".run_mode_plk", "w") as f:
            f.write(mode)
        print(f"  Zapisano .run_mode_plk = {mode}")
        return mode

    return "idle"


if __name__ == "__main__":
    result = main()
    sys.exit(0)
