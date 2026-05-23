"""
PLK DEBUG - czysta diagnostyka zrodla danych Sofascore.

Co robi: uderza w te same endpointy co update_plk.py i wypisuje WSZYSTKO
w terminalu po polsku. Zero generowania HTML, zero AI, zero Gemini.

Cel: jednoznacznie ustalic czy 'Brak meczow PLK na dzis' to:
  (a) prawda (PLK faktycznie nie gra dzisiaj), czy
  (b) blad w pobieraniu danych (zly sezon, 403, pusta odpowiedz, itp.)

URUCHOMIENIE:
    pip install requests
    python plk_local/plk_debug.py

Wynik: tylko stdout. Dumpy JSON-ow leca do plk_local/_debug/.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    print("!! Brak biblioteki 'requests'. Zainstaluj: pip install requests")
    sys.exit(1)


# -------------------- konfig identyczny z update_plk.py --------------------
TOURNAMENT_ID = 263
TOURNAMENT_NAME = "Orlen Basket Liga (PLK)"
SOFA_BASE = "https://api.sofascore.com/api/v1"
SOFA_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/123.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.sofascore.com/",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_DIR = os.path.join(SCRIPT_DIR, "_debug")
os.makedirs(DEBUG_DIR, exist_ok=True)


# -------------------- helpery --------------------

def hr(title=""):
    line = "=" * 70
    if title:
        print(f"\n{line}\n  {title}\n{line}")
    else:
        print(line)


def get_polish_today():
    """Lokalna data PL (Europe/Warsaw, w maju = CEST UTC+2)."""
    cet = timezone(timedelta(hours=2))
    return datetime.now(cet).strftime("%Y-%m-%d"), datetime.now(cet)


def fetch_json(url, label):
    print(f"  -> GET {url}")
    t0 = time.time()
    try:
        r = requests.get(url, headers=SOFA_HEADERS, timeout=15)
    except Exception as e:
        print(f"     [EXCEPTION] {type(e).__name__}: {e}")
        return None
    dt_ms = int((time.time() - t0) * 1000)
    print(f"     <- HTTP {r.status_code} ({dt_ms} ms, {len(r.content)} B)")
    if r.status_code != 200:
        print(f"     body[:300]: {r.text[:300]}")
        return None
    try:
        data = r.json()
    except Exception as e:
        print(f"     [JSON parse error] {e}")
        return None
    # zapisz dump
    path = os.path.join(DEBUG_DIR, f"debug_{label}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        print(f"     dump zapisany: {path}")
    except Exception as e:
        print(f"     [dump error] {e}")
    return data


def fmt_event(ev, today_pl):
    ts = ev.get("startTimestamp")
    cet = timezone(timedelta(hours=2))
    when_iso, when_local = "-", "-"
    same_day = False
    if ts:
        try:
            dt_utc = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            dt_pl = dt_utc.astimezone(cet)
            when_iso = dt_utc.strftime("%Y-%m-%d %H:%M UTC")
            when_local = dt_pl.strftime("%Y-%m-%d %H:%M PL")
            same_day = dt_pl.strftime("%Y-%m-%d") == today_pl
        except Exception:
            pass
    home = (ev.get("homeTeam") or {}).get("name", "?")
    away = (ev.get("awayTeam") or {}).get("name", "?")
    status = ((ev.get("status") or {}).get("type") or "?")
    rnd = (ev.get("roundInfo") or {}).get("name") or (ev.get("roundInfo") or {}).get("round") or "-"
    flag = " <-- DZISIAJ" if same_day else ""
    return f"  {when_local:<22} | {status:<11} | {rnd!s:<10} | {away} @ {home}{flag}"


# -------------------- glowny diag --------------------

def main():
    today_pl, now_pl = get_polish_today()

    hr("PLK DEBUG / DIAGNOSTYKA ZRODLA DANYCH")
    print(f"  Czas lokalny PL: {now_pl.strftime('%Y-%m-%d %H:%M %Z')}")
    print(f"  Sprawdzam mecze na: {today_pl}")
    print(f"  Liga:               {TOURNAMENT_NAME}")
    print(f"  Sofascore tournament id: {TOURNAMENT_ID}")
    print(f"  Endpoint base:      {SOFA_BASE}")
    print(f"  Dumpy JSON:         {DEBUG_DIR}/")

    # 1) Sezony
    hr("[1/4] Lista sezonow PLK")
    seasons_data = fetch_json(
        f"{SOFA_BASE}/unique-tournament/{TOURNAMENT_ID}/seasons",
        "seasons",
    )
    if not seasons_data:
        print("\n!! Endpoint /seasons nie odpowiada. Diagnoza skonczona.")
        print("   Mozliwe przyczyny:")
        print("   - blokada IP / 403 / rate limit Sofascore")
        print("   - zmieniony tournament id (263 -> cos innego?)")
        print("   - brak internetu w tej maszynie")
        return

    seasons = seasons_data.get("seasons") or []
    print(f"\n  Znaleziono {len(seasons)} sezonow. Najnowsze 8:")
    for s in seasons[:8]:
        print(f"    id={s.get('id'):<10} year='{s.get('year')}'  name='{s.get('name')}'")

    # wybor sezonu - identyczna logika jak update_plk.py
    chosen = None
    for s in seasons:
        year = str(s.get("year") or "")
        if "25/26" in year or "2025/26" in year or "2025-26" in year or year.startswith("25"):
            chosen = s
            break
    if not chosen and seasons:
        chosen = seasons[0]

    if not chosen:
        print("\n!! Nie udalo sie wybrac zadnego sezonu. Stop.")
        return

    season_id = chosen.get("id")
    print(f"\n  >>> WYBRANY SEZON: id={season_id}, year='{chosen.get('year')}', name='{chosen.get('name')}'")
    print(f"      (uwaga: ten sam algorytm wyboru co update_plk.py)")

    # 2) Najblizsze mecze (events/next)
    hr("[2/4] Najblizsze mecze (events/next/0)")
    next_data = fetch_json(
        f"{SOFA_BASE}/unique-tournament/{TOURNAMENT_ID}/season/{season_id}/events/next/0",
        "events_next_p0",
    )
    next_events = (next_data or {}).get("events") or []
    print(f"\n  Liczba meczow next p0: {len(next_events)}")
    if next_events:
        print(f"  hasNextPage: {(next_data or {}).get('hasNextPage')}")
        print(f"\n  Pierwsze 15 nadchodzacych:")
        print(f"  {'data lokalna':<22} | {'status':<11} | {'runda':<10} | mecz")
        print(f"  {'-'*22} | {'-'*11} | {'-'*10} | {'-'*40}")
        for ev in next_events[:15]:
            print(fmt_event(ev, today_pl))
    else:
        print("  (brak nadchodzacych meczow w tym sezonie wg API)")

    # 3) Ostatnie mecze (events/last)
    hr("[3/4] Ostatnie mecze (events/last/0)")
    last_data = fetch_json(
        f"{SOFA_BASE}/unique-tournament/{TOURNAMENT_ID}/season/{season_id}/events/last/0",
        "events_last_p0",
    )
    last_events = (last_data or {}).get("events") or []
    print(f"\n  Liczba meczow last p0: {len(last_events)}")
    if last_events:
        print(f"\n  Ostatnie 15 rozegranych:")
        print(f"  {'data lokalna':<22} | {'status':<11} | {'runda':<10} | mecz")
        print(f"  {'-'*22} | {'-'*11} | {'-'*10} | {'-'*40}")
        for ev in last_events[-15:]:
            print(fmt_event(ev, today_pl))
    else:
        print("  (brak rozegranych meczow w tym sezonie wg API)")

    # 4) Filtrowanie na dzisiaj - dokladnie ta sama logika co w produkcji
    hr(f"[4/4] Filtrowanie meczow na DZISIAJ ({today_pl})")
    cet = timezone(timedelta(hours=2))
    all_events = next_events + last_events
    today_events = []
    for ev in all_events:
        ts = ev.get("startTimestamp")
        if not ts:
            continue
        try:
            dt = datetime.fromtimestamp(int(ts), tz=cet)
        except Exception:
            continue
        if dt.strftime("%Y-%m-%d") == today_pl:
            today_events.append(ev)

    print(f"\n  Razem przeszukane mecze (next+last): {len(all_events)}")
    print(f"  Mecze dopasowane do {today_pl}:        {len(today_events)}")

    if today_events:
        print(f"\n  >>> DZISIEJSZE MECZE PLK ({len(today_events)}):")
        for ev in today_events:
            print(fmt_event(ev, today_pl))
        print(f"\n  WERDYKT: zrodlo OK, mecze sa, problem byl chyba przejsciowy.")
        print(f"           Odpal teraz: python update_plk.py")
    else:
        # Pokaz co JEST najblizej dzisiaj (3 dni temu / w przyszlosci) - zeby
        # bylo jasne czy to martwy okres w lidze, czy zly sezon w API.
        nearest = []
        for ev in all_events:
            ts = ev.get("startTimestamp")
            if not ts:
                continue
            try:
                dt = datetime.fromtimestamp(int(ts), tz=cet)
            except Exception:
                continue
            delta_days = (dt.date() - now_pl.date()).days
            nearest.append((abs(delta_days), delta_days, ev))
        nearest.sort(key=lambda x: x[0])

        print(f"\n  WERDYKT: API NIE ZWRACA zadnych meczow PLK na {today_pl}.")
        if nearest:
            print(f"\n  Najblizsze 5 meczow w API (wg odleglosci od dzis):")
            for _, delta, ev in nearest[:5]:
                tag = f"{'+' if delta >= 0 else ''}{delta}d"
                print(f"    [{tag:>5}] {fmt_event(ev, today_pl)[2:]}")
            print()
            print("  Jesli najblizsze mecze sa pare dni od dzis - to zwykly off-day.")
            print("  Jesli sa hibernacja (>30 dni) i sezon w 'name' jest stary - zly")
            print("  season_id i trzeba zmodyfikowac wybor sezonu w update_plk.py.")
        else:
            print("\n  API nie zwraca W OGOLE meczow w wybranym sezonie - to wyglada")
            print("  na bug w wyborze sezonu albo blokade Sofascore.")

    hr("KONIEC DIAGNOSTYKI")
    print(f"  Pelne dumpy JSON do dalszej analizy: {DEBUG_DIR}/")


if __name__ == "__main__":
    main()
