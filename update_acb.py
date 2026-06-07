"""
ACB (Liga Endesa, Hiszpania) Free Picks - generator typow.

Zrodlo danych (w kolejnosci prob):
  1. Sofascore public API (tournament_id=4408)
  2. 24score.com scraper (score24_data.py)
  3. Gemini Google Search - ostateczny fallback

UI: league_ui.py (wspolny szablon dla wszystkich lig).

KLUCZOWA LOGIKA UTRWALANIA TYPOW:
  Jezeli ai_analyses.json zawiera dzisiejsza date -> wczytaj typ z pliku.
  Nie generuj nowego. Zapobiega nadpisywaniu AI typow przez pozniejszy run.

URUCHOMIENIE LOKALNE:
    pip install requests google-genai pytz
    export GEMINI_API_KEY=...
    python update_acb.py

Wynik: acb/index.html
"""

import os
import re
import json
import time
import textwrap
from datetime import datetime, timezone, timedelta

import requests

# ==========================================
# KONFIGURACJA
# ==========================================
LEAGUE_NAME        = "Liga Endesa (ACB)"
OUTPUT_DIR         = "acb"
DEBUG_DIR          = "acb/_debug"
SOFA_TOURNAMENT_ID = 4408
SOFA_SEASON_ID     = 80922   # fallback gdy API niedostepne

USE_AI_PREDICTIONS = os.environ.get("PLK_LIVE_MODE", "").lower() not in ("true", "1", "yes")
AI_MODEL           = "gemini-2.5-flash"

BRAND_TITLE  = "ACB PUBLIC HUB"
BRAND_ACCENT = "#f59e0b"

CET = timezone(timedelta(hours=2))

SOFA_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "es,en-US;q=0.9,en;q=0.8",
    "Referer":         "https://www.sofascore.com/",
}

DEFAULT_LOGO = (
    "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    "<circle cx='50' cy='50' r='44' fill='none' stroke='%23f59e0b' stroke-width='3'/>"
    "<text y='62' x='50' text-anchor='middle' font-size='42' fill='%23f59e0b'>"
    "%F0%9F%8F%80</text></svg>"
)

# Sofascore team IDs dla ACB (z URL: sofascore.com/basketball/team/name/ID)
ACB_LOGOS = {
    "Real Madrid":       "https://api.sofascore.app/api/v1/team/3540/image",
    "Barcelona":         "https://api.sofascore.app/api/v1/team/3543/image",
    "Baskonia":          "https://api.sofascore.app/api/v1/team/3553/image",
    "Murcia":            "https://api.sofascore.app/api/v1/team/3555/image",
    "Valencia":          "https://api.sofascore.app/api/v1/team/3545/image",
    "Tenerife":          "https://api.sofascore.app/api/v1/team/78043/image",
    "Unicaja":           "https://api.sofascore.app/api/v1/team/3556/image",
    "Joventut Badalona": "https://api.sofascore.app/api/v1/team/3544/image",
    "Bilbao":            "https://api.sofascore.app/api/v1/team/5615/image",
    "Gran Canaria":      "https://api.sofascore.app/api/v1/team/3554/image",
    "Breogan":           "https://api.sofascore.app/api/v1/team/3547/image",
    "Andorra":           "https://api.sofascore.app/api/v1/team/3548/image",
    "Manresa":           "https://api.sofascore.app/api/v1/team/3552/image",
    "Girona":            "https://api.sofascore.app/api/v1/team/3551/image",
    "Zaragoza":          "https://api.sofascore.app/api/v1/team/3549/image",
    "Burgos":            "https://api.sofascore.app/api/v1/team/3557/image",
    "Lleida":            "https://api.sofascore.app/api/v1/team/3558/image",
    "Granada":           "https://api.sofascore.app/api/v1/team/3559/image",
}

_gemini_client = None
_ai_log        = []


# ==========================================
# HELPERS
# ==========================================

def get_today_str():
    return datetime.now(CET).strftime("%Y-%m-%d")


def _save_debug(name, data):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    try:
        with open(os.path.join(DEBUG_DIR, f"sofa_{name}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def load_saved_predictions(today_slug):
    """
    Wczytuje typy AI z ai_analyses.json jezeli sa z dzisiaj.
    Zwraca dict {matchup_key: pred_dict} lub pusty dict.
    """
    path = os.path.join(OUTPUT_DIR, "ai_analyses.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") != today_slug:
            return {}
        saved = {}
        for m in data.get("matches", []):
            matchup = m.get("matchup", "")
            if matchup and m.get("ai_pick"):
                saved[matchup] = {
                    "winner":       m["ai_pick"],
                    "reasoning":    m.get("reasoning", ""),
                    "key_factors":  m.get("key_factors", []),
                    "confidence":   m.get("confidence"),
                    "injury_notes": m.get("injury_notes", ""),
                }
        print(f"   [cache] Wczytano {len(saved)} typow z ai_analyses.json ({today_slug})")
        return saved
    except Exception as e:
        print(f"   [cache] Blad: {e}")
        return {}


def save_picks(picks, today_slug):
    path = os.path.join(OUTPUT_DIR, "propozycje_typow.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# ACB typy na {today_slug}\n")
        f.write("\n".join(picks))
    print(f"   Zapisano {len(picks)} typow")


# ==========================================
# SOFASCORE
# ==========================================

def _sofa_fetch(url):
    try:
        r = requests.get(url, headers=SOFA_HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json()
        print(f"   [sofa] HTTP {r.status_code}: {url}")
        return None
    except Exception as e:
        print(f"   [sofa] Blad: {e}")
        return None


def fetch_sofa_season_id():
    data = _sofa_fetch(
        f"https://api.sofascore.com/api/v1/unique-tournament/{SOFA_TOURNAMENT_ID}/seasons"
    )
    if not data:
        print(f"   [sofa] ACB /seasons niedostepne - fallback id={SOFA_SEASON_ID}")
        return SOFA_SEASON_ID
    seasons = data.get("seasons") or []
    if seasons:
        sid = seasons[0].get("id", SOFA_SEASON_ID)
        print(f"   [sofa] ACB season_id={sid}")
        return sid
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
    print(f"   [sofa] ACB mecze na {today_slug}: {len(games)}")
    return games


def fetch_sofa_standings(season_id):
    data = _sofa_fetch(
        f"https://api.sofascore.com/api/v1/unique-tournament/{SOFA_TOURNAMENT_ID}"
        f"/season/{season_id}/standings/total"
    )
    if not data:
        return {}
    pct_map = {}
    for row in (data.get("standings") or [{}])[0].get("rows", []):
        team = row.get("team") or {}
        tid  = team.get("id")
        wins = row.get("wins", 0)
        losses = row.get("losses", 0)
        total  = wins + losses
        if tid and total > 0:
            pct_map[tid] = round(wins / total, 3)
    print(f"   [sofa] ACB standings: {len(pct_map)} druzyn")
    return pct_map


def sofa_game_status(ev):
    stype = (ev.get("status") or {}).get("type", "")
    if stype == "finished":
        return "post"
    if stype == "inprogress":
        return "in"
    return "pre"


def sofa_fmt_time(ev):
    ts = ev.get("startTimestamp")
    if not ts:
        return ""
    try:
        dt = datetime.fromtimestamp(int(ts), tz=CET)
        return dt.strftime("%H:%M CET")
    except Exception:
        return ""


def sofa_score(ev, side):
    key = "homeScore" if side == "home" else "awayScore"
    return int((ev.get(key) or {}).get("current", 0))


def sofa_team_logo(team):
    tid  = (team or {}).get("id")
    name = (team or {}).get("name", "")
    if tid:
        return f"https://api.sofascore.app/api/v1/team/{tid}/image"
    return ACB_LOGOS.get(name, DEFAULT_LOGO)


# ==========================================
# FALLBACK: 24score + Gemini
# ==========================================

def fetch_games_via_24score(today_slug):
    try:
        import score24_data
        games = score24_data.fetch_games_today("acb", today_slug)
        if games:
            print(f"   [24score] ACB: {len(games)} meczow")
        return games
    except Exception as e:
        print(f"   [24score] Blad: {e}")
        return []


def fetch_games_via_ai(today_slug):
    client = _get_gemini()
    if not client:
        return []
    prompt = f"""Podaj dzisiejsze mecze ACB (Liga Endesa, Hiszpania) na date {today_slug}.
Uzyj Google Search (acb.com, marca.com, sport.es, as.com).

Odpowiedz TYLKO czystym JSON (bez markdown):
[
  {{
    "home": "<nazwa gospodarzy>",
    "away": "<nazwa gosci>",
    "time_cet": "<godzina CET np. 20:30>",
    "status": "pre",
    "phase": "<faza np. Playoff lub Regular Season>"
  }}
]
Jesli brak meczow na {today_slug} zwroc: []"""
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
            return []
        games_raw = json.loads(m.group())
        events = []
        for g in games_raw:
            home_name = g.get("home", "")
            away_name = g.get("away", "")
            if not home_name or not away_name:
                continue
            ts = None
            try:
                dt = datetime.strptime(
                    f"{today_slug} {g.get('time_cet','20:00')}",
                    "%Y-%m-%d %H:%M"
                ).replace(tzinfo=CET)
                ts = int(dt.timestamp())
            except Exception:
                pass
            events.append({
                "homeTeam":       {"name": home_name, "id": None},
                "awayTeam":       {"name": away_name, "id": None},
                "startTimestamp": ts,
                "status":         {"type": "notstarted"},
                "homeScore":      {"current": 0},
                "awayScore":      {"current": 0},
                "roundInfo":      {"name": g.get("phase", "ACB")},
                "_source":        "gemini_search",
            })
        print(f"   [AI-games] ACB: {len(events)} meczow")
        return events
    except Exception as e:
        print(f"   [AI-games] Blad: {e}")
        return []


# ==========================================
# AI PREDICTIONS
# ==========================================

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
            if w in h.lower(): return h
            if w in a.lower(): return a
    return None


def predict_ai(home, away, h_pct, a_pct, ev, today):
    client = _get_gemini()
    if not client:
        return None
    h_name = home.get("name", "Home")
    a_name = away.get("name", "Away")
    phase  = ((ev.get("roundInfo") or {}).get("name") or "Sezon zasadniczy")
    h_w    = round(h_pct * 34)
    h_l    = 34 - h_w
    a_w    = round(a_pct * 34)
    a_l    = 34 - a_w

    prompt = f"""
=========================================================================
SYSTEM
=========================================================================
Jestes ekspertem koszykarskim ACB (Liga Endesa, Hiszpania).
DZISIEJSZA DATA: {today}. Twoja wiedza jest przestarzala - sprawdzaj przez
Google Search. NIE ZGADUJ. Brak danych = "brak danych".

=========================================================================
MECZ DZISIAJ
=========================================================================
Liga:      ACB Liga Endesa (Hiszpania)
Faza:      {phase}
GOSPODARZ: {h_name}
GOSC:      {a_name}

=========================================================================
DANE STATYSTYCZNE (sezon 2025/26)
=========================================================================
BILANS:
   {h_name}: ~{h_w}-{h_l} ({h_pct:.0%})
   {a_name}: ~{a_w}-{a_l} ({a_pct:.0%})

=========================================================================
ZADANIE - Google Search dla kazdego punktu:
=========================================================================
1. KONTUZJE na {today}: acb.com, marca.com, sport.es, as.com, mundobasket.es
   Twitter/X klubow ({h_name}, {a_name})
2. FORMA 5 OSTATNICH MECZOW obu druzyn w ACB
3. H2H W TYM SEZONIE - jesli playoff: stan serii?
4. KONTEKST FAZY: playoff = wazniejszy home court (~60-65%)
5. TOP GRACZE - aktualna forma liderow obu druzyn

WAGA SYGNALOW:
   1. Kontuzje liderow  2. Forma/streak  3. Home court playoff
   4. H2H serii  5. Bilans sezonowy

ODPOWIEDZ - czysty JSON, bez markdown:
{{
  "winner_name": "<dokladna nazwa: '{h_name}' lub '{a_name}'>",
  "confidence": <1-10>,
  "reasoning": "<2-3 zdania po polsku>",
  "key_factors": ["<czynnik 1>", "<czynnik 2>", "<czynnik 3>"],
  "injury_notes": "<co znalazles na DZIS lub 'brak istotnych brakow'>",
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
        m    = re.search(r'\{.*\}', text, re.DOTALL)
        if not m:
            return None
        data   = json.loads(m.group())
        winner = _norm_name(data.get("winner_name"), h_name, a_name)
        if not winner:
            return None
        return {
            "winner":       winner,
            "confidence":   int(data.get("confidence", 5)),
            "reasoning":    data.get("reasoning", ""),
            "key_factors":  data.get("key_factors", []),
            "injury_notes": data.get("injury_notes", ""),
        }
    except Exception as e:
        print(f"   ! AI ACB: {e}")
        return None


def predict(ev, pct_map, today_slug, saved_predictions=None):
    """
    Zwraca dict {winner, reasoning, key_factors, confidence, injury_notes}.
    Jezeli saved_predictions zawiera dzisiejszy typ -> uzywa go bez AI.
    """
    home        = ev.get("homeTeam") or {}
    away        = ev.get("awayTeam") or {}
    h_name      = home.get("name", "Home")
    a_name      = away.get("name", "Away")
    h_id        = home.get("id")
    a_id        = away.get("id")
    h_pct       = pct_map.get(h_id, 0.0)
    a_pct       = pct_map.get(a_id, 0.0)
    formula     = h_name if (h_pct + 0.05) > a_pct else a_name
    matchup_key = f"{a_name} @ {h_name}"

    def _r(winner, reasoning="", key_factors=None, confidence=None, injury_notes=""):
        return {"winner": winner, "reasoning": reasoning,
                "key_factors": key_factors or [], "confidence": confidence,
                "injury_notes": injury_notes or ""}

    # KLUCZOWE: uzyj zapisanego typu jesli istnieje
    if saved_predictions and matchup_key in saved_predictions:
        saved = saved_predictions[matchup_key]
        print(f"   [cache] {matchup_key} -> {saved['winner']}")
        return _r(**saved)

    state = sofa_game_status(ev)
    if state == "post":
        return _r(formula)

    ts = ev.get("startTimestamp")
    if ts:
        try:
            if datetime.fromtimestamp(int(ts), tz=CET) <= datetime.now(CET):
                print(f"   [TIME-skip] {matchup_key} -> formula")
                return _r(formula)
        except Exception:
            pass

    if USE_AI_PREDICTIONS:
        result = predict_ai(home, away, h_pct, a_pct, ev, today_slug)
        if result:
            print(f"   [AI] {matchup_key} -> {result['winner']} (conf {result['confidence']}/10)")
            _ai_log.append({
                "matchup":      matchup_key,
                "phase":        ((ev.get("roundInfo") or {}).get("name") or "?"),
                "ai_pick":      result["winner"],
                "formula_pick": formula,
                "agreement":    result["winner"] == formula,
                "confidence":   result["confidence"],
                "reasoning":    result["reasoning"],
                "key_factors":  result["key_factors"],
                "injury_notes": result.get("injury_notes", ""),
            })
            time.sleep(1)
            return _r(result["winner"], result["reasoning"], result["key_factors"],
                      result["confidence"], result.get("injury_notes", ""))
        print(f"   [FORMULA-fallback] {matchup_key} -> {formula}")
        _ai_log.append({"matchup": matchup_key, "ai_pick": None,
                        "formula_pick": formula, "note": "AI fallback"})
    return _r(formula)


def save_ai_log(today_slug):
    if not _ai_log:
        return
    path = os.path.join(OUTPUT_DIR, "ai_analyses.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "date":         today_slug,
            "league":       "ACB",
            "model":        AI_MODEL,
            "matches":      _ai_log,
        }, f, indent=2, ensure_ascii=False)
    print(f"   Zapisano ai_analyses.json")

    bar = "=" * 72
    print(f"\n{bar}\n   ANALIZY AI / DEV PRINT  (ACB)\n{bar}")
    for i, m in enumerate(_ai_log, 1):
        ai = m.get("ai_pick")
        if not ai:
            print(f"\n   [{i}] {m['matchup']}: BRAK AI -> {m.get('formula_pick')}")
            continue
        conf = m.get("confidence", "?")
        ag   = "ZGODNE" if m.get("agreement") else "ROZNI sie"
        print(f"\n   [{i}] {m['matchup']}  ({m.get('phase') or '-'})")
        print(f"       AI pick:  {ai}  (conf {conf}/10)  [{ag}]")
        print(textwrap.fill(m.get("reasoning") or "(brak)", width=72,
                            initial_indent="       Reason:   ",
                            subsequent_indent="                 "))
        for f in (m.get("key_factors") or []):
            print(f"         - {f}")
        inj = (m.get("injury_notes") or "").strip()
        if inj and "brak" not in inj.lower():
            print(textwrap.fill(inj, width=72,
                                initial_indent="       Kontuzje: ",
                                subsequent_indent="                 "))
    print(f"\n{bar}\n")


# ==========================================
# BUILD CARDS
# ==========================================

def build_cards(games, pct_map, today_slug, saved_predictions=None):
    from league_ui import render_card
    cards        = []
    picks        = []
    summaries    = []
    matches_data = {}

    for ev in games:
        try:
            home    = ev.get("homeTeam") or {}
            away    = ev.get("awayTeam") or {}
            h_name  = home.get("name", "?")
            a_name  = away.get("name", "?")
            h_logo  = sofa_team_logo(home)
            a_logo  = sofa_team_logo(away)
            h_score = sofa_score(ev, "home")
            a_score = sofa_score(ev, "away")

            state = sofa_game_status(ev)
            pred  = predict(ev, pct_map, today_slug, saved_predictions)
            pick  = pred["winner"]

            if state == "pre":
                status = sofa_fmt_time(ev) or "Scheduled"
                picks.append(f"{a_name} @ {h_name} -> Typ: {pick}")
                summaries.append(f"{a_name} vs {h_name}: AI - {pick}")
            elif state == "in":
                status = "LIVE"
            else:
                status = "Final"
                actual = h_name if h_score > a_score else (a_name if a_score > h_score else "")
                if actual:
                    summaries.append(f"{a_name} vs {h_name}: picked {pick}, "
                                     f"{actual} won {max(h_score,a_score)}-{min(h_score,a_score)}")

            game_id = f"acb_{ev.get('id') or id(ev)}"
            cards.append(render_card(
                game_id, h_name, a_name, h_logo, a_logo,
                h_score, a_score, state, status, pred, DEFAULT_LOGO
            ))
            matches_data[game_id] = {
                "matchup":      f"{a_name} @ {h_name}",
                "pick":         pick,
                "reasoning":    pred.get("reasoning", ""),
                "key_factors":  pred.get("key_factors") or [],
                "confidence":   pred.get("confidence"),
                "injury_notes": pred.get("injury_notes", ""),
                "audit":        "",
            }
        except Exception as e:
            print(f"   Blad przy meczu ACB: {e}")

    return "".join(cards), picks, summaries, matches_data


# ==========================================
# BUILD PAGE
# ==========================================

def build_page(title_date, cards_html, summaries, matches_data=None):
    from league_ui import render_page
    return render_page(
        league_logo_url="https://www.proballers.com/api/getLeagueLogo?id=30&width=300",
        league_title=BRAND_TITLE,
        league_subtitle=f"{LEAGUE_NAME} \u00b7 Live Scores & Public AI Model Picks \u2014 {title_date}",
        cards_html=cards_html,
        matches_data=matches_data or {},
        last_updated=datetime.now().strftime("%B %d, %Y at %H:%M"),
        data_source="Sofascore / 24score",
        default_logo=DEFAULT_LOGO,
        league_accent=BRAND_ACCENT,
    )


# ==========================================
# MAIN
# ==========================================

def main():
    print(f"=== URUCHAMIAM ACB UPDATE ({datetime.now().strftime('%H:%M')}) ===")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(DEBUG_DIR, exist_ok=True)

    today_slug = get_today_str()
    today_str  = datetime.now(CET).strftime("%B %d, %Y")

    print(f"   Data: {today_slug} ({today_str})")
    if USE_AI_PREDICTIONS and os.environ.get("GEMINI_API_KEY"):
        print(f"   Tryb predykcji: AI ({AI_MODEL} + Google Search)")
    else:
        print(f"   Tryb predykcji: FORMULA W-L")

    # Wczytaj zapisane typy z dzisiaj
    saved_predictions = load_saved_predictions(today_slug)

    # PRIMARY: Sofascore
    print("\n=> Sofascore (primary):")
    season_id = fetch_sofa_season_id()
    pct_map   = fetch_sofa_standings(season_id)
    games     = fetch_sofa_games_today(season_id, today_slug)

    # FALLBACK 1: 24score
    if not games:
        print("=> Sofascore zablokowane - probuje 24score.com...")
        games = fetch_games_via_24score(today_slug)
        if games and not pct_map:
            try:
                import score24_data
                pct_map_raw = score24_data.fetch_standings("acb")
                # Konwertuj {name: pct} na {None: pct} - uzywamy name-based lookup
                pct_map = pct_map_raw
            except Exception:
                pass

    # FALLBACK 2: Gemini Google Search
    if not games and os.environ.get("GEMINI_API_KEY"):
        print("=> 24score niedostepne - probuje Gemini Google Search...")
        games = fetch_games_via_ai(today_slug)

    print(f"\n   Mecze na {today_slug}: {len(games)}")

    # Build
    cards_html, picks, summaries, matches_data = build_cards(
        games, pct_map, today_slug, saved_predictions
    )

    out = os.path.join(OUTPUT_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build_page(today_str, cards_html, summaries, matches_data))
    print(f"\n-> Zapisano {out}")

    if picks:
        save_picks(picks, today_slug)
    else:
        print("   Brak typow pre-game.")

    save_ai_log(today_slug)

    if not games:
        print(f"\n   Brak meczow ACB na {today_slug}.")

    print(f"\n=== GOTOWE ===")


if __name__ == "__main__":
    main()
