"""
PLK (Polska Liga Koszykowki / Orlen Basket Liga) Free Picks - generator typow.

ARCHITEKTURA:
  - Primary source: PulsBasketu Public API (api.pulsbasketu.com)
  - Fallback: Sofascore (uniqueTournament=263)
  - UI: league_ui.py (wspolny szablon dla wszystkich lig)

KLUCZOWA LOGIKA UTRWALANIA TYPOW:
  Jezeli ai_analyses.json zawiera dzisiejsza date -> wczytaj typ z pliku.
  Nie generuj nowego. Zapobiega to nadpisywaniu typing AI przez pozniejszy
  run w trybie live/post (ktory uzywaj formuly zamiast AI).

URUCHOMIENIE LOKALNE:
    pip install requests google-genai pytz
    export GEMINI_API_KEY=...
    python update_plk.py
"""

import os
import re
import json
import time
import textwrap
from datetime import datetime, timezone, timedelta

import requests
import plk_data as pb

# ==========================================
# KONFIGURACJA
# ==========================================
TOURNAMENT_NAME_PL = "Orlen Basket Liga"
OUTPUT_DIR         = "plk"
DEBUG_DIR          = "plk/_debug"

USE_AI_PREDICTIONS = os.environ.get("PLK_LIVE_MODE", "").lower() not in ("true", "1", "yes")
AI_MODEL           = "gemini-2.5-flash"

BRAND_TITLE  = "PLK PUBLIC HUB"
BRAND_ACCENT = "#dc2626"

CET = timezone(timedelta(hours=2))

DEFAULT_LOGO = (
    "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    "<circle cx='50' cy='50' r='44' fill='none' stroke='%23dc2626' stroke-width='3'/>"
    "<text y='62' x='50' text-anchor='middle' font-size='42' fill='%23dc2626'>&#x1F3C0;</text></svg>"
)

# ==========================================
# HELPERS
# ==========================================

def get_today_date_str():
    return datetime.now(CET).strftime("%Y-%m-%d")


def save_picks_for_audit(picks, today_slug):
    path = os.path.join(OUTPUT_DIR, "propozycje_typow.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# PLK typy na {today_slug}\n")
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
        print(f"   [cache] Blad wczytywania ai_analyses.json: {e}")
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


def _format_top_scorers(scorers):
    if not scorers:
        return "  - brak danych"
    lines = []
    for s in scorers:
        bits = [f"{s['name']}: {s['ppg']} ppg"]
        if s.get("apg"): bits.append(f"{s['apg']} apg")
        if s.get("rpg"): bits.append(f"{s['rpg']} rpg")
        if s.get("mpg"): bits.append(f"{s['mpg']} min")
        lines.append("  - " + ", ".join(bits))
    return "\n".join(lines)


def _format_recent_games(recent, team_id):
    if not recent:
        return "  - brak danych"
    lines = []
    for g in recent:
        win = "W" if g.get("win") else "L"
        lines.append(f"  - {g.get('date','')} {g.get('role','')} vs {g.get('opponent','?')}: {g.get('score','')} -> {win}")
    return "\n".join(lines)


def _format_advanced(adv):
    if not adv:
        return "  brak danych"
    parts = []
    for key, label in [("ortg","ORtg"),("drtg","DRtg"),("net_rtg","NetRtg"),
                        ("efg","eFG%"),("ts","TS%"),("tov_perc","TOV%"),
                        ("oreb_perc","OREB%"),("polish_pts_perc","PolishPTS%")]:
        if adv.get(key) is not None:
            val = f"{adv[key]:+}" if key == "net_rtg" else adv[key]
            parts.append(f"{label} {val}")
    return "  " + ", ".join(parts)


def build_ai_prompt(home, away, today, table_by_id, all_games):
    h_id   = home.get("team_id")
    a_id   = away.get("team_id")
    h_name = home.get("name") or "Home"
    a_name = away.get("name") or "Away"

    h_rec = pb.get_team_record(table_by_id, h_id)
    a_rec = pb.get_team_record(table_by_id, a_id)
    h_pct = round(100 * h_rec["wins"] / max(1, h_rec["wins"] + h_rec["losses"]))
    a_pct = round(100 * a_rec["wins"] / max(1, a_rec["wins"] + a_rec["losses"]))

    h_streak = pb.get_streak_last_n(table_by_id, h_id, 15) or "-"
    a_streak = pb.get_streak_last_n(table_by_id, a_id, 15) or "-"

    h_recent = pb.get_recent_games_for_team(table_by_id, h_id, 5)
    a_recent = pb.get_recent_games_for_team(table_by_id, a_id, 5)

    h_st  = pb.fetch_season_team(h_id) if h_id else None
    a_st  = pb.fetch_season_team(a_id) if a_id else None
    h_adv = pb.get_advanced_stats(h_st)
    a_adv = pb.get_advanced_stats(a_st)
    h_opp = pb.get_opponent_avg_stats(h_st)
    a_opp = pb.get_opponent_avg_stats(a_st)
    h_top = pb.get_top_scorers_for_team(h_st, 3)
    a_top = pb.get_top_scorers_for_team(a_st, 3)

    h2h         = pb.get_h2h_in_season(all_games, h_id, a_id)
    h2h_summary = pb.summarize_h2h(h2h, h_id, h_name, a_id, a_name)
    h2h_lines   = ("\n   ".join(h2h_summary["games"])) or "brak"

    odds_h   = home.get("__odds_home")
    odds_a   = home.get("__odds_away")
    implied  = pb.get_implied_probabilities(odds_h, odds_a) if (odds_h and odds_a) else None
    odds_str = (f"H {odds_h} ({implied['home_pct'] if implied else '?'}%), "
                f"A {odds_a} ({implied['away_pct'] if implied else '?'}%)") \
        if (odds_h and odds_a) else "brak"

    phase    = home.get("__stage_name") or "Sezon zasadniczy"
    rnd      = home.get("__round_name") or ""
    arena    = home.get("__arena") or ""
    city     = home.get("__city") or ""
    refs     = home.get("__referees") or []
    ref_str  = ", ".join(refs) if refs else "brak danych"

    return f"""
=========================================================================
SYSTEM
=========================================================================
Jestes ekspertem koszykarskim PLK (Orlen Basket Liga). DZISIEJSZA DATA: {today}.
Twoja wiedza wewnetrzna jest przestarzala - sprawdzaj przez Google Search.
NIE ZGADUJ. Brak danych = "brak danych".

=========================================================================
MECZ DZISIAJ
=========================================================================
Faza:      {phase}
Runda:     {rnd}
Hala:      {arena}, {city}
Sedziowie: {ref_str}

GOSPODARZ: {h_name}
GOSC:      {a_name}

=========================================================================
DANE Z PULSBASKETU.COM (sezon 2025/26)
=========================================================================

BILANS:
   {h_name}: {h_rec['wins']}-{h_rec['losses']} ({h_pct}%, miejsce #{h_rec.get('real_position') or '?'})
   {a_name}: {a_rec['wins']}-{a_rec['losses']} ({a_pct}%, miejsce #{a_rec.get('real_position') or '?'})

DOM/WYJAZD:
   {h_name} u siebie:     {h_rec['wins_home']}-{h_rec['losses_home']}
   {a_name} na wyjezdzie: {a_rec['wins_away']}-{a_rec['losses_away']}

FORMA (ostatnie 15, W=wygrana, najnowszy z prawej):
   {h_name}: {h_streak}
   {a_name}: {a_streak}

OSTATNIE 5 MECZOW:
   {h_name}:
{_format_recent_games(h_recent, h_id)}
   {a_name}:
{_format_recent_games(a_recent, a_id)}

ATAK / OBRONA:
   {h_name}: {h_rec['ppg']} pkt / {h_rec['papg']} traconych (NetRtg {h_rec['net_rating_simple']:+})
   {a_name}: {a_rec['ppg']} pkt / {a_rec['papg']} traconych (NetRtg {a_rec['net_rating_simple']:+})

ADVANCED METRICS:
   {h_name}:
{_format_advanced(h_adv)}
   {a_name}:
{_format_advanced(a_adv)}

JAK RYWALE GRAJA PRZECIW NIM:
   vs {h_name}: {h_opp.get('points','?')} pkt/mecz, {h_opp.get('f3p','?')}% za 3
   vs {a_name}: {a_opp.get('points','?')} pkt/mecz, {a_opp.get('f3p','?')}% za 3

TOP SCORERZY:
   {h_name}:
{_format_top_scorers(h_top)}
   {a_name}:
{_format_top_scorers(a_top)}

H2H W TYM SEZONIE:
   {h2h_summary['summary']}
   {h2h_lines}

KURSY: {odds_str}

=========================================================================
ZADANIE - Google Search dla kazdego punktu:
=========================================================================
1. KONTUZJE na {today}: sport.pl, plk.pl, Twitter/X klubow
2. FOUL-OUTY w poprzednim meczu serii
3. KONTEKST PLAYOFFU: stan serii, desperation factor
4. FORMA 3 OSTATNICH MECZOW

WAGA SYGNALOW:
   1. Kontuzje liderow  2. Forma/streak  3. Home court playoff
   4. H2H serii  5. NetRtg/Advanced  6. Kursy

=========================================================================
ODPOWIEDZ - czysty JSON, bez markdown
=========================================================================
{{
  "winner_name": "<dokladna nazwa: '{h_name}' lub '{a_name}'>",
  "confidence": <1-10>,
  "reasoning": "<2-3 zdania po polsku>",
  "key_factors": ["<czynnik 1>", "<czynnik 2>", "<czynnik 3>"],
  "injury_notes": "<co znalazles na DZIS lub 'brak istotnych brakow'>",
  "agreement_with_odds": <true|false|"no_odds">
}}
"""


def predict_winner_ai(home, away, today, table_by_id, all_games):
    client = _get_gemini_client()
    if client is None:
        return None
    h_name = home.get("name") or "Home"
    a_name = away.get("name") or "Away"
    prompt = build_ai_prompt(home, away, today, table_by_id, all_games)
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
        winner = _normalize_winner_name(data.get("winner_name",""), h_name, a_name)
        if not winner:
            return None
        return {
            "winner":              winner,
            "confidence":          int(data.get("confidence", 5)),
            "reasoning":           data.get("reasoning", ""),
            "key_factors":         data.get("key_factors", []),
            "injury_notes":        data.get("injury_notes", ""),
            "agreement_with_odds": data.get("agreement_with_odds"),
        }
    except Exception as e:
        print(f"   ! Blad AI ({a_name} vs {h_name}): {e}")
        return None


def predict_winner_formula(home, away, table_by_id):
    h_name = home.get("name") or "Home"
    a_name = away.get("name") or "Away"
    h_id   = home.get("team_id")
    a_id   = away.get("team_id")
    h_rec  = pb.get_team_record(table_by_id, h_id)
    a_rec  = pb.get_team_record(table_by_id, a_id)
    h_pct  = h_rec["wins"] / max(1, h_rec["wins"] + h_rec["losses"])
    a_pct  = a_rec["wins"] / max(1, a_rec["wins"] + a_rec["losses"])
    return h_name if (h_pct + 0.05) > a_pct else a_name


def _is_game_started(game):
    if game.get("finished"):
        return True
    dt = pb.parse_game_date(game)
    return dt is not None and dt <= datetime.now(CET)


def predict_winner(home, away, table_by_id, all_games, game, today_slug, state,
                   saved_predictions=None):
    """
    Zwraca dict {winner, reasoning, key_factors, confidence, injury_notes}.

    Jezeli saved_predictions zawiera dzisiejszy typ dla tego meczu -> uzywa go.
    Nie wywoluje AI ponownie. Zapobiega nadpisywaniu typow w trybach live/post.
    """
    h_name      = home.get("name") or "Home"
    a_name      = away.get("name") or "Away"
    formula_pick = predict_winner_formula(home, away, table_by_id)
    matchup_key  = f"{a_name} @ {h_name}"

    def _r(winner, reasoning="", key_factors=None, confidence=None, injury_notes=""):
        return {"winner": winner, "reasoning": reasoning,
                "key_factors": key_factors or [], "confidence": confidence,
                "injury_notes": injury_notes}

    # ── KLUCZOWA ZMIANA: uzyj zapisanego typu jesli istnieje ──
    if saved_predictions and matchup_key in saved_predictions:
        saved = saved_predictions[matchup_key]
        print(f"   [cache] {matchup_key} -> {saved['winner']} (wczytano z ai_analyses.json)")
        return _r(**saved)

    if state == "post":
        return _r(formula_pick)

    if _is_game_started(game):
        print(f"   [TIME-skip] {matchup_key} -> formula")
        return _r(formula_pick)

    if USE_AI_PREDICTIONS:
        ai = predict_winner_ai(home, away, today_slug, table_by_id, all_games)
        if ai:
            print(f"   [AI] {matchup_key} -> {ai['winner']} (conf {ai['confidence']}/10)")
            _ai_log.append({
                "matchup":             matchup_key,
                "phase":               home.get("__stage_name"),
                "round":               home.get("__round_name"),
                "date":                game.get("date"),
                "ai_pick":             ai["winner"],
                "formula_pick":        formula_pick,
                "agreement":           ai["winner"] == formula_pick,
                "confidence":          ai["confidence"],
                "reasoning":           ai["reasoning"],
                "key_factors":         ai["key_factors"],
                "injury_notes":        ai.get("injury_notes", ""),
                "agreement_with_odds": ai.get("agreement_with_odds"),
            })
            time.sleep(1)
            return _r(ai["winner"], ai["reasoning"], ai["key_factors"],
                      ai["confidence"], ai.get("injury_notes", ""))
        print(f"   [FORMULA-fallback] {matchup_key} -> {formula_pick}")
        _ai_log.append({"matchup": matchup_key, "ai_pick": None,
                        "formula_pick": formula_pick, "note": "AI fallback"})
    return _r(formula_pick)


def _print_ai_summary():
    if not _ai_log:
        return
    bar = "=" * 72
    print(f"\n{bar}\n   ANALIZY AI / DEV PRINT  (PLK)\n{bar}")
    for i, m in enumerate(_ai_log, 1):
        matchup   = m.get("matchup", "?")
        phase     = m.get("phase") or "-"
        rnd       = m.get("round") or ""
        ai_pick   = m.get("ai_pick")
        formula   = m.get("formula_pick", "-")
        if ai_pick is None:
            print(f"\n   [{i}] {matchup}  ({phase} {rnd})")
            print(f"       AI:      BRAK -> formula: {formula}")
            continue
        conf      = m.get("confidence", "?")
        agreement = "ZGODNE" if m.get("agreement") else "ROZNI sie"
        reasoning = (m.get("reasoning") or "").strip() or "(brak)"
        factors   = m.get("key_factors") or []
        injury    = (m.get("injury_notes") or "").strip()
        print(f"\n   [{i}] {matchup}  ({phase} {rnd})")
        print(f"       AI pick:   {ai_pick}   (conf {conf}/10)")
        print(f"       Formula:   {formula}   [{agreement} z formula]")
        print(textwrap.fill(reasoning, width=72,
                            initial_indent="       Reason:    ",
                            subsequent_indent="                  "))
        for f in factors:
            print(f"         - {f}")
        if injury and injury.lower() not in ("brak istotnych braków", "brak danych"):
            print(textwrap.fill(injury, width=72,
                                initial_indent="       Kontuzje:  ",
                                subsequent_indent="                  "))
    print(f"\n{bar}\n")


def save_ai_log(today_slug):
    if not _ai_log:
        return
    path    = os.path.join(OUTPUT_DIR, "ai_analyses.json")
    payload = {
        "generated_at": datetime.now().isoformat(),
        "date":         today_slug,
        "league":       "PLK",
        "model":        AI_MODEL,
        "data_source":  "pulsbasketu.com",
        "matches":      _ai_log,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"   Zapisano analizy AI do {path}")
    _print_ai_summary()


# ==========================================
# BUILD CARDS
# ==========================================

def build_game_cards(today_games, table_by_id, all_games, today_slug, saved_predictions=None):
    from league_ui import render_card
    cards_html    = ""
    picks         = []
    summaries     = []
    matches_data  = {}

    for g in today_games:
        try:
            home = dict(g.get("home_team") or {})
            away = dict(g.get("away_team") or {})
            if not home or not away:
                continue

            meta = {
                "__odds_home":  g.get("odds_home"),
                "__odds_away":  g.get("odds_away"),
                "__stage_name": g.get("stage_name"),
                "__round_name": g.get("round_name"),
                "__arena":      g.get("arena"),
                "__city":       g.get("city"),
                "__referees":   g.get("referees") or [],
            }
            home.update(meta)
            away.update(meta)

            h_name  = home.get("name") or "?"
            a_name  = away.get("name") or "?"
            h_logo  = home.get("logo") or DEFAULT_LOGO
            a_logo  = away.get("logo") or DEFAULT_LOGO
            h_score = int(home.get("score") or 0)
            a_score = int(away.get("score") or 0)

            state = pb.game_status(g)
            pred  = predict_winner(home, away, table_by_id, all_games, g,
                                   today_slug, state, saved_predictions)

            if state == "pre":
                tip         = pb.fmt_game_time(g)
                status_text = tip if tip else "Scheduled"
                picks.append(f"{a_name} @ {h_name} -> Typ: {pred['winner']}")
                summaries.append(f"{a_name} vs {h_name}: AI - {pred['winner']}")
            elif state == "in":
                status_text = "LIVE"
            else:
                status_text = "Final"
                actual = h_name if h_score > a_score else (a_name if a_score > h_score else "")
                if actual:
                    summaries.append(f"{a_name} vs {h_name}: picked {pred['winner']}, "
                                     f"{actual} won {max(h_score,a_score)}-{min(h_score,a_score)}")

            game_id     = f"plk_{g.get('game_id', id(g))}"
            cards_html += render_card(
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
        league_logo_url="https://upload.wikimedia.org/wikipedia/fr/c/c9/Logo_PLK.png",
        league_title=BRAND_TITLE,
        league_subtitle=f"{TOURNAMENT_NAME_PL} \u00b7 Live Scores & Public AI Model Picks \u2014 {title_date}",
        cards_html=cards_html,
        matches_data=matches_data or {},
        last_updated=datetime.now().strftime("%B %d, %Y at %H:%M"),
        data_source="pulsbasketu.com",
        default_logo=DEFAULT_LOGO,
        league_accent=BRAND_ACCENT,
    )


# ==========================================
# SOFASCORE FALLBACK
# ==========================================

def _sofa_fetch(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
        "Referer": "https://www.sofascore.com/",
        "Origin": "https://www.sofascore.com",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json()
        print(f"   [sofa] HTTP {r.status_code}: {url}")
        return None
    except Exception as e:
        print(f"   [sofa] Blad: {e}")
        return None


def fallback_sofascore_today(today_slug):
    SOFA_TOURNAMENT_ID = 263
    SOFA_SEASON_ID     = 63600

    data = _sofa_fetch(
        f"https://api.sofascore.com/api/v1/unique-tournament/{SOFA_TOURNAMENT_ID}"
        f"/seasons"
    )
    if data:
        seasons = data.get("seasons") or []
        if seasons:
            SOFA_SEASON_ID = seasons[0].get("id", SOFA_SEASON_ID)

    games = []
    for kind in ("next", "last"):
        data = _sofa_fetch(
            f"https://api.sofascore.com/api/v1/unique-tournament/{SOFA_TOURNAMENT_ID}"
            f"/season/{SOFA_SEASON_ID}/events/{kind}/0"
        )
        if not data:
            continue
        for ev in data.get("events") or []:
            ts = ev.get("startTimestamp")
            if not ts:
                continue
            try:
                dt = datetime.fromtimestamp(int(ts), tz=CET)
            except Exception:
                continue
            if dt.strftime("%Y-%m-%d") != today_slug:
                continue
            home_t = ev.get("homeTeam") or {}
            away_t = ev.get("awayTeam") or {}
            h_id   = home_t.get("id")
            a_id   = away_t.get("id")
            games.append({
                "home_team": {
                    "name":    home_t.get("name", "?"),
                    "team_id": h_id,
                    "score":   (ev.get("homeScore") or {}).get("current", 0),
                    "logo":    f"https://api.sofascore.app/api/v1/team/{h_id}/image" if h_id else DEFAULT_LOGO,
                },
                "away_team": {
                    "name":    away_t.get("name", "?"),
                    "team_id": a_id,
                    "score":   (ev.get("awayScore") or {}).get("current", 0),
                    "logo":    f"https://api.sofascore.app/api/v1/team/{a_id}/image" if a_id else DEFAULT_LOGO,
                },
                "date":       datetime.fromtimestamp(int(ts), tz=CET).isoformat(),
                "finished":   (ev.get("status") or {}).get("type") == "finished",
                "stage_name": ((ev.get("roundInfo") or {}).get("name") or ""),
                "round_name": "",
                "odds_home":  None,
                "odds_away":  None,
                "game_id":    ev.get("id"),
            })

    print(f"   [sofa fallback] Znaleziono {len(games)} meczow na {today_slug}")
    return games, "sofascore"


# ==========================================
# MAIN
# ==========================================

def main():
    print(f"=== URUCHAMIAM PLK UPDATE ({datetime.now().strftime('%H:%M')}) ===")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(DEBUG_DIR, exist_ok=True)

    today_slug = get_today_date_str()
    today_str  = datetime.now(CET).strftime("%B %d, %Y")
    season     = pb.default_season()

    print(f"   Data: {today_slug} ({today_str})")
    print(f"   Liga: {TOURNAMENT_NAME_PL}, sezon API: {season}")
    if USE_AI_PREDICTIONS and os.environ.get("GEMINI_API_KEY"):
        print(f"   Tryb predykcji: AI ({AI_MODEL} + Google Search)")
    else:
        print(f"   Tryb predykcji: FORMULA W-L")

    # ── Wczytaj zapisane typy z dzisiaj (zapobiega nadpisywaniu) ──
    saved_predictions = load_saved_predictions(today_slug)

    # ── PRIMARY: PulsBasketu ──
    print("\n=> Probuje PulsBasketu (primary):")
    all_games    = pb.fetch_games_list(season)
    table_by_id  = pb.fetch_table(season)
    today_games  = pb.filter_games_for_date(all_games, today_slug) if all_games else []
    source       = "pulsbasketu" if (all_games or table_by_id) else None

    # ── FALLBACK: Sofascore ──
    if not all_games and not table_by_id:
        print("=> PulsBasketu niedostepne - probuje Sofascore")
        today_games, source = fallback_sofascore_today(today_slug)
        all_games   = today_games
        table_by_id = {}

    print(f"\n   Zrodlo danych: {source or 'BRAK'}")
    print(f"   Mecze na {today_slug}: {len(today_games)}\n")

    # ── BUILD ──
    cards_html, picks, summaries, matches_data = build_game_cards(
        today_games, table_by_id, all_games, today_slug, saved_predictions
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

    if not today_games:
        print(f"\n   Brak meczow PLK na {today_slug}.")

    print(f"\n=== GOTOWE. Otworz {out_path} w przegladarce. ===")


if __name__ == "__main__":
    main()
