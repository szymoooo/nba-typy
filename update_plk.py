"""
PLK (Polska Liga Koszykowki / Orlen Basket Liga) Free Picks - generator typow.

Klon mechaniki update_euroleague.py, ale dla polskiej PLK.
Zrodlo danych: nieoficjalne JSON API Sofascore (free, no-auth, uzywane
przez ich publiczna strone). PLK = uniqueTournament id 263.

URUCHOMIENIE LOKALNE:
    pip install requests google-genai pytz
    export GEMINI_API_KEY=...   # opcjonalne, wlacza AI predictions
    python update_plk.py

Wynik: plk/index.html (otworz w przegladarce)
"""

import requests
import json
import os
import re
import time
from datetime import datetime, timezone, timedelta

# ==========================================
# KONFIGURACJA
# ==========================================
TOURNAMENT_ID = 263            # Sofascore uniqueTournament id dla PLK / Orlen Basket Liga
TOURNAMENT_NAME_PL = "Orlen Basket Liga"
OUTPUT_DIR = "plk"             # produkcyjny folder serwowany przez GH Pages jako /plk/
DEBUG_DIR = "plk/_debug"       # dumpy z API (debug)

# Wlacz/wylacz prawdziwa analize AI Gemini z Google Search.
USE_AI_PREDICTIONS = True
AI_MODEL = "gemini-2.5-flash"

BRAND_TITLE = "PLK PUBLIC HUB"
BRAND_ACCENT = "#dc2626"        # czerwien Polski / PLK
BRAND_DOMAIN = "https://nba-freepicks.com/plk/"

SOFA_BASE = "https://api.sofascore.com/api/v1"
SOFA_HEADERS = {
    # Sofascore zwraca 403 bez wiarygodnego User-Agenta
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/123.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.sofascore.com/",
}

DEFAULT_LOGO = (
    "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    "<circle cx='50' cy='50' r='44' fill='none' stroke='%23dc2626' stroke-width='3'/>"
    "<text y='62' x='50' text-anchor='middle' font-size='42' fill='%23dc2626'>"
    "%F0%9F%8F%80</text></svg>"
)


# ==========================================
# API CLIENT (Sofascore)
# ==========================================

def fetch_json(url, timeout=15):
    """Bezpieczne pobranie JSON. Zwraca (data, status, err_text)."""
    try:
        r = requests.get(url, headers=SOFA_HEADERS, timeout=timeout)
        if r.status_code != 200:
            return None, r.status_code, r.text[:300]
        return r.json(), 200, None
    except Exception as e:
        return None, None, str(e)[:300]


def _dump_debug(name, data):
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        path = os.path.join(DEBUG_DIR, f"debug_{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        print(f"        zapisano dump: {path}")
    except Exception:
        pass


def fetch_current_season_id():
    """Pobiera liste sezonow PLK i wybiera najnowszy (2025-26 lub kolejny)."""
    url = f"{SOFA_BASE}/unique-tournament/{TOURNAMENT_ID}/seasons"
    data, status, err = fetch_json(url)
    if not data:
        print(f"   [FAIL] /seasons -> HTTP {status} {err or ''}")
        return None
    _dump_debug("seasons", data)
    seasons = data.get("seasons") or []
    if not seasons:
        return None

    # Najnowsze sezony zwykle sa na poczatku listy. Probujemy wybrac taki
    # ktory zawiera "2025" w nazwie/yearze, w przeciwnym razie pierwszy z listy.
    for s in seasons:
        year = str(s.get("year") or "")
        if "25/26" in year or "2025/26" in year or "2025-26" in year or year.startswith("25"):
            print(f"   Wybrany sezon: {s.get('name')} (id={s.get('id')})")
            return s.get("id")
    s = seasons[0]
    print(f"   Wybrany sezon (fallback - pierwszy z listy): {s.get('name')} (id={s.get('id')})")
    return s.get("id")


def fetch_events_for_season(season_id, kind="next"):
    """kind = 'next' lub 'last'. Iteruje po stronach az do pustej."""
    all_events = []
    page = 0
    while page < 20:  # safety
        url = f"{SOFA_BASE}/unique-tournament/{TOURNAMENT_ID}/season/{season_id}/events/{kind}/{page}"
        data, status, err = fetch_json(url)
        if not data:
            if page == 0:
                print(f"   [FAIL] /events/{kind}/0 -> HTTP {status} {err or ''}")
            break
        if page == 0:
            _dump_debug(f"events_{kind}_p0", data)
        events = data.get("events") or []
        if not events:
            break
        all_events.extend(events)
        has_next = bool(data.get("hasNextPage"))
        if not has_next:
            break
        page += 1
        time.sleep(0.2)
    print(f"   /events/{kind} zwrocil {len(all_events)} meczow")
    return all_events


def fetch_standings_map(season_id):
    """Zwraca {team_id: win_pct} dla wszystkich druzyn."""
    url = f"{SOFA_BASE}/unique-tournament/{TOURNAMENT_ID}/season/{season_id}/standings/total"
    data, status, err = fetch_json(url)
    if not data:
        print(f"   [FAIL] /standings/total -> HTTP {status} {err or ''}")
        return {}
    _dump_debug("standings_total", data)

    pct_map = {}
    standings_list = data.get("standings") or []
    for table in standings_list:
        for row in table.get("rows") or []:
            team = row.get("team") or {}
            tid = team.get("id")
            wins = row.get("wins", 0) or 0
            losses = row.get("losses", 0) or 0
            try:
                wins, losses = int(wins), int(losses)
            except Exception:
                wins, losses = 0, 0
            total = wins + losses
            if tid:
                pct_map[tid] = (wins / total) if total > 0 else 0.0
    print(f"   Zaladowano statystyki dla {len(pct_map)} druzyn")
    return pct_map


# ==========================================
# HELPERS
# ==========================================

def get_today_date_str():
    """Lokalna data Polska (Europe/Warsaw, UTC+1/+2). Zwraca YYYY-MM-DD."""
    cet = timezone(timedelta(hours=2))  # CEST uproszczone
    return datetime.now(cet).strftime("%Y-%m-%d")


def filter_events_for_date(events, date_str):
    """Sofascore zwraca startTimestamp (unix UTC). Filtruj po lokalnej dacie PL."""
    cet = timezone(timedelta(hours=2))
    out = []
    for ev in events:
        ts = ev.get("startTimestamp")
        if not ts:
            continue
        try:
            dt = datetime.fromtimestamp(int(ts), tz=cet)
        except Exception:
            continue
        if dt.strftime("%Y-%m-%d") == date_str:
            out.append(ev)
    return out


def get_team_logo(team):
    """Zwraca URL do logo druzyny w Sofascore."""
    if not isinstance(team, dict):
        return DEFAULT_LOGO
    tid = team.get("id")
    if tid:
        return f"https://api.sofascore.app/api/v1/team/{tid}/image"
    return DEFAULT_LOGO


def map_status(ev):
    """Sofascore status -> ('pre'|'in'|'post', display_text)."""
    status = ev.get("status") or {}
    t = (status.get("type") or "").lower()
    desc = (status.get("description") or "").strip()
    if t in ("notstarted", "scheduled", "delayed", "postponed"):
        return "pre", desc or "Scheduled"
    if t in ("inprogress", "live"):
        return "in", desc or "LIVE"
    if t in ("finished", "ended", "afterextra", "afterpenalties"):
        return "post", "Final"
    return "pre", desc or "Scheduled"


def fmt_game_time(ts):
    """Unix timestamp -> 'HH:MM CET' (czas polski)."""
    if not ts:
        return ""
    try:
        cet = timezone(timedelta(hours=2))
        return datetime.fromtimestamp(int(ts), tz=cet).strftime("%H:%M") + " CET"
    except Exception:
        return ""


def get_score(ev, side):
    """side='home'|'away' -> int score (0 jesli brak)."""
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


def save_picks_for_audit(picks, today_slug):
    path = os.path.join(OUTPUT_DIR, "propozycje_typow.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# PLK typy na {today_slug}\n")
        f.write("\n".join(picks))
    print(f"   Zapisano {len(picks)} typow do {path}")


# ==========================================
# AI PREDICTIONS (Gemini + Google Search)
# ==========================================

_gemini_client = None
_ai_log = []


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    try:
        from google import genai
        _gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        return _gemini_client
    except ImportError:
        print("   ! Brak biblioteki google-genai. Zainstaluj: pip install google-genai")
        return None
    except Exception as e:
        print(f"   ! Blad inicjalizacji Gemini: {e}")
        return None


def _normalize_winner_name(ai_winner, h_name, a_name):
    if not ai_winner:
        return None
    ai_low = ai_winner.lower().strip()
    h_low = (h_name or "").lower()
    a_low = (a_name or "").lower()
    if ai_low == h_low:
        return h_name
    if ai_low == a_low:
        return a_name
    if ai_low in h_low or h_low in ai_low:
        return h_name
    if ai_low in a_low or a_low in ai_low:
        return a_name
    for word in ai_low.split():
        if len(word) >= 4:
            if word in h_low:
                return h_name
            if word in a_low:
                return a_name
    return None


def predict_winner_ai(home, away, h_pct, a_pct, game_context):
    client = _get_gemini_client()
    if client is None:
        return None

    h_name = home.get("name") or "Home"
    a_name = away.get("name") or "Away"
    phase = game_context.get("phase") or "Sezon zasadniczy"
    date_iso = game_context.get("date") or ""
    today = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""
Mecz polskiej PLK ({TOURNAMENT_NAME_PL}): {a_name} (gosc) vs {h_name} (gospodarz)
Faza: {phase}
Data meczu: {date_iso[:10]}
DZISIEJSZA DATA: {today}

Bilans w sezonie 2025-26 PLK:
  - {a_name}: {a_pct:.0%} skutecznosci
  - {h_name}: {h_pct:.0%} skutecznosci

ZADANIE: Wytypuj zwyciezce tego konkretnego meczu PLK.

PROCES (uzyj Google Search):
1. Sprawdz forme ostatnich 5 meczow obu druzyn w PLK
2. Sprawdz bezposrednie spotkania w sezonie 2025-26
3. Sprawdz kluczowe kontuzje na {today} (sport.pl, plk.pl, polskikosz.pl)
4. Uwzglednij specyfike fazy "{phase}":
   - Faza zasadnicza = forma + bilans
   - Play-off / cwiercfinal / polfinal / final = doswiadczenie kluczowe,
     parkiet domowy mocniej liczy
5. Sprawdz historyczne osiagniecia obu klubow w tej fazie

PRZYKLADAJ DUZA WAGE do:
- aktualnych kontuzji
- formy (ostatnie 5 meczow > caly sezon)
- atutu wlasnego parkietu w play-offach

Odpowiedz WYLACZNIE czystym JSON-em (bez markdown, bez komentarzy):
{{
  "winner_name": "<dokladna nazwa z dwoch: '{h_name}' lub '{a_name}'>",
  "confidence": <liczba 1-10 gdzie 10 = pewny>,
  "reasoning": "<2-3 zdania uzasadnienia po polsku>",
  "key_factors": ["<czynnik 1>", "<czynnik 2>", "<czynnik 3>"]
}}
"""

    try:
        from google.genai import types
        last_err = None
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=AI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(google_search=types.GoogleSearch())]
                    )
                )
                last_err = None
                break
            except Exception as e:
                last_err = e
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                    wait = 5 * (attempt + 1)
                    print(f"   ! AI tymczasowo niedostepny ({err_str[:60]}...), retry za {wait}s")
                    time.sleep(wait)
                    continue
                raise
        if last_err is not None:
            raise last_err
        text = (response.text or "").strip()

        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if not json_match:
            print(f"   ! AI nie zwrocilo JSON-a dla {a_name} vs {h_name}")
            return None
        data = json.loads(json_match.group())

        ai_winner_raw = data.get("winner_name", "")
        winner = _normalize_winner_name(ai_winner_raw, h_name, a_name)
        if not winner:
            print(f"   ! AI zwrocilo nieznana druzyne '{ai_winner_raw}' dla {a_name} vs {h_name}")
            return None

        return {
            "winner": winner,
            "confidence": int(data.get("confidence", 5)),
            "reasoning": data.get("reasoning", ""),
            "key_factors": data.get("key_factors", []),
            "raw_winner_name": ai_winner_raw,
        }
    except Exception as e:
        print(f"   ! Blad AI predict ({a_name} vs {h_name}): {e}")
        return None


def _is_game_started(ts):
    """Czy start meczu (unix ts) juz minal?"""
    if not ts:
        return False
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc) <= datetime.now(timezone.utc)
    except Exception:
        return False


def predict_winner(home, away, pct_map, game_context, state="pre"):
    h_name = home.get("name") or "Home"
    a_name = away.get("name") or "Away"
    h_id = home.get("id")
    a_id = away.get("id")
    h_pct = pct_map.get(h_id, 0.0)
    a_pct = pct_map.get(a_id, 0.0)

    formula_pick = h_name if (h_pct + 0.05) > a_pct else a_name

    if state == "post":
        return formula_pick

    if _is_game_started(game_context.get("startTimestamp")):
        print(f"   [TIME-skip] {a_name} vs {h_name} -> mecz juz w trakcie/skonczony, formula")
        return formula_pick

    if USE_AI_PREDICTIONS:
        ai_result = predict_winner_ai(home, away, h_pct, a_pct, game_context)
        if ai_result:
            print(f"   [AI] {a_name} vs {h_name} -> {ai_result['winner']} "
                  f"(conf {ai_result['confidence']}/10)")
            _ai_log.append({
                "matchup": f"{a_name} @ {h_name}",
                "phase": game_context.get("phase"),
                "date": game_context.get("date"),
                "ai_pick": ai_result["winner"],
                "formula_pick": formula_pick,
                "agreement": ai_result["winner"] == formula_pick,
                "confidence": ai_result["confidence"],
                "reasoning": ai_result["reasoning"],
                "key_factors": ai_result["key_factors"],
            })
            time.sleep(1)
            return ai_result["winner"]
        print(f"   [FORMULA-fallback] {a_name} vs {h_name} -> {formula_pick}")
        _ai_log.append({
            "matchup": f"{a_name} @ {h_name}",
            "ai_pick": None,
            "formula_pick": formula_pick,
            "note": "AI nie zwrocilo wyniku, uzyto formuly W-L",
        })
        return formula_pick
    return formula_pick


def save_ai_log(today_slug):
    if not _ai_log:
        return
    path = os.path.join(OUTPUT_DIR, "ai_analyses.json")
    payload = {
        "generated_at": datetime.now().isoformat(),
        "date": today_slug,
        "league": "PLK",
        "model": AI_MODEL,
        "matches": _ai_log,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"   Zapisano analizy AI do {path}")


# ==========================================
# CSS
# ==========================================

def get_shared_styles():
    return f"""
        :root {{
            --bg: #0f172a;
            --card-bg: #1e293b;
            --accent: {BRAND_ACCENT};
            --text: #f8fafc;
            --subtext: #94a3b8;
            --win: #10b981;
            --loss: #ef4444;
            --border: #334155;
        }}
        * {{ box-sizing: border-box; }}
        body {{ background-color: var(--bg); color: var(--text); font-family: 'Montserrat', sans-serif; margin: 0; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        header {{ text-align: center; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 1px solid var(--border); }}
        h1 {{ font-weight: 900; letter-spacing: -1px; margin: 0; color: var(--accent); font-size: 2.5rem; }}
        .subtitle {{ color: var(--subtext); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 10px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 25px; }}
        .card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 20px; overflow: hidden; display: flex; flex-direction: column; transition: transform 0.2s, box-shadow 0.2s; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.2); }}
        .card:hover {{ transform: translateY(-5px); box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3); border-color: var(--accent); }}
        .card-header {{ background: rgba(0,0,0,0.3); padding: 12px 25px; display: flex; justify-content: center; align-items: center; border-bottom: 1px solid var(--border); }}
        .status {{ font-size: 0.75rem; font-weight: 900; color: var(--subtext); text-transform: uppercase; letter-spacing: 1px; }}
        .live {{ color: #ef4444; animation: pulse 1.5s infinite; }}
        .matchup {{ display: flex; justify-content: space-between; align-items: stretch; padding: 30px 20px; flex-grow: 1; gap: 12px; }}
        .team {{ text-align: center; flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; }}
        .team-name {{ font-weight: 900; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px; width: 100%; line-height: 1.25; text-shadow: 0 2px 4px rgba(0,0,0,0.6); word-wrap: break-word; }}
        .team-logo {{ width: 100px; height: 100px; object-fit: contain; opacity: 0.95; background: rgba(255,255,255,0.04); border-radius: 12px; padding: 6px; }}
        .score-container {{ display: flex; align-items: center; justify-content: center; gap: 15px; }}
        .score {{ font-size: 2.8rem; font-weight: 900; line-height: 1; text-shadow: 0 2px 5px rgba(0,0,0,0.8); }}
        .score.winner {{ color: var(--win); }}
        .score.loser {{ color: var(--subtext); opacity: 0.8; }}
        .vs-sep {{ color: var(--border); font-style: italic; font-weight: 900; font-size: 1.5rem; }}
        .prediction-box {{ background: rgba(15,23,42,0.6); padding: 20px; text-align: center; border-top: 1px solid var(--border); margin-top: auto; }}
        .pred-label {{ font-size: 0.7rem; color: var(--subtext); text-transform: uppercase; font-weight: 700; letter-spacing: 1px; margin-bottom: 8px; }}
        .pred-val {{ font-size: 1.2rem; font-weight: 900; color: var(--text); display: flex; align-items: center; justify-content: center; gap: 8px; }}
        .footer {{ text-align: center; color: var(--subtext); font-size: 0.75rem; margin-top: 50px; padding-bottom: 20px; }}
        .empty {{ text-align: center; color: #888; padding: 60px 20px; font-size: 1rem; line-height: 1.6; }}
        .empty .ico {{ font-size: 3rem; margin-bottom: 16px; display: block; }}
        @keyframes pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.5; }} }}
        @media (max-width: 768px) {{
            .grid {{ grid-template-columns: 1fr; }}
            .matchup {{ padding: 25px 15px; }}
            .score {{ font-size: 2.2rem; }}
        }}
    """


# ==========================================
# BUILDER KART MECZOW
# ==========================================

def build_game_cards(events, pct_map):
    cards_html = ""
    picks = []
    summaries = []

    for ev in events:
        try:
            home = ev.get("homeTeam") or {}
            away = ev.get("awayTeam") or {}
            if not home or not away:
                continue

            h_name = home.get("name") or home.get("shortName") or "?"
            a_name = away.get("name") or away.get("shortName") or "?"
            h_logo = get_team_logo(home)
            a_logo = get_team_logo(away)

            h_score = get_score(ev, "home")
            a_score = get_score(ev, "away")

            state, _status_raw = map_status(ev)

            ts = ev.get("startTimestamp")
            game_context = {
                "phase": (ev.get("roundInfo") or {}).get("name") or
                         (ev.get("roundInfo") or {}).get("round"),
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else "",
                "startTimestamp": ts,
            }
            predicted_winner = predict_winner(home, away, pct_map, game_context, state=state)

            if state == "pre":
                tip = fmt_game_time(ts)
                status_text = tip if tip else "Scheduled"
                picks.append(f"{a_name} @ {h_name} -> Typ: {predicted_winner}")
                score_html = '<span class="vs-sep" style="font-size:2rem;">VS</span>'
                summaries.append(f"{a_name} vs {h_name}: AI prediction - {predicted_winner} to win")
                outcome_icon = ""
            elif state == "in":
                status_text = "LIVE"
                score_html = (f'<span class="score">{a_score}</span>'
                              f'<span class="vs-sep">:</span>'
                              f'<span class="score">{h_score}</span>')
                summaries.append(f"{a_name} vs {h_name} (live): AI picked {predicted_winner}")
                outcome_icon = ""
            else:
                status_text = "Final"
                if h_score > a_score:
                    actual = h_name
                    h_class, a_class = "score winner", "score loser"
                elif a_score > h_score:
                    actual = a_name
                    h_class, a_class = "score loser", "score winner"
                else:
                    actual = ""
                    h_class, a_class = "score", "score"
                score_html = (f'<span class="{a_class}">{a_score}</span>'
                              f'<span class="vs-sep">:</span>'
                              f'<span class="{h_class}">{h_score}</span>')
                if actual:
                    summaries.append(f"{a_name} vs {h_name}: AI picked {predicted_winner}, "
                                     f"{actual} won {max(h_score, a_score)}-{min(h_score, a_score)}")
                    outcome_icon = (' <span style="color:#10b981;">&#10003;</span>'
                                    if predicted_winner == actual else
                                    ' <span style="color:#ef4444;">&#10007;</span>')
                else:
                    outcome_icon = ""

            status_class = "status live" if state == "in" else "status"

            cards_html += f"""
            <div class="card">
                <div class="card-header">
                    <span class="{status_class}">{status_text}</span>
                </div>
                <div class="matchup">
                    <div class="team">
                        <img src="{a_logo}" class="team-logo" alt="{a_name}" onerror="this.src='{DEFAULT_LOGO}'">
                        <span class="team-name">{a_name}</span>
                    </div>
                    <div class="score-container">{score_html}</div>
                    <div class="team">
                        <img src="{h_logo}" class="team-logo" alt="{h_name}" onerror="this.src='{DEFAULT_LOGO}'">
                        <span class="team-name">{h_name}</span>
                    </div>
                </div>
                <div class="prediction-box">
                    <div class="pred-label">Public AI Model Picks</div>
                    <div class="pred-val">{predicted_winner}{outcome_icon}</div>
                </div>
            </div>
            """
        except Exception as e:
            print(f"   Blad przy meczu: {e}")
            continue

    return cards_html, picks, summaries


# ==========================================
# BUILDER STRONY
# ==========================================

def build_page(title_date, cards_html, summaries):
    games_meta = " | ".join(summaries[:5])
    meta_title = f"PLK AI Picks Today {title_date} - Free Predictions Orlen Basket Liga"
    meta_desc = (f"Free PLK ({TOURNAMENT_NAME_PL}) AI predictions for {title_date}. {games_meta}"
                 if games_meta else
                 f"Daily PLK ({TOURNAMENT_NAME_PL}) game predictions powered by AI. "
                 f"Free picks for every game - {title_date}.")
    meta_desc = meta_desc[:160]

    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{meta_title}</title>
    <meta name="description" content="{meta_desc}">
    <meta name="robots" content="index, follow">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>&#x1F3C0;</text></svg>">
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800;900&display=swap" rel="stylesheet">
    <style>{get_shared_styles()}</style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{BRAND_TITLE}</h1>
            <div class="subtitle">{TOURNAMENT_NAME_PL} &middot; Live Scores &amp; Public AI Model Picks &mdash; {title_date}</div>
        </header>

        <div class="grid">
            {cards_html if cards_html.strip() else '<div class="empty"><span class="ico">&#127936;</span>Brak meczow PLK na dzis.<br><small>Sprawdz pozniej lub wybierz inna date.</small></div>'}
        </div>

        <div class="footer">
            Last updated: {datetime.now().strftime("%B %d, %Y at %H:%M")} &middot; Data source: Sofascore public API
        </div>
    </div>
</body>
</html>"""


# ==========================================
# MAIN
# ==========================================

def main():
    print(f"=== URUCHAMIAM PLK UPDATE ({datetime.now().strftime('%H:%M')}) ===")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    today_slug = get_today_date_str()
    today_str = datetime.now().strftime("%B %d, %Y")
    print(f"   Data: {today_slug} ({today_str})")
    print(f"   Liga: {TOURNAMENT_NAME_PL} (Sofascore tournament id={TOURNAMENT_ID})")

    if USE_AI_PREDICTIONS and os.environ.get("GEMINI_API_KEY"):
        print(f"   Tryb predykcji: AI ({AI_MODEL} + Google Search)")
    elif USE_AI_PREDICTIONS:
        print(f"   Tryb predykcji: FORMULA W-L (brak GEMINI_API_KEY)")
    else:
        print(f"   Tryb predykcji: FORMULA W-L (USE_AI_PREDICTIONS=False)")
    print()

    season_id = fetch_current_season_id()
    if not season_id:
        print("!! Nie udalo sie pobrac sezonu - sprawdz {DEBUG_DIR}/.")
        # Generuj pusta strone, zeby link na hubie nie byl 404
        out_path = os.path.join(OUTPUT_DIR, "index.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(build_page(today_str, "", []))
        return

    print()
    pct_map = fetch_standings_map(season_id)
    print()
    next_events = fetch_events_for_season(season_id, "next")
    last_events = fetch_events_for_season(season_id, "last")
    all_events = next_events + last_events

    today_events = filter_events_for_date(all_events, today_slug)
    print(f"   Mecze na {today_slug}: {len(today_events)}")
    print()

    cards_html, picks, summaries = build_game_cards(today_events, pct_map)

    out_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(build_page(today_str, cards_html, summaries))
    print(f"\n-> Zapisano {out_path}")

    if picks:
        save_picks_for_audit(picks, today_slug)
    else:
        print("   Brak typow pre-game (gry juz w trakcie/zakonczone albo brak meczow).")

    save_ai_log(today_slug)

    if not today_events:
        print(f"\n   Brak meczow PLK na {today_slug}.")
        print(f"   Sprawdz dump {DEBUG_DIR}/debug_events_next_p0.json - czy w API sa mecze?")

    print(f"\n=== GOTOWE. Otworz {out_path} w przegladarce. ===")


if __name__ == "__main__":
    main()
