"""
LBA (Lega Basket Serie A) Free Picks - generator typow.

Zrodlo danych: legabasket.it public API (no-auth, odkryte DevTools).
UI: league_ui.py (wspolny szablon dla wszystkich lig).

KLUCZOWA LOGIKA UTRWALANIA TYPOW:
  Jezeli ai_analyses.json zawiera dzisiejsza date -> wczytaj typ z pliku.
  Nie generuj nowego. Zapobiega nadpisywaniu AI typow przez pozniejszy run.

URUCHOMIENIE LOKALNE:
    pip install requests google-genai pytz
    export GEMINI_API_KEY=...
    python update_lba.py

Wynik: lba/index.html
"""

import os
import re
import json
import time
import textwrap
from datetime import datetime, timezone, timedelta

import requests
import lba_data as ld

# ==========================================
# KONFIGURACJA
# ==========================================
LEAGUE_NAME  = "Lega Basket Serie A"
OUTPUT_DIR   = "lba"
DEBUG_DIR    = "lba/_debug"

USE_AI_PREDICTIONS = os.environ.get("PLK_LIVE_MODE", "").lower() not in ("true", "1", "yes")
AI_MODEL           = "gemini-2.5-flash"

BRAND_TITLE  = "LBA PUBLIC HUB"
BRAND_ACCENT = "#006db7"

CET = timezone(timedelta(hours=2))

DEFAULT_LOGO = (
    "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    "<circle cx='50' cy='50' r='44' fill='none' stroke='%23006db7' stroke-width='3'/>"
    "<text y='62' x='50' text-anchor='middle' font-size='42' fill='%23006db7'>"
    "%F0%9F%8F%80</text></svg>"
)

_gemini_client = None
_ai_log        = []


# ==========================================
# HELPERS
# ==========================================

def get_today_str():
    return datetime.now(CET).strftime("%Y-%m-%d")


def save_picks(picks, today_slug):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "propozycje_typow.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# LBA typy na {today_slug}\n")
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
# AI
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


def build_prompt(match, table, all_matches, player_stats, today):
    h_id   = match.get("h_team_id")
    v_id   = match.get("v_team_id")
    h_name = match.get("h_team_name") or "Home"
    v_name = match.get("v_team_name") or "Away"

    h_row = table.get(h_id) or {}
    v_row = table.get(v_id) or {}
    h_w, h_l = h_row.get("wins", 0), h_row.get("losses", 0)
    v_w, v_l = v_row.get("wins", 0), v_row.get("losses", 0)
    h_pct = round(100 * h_w / max(1, h_w + h_l))
    v_pct = round(100 * v_w / max(1, v_w + v_l))
    h_net = ld.get_net_rating_simple(table, h_id)
    v_net = ld.get_net_rating_simple(table, v_id)

    arena      = match.get("plant_name") or "?"
    city       = match.get("town_name") or "?"
    day_name   = match.get("day_name") or "?"
    hour       = ld.fmt_match_time(match)
    match_serie = match.get("match_serie") or ""
    serie_wins  = match.get("match_hw", 0) or 0
    serie_losses = match.get("match_vw", 0) or 0

    h_top = ld.get_top_scorers_by_team(player_stats, h_id, 3)
    v_top = ld.get_top_scorers_by_team(player_stats, v_id, 3)

    def fmt_scorers(scorers):
        if not scorers:
            return "  - brak danych"
        return "\n".join(
            f"  - {s['name']}: {s['ppg']} ppg, {s['mpg']} min/mecz ({s['presences']} meczow)"
            for s in scorers
        )

    h2h_text = ld.format_h2h(
        ld.get_h2h_in_season(all_matches, h_id, v_id),
        h_id, h_name, v_id, v_name
    )

    series_text = ""
    if match_serie:
        series_text = (
            f"\nSTAN SERII PLAYOFF:\n"
            f"  {h_name}: {serie_wins} wygrane\n"
            f"  {v_name}: {serie_losses} wygrane\n"
            f"  Format meczu: {match_serie}"
        )

    return f"""
=========================================================================
SYSTEM
=========================================================================
Jestes ekspertem koszykarskim LBA (Lega Basket Serie A, Wlochy).
DZISIEJSZA DATA: {today}. Twoja wiedza jest przestarzala - sprawdzaj przez
Google Search. NIE ZGADUJ. Brak danych = "brak danych".

=========================================================================
MECZ DZISIAJ
=========================================================================
Liga:    {LEAGUE_NAME}
Faza:    {day_name}
Hala:    {arena}, {city}
Tip-off: {hour}

GOSPODARZ: {h_name}
GOSC:      {v_name}

=========================================================================
DANE Z LEGABASKET.IT (sezon 2025/26)
=========================================================================

BILANS:
   {h_name}: {h_w}-{h_l} ({h_pct}%, NetRtg {h_net:+})
   {v_name}: {v_w}-{v_l} ({v_pct}%, NetRtg {v_net:+})
{series_text}

TOP SCORERZY:
   {h_name}:
{fmt_scorers(h_top)}
   {v_name}:
{fmt_scorers(v_top)}

H2H W TYM SEZONIE:
   {h2h_text}

=========================================================================
ZADANIE - Google Search dla kazdego punktu:
=========================================================================
1. KONTUZJE na {today}: gazzetta.it, legabasket.it, basketinside.com, X/Twitter klubow
   Filtruj TYLKO sekcje koszykarska (nie pilka nozna).
2. Forma ostatnich 3 meczow obu druzyn
3. Kontekst fazy (playoff = wieksza waga parkietu domowego)
4. Kontuzje/foul-outy z poprzedniego meczu serii

WAGA SYGNALOW:
   1. Kontuzje liderow  2. Stan serii playoff  3. Forma  4. Home court  5. NetRtg

ODPOWIEDZ - czysty JSON, bez markdown:
{{
  "winner_name": "<dokladna nazwa: '{h_name}' lub '{v_name}'>",
  "confidence": <1-10>,
  "reasoning": "<2-3 zdania po polsku>",
  "key_factors": ["<czynnik 1>", "<czynnik 2>", "<czynnik 3>"],
  "injury_notes": "<co znalazles na DZIS lub 'brak istotnych brakow'>",
  "agreement_with_odds": "no_odds"
}}
"""


def predict_ai(match, table, all_matches, player_stats, today):
    client = _get_gemini()
    if not client:
        return None
    h_name = match.get("h_team_name") or "Home"
    v_name = match.get("v_team_name") or "Away"
    prompt = build_prompt(match, table, all_matches, player_stats, today)
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
        data   = json.loads(m.group())
        winner = _norm_name(data.get("winner_name"), h_name, v_name)
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
        print(f"   ! AI LBA: {e}")
        return None


def predict_formula(match, table):
    h_id   = match.get("h_team_id")
    v_id   = match.get("v_team_id")
    h_name = match.get("h_team_name") or "Home"
    v_name = match.get("v_team_name") or "Away"
    h_pct  = ld.get_win_pct(table, h_id)
    v_pct  = ld.get_win_pct(table, v_id)
    return h_name if (h_pct + 0.05) > v_pct else v_name


def predict(match, table, all_matches, player_stats, today, saved_predictions=None):
    """
    Zwraca dict {winner, reasoning, key_factors, confidence, injury_notes}.
    Jezeli saved_predictions zawiera dzisiejszy typ -> uzywa go bez AI.
    """
    h_name      = match.get("h_team_name") or "Home"
    v_name      = match.get("v_team_name") or "Away"
    formula     = predict_formula(match, table)
    state       = ld.match_status(match)
    matchup_key = f"{v_name} @ {h_name}"

    def _r(winner, reasoning="", key_factors=None, confidence=None, injury_notes=""):
        return {"winner": winner, "reasoning": reasoning,
                "key_factors": key_factors or [], "confidence": confidence,
                "injury_notes": injury_notes or ""}

    # KLUCZOWE: uzyj zapisanego typu jesli istnieje
    if saved_predictions and matchup_key in saved_predictions:
        saved = saved_predictions[matchup_key]
        print(f"   [cache] {matchup_key} -> {saved['winner']}")
        return _r(**saved)

    if state == "post":
        return _r(formula)

    dt = ld.parse_match_dt(match)
    if dt and dt <= datetime.now(CET):
        print(f"   [TIME-skip] {matchup_key} -> formula")
        return _r(formula)

    if USE_AI_PREDICTIONS:
        result = predict_ai(match, table, all_matches, player_stats, today)
        if result:
            print(f"   [AI] {matchup_key} -> {result['winner']} (conf {result['confidence']}/10)")
            _ai_log.append({
                "matchup":      matchup_key,
                "day":          match.get("day_name"),
                "date":         match.get("match_datetime"),
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
            "league":       "LBA",
            "model":        AI_MODEL,
            "matches":      _ai_log,
        }, f, indent=2, ensure_ascii=False)
    print(f"   Zapisano ai_analyses.json")

    bar = "=" * 72
    print(f"\n{bar}\n   ANALIZY AI / DEV PRINT  (LBA)\n{bar}")
    for i, m in enumerate(_ai_log, 1):
        ai = m.get("ai_pick")
        if not ai:
            print(f"\n   [{i}] {m['matchup']}: BRAK AI -> {m.get('formula_pick')}")
            continue
        conf = m.get("confidence", "?")
        ag   = "ZGODNE" if m.get("agreement") else "ROZNI sie od formuly"
        print(f"\n   [{i}] {m['matchup']}  ({m.get('day') or '-'})")
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

def build_cards(today_matches, table, all_matches, player_stats, today_slug,
                saved_predictions=None):
    from league_ui import render_card
    cards_list   = []
    picks_list   = []
    summaries    = []
    matches_data = {}

    for m in today_matches:
        try:
            h_name     = m.get("h_team_name") or "?"
            v_name     = m.get("v_team_name") or "?"
            h_logo_key = m.get("home_logo_key") or ""
            v_logo_key = m.get("v_logo_key") or ""
            h_logo     = ld.logo_url(h_logo_key) or DEFAULT_LOGO
            v_logo     = ld.logo_url(v_logo_key) or DEFAULT_LOGO
            h_score    = int(m.get("home_final_score") or 0)
            v_score    = int(m.get("visitor_final_score") or 0)

            state = ld.match_status(m)
            pred  = predict(m, table, all_matches, player_stats,
                            today_slug, saved_predictions)
            pick  = pred["winner"]

            if state == "pre":
                tip    = ld.fmt_match_time(m)
                status = tip or "Scheduled"
                picks_list.append(f"{v_name} @ {h_name} -> Typ: {pick}")
                summaries.append(f"{v_name} vs {h_name}: AI - {pick}")
            elif state == "in":
                status = "LIVE"
            else:
                status = "Final"
                actual = h_name if h_score > v_score else (v_name if v_score > h_score else "")
                if actual:
                    summaries.append(f"{v_name} vs {h_name}: picked {pick}, "
                                     f"{actual} won {max(h_score,v_score)}-{min(h_score,v_score)}")

            game_id = f"lba_{m.get('game_id') or id(m)}"
            cards_list.append(render_card(
                game_id, h_name, v_name, h_logo, v_logo,
                h_score, v_score, state, status, pred, DEFAULT_LOGO
            ))
            matches_data[game_id] = {
                "matchup":      f"{v_name} @ {h_name}",
                "pick":         pick,
                "reasoning":    pred.get("reasoning", ""),
                "key_factors":  pred.get("key_factors") or [],
                "confidence":   pred.get("confidence"),
                "injury_notes": pred.get("injury_notes", ""),
                "audit":        "",
            }
        except Exception as e:
            print(f"   Blad przy meczu LBA: {e}")

    return "".join(cards_list), picks_list, summaries, matches_data


# ==========================================
# BUILD PAGE
# ==========================================

def build_page(title_date, cards_html, summaries, matches_data=None):
    from league_ui import render_page
    return render_page(
        league_logo_url="https://www.legabasket.it/_next/static/media/LogoGradientSponsor.7fe64737.svg",
        league_title=BRAND_TITLE,
        league_subtitle=f"{LEAGUE_NAME} \u00b7 Live Scores & Public AI Model Picks \u2014 {title_date}",
        cards_html=cards_html,
        matches_data=matches_data or {},
        last_updated=datetime.now().strftime("%B %d, %Y at %H:%M"),
        data_source="legabasket.it",
        default_logo=DEFAULT_LOGO,
        league_accent=BRAND_ACCENT,
    )


# ==========================================
# MAIN
# ==========================================

def main():
    print(f"=== URUCHAMIAM LBA UPDATE ({datetime.now().strftime('%H:%M')}) ===")
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

    # Pobierz dane
    champ_id, season_id = ld.find_current_championship()
    if not champ_id:
        print("   ! Brak danych LBA - zapisuje pustą stronę")
        out = os.path.join(OUTPUT_DIR, "index.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(build_page(today_str, "", [], {}))
        return

    all_matches  = ld.fetch_matches(champ_id)
    table        = ld.fetch_table(champ_id)
    player_stats = ld.fetch_player_stats(champ_id, season_id)

    today_matches = [
        m for m in (all_matches or [])
        if ld.match_date_str(m) == today_slug
    ]
    print(f"   Mecze na {today_slug}: {len(today_matches)}")

    # Build
    cards_html, picks, summaries, matches_data = build_cards(
        today_matches, table, all_matches, player_stats, today_slug, saved_predictions
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

    if not today_matches:
        print(f"\n   Brak meczow LBA na {today_slug}.")

    print(f"\n=== GOTOWE. Otworz {out} w przegladarce. ===")


if __name__ == "__main__":
    main()
