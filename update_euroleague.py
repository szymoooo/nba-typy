"""
EuroLeague Free Picks - generator typow.

Zrodlo danych: oficjalne API api-live.euroleague.net (free, no-auth).
UI: league_ui.py (wspolny szablon dla wszystkich lig).

KLUCZOWA LOGIKA UTRWALANIA TYPOW:
  Jezeli ai_analyses.json zawiera dzisiejsza date -> wczytaj typ z pliku.
  Nie generuj nowego. Zapobiega nadpisywaniu AI typow przez pozniejszy run.

URUCHOMIENIE LOKALNE:
    pip install requests google-genai pytz
    export GEMINI_API_KEY=...
    python update_euroleague.py
"""

import requests
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# ==========================================
# KONFIGURACJA
# ==========================================
SEASON_CODE = "E2025"
COMPETITION = "E"
OUTPUT_DIR  = "euroleague"
DEBUG_DIR   = "euroleague/_debug"

USE_AI_PREDICTIONS = True
AI_MODEL           = "gemini-2.5-flash"

BRAND_TITLE  = "EUROLEAGUE PUBLIC HUB"
BRAND_ACCENT = "#ff6600"

CET = timezone(timedelta(hours=2))

GAMES_ENDPOINTS = [
    ("incrowd_v2",
     f"https://feeds.incrowdsports.com/provider/euroleague-feeds/v2/competitions/{COMPETITION}/seasons/{SEASON_CODE}/games",
     {"limit": 500}),
    ("v3",
     f"https://api-live.euroleague.net/v3/competitions/{COMPETITION}/seasons/{SEASON_CODE}/games",
     {"limit": 500}),
    ("v2",
     f"https://api-live.euroleague.net/v2/competitions/{COMPETITION}/seasons/{SEASON_CODE}/games",
     {"limit": 500}),
    ("v1_schedules",
     f"https://api-live.euroleague.net/v1/schedules",
     {"seasonCode": SEASON_CODE}),
    ("v1_results",
     f"https://api-live.euroleague.net/v1/results",
     {"seasonCode": SEASON_CODE}),
]

STANDINGS_ENDPOINTS = [
    ("incrowd_v2",
     f"https://feeds.incrowdsports.com/provider/euroleague-feeds/v2/competitions/{COMPETITION}/seasons/{SEASON_CODE}/standings",
     {}),
    ("v3",
     f"https://api-live.euroleague.net/v3/competitions/{COMPETITION}/seasons/{SEASON_CODE}/standings",
     {}),
    ("v2",
     f"https://api-live.euroleague.net/v2/competitions/{COMPETITION}/seasons/{SEASON_CODE}/standings",
     {}),
    ("v1_standings",
     f"https://api-live.euroleague.net/v1/standings",
     {"seasonCode": SEASON_CODE}),
]

EUROLEAGUE_LOGOS = {
    "MAD": "https://upload.wikimedia.org/wikipedia/en/8/89/Real_Madrid_CF.svg",
    "BAR": "https://upload.wikimedia.org/wikipedia/en/4/47/FC_Barcelona_%28crest%29.svg",
    "OLY": "https://upload.wikimedia.org/wikipedia/en/8/85/Olympiacos_BC.svg",
    "PAN": "https://upload.wikimedia.org/wikipedia/en/d/de/Panathinaikos_BC_logo.svg",
    "ULK": "https://upload.wikimedia.org/wikipedia/en/2/27/Fenerbahce_basketball_logo.png",
    "EFS": "https://upload.wikimedia.org/wikipedia/en/0/0a/Anadolu_Efes_logo.png",
    "IST": "https://upload.wikimedia.org/wikipedia/en/0/0a/Anadolu_Efes_logo.png",
    "MIL": "https://upload.wikimedia.org/wikipedia/en/6/68/Olimpia_Milano_logo_2017.svg",
    "MCO": "https://upload.wikimedia.org/wikipedia/en/4/47/AS_Monaco_Basket_logo.png",
    "BAS": "https://upload.wikimedia.org/wikipedia/en/2/27/Saski_Baskonia_logo.svg",
    "BER": "https://upload.wikimedia.org/wikipedia/en/d/d3/ALBA_Berlin_logo.svg",
    "RED": "https://upload.wikimedia.org/wikipedia/en/4/45/KK_Crvena_zvezda.svg",
    "DUB": "",
    "HTA": "",
    "ASV": "https://upload.wikimedia.org/wikipedia/en/3/35/ASVEL_Basket_logo.svg",
    "MTA": "https://upload.wikimedia.org/wikipedia/en/8/8e/Maccabi_Tel_Aviv_BC_logo.svg",
    "TEL": "https://upload.wikimedia.org/wikipedia/en/8/8e/Maccabi_Tel_Aviv_BC_logo.svg",
    "PRS": "https://upload.wikimedia.org/wikipedia/en/0/00/Paris_Basketball_logo.svg",
    "PAR": "https://upload.wikimedia.org/wikipedia/en/0/02/KK_Partizan_logo.svg",
    "VAL": "https://upload.wikimedia.org/wikipedia/en/2/2a/Valencia_Basket_logo.svg",
    "VIR": "https://upload.wikimedia.org/wikipedia/en/3/35/Virtus_Pallacanestro_Bologna_logo.svg",
    "ZAL": "https://upload.wikimedia.org/wikipedia/en/c/c1/BC_%C5%BDalgiris_logo.svg",
}

DEFAULT_LOGO = (
    "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    "<circle cx='50' cy='50' r='44' fill='none' stroke='%23ff6600' stroke-width='3'/>"
    "<text y='62' x='50' text-anchor='middle' font-size='42' fill='%23ff6600'>&#x1F3C0;</text></svg>"
)

# ==========================================
# API CLIENT
# ==========================================

def fetch_json(url, params=None, timeout=15):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        if r.status_code == 200:
            ct = r.headers.get("Content-Type", "")
            if "json" in ct or r.text.strip().startswith("{") or r.text.strip().startswith("["):
                return r.json(), 200, None
            return None, r.status_code, f"Non-JSON: {ct}"
        return None, r.status_code, f"HTTP {r.status_code}"
    except Exception as e:
        return None, 0, str(e)


def _save_debug(name, data):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    path = os.path.join(DEBUG_DIR, f"debug_{name}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def try_endpoints(endpoints, kind):
    for label, url, params in endpoints:
        result, status, err = fetch_json(url, params)
        if result is not None:
            print(f"   [{kind}] OK via {label} ({url[:60]}...)")
            _save_debug(f"{kind}_{label}", result)
            return label, result
        print(f"   [{kind}] FAIL {label}: {err}")
    return None, None


# ==========================================
# DATA HELPERS
# ==========================================

def get_today_date_str():
    return datetime.now(CET).strftime("%Y-%m-%d")


def parse_standings_xml(xml_text):
    pct_map = {}
    try:
        root = ET.fromstring(xml_text)
        for club in root.iter("club"):
            code = club.get("code", "").upper()
            wins = int(club.findtext("wins_total") or club.findtext("wins") or 0)
            losses = int(club.findtext("losses_total") or club.findtext("losses") or 0)
            total = wins + losses
            if code and total > 0:
                pct_map[code] = round(wins / total, 3)
    except Exception as e:
        print(f"   [standings-xml] Parse error: {e}")
    return pct_map


def fetch_games_for_date(date_str):
    label, data = try_endpoints(GAMES_ENDPOINTS, "games")
    if not data:
        print("   !! Brak danych z zadnego endpointu gier.")
        return [], "none"

    games_raw = (data.get("data") or data.get("games") or
                 data.get("results") or data.get("schedules") or
                 (data if isinstance(data, list) else []))

    today_games = []
    for g in games_raw:
        date_field = (g.get("utcDate") or g.get("date") or
                      g.get("startDate") or g.get("starttime") or "")
        if date_str in str(date_field):
            today_games.append(g)

    print(f"   [games] {len(today_games)} meczow na {date_str} (z {len(games_raw)} total)")
    return today_games, label


def fetch_standings_map():
    label, data = try_endpoints(STANDINGS_ENDPOINTS, "standings")
    if not data:
        return {}
    pct_map = {}

    # JSON formats
    clubs = (data.get("standings") or data.get("teams") or
             data.get("clubs") or data.get("data") or
             (data if isinstance(data, list) else []))

    for entry in clubs:
        if isinstance(entry, dict):
            code  = (entry.get("code") or entry.get("clubCode") or
                     entry.get("team_code") or "").upper()
            wins  = int(entry.get("wins") or entry.get("w") or 0)
            losses = int(entry.get("losses") or entry.get("l") or 0)
            total  = wins + losses
            if code and total > 0:
                pct_map[code] = round(wins / total, 3)

    # XML fallback
    if not pct_map and isinstance(data, str) and "<" in data:
        pct_map = parse_standings_xml(data)

    print(f"   [standings] {len(pct_map)} druzyn: {label}")
    return pct_map


def get_team_logo(team_obj):
    if not team_obj:
        return DEFAULT_LOGO
    for key in ("imageUrls", "images"):
        imgs = team_obj.get(key)
        if isinstance(imgs, dict):
            for sub in ("crest", "logo", "primary"):
                url = imgs.get(sub)
                if url:
                    return url
    code = (team_obj.get("code") or team_obj.get("tvCode") or "").upper()
    return EUROLEAGUE_LOGOS.get(code, DEFAULT_LOGO) or DEFAULT_LOGO


def map_status(status_raw):
    if not status_raw:
        return "pre", "Scheduled"
    s = str(status_raw).lower()
    if any(x in s for x in ("live", "inprogress", "progress", "playing", "q1", "q2", "q3", "q4", "ot")):
        return "in", "LIVE"
    if any(x in s for x in ("final", "finish", "ended", "played", "result", "confirmed", "closed")):
        return "post", "Final"
    return "pre", "Scheduled"


def fmt_game_time(date_raw):
    if not date_raw:
        return ""
    try:
        s = str(date_raw).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_cet = dt.astimezone(CET)
        return dt_cet.strftime("%H:%M CET")
    except Exception:
        return ""


def save_picks_for_audit(picks, today_slug):
    path = os.path.join(OUTPUT_DIR, "propozycje_typow.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# EuroLeague typy na {today_slug}\n")
        f.write("\n".join(picks))
    print(f"   Zapisano {len(picks)} typow do {path}")


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


# ==========================================
# AI PREDICTIONS
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
        print("   ! Brak biblioteki google-genai.")
        return None
    except Exception as e:
        print(f"   ! Blad inicjalizacji Gemini: {e}")
        return None


def _normalize_winner_name(ai_winner, h_name, a_name):
    if not ai_winner:
        return None
    ai_low = ai_winner.lower().strip()
    h_low  = (h_name or "").lower()
    a_low  = (a_name or "").lower()
    if ai_low == h_low: return h_name
    if ai_low == a_low: return a_name
    if ai_low in h_low or h_low in ai_low: return h_name
    if ai_low in a_low or a_low in ai_low: return a_name
    for word in ai_low.split():
        if len(word) >= 4:
            if word in h_low: return h_name
            if word in a_low: return a_name
    return None


def predict_winner_ai(home, away, h_pct, a_pct, game_context):
    client = _get_gemini_client()
    if client is None:
        return None

    h_name = home.get("name") or home.get("code") or "Home"
    a_name = away.get("name") or away.get("code") or "Away"
    phase  = game_context.get("phase") or "Sezon zasadniczy"
    today  = datetime.now(CET).strftime("%Y-%m-%d")

    prompt = f"""
Mecz EuroLeague: {a_name} (gosc) vs {h_name} (gospodarz)
Faza: {phase}
DZISIEJSZA DATA: {today}

Bilans w sezonie 2025-26:
  - {h_name}: {h_pct:.0%} skutecznosci
  - {a_name}: {a_pct:.0%} skutecznosci

ZADANIE: Wytypuj zwyciezce. Uzyj Google Search:
1. Forma ostatnich 5 meczow obu druzyn
2. Bezposrednie mecze w sezonie 2025-26
3. Kluczowe kontuzje na {today}
4. Kontekst fazy: Final Four/Playoffs = eliminacyjne, neutralny parkiet
5. Historia w tej fazie

WAGA: kontuzje > forma > faza > bilans

Odpowiedz WYLACZNIE czystym JSON (bez markdown):
{{
  "winner_name": "<'{h_name}' lub '{a_name}'>",
  "confidence": <1-10>,
  "reasoning": "<2-3 zdania po polsku>",
  "key_factors": ["<czynnik 1>", "<czynnik 2>", "<czynnik 3>"],
  "injury_notes": "<kontuzje na {today} lub 'brak istotnych brakow'>"
}}
"""
    try:
        from google.genai import types
        last_err = None
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=AI_MODEL, contents=prompt,
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
                    print(f"   ! AI retry za {wait}s")
                    time.sleep(wait)
                    continue
                raise
        if last_err:
            raise last_err

        text = (response.text or "").strip()
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if not m:
            print(f"   ! AI brak JSON dla {a_name} vs {h_name}")
            return None
        data   = json.loads(m.group())
        winner = _normalize_winner_name(data.get("winner_name", ""), h_name, a_name)
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
        print(f"   ! Blad AI ({a_name} vs {h_name}): {e}")
        return None


def _is_game_started(game_context):
    date_str = game_context.get("date") or ""
    if not date_str:
        return False
    try:
        s = date_str.replace("Z", "+00:00")
        game_dt = datetime.fromisoformat(s)
        if game_dt.tzinfo is None:
            game_dt = game_dt.replace(tzinfo=timezone.utc)
        return game_dt <= datetime.now(timezone.utc)
    except Exception:
        return False


def predict_winner(home, away, pct_map, game_context, state="pre", saved_predictions=None):
    """
    Zwraca dict {winner, reasoning, key_factors, confidence, injury_notes}.
    Jezeli saved_predictions zawiera dzisiejszy typ -> uzywa go bez wywolywania AI.
    """
    h_name = home.get("name") or home.get("code") or "Home"
    a_name = away.get("name") or away.get("code") or "Away"
    h_code = (home.get("code") or "").upper()
    a_code = (away.get("code") or "").upper()
    h_pct  = pct_map.get(h_code, 0.0)
    a_pct  = pct_map.get(a_code, 0.0)

    formula_pick = h_name if (h_pct + 0.05) > a_pct else a_name
    matchup_key  = f"{a_name} @ {h_name}"

    def _r(winner, reasoning="", key_factors=None, confidence=None, injury_notes=""):
        return {"winner": winner, "reasoning": reasoning,
                "key_factors": key_factors or [], "confidence": confidence,
                "injury_notes": injury_notes}

    # KLUCZOWE: uzyj zapisanego typu jesli istnieje
    if saved_predictions and matchup_key in saved_predictions:
        saved = saved_predictions[matchup_key]
        print(f"   [cache] {matchup_key} -> {saved['winner']}")
        return _r(**saved)

    if state == "post":
        return _r(formula_pick)

    if _is_game_started(game_context):
        print(f"   [TIME-skip] {matchup_key} -> formula")
        return _r(formula_pick)

    if USE_AI_PREDICTIONS:
        ai = predict_winner_ai(home, away, h_pct, a_pct, game_context)
        if ai:
            print(f"   [AI] {matchup_key} -> {ai['winner']} (conf {ai['confidence']}/10)")
            _ai_log.append({
                "matchup":      matchup_key,
                "phase":        game_context.get("phase"),
                "date":         game_context.get("date"),
                "ai_pick":      ai["winner"],
                "formula_pick": formula_pick,
                "agreement":    ai["winner"] == formula_pick,
                "confidence":   ai["confidence"],
                "reasoning":    ai["reasoning"],
                "key_factors":  ai["key_factors"],
                "injury_notes": ai.get("injury_notes", ""),
            })
            time.sleep(1)
            return _r(ai["winner"], ai["reasoning"], ai["key_factors"],
                      ai["confidence"], ai.get("injury_notes", ""))
        print(f"   [FORMULA-fallback] {matchup_key} -> {formula_pick}")
        _ai_log.append({"matchup": matchup_key, "ai_pick": None,
                        "formula_pick": formula_pick, "note": "AI fallback"})
    return _r(formula_pick)


def save_ai_log(today_slug):
    if not _ai_log:
        return
    path = os.path.join(OUTPUT_DIR, "ai_analyses.json")
    payload = {
        "generated_at": datetime.now().isoformat(),
        "date":         today_slug,
        "league":       "EuroLeague",
        "model":        AI_MODEL,
        "data_source":  "euroleague.net",
        "matches":      _ai_log,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"   Zapisano analizy AI do {path}")


# ==========================================
# BUILD CARDS
# ==========================================

def build_game_cards(games, pct_map, saved_predictions=None):
    from league_ui import render_card
    cards_html   = ""
    picks        = []
    summaries    = []
    matches_data = {}

    for g in games:
        try:
            home = g.get("homeTeam") or g.get("home") or {}
            away = g.get("awayTeam") or g.get("away") or {}
            if not home or not away:
                continue

            h_name = home.get("name") or home.get("tvCode") or home.get("code") or "?"
            a_name = away.get("name") or away.get("tvCode") or away.get("code") or "?"
            h_logo = get_team_logo(home)
            a_logo = get_team_logo(away)

            try:
                h_score = int(home.get("score") or 0)
                a_score = int(away.get("score") or 0)
            except Exception:
                h_score, a_score = 0, 0

            state, _ = map_status(g.get("status") or g.get("statusType"))

            game_context = {
                "phase": (g.get("phaseType") or {}).get("name") if isinstance(g.get("phaseType"), dict) else g.get("phaseType"),
                "date":  g.get("date") or g.get("utcDate"),
                "round": (g.get("round") or {}).get("name") if isinstance(g.get("round"), dict) else None,
            }

            pred = predict_winner(home, away, pct_map, game_context,
                                  state=state, saved_predictions=saved_predictions)

            if state == "pre":
                tip         = fmt_game_time(game_context.get("date"))
                status_text = tip if tip else "Scheduled"
                picks.append(f"{a_name} @ {h_name} -> Typ: {pred['winner']}")
                summaries.append(f"{a_name} vs {h_name}: AI - {pred['winner']}")
            elif state == "in":
                status_text = "LIVE " + str(g.get("clock") or "")
            else:
                status_text = "Final"
                actual = h_name if h_score > a_score else (a_name if a_score > h_score else "")
                if actual:
                    summaries.append(f"{a_name} vs {h_name}: picked {pred['winner']}, "
                                     f"{actual} won {max(h_score,a_score)}-{min(h_score,a_score)}")

            game_id      = f"euro_{g.get('game_code') or g.get('id') or id(g)}"
            cards_html  += render_card(
                game_id, h_name, a_name, h_logo, a_logo,
                h_score, a_score, state, status_text, pred, DEFAULT_LOGO
            )
            matches_data[game_id] = {
                "matchup":      f"{a_name} @ {h_name}",
                "pick":         pred["winner"],
                "reasoning":    pred.get("reasoning", ""),
                "key_factors":  pred.get("key_factors") or [],
                "confidence":   pred.get("confidence"),
                "injury_notes": pred.get("injury_notes", ""),
                "audit":        "",
            }

        except Exception as e:
            print(f"   Blad przy meczu: {e}")
            continue

    return cards_html, picks, summaries, matches_data


# ==========================================
# BUILD PAGE
# ==========================================

def build_page(title_date, cards_html, summaries, matches_data=None):
    from league_ui import render_page
    return render_page(
        league_logo_url="https://raw.githubusercontent.com/szymoooo/nba-typy/main/euroleague/euroleague-logo.png",
        league_title=BRAND_TITLE,
        league_subtitle=f"EuroLeague \u00b7 Live Scores & Public AI Model Picks \u2014 {title_date}",
        cards_html=cards_html,
        matches_data=matches_data or {},
        last_updated=datetime.now().strftime("%B %d, %Y at %H:%M"),
        data_source="euroleague.net",
        default_logo=DEFAULT_LOGO,
        league_accent=BRAND_ACCENT,
    )


# ==========================================
# MAIN
# ==========================================

def main():
    print(f"=== URUCHAMIAM EUROLEAGUE UPDATE ({datetime.now().strftime('%H:%M')}) ===")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(DEBUG_DIR, exist_ok=True)

    today_slug = get_today_date_str()
    today_str  = datetime.now(CET).strftime("%B %d, %Y")
    print(f"   Data: {today_slug} ({today_str})")
    print(f"   Sezon: {SEASON_CODE}, Liga: {COMPETITION}")

    if USE_AI_PREDICTIONS and os.environ.get("GEMINI_API_KEY"):
        print(f"   Tryb predykcji: AI ({AI_MODEL} + Google Search)")
    else:
        print(f"   Tryb predykcji: FORMULA W-L")

    # Wczytaj zapisane typy z dzisiaj
    saved_predictions = load_saved_predictions(today_slug)

    pct_map = fetch_standings_map()
    games, src_label = fetch_games_for_date(today_slug)

    cards_html, picks, summaries, matches_data = build_game_cards(
        games, pct_map, saved_predictions
    )

    out_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(build_page(today_str, cards_html, summaries, matches_data))
    print(f"\n-> Zapisano {out_path}")

    if picks:
        save_picks_for_audit(picks, today_slug)
    else:
        print("   Brak typow pre-game.")

    save_ai_log(today_slug)

    if not games:
        print(f"\n   Brak meczow EuroLeague na {today_slug}.")

    print(f"\n=== GOTOWE. Otworz {out_path} w przegladarce. ===")


if __name__ == "__main__":
    main()
