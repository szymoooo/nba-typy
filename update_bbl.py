"""
BBL (easyCredit BBL, Niemcy) Free Picks.

Źródło danych (w kolejności prób):
  1. Sofascore public API (tournament_id=105)
  2. 24score.com scraper (score24_data.py) - gdy Sofascore zablokowany
  3. Gemini Google Search - ostateczny fallback

URUCHOMIENIE LOKALNE:
    export GEMINI_API_KEY=...
    python update_bbl.py

Wynik: bbl/index.html
"""

import os
import re
import json
import time
import textwrap
from datetime import datetime, timezone, timedelta
import requests

LEAGUE_NAME = "easyCredit BBL"
OUTPUT_DIR = "bbl"
DEBUG_DIR = "bbl/_debug"
SOFA_TOURNAMENT_ID = 4441  # BBL easyCredit Bundesliga (105=404 Not Found, 227=BBL Germany)
SOFA_SEASON_ID = 79994     # sezon 25/26 - hardkodowany fallback gdy API niedostepne
SOFA_SEASON_YEAR = "25/26"

USE_AI_PREDICTIONS = os.environ.get("PLK_LIVE_MODE", "").lower() not in ("true", "1", "yes")
AI_MODEL = "gemini-2.5-flash"
BRAND_TITLE = "BBL PUBLIC HUB"
BRAND_ACCENT = "#e30613"  # czerwień BBL

DEFAULT_LOGO = (
    "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    "<circle cx='50' cy='50' r='44' fill='none' stroke='%23e30613' stroke-width='3'/>"
    "<text y='62' x='50' text-anchor='middle' font-size='42' fill='%23e30613'>"
    "%F0%9F%8F%80</text></svg>"
)

CET = timezone(timedelta(hours=2))
SOFA_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/123.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "de,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.sofascore.com/",
}

_gemini_client = None
_ai_log = []


def _sofa_fetch(url):
    try:
        r = requests.get(url, headers=SOFA_HEADERS, timeout=15)
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        print(f"   [sofa-EXC] {type(e).__name__}: {e}")
        return None


def _save_debug(name, data):
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        with open(os.path.join(DEBUG_DIR, f"sofa_{name}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    except Exception:
        pass


def get_today_str():
    return datetime.now(CET).strftime("%Y-%m-%d")


def fetch_sofa_season_id():
    """Pobiera aktualny season_id dla BBL z Sofascore.
    GitHub Actions IP jest blokowane przez Sofascore - fallback na SOFA_SEASON_ID."""
    data = _sofa_fetch(f"https://api.sofascore.com/api/v1/unique-tournament/{SOFA_TOURNAMENT_ID}/seasons")
    if not data:
        print(f"   [sofa] BBL /seasons niedostepne (blocked?) - fallback id={SOFA_SEASON_ID}")
        return SOFA_SEASON_ID
    _save_debug("seasons", data)
    seasons = data.get("seasons") or []
    print(f"   [sofa] BBL dostepne sezony: {[(s.get('name'), s.get('year'), s.get('id')) for s in seasons[:5]]}")
    for s in seasons:
        year = str(s.get("year") or "")
        if ("25/26" in year or "2025/2026" in year or
                year == "2025" or year.startswith("2025")):
            print(f"   [sofa] BBL sezon: {s.get('name')} (id={s.get('id')})")
            return s.get("id")
    if seasons:
        s = seasons[0]
        print(f"   [sofa] BBL sezon (fallback latest): {s.get('name')} (id={s.get('id')})")
        return s.get("id")
    return SOFA_SEASON_ID


def fetch_sofa_games_today(season_id, today_slug):
    games = []
    for kind in ("next", "last"):
        data = _sofa_fetch(
            f"https://api.sofascore.com/api/v1/unique-tournament/{SOFA_TOURNAMENT_ID}"
            f"/season/{season_id}/events/{kind}/0"
        )
        if not data:
            continue
        if kind == "next":
            _save_debug("events_next", data)
        for ev in data.get("events") or []:
            ts = ev.get("startTimestamp")
            if not ts:
                continue
            try:
                dt = datetime.fromtimestamp(int(ts), tz=CET)
            except Exception:
                continue
            if dt.strftime("%Y-%m-%d") == today_slug:
                games.append(ev)
    print(f"   [sofa] BBL mecze na {today_slug}: {len(games)}")
    return games


def fetch_games_via_ai(today_slug):
    """Fallback: pobiera dzisiejsze mecze BBL przez Gemini Google Search.
    Zwraca listę event-like dictów kompatybilnych z budową kart HTML."""
    client = _get_gemini()
    if not client:
        print("   [AI-games] Brak klucza Gemini - nie można pobrać meczów przez AI")
        return []

    prompt = f"""Podaj mi dzisiejsze mecze BBL (easyCredit Basketball Bundesliga, Niemcy) na datę {today_slug}.
Użyj Google Search aby znaleźć wyniki/harmonogram z basketball-bundesliga.de lub sport1.de lub spox.com.

Odpowiedz TYLKO czystym JSON (bez markdown), lista obiektów:
[
  {{
    "home": "<nazwa drużyny gospodarzy>",
    "away": "<nazwa drużyny gości>",
    "time_cet": "<godzina CET np. 20:30>",
    "status": "pre",
    "phase": "<faza np. Playoff Semifinals lub Regular Season>"
  }}
]

Jeśli nie ma meczów BBL na {today_slug}, zwróć pustą listę: []
Nie dodawaj żadnego tekstu przed ani po JSON."""

    try:
        from google.genai import types
        resp = client.models.generate_content(
            model=AI_MODEL, contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        text = (resp.text or "").strip()
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if not m:
            print(f"   [AI-games] Brak JSON w odpowiedzi Gemini: {text[:200]}")
            return []
        games_raw = json.loads(m.group())
        events = []
        for g in games_raw:
            home_name = g.get("home", "")
            away_name = g.get("away", "")
            if not home_name or not away_name:
                continue
            status_str = str(g.get("status", "pre")).lower()
            sofa_status_type = "notstarted" if status_str == "pre" else (
                "inprogress" if status_str in ("in", "live") else "finished"
            )
            ts = None
            try:
                time_str = g.get("time_cet", "20:00")
                dt = datetime.strptime(f"{today_slug} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=CET)
                ts = int(dt.timestamp())
            except Exception:
                ts = None
            events.append({
                "homeTeam": {"name": home_name, "id": None},
                "awayTeam": {"name": away_name, "id": None},
                "startTimestamp": ts,
                "status": {"type": sofa_status_type},
                "homeScore": {"current": 0},
                "awayScore": {"current": 0},
                "roundInfo": {"name": g.get("phase", "BBL")},
                "_source": "gemini_search",
            })
        print(f"   [AI-games] BBL mecze (Gemini): {len(events)}")
        _save_debug("ai_games", events)
        return events
    except Exception as e:
        print(f"   [AI-games] Blad: {e}")
        return []




def fetch_sofa_standings(season_id):
    data = _sofa_fetch(
        f"https://api.sofascore.com/api/v1/unique-tournament/{SOFA_TOURNAMENT_ID}"
        f"/season/{season_id}/standings/total"
    )
    if not data:
        return {}
    _save_debug("standings", data)
    pct_map = {}
    for table in data.get("standings") or []:
        for row in table.get("rows") or []:
            team = row.get("team") or {}
            tid = team.get("id")
            wins = int(row.get("wins", 0) or 0)
            losses = int(row.get("losses", 0) or 0)
            total = wins + losses
            if tid:
                pct_map[tid] = (wins / total) if total > 0 else 0.0
    print(f"   [sofa] BBL standings: {len(pct_map)} druzyn")
    return pct_map


def sofa_game_status(ev):
    t = ((ev.get("status") or {}).get("type") or "").lower()
    if t in ("notstarted", "scheduled"):
        return "pre"
    if t in ("inprogress", "live"):
        return "in"
    return "post"


def sofa_fmt_time(ev):
    ts = ev.get("startTimestamp")
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts), tz=CET).strftime("%H:%M") + " CET"
    except Exception:
        return ""


def sofa_score(ev, side):
    key = "homeScore" if side == "home" else "awayScore"
    sc = ev.get(key) or {}
    if isinstance(sc, dict):
        v = sc.get("current")
        if v is None:
            v = sc.get("display")
        try:
            return int(v) if v is not None else 0
        except Exception:
            return 0
    try:
        return int(sc)
    except Exception:
        return 0


def sofa_team_logo(team):
    tid = (team or {}).get("id")
    if tid:
        return f"https://api.sofascore.app/api/v1/team/{tid}/image"
    name = (team or {}).get("name", "")
    return BBL_LOGOS.get(name, DEFAULT_LOGO)


# Sofascore team IDs dla BBL (z URL: sofascore.com/basketball/team/name/ID)
BBL_LOGOS = {
    "Bayern":           "https://api.sofascore.app/api/v1/team/3564/image",
    "Alba Berlin":      "https://api.sofascore.app/api/v1/team/3563/image",
    "Bamberg":          "https://api.sofascore.app/api/v1/team/3565/image",
    "Bonn":             "https://api.sofascore.app/api/v1/team/3566/image",
    "Ulm":              "https://api.sofascore.app/api/v1/team/3567/image",
    "Vechta":           "https://api.sofascore.app/api/v1/team/3568/image",
    "Trier":            "https://api.sofascore.app/api/v1/team/3569/image",
    "Wurzburg":         "https://api.sofascore.app/api/v1/team/3570/image",
    "Hamburg":          "https://api.sofascore.app/api/v1/team/3571/image",
    "Rostock":          "https://api.sofascore.app/api/v1/team/3572/image",
    "Braunschweig":     "https://api.sofascore.app/api/v1/team/3573/image",
    "Göttingen":        "https://api.sofascore.app/api/v1/team/3574/image",
    "Fraport Skyliners": "https://api.sofascore.app/api/v1/team/3575/image",
    "Chemnitz":         "https://api.sofascore.app/api/v1/team/3576/image",
    "Gießen":           "https://api.sofascore.app/api/v1/team/3577/image",
    "Oldenburg":        "https://api.sofascore.app/api/v1/team/3578/image",
}


def _get_gemini():
    global _gemini_client
    if _gemini_client:
        return _gemini_client
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    try:
        from google import genai
        _gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        return _gemini_client
    except Exception as e:
        print(f"   ! Gemini init: {e}")
        return None


def _norm_name(ai_name, h, a):
    if not ai_name:
        return None
    n = ai_name.lower().strip()
    if n == h.lower() or h.lower() in n or n in h.lower():
        return h
    if n == a.lower() or a.lower() in n or n in a.lower():
        return a
    for w in n.split():
        if len(w) >= 4:
            if w in h.lower():
                return h
            if w in a.lower():
                return a
    return None


def predict_ai(home, away, h_pct, a_pct, ev, today):
    client = _get_gemini()
    if not client:
        return None
    h_name = home.get("name", "Home")
    a_name = away.get("name", "Away")
    phase = ((ev.get("roundInfo") or {}).get("name") or
             str((ev.get("roundInfo") or {}).get("round") or "Sezon zasadniczy"))

    h_w = round(h_pct * 34)
    h_l = 34 - h_w
    a_w = round(a_pct * 34)
    a_l = 34 - a_w

    prompt = f"""
=========================================================================
SYSTEM
=========================================================================
Jesteś ekspertem koszykarskim BBL (easyCredit Basketball Bundesliga, Niemcy).
DZISIEJSZA DATA: {today}. Twoja wiedza jest przestarzała - sprawdzaj przez
Google Search. NIE ZGADUJ. Brak danych = "brak danych".

=========================================================================
MECZ DZISIAJ
=========================================================================
Liga:      BBL easyCredit Bundesliga (Niemcy)
Faza:      {phase}
GOSPODARZ: {h_name}
GOŚĆ:      {a_name}

=========================================================================
DANE STATYSTYCZNE (sezon 2025/26)
=========================================================================
BILANS:
   {h_name}: ~{h_w}-{h_l} ({h_pct:.0%} skuteczność)
   {a_name}: ~{a_w}-{a_l} ({a_pct:.0%} skuteczność)

=========================================================================
ZADANIE - Google Search dla każdego punktu:
=========================================================================
1. KONTUZJE i ZMIANY W SKŁADZIE na {today}:
   - basketball-bundesliga.de, sport1.de, spox.com, bild.de
   - Twitter/X klubów ({h_name}, {a_name})
   - Czy kluczowy gracz jest niezdolny do gry?

2. FORMA 5 OSTATNICH MECZÓW obu drużyn w BBL:
   - Seria zwycięstw/porażek
   - Wyniki domowe vs. wyjazdowe

3. H2H W TYM SEZONIE (2025/26):
   - Ile razy się spotkali? Kto wygrał?
   - Jeśli playoff: stan serii (np. 2-1)?

4. KONTEKST FAZY PLAYOFF:
   - Stan serii (np. Bayern 2-1 Trier)?
   - Mecz decydujący = "desperation factor" dla drużyny w zagrożeniu
   - Przewaga własnego parkietu w BBL playoffs

5. TOP GRACZE - wyszukaj aktualną formę liderów:
   - {h_name}: kto jest kluczowym graczem?
   - {a_name}: kto jest kluczowym graczem?

WAGA SYGNAŁÓW (od najważniejszego):
   1. Aktualne kontuzje liderów (dziś)
   2. Stan serii playoff + desperation factor
   3. Forma 5 ostatnich meczów
   4. Przewaga domowa
   5. H2H w sezonie
   6. Bilans sezonowy (win%)

=========================================================================
ODPOWIEDŹ - czysty JSON, bez markdown
=========================================================================
{{
  "winner_name": "<dokładna nazwa: '{h_name}' lub '{a_name}'>",
  "confidence": <1-10>,
  "reasoning": "<2-3 zdania po polsku>",
  "key_factors": ["<czynnik 1>", "<czynnik 2>", "<czynnik 3>"],
  "injury_notes": "<co znalazłeś na dziś lub 'brak istotnych braków'>",
  "agreement_with_odds": "no_odds"
}}
"""
    try:
        from google.genai import types
        resp = None
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=AI_MODEL, contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(google_search=types.GoogleSearch())]
                    )
                )
                break
            except Exception as e:
                if any(x in str(e) for x in ("503", "UNAVAILABLE", "429")):
                    time.sleep(5 * (attempt + 1))
                    continue
                raise
        if resp is None:
            return None
        text = (resp.text or "").strip()
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group())
        winner = _norm_name(data.get("winner_name"), h_name, a_name)
        if not winner:
            return None
        return {
            "winner": winner,
            "confidence": int(data.get("confidence", 5)),
            "reasoning": data.get("reasoning", ""),
            "key_factors": data.get("key_factors", []),
            "injury_notes": data.get("injury_notes", ""),
        }
    except Exception as e:
        print(f"   ! AI BBL: {e}")
        return None


def predict(ev, pct_map, today_slug):
    home = ev.get("homeTeam") or {}
    away = ev.get("awayTeam") or {}
    h_name = home.get("name", "Home")
    a_name = away.get("name", "Away")
    h_id = home.get("id")
    a_id = away.get("id")
    h_pct = pct_map.get(h_id, 0.0)
    a_pct = pct_map.get(a_id, 0.0)
    formula = h_name if (h_pct + 0.05) > a_pct else a_name

    def _r(winner, reasoning="", key_factors=None, confidence=None, injury_notes=""):
        return {"winner": winner, "reasoning": reasoning,
                "key_factors": key_factors or [], "confidence": confidence,
                "injury_notes": injury_notes}

    state = sofa_game_status(ev)
    if state == "post":
        return _r(formula)

    ts = ev.get("startTimestamp")
    if ts:
        try:
            if datetime.fromtimestamp(int(ts), tz=CET) <= datetime.now(CET):
                print(f"   [TIME-skip] {a_name} vs {h_name} -> formula")
                return _r(formula)
        except Exception:
            pass

    if USE_AI_PREDICTIONS:
        result = predict_ai(home, away, h_pct, a_pct, ev, today_slug)
        if result:
            print(f"   [AI] {a_name} vs {h_name} -> {result['winner']} (conf {result['confidence']}/10)")
            _ai_log.append({
                "matchup": f"{a_name} @ {h_name}",
                "phase": ((ev.get("roundInfo") or {}).get("name") or "?"),
                "ai_pick": result["winner"],
                "formula_pick": formula,
                "agreement": result["winner"] == formula,
                "confidence": result["confidence"],
                "reasoning": result["reasoning"],
                "key_factors": result["key_factors"],
                "injury_notes": result.get("injury_notes", ""),
            })
            time.sleep(1)
            return _r(result["winner"], result["reasoning"], result["key_factors"],
                      result["confidence"], result.get("injury_notes", ""))
        _ai_log.append({"matchup": f"{a_name} @ {h_name}", "ai_pick": None,
                        "formula_pick": formula, "note": "AI fallback"})
    return _r(formula)


def save_ai_log(today_slug):
    if not _ai_log:
        return
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "ai_analyses.json"), "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now().isoformat(), "date": today_slug,
                   "league": "BBL", "model": AI_MODEL, "matches": _ai_log},
                  f, indent=2, ensure_ascii=False)
    bar = "=" * 72
    print(f"\n{bar}\n   ANALIZY AI / DEV PRINT  (BBL)\n{bar}")
    for i, m in enumerate(_ai_log, 1):
        ai = m.get("ai_pick")
        if not ai:
            print(f"\n   [{i}] {m['matchup']}: BRAK AI -> {m.get('formula_pick')}")
            continue
        print(f"\n   [{i}] {m['matchup']}  [{m.get('phase') or '-'}]")
        print(f"       AI pick: {ai}  (conf {m.get('confidence')}/10)")
        print(textwrap.fill(m.get("reasoning") or "(brak)", width=72,
                            initial_indent="       Reason:  ",
                            subsequent_indent="                "))
    print(f"\n{bar}\n")


def save_picks(picks, today_slug):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "propozycje_typow.txt"), "w", encoding="utf-8") as f:
        f.write(f"# BBL typy na {today_slug}\n")
        f.write("\n".join(picks))
    print(f"   Zapisano {len(picks)} typów")


CSS = f"""
:root{{--bg:#0f172a;--card:#1e293b;--acc:{BRAND_ACCENT};--tx:#f8fafc;
      --sub:#94a3b8;--win:#10b981;--br:#334155;}}
*{{box-sizing:border-box;}}
body{{background:var(--bg);color:var(--tx);font-family:'Montserrat',sans-serif;margin:0;padding:20px;}}
.container{{max-width:1200px;margin:0 auto;}}
header{{text-align:center;margin-bottom:40px;padding-bottom:20px;border-bottom:1px solid var(--br);}}
h1{{font-weight:900;letter-spacing:-1px;margin:0;color:var(--acc);font-size:2.5rem;}}
.sub{{color:var(--sub);font-size:.9rem;text-transform:uppercase;letter-spacing:1px;margin-top:10px;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(450px,1fr));gap:25px;}}
.card{{background:var(--card);border:1px solid var(--br);border-radius:20px;overflow:hidden;
       display:flex;flex-direction:column;box-shadow:0 10px 15px -3px rgba(0,0,0,.2);
       transition:transform .2s;}}
.card:hover{{transform:translateY(-5px);border-color:var(--acc);}}
.card-h{{background:rgba(0,0,0,.3);padding:12px 25px;text-align:center;border-bottom:1px solid var(--br);
         font-size:.75rem;font-weight:900;color:var(--sub);text-transform:uppercase;}}
.card-h.live{{color:#ef4444;animation:pulse 1.5s infinite;}}
.matchup{{display:flex;justify-content:space-between;padding:30px 20px;flex-grow:1;gap:12px;}}
.team{{text-align:center;flex:1;display:flex;flex-direction:column;align-items:center;gap:14px;}}
.team img{{width:100px;height:100px;object-fit:contain;background:rgba(255,255,255,.04);border-radius:12px;padding:6px;}}
.team-name{{font-weight:900;font-size:.85rem;text-transform:uppercase;word-wrap:break-word;}}
.scores{{display:flex;align-items:center;justify-content:center;gap:15px;}}
.score{{font-size:2.8rem;font-weight:900;}}
.score.win{{color:var(--win);}}
.score.lose{{color:var(--sub);opacity:.8;}}
.vs{{color:var(--br);font-style:italic;font-weight:900;font-size:1.5rem;}}
.pred{{background:rgba(15,23,42,.6);padding:20px;text-align:center;border-top:1px solid var(--br);margin-top:auto;}}
.pred-l{{font-size:.7rem;color:var(--sub);text-transform:uppercase;font-weight:700;letter-spacing:1px;margin-bottom:8px;}}
.pred-v{{font-size:1.2rem;font-weight:900;}}
.empty{{text-align:center;color:#888;padding:60px 20px;}}
.empty .ico{{font-size:3rem;display:block;margin-bottom:16px;}}
.footer{{text-align:center;color:var(--sub);font-size:.75rem;margin-top:50px;padding-bottom:20px;}}
@keyframes pulse{{0%,100%{{opacity:1;}}50%{{opacity:.5;}}}}
"""


def build_cards(games, pct_map, today_slug):
    cards = []
    picks = []
    summaries = []
    for ev in games:
        try:
            home = ev.get("homeTeam") or {}
            away = ev.get("awayTeam") or {}
            h_name = home.get("name", "?")
            a_name = away.get("name", "?")
            h_logo = sofa_team_logo(home)
            a_logo = sofa_team_logo(away)
            h_score = sofa_score(ev, "home")
            a_score = sofa_score(ev, "away")
            state = sofa_game_status(ev)
            pred = predict(ev, pct_map, today_slug)
            pick = pred["winner"]
            ai_reasoning = pred.get("reasoning", "")
            ai_factors = pred.get("key_factors") or []
            ai_confidence = pred.get("confidence")
            ai_injury = pred.get("injury_notes", "")

            if state == "pre":
                tip = sofa_fmt_time(ev)
                status = tip or "Scheduled"
                score_html = '<span class="vs">VS</span>'
                picks.append(f"{a_name} @ {h_name} -> Typ: {pick}")
                summaries.append(f"{a_name} vs {h_name}: AI prediction - {pick} to win")
                outcome = ""
            elif state == "in":
                status = "LIVE"
                score_html = f'<span class="score">{a_score}</span><span class="vs">:</span><span class="score">{h_score}</span>'
                outcome = ""
            else:
                status = "Final"
                actual = h_name if h_score > a_score else (a_name if a_score > h_score else "")
                hc = "score win" if h_score > a_score else ("score lose" if h_score < a_score else "score")
                ac = "score win" if a_score > h_score else ("score lose" if a_score < h_score else "score")
                score_html = f'<span class="{ac}">{a_score}</span><span class="vs">:</span><span class="{hc}">{h_score}</span>'
                outcome = (' <span style="color:#10b981">&#10003;</span>' if actual and pick == actual
                           else (' <span style="color:#ef4444">&#10007;</span>' if actual else ""))

            # AI reasoning block
            reasoning_html = ""
            if state == "pre" and ai_reasoning:
                conf_badge = (f'<span style="background:#1e3a5f;color:#60a5fa;font-size:.7rem;'
                              f'font-weight:900;padding:3px 8px;border-radius:20px;margin-left:8px;">'
                              f'Pewność: {ai_confidence}/10</span>') if ai_confidence else ""
                factors_html = ""
                if ai_factors:
                    li_items = "".join(f'<li style="margin-bottom:4px;">{f}</li>' for f in ai_factors)
                    factors_html = (f'<ul style="margin:10px 0 0 0;padding-left:18px;'
                                    f'color:#94a3b8;font-size:.78rem;line-height:1.5;">{li_items}</ul>')
                injury_html = ""
                if ai_injury:
                    injury_html = (f'<div style="margin-top:8px;padding:8px 10px;'
                                   f'background:rgba(239,68,68,.08);border-radius:8px;'
                                   f'color:#fca5a5;font-size:.75rem;">🩹 {ai_injury}</div>')
                reasoning_html = f"""
              <div style="background:rgba(15,23,42,.8);border-top:1px solid #334155;padding:16px 20px;">
                <div style="font-size:.65rem;color:#64748b;text-transform:uppercase;font-weight:700;
                            letter-spacing:1px;margin-bottom:8px;">🤖 AI Reasoning{conf_badge}</div>
                <div style="color:#cbd5e1;font-size:.82rem;line-height:1.6;">{ai_reasoning}</div>
                {factors_html}
                {injury_html}
              </div>"""

            live_class = " live" if state == "in" else ""
            cards.append(f"""
            <div class="card">
              <div class="card-h{live_class}">{status}</div>
              <div class="matchup">
                <div class="team">
                  <img src="{a_logo}" alt="{a_name}" onerror="this.src='{DEFAULT_LOGO}'">
                  <span class="team-name">{a_name}</span>
                </div>
                <div class="scores">{score_html}</div>
                <div class="team">
                  <img src="{h_logo}" alt="{h_name}" onerror="this.src='{DEFAULT_LOGO}'">
                  <span class="team-name">{h_name}</span>
                </div>
              </div>
              <div class="pred">
                <div class="pred-l">Public AI Model Picks</div>
                <div class="pred-v">{pick}{outcome}</div>
              </div>
              {reasoning_html}
            </div>""")
        except Exception as e:
            print(f"   Błąd przy meczu BBL: {e}")
    return "".join(cards), picks, summaries


def build_page(title_date, cards_html, summaries):
    desc = " | ".join(summaries[:4]) or f"BBL AI picks for {title_date}"
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>BBL AI Picks {title_date} - easyCredit Bundesliga</title>
  <meta name="description" content="{desc[:160]}">
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800;900&display=swap" rel="stylesheet">
  <style>{CSS}</style>
</head>
<body>
  <div class="container">
    <header>
      <img src="https://www.proballers.com/api/getLeagueLogo?id=118&width=300"
           alt="BBL logo"
           onerror="this.style.display='none'"
           style="height:70px;object-fit:contain;margin-bottom:12px;display:block;margin-left:auto;margin-right:auto;">
      <h1>{BRAND_TITLE}</h1>
      <div class="sub">{LEAGUE_NAME} &middot; Live Scores &amp; AI Model Picks &mdash; {title_date}</div>
    </header>
    <div class="grid">
      {cards_html or '<div class="empty"><span class="ico">&#127936;</span>Brak meczów BBL na dziś.</div>'}
    </div>
    <div class="footer">
      Last updated: {datetime.now().strftime("%B %d, %Y at %H:%M")} &middot; Data: Sofascore
    </div>
  </div>
</body>
</html>"""


def main():
    print(f"=== URUCHAMIAM BBL UPDATE ({datetime.now().strftime('%H:%M')}) ===")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    today_slug = get_today_str()
    today_str = datetime.now().strftime("%B %d, %Y")
    print(f"   Data: {today_slug}")

    if USE_AI_PREDICTIONS and os.environ.get("GEMINI_API_KEY"):
        print(f"   Tryb: AI ({AI_MODEL})")
    else:
        print(f"   Tryb: FORMULA W-L")

    season_id = fetch_sofa_season_id()
    if not season_id:
        print("!! Brak season_id BBL - pusta strona")
        with open(os.path.join(OUTPUT_DIR, "index.html"), "w") as f:
            f.write(build_page(today_str, "", []))
        return

    pct_map = fetch_sofa_standings(season_id)
    games = fetch_sofa_games_today(season_id, today_slug)
    data_source = "Sofascore"

    # Fallback 1: 24score.com scraper
    if not games:
        print("   [FALLBACK-1] Sofascore zablokowane - próbuję 24score.com...")
        try:
            import score24_data
            games = score24_data.fetch_games_today("bbl", today_slug)
            if games:
                data_source = "24score.com"
                if not pct_map:
                    pct_map = score24_data.fetch_standings("bbl")
        except Exception as e:
            print(f"   [FALLBACK-1] 24score błąd: {e}")

    # Fallback 2: Gemini Google Search
    if not games and os.environ.get("GEMINI_API_KEY"):
        print("   [FALLBACK-2] Próbuję Gemini Google Search...")
        games = fetch_games_via_ai(today_slug)
        if games:
            data_source = "Gemini Search"

    cards_html, picks, summaries = build_cards(games, pct_map, today_slug)

    out = os.path.join(OUTPUT_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build_page(today_str, cards_html, summaries))
    print(f"\n-> Zapisano {out}")

    if picks:
        save_picks(picks, today_slug)
    else:
        print("   Brak typów pre-game.")

    save_ai_log(today_slug)
    print(f"\n=== GOTOWE. Otworz {out} ===")


if __name__ == "__main__":
    main()
