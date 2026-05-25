"""
24score.com scraper dla ACB i BBL.

Architektura (odkryta przez DevTools):
1. GET strona -> wyciąg data_key z JS + zachowaj PHPSESSID cookie
2. GET /backend/load_page_data.php?data_key=KEY (ta sama sesja!) -> HTML z danymi
   WAŻNE: data_key jest jednorazowy i powiązany z sesją HTTP (PHPSESSID).
   Bez Session() dostajemy "data error".

Standings: tr > td: [rank, team, games, wins, losses, win_pct]
Fixtures:  tr > td: [date, "Home - Away", score, quarters, odds1, odds2]
"""

import re
import requests
from datetime import datetime, timezone, timedelta

CET = timezone(timedelta(hours=2))
BASE = "https://en.24score.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BASE + "/",
}

URLS = {
    "acb": {
        "fixtures":  BASE + "/basketball/spain/acb_league/2025-2026/regular_season/fixtures/",
        "standings": BASE + "/basketball/spain/acb_league/2025-2026/regular_season/standings/",
    },
    "bbl": {
        "fixtures":  BASE + "/basketball/germany/bbl/2025-2026/play-off/fixtures/",
        "standings": BASE + "/basketball/germany/bbl/2025-2026/play-off/standings/",
    },
}


def _fetch_data(page_url):
    """
    Pobiera dane 24score w 2 krokach przez tę samą sesję HTTP (PHPSESSID).
    Krok 1: GET strony -> cookies + data_key z JS
    Krok 2: GET load_page_data.php?data_key=KEY -> HTML z danymi
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        r = session.get(page_url, timeout=20)
        if r.status_code != 200:
            print(f"   [24score] HTTP {r.status_code}: {page_url}")
            return None
    except Exception as e:
        print(f"   [24score] Błąd strony: {e}")
        return None

    m = re.search(r'"data_key"\s*:\s*"([A-Za-z0-9_\-]+)"', r.text)
    if not m:
        m = re.search(r'data_key["\s:]+([A-Za-z0-9_\-]{10,})', r.text)
    if not m:
        print(f"   [24score] Brak data_key w: {page_url}")
        return None

    data_key = m.group(1)
    print(f"   [24score] data_key={data_key[:16]}... cookies={list(session.cookies.keys())}")

    api_url = f"{BASE}/backend/load_page_data.php?data_key={data_key}"
    try:
        r2 = session.get(api_url, timeout=20)
        if 'data error' in r2.text:
            print("   [24score] data error - klucz nieważny")
            return None
        print(f"   [24score] Dane: {len(r2.text)} znaków")
        return r2.text
    except Exception as e:
        print(f"   [24score] Błąd API: {e}")
        return None


def _clean(html_fragment):
    text = re.sub(r'<[^>]+>', ' ', html_fragment)
    text = text.replace('&nbsp;', ' ').replace('&ndash;', '–')
    text = text.replace('&#8211;', '–').replace('&amp;', '&')
    return re.sub(r'\s+', ' ', text).strip()


def _parse_rows(html):
    rows = []
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE):
        cells = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL | re.IGNORECASE)
        if not cells:
            continue
        cleaned = [_clean(c) for c in cells]
        if any(cleaned):
            rows.append(cleaned)
    return rows


def _parse_date(s):
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            pass
    return None


def _parse_score(s):
    s = s.strip()
    if not s or s in ('— —', '–', '-'):
        return 0, 0, 'notstarted'
    if re.match(r'^\d{1,2}:\d{2}$', s):
        h, mn = map(int, s.split(':'))
        if h <= 23 and mn <= 59:
            return 0, 0, 'notstarted'
    m = re.match(r'(\d+)\s*:\s*(\d+)', s)
    if m:
        return int(m.group(1)), int(m.group(2)), 'finished'
    return 0, 0, 'notstarted'


def fetch_games_today(league_key, today_slug):
    """Pobiera dzisiejsze mecze. Zwraca listę eventów (Sofascore-compatible)."""
    url = URLS.get(league_key, {}).get("fixtures")
    if not url:
        return []

    print(f"   [24score] {league_key} fixtures: {url}")
    data_html = _fetch_data(url)
    if not data_html:
        return []

    rows = _parse_rows(data_html)
    today = datetime.strptime(today_slug, "%Y-%m-%d").date()
    events = []

    for row in rows:
        if len(row) < 2:
            continue
        row_date = _parse_date(row[0])
        if row_date != today:
            continue

        matchup = row[1]
        sep = '–' if '–' in matchup else (' - ' if ' - ' in matchup else None)
        if sep is None:
            continue
        parts = matchup.split(sep, 1)
        if len(parts) != 2:
            continue
        home, away = parts[0].strip(), parts[1].strip()
        if not home or not away:
            continue

        score_raw = row[2].strip() if len(row) > 2 else ''
        hs, as_, status = _parse_score(score_raw)

        ts = None
        try:
            dt = datetime.strptime(f"{today_slug} 20:00", "%Y-%m-%d %H:%M").replace(tzinfo=CET)
            ts = int(dt.timestamp())
        except Exception:
            pass

        events.append({
            "homeTeam": {"name": home, "id": None},
            "awayTeam": {"name": away, "id": None},
            "startTimestamp": ts,
            "status": {"type": status},
            "homeScore": {"current": hs},
            "awayScore": {"current": as_},
            "roundInfo": {"name": ""},
            "_source": "24score",
        })

    if not events:
        all_dates = sorted({row[0] for row in rows if len(row) >= 2 and _parse_date(row[0])})
        print(f"   [24score] Brak na {today_slug}. Daty: {all_dates[-5:] if all_dates else 'brak'}")
    else:
        print(f"   [24score] {len(events)} meczów na {today_slug}")

    return events


def fetch_standings(league_key):
    """Pobiera tabelę. Zwraca dict {team_name: win_pct}."""
    url = URLS.get(league_key, {}).get("standings")
    if not url:
        return {}

    print(f"   [24score] {league_key} standings: {url}")
    data_html = _fetch_data(url)
    if not data_html:
        return {}

    rows = _parse_rows(data_html)
    pct_map = {}

    for row in rows:
        if len(row) < 5 or not re.match(r'^\d+$', row[0]):
            continue
        team = row[1].strip()
        if not team or team.isdigit():
            continue
        try:
            wins, losses = int(row[3]), int(row[4])
            total = wins + losses
            if total > 0:
                pct_map[team] = round(wins / total, 3)
        except (ValueError, IndexError):
            try:
                pct_map[team] = round(float(row[5].replace('%','').replace(',','.')) / 100, 3)
            except Exception:
                pass

    print(f"   [24score] Tabela {league_key}: {len(pct_map)} drużyn")
    return pct_map


if __name__ == "__main__":
    import sys
    today = sys.argv[1] if len(sys.argv) > 1 else datetime.now(CET).strftime("%Y-%m-%d")

    print(f"\n=== ACB standings ===")
    for k, v in list(fetch_standings("acb").items())[:5]:
        print(f"  {k}: {v}")

    print(f"\n=== ACB games {today} ===")
    for g in fetch_games_today("acb", today):
        print(f"  {g['homeTeam']['name']} vs {g['awayTeam']['name']} [{g['status']['type']}]")

    print(f"\n=== BBL games {today} ===")
    for g in fetch_games_today("bbl", today):
        print(f"  {g['homeTeam']['name']} vs {g['awayTeam']['name']} [{g['status']['type']}]")
