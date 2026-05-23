"""
PLK (Polska Liga Koszykowki / Orlen Basket Liga) Free Picks - generator typow.

ARCHITEKTURA (v2):
  - Primary source: PulsBasketu Public API (api.pulsbasketu.com)
    Bogata analityka per-team: ortg/drtg/NetRtg, eFG%, polish_pts_perc,
    opponent stats (jak rywale graja przeciw nam), top scorerzy.
    Trzy endpointy: /games-list, /table, /season-teams/{id}
  - Fallback: Sofascore (uniqueTournament=263) - na wypadek awarii pulsbasketu

URUCHOMIENIE LOKALNE:
    pip install requests google-genai pytz
    export GEMINI_API_KEY=...   # opcjonalne, wlacza AI predictions
    python update_plk.py

Wynik: plk/index.html (otworz w przegladarce)
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
OUTPUT_DIR = "plk"
DEBUG_DIR = "plk/_debug"

# AI
USE_AI_PREDICTIONS = True
AI_MODEL = "gemini-2.5-flash"

# Brand
BRAND_TITLE = "PLK PUBLIC HUB"
BRAND_ACCENT = "#dc2626"
BRAND_DOMAIN = "https://nba-freepicks.com/plk/"

DEFAULT_LOGO = (
    "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    "<circle cx='50' cy='50' r='44' fill='none' stroke='%23dc2626' stroke-width='3'/>"
    "<text y='62' x='50' text-anchor='middle' font-size='42' fill='%23dc2626'>"
    "%F0%9F%8F%80</text></svg>"
)

CET = timezone(timedelta(hours=2))


# ==========================================
# HELPERS - UTILS
# ==========================================

def get_today_date_str():
    return datetime.now(CET).strftime("%Y-%m-%d")


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


def _format_top_scorers(scorers):
    if not scorers:
        return "  - brak danych z PulsBasketu (sprawdz Google Search)"
    lines = []
    for s in scorers:
        bits = [f"{s['name']}: {s['ppg']} ppg"]
        if s.get("apg"):
            bits.append(f"{s['apg']} apg")
        if s.get("rpg"):
            bits.append(f"{s['rpg']} rpg")
        if s.get("mpg"):
            bits.append(f"{s['mpg']} min")
        if s.get("fouls"):
            bits.append(f"{s['fouls']} fauli/mecz")
        lines.append("  - " + ", ".join(bits))
    return "\n".join(lines)


def _format_recent_games(recent, team_id):
    if not recent:
        return "  - brak danych"
    lines = []
    for g in recent:
        date = g.get("date", "")
        opp = g.get("opponent", "?")
        score = g.get("score", "")
        role = g.get("role", "")
        win = "W" if g.get("win") else "L"
        lines.append(f"  - {date} {role} vs {opp}: {score} -> {win}")
    return "\n".join(lines)


def _format_advanced(adv):
    if not adv:
        return "  brak danych"
    parts = []
    if adv.get("ortg"):
        parts.append(f"ORtg {adv['ortg']}")
    if adv.get("drtg"):
        parts.append(f"DRtg {adv['drtg']}")
    if adv.get("net_rtg") is not None:
        parts.append(f"NetRtg {adv['net_rtg']:+}")
    if adv.get("efg"):
        parts.append(f"eFG% {adv['efg']}")
    if adv.get("ts"):
        parts.append(f"TS% {adv['ts']}")
    if adv.get("tov_perc"):
        parts.append(f"TOV% {adv['tov_perc']}")
    if adv.get("oreb_perc"):
        parts.append(f"OREB% {adv['oreb_perc']}")
    if adv.get("dreb_perc"):
        parts.append(f"DREB% {adv['dreb_perc']}")
    if adv.get("polish_pts_perc"):
        parts.append(f"Polish PTS% {adv['polish_pts_perc']}")
    if adv.get("bench_pts_perc"):
        parts.append(f"Bench% {adv['bench_pts_perc']}")
    return "  " + ", ".join(parts)


def build_ai_prompt(home, away, today, table_by_id, all_games):
    """Bogaty prompt z 11 sekcjami danych z PulsBasketu."""
    h_id = home.get("team_id")
    a_id = away.get("team_id")
    h_name = home.get("name") or "Home"
    a_name = away.get("name") or "Away"

    # Bilans z table
    h_rec = pb.get_team_record(table_by_id, h_id)
    a_rec = pb.get_team_record(table_by_id, a_id)
    h_pct = round(100 * h_rec["wins"] / max(1, h_rec["wins"] + h_rec["losses"]))
    a_pct = round(100 * a_rec["wins"] / max(1, a_rec["wins"] + a_rec["losses"]))

    # Forma - streak ostatnie 15
    h_streak = pb.get_streak_last_n(table_by_id, h_id, 15) or "-"
    a_streak = pb.get_streak_last_n(table_by_id, a_id, 15) or "-"

    # Ostatnie 5 meczow
    h_recent = pb.get_recent_games_for_team(table_by_id, h_id, 5)
    a_recent = pb.get_recent_games_for_team(table_by_id, a_id, 5)

    # Per-team rich data (advanced + opponent + top scorers)
    h_st = pb.fetch_season_team(h_id) if h_id else None
    a_st = pb.fetch_season_team(a_id) if a_id else None
    h_adv = pb.get_advanced_stats(h_st)
    a_adv = pb.get_advanced_stats(a_st)
    h_opp = pb.get_opponent_avg_stats(h_st)
    a_opp = pb.get_opponent_avg_stats(a_st)
    h_top = pb.get_top_scorers_for_team(h_st, 3)
    a_top = pb.get_top_scorers_for_team(a_st, 3)

    # H2H
    h2h = pb.get_h2h_in_season(all_games, h_id, a_id)
    h2h_summary = pb.summarize_h2h(h2h, h_id, h_name, a_id, a_name)
    h2h_lines = ("\n   ".join(h2h_summary["games"])) or "brak"

    # Kursy
    odds_h = home.get("__odds_home")  # dorzucone w build_game_cards
    odds_a = home.get("__odds_away")
    implied = pb.get_implied_probabilities(odds_h, odds_a) if (odds_h and odds_a) else None
    odds_str = (f"H {odds_h} ({implied['home_pct'] if implied else '?'}%), "
                f"A {odds_a} ({implied['away_pct'] if implied else '?'}%)") \
        if (odds_h and odds_a) else "brak (mecz przed otwarciem rynku)"

    # Faza i runda
    phase = home.get("__stage_name") or "Sezon zasadniczy"
    rnd = home.get("__round_name") or ""
    arena = home.get("__arena") or ""
    city = home.get("__city") or ""
    referees = home.get("__referees") or []
    ref_str = ", ".join(referees) if referees else "brak danych"

    # ----- SKLADANIE PROMPTA -----
    prompt = f"""
=========================================================================
SYSTEM
=========================================================================
Jestes ekspertem koszykarskim PLK (Orlen Basket Liga). DZISIEJSZA DATA: {today}.
Twoja wiedza wewnetrzna jest przestarzala - sprawdzaj newsy przez Google
Search. NIE ZGADUJ. Brak danych = "brak danych".

=========================================================================
MECZ DZISIAJ
=========================================================================
Faza:    {phase}
Runda:   {rnd}
Hala:    {arena}, {city}
Sedziowie: {ref_str}

GOSPODARZ: {h_name}
GOSC:      {a_name}

=========================================================================
DANE Z PULSBASKETU.COM (sezon 2025/26 do dzisiaj)
=========================================================================

BILANS:
   {h_name}: {h_rec['wins']}-{h_rec['losses']} ({h_pct}%, miejsce #{h_rec.get('real_position') or '?'})
   {a_name}: {a_rec['wins']}-{a_rec['losses']} ({a_pct}%, miejsce #{a_rec.get('real_position') or '?'})

DOM/WYJAZD:
   {h_name} u siebie:    {h_rec['wins_home']}-{h_rec['losses_home']}
   {a_name} na wyjezdzie: {a_rec['wins_away']}-{a_rec['losses_away']}

FORMA - ostatnie 15 wynikow chronologicznie (W=wygrana, najnowszy z prawej):
   {h_name}: {h_streak}
   {a_name}: {a_streak}

OSTATNIE 5 MECZOW:
   {h_name}:
{_format_recent_games(h_recent, h_id)}
   {a_name}:
{_format_recent_games(a_recent, a_id)}

ATAK / OBRONA (sredni na mecz):
   {h_name}: {h_rec['ppg']} pkt zdobytych / {h_rec['papg']} traconych  (NetRating prosty {h_rec['net_rating_simple']:+})
   {a_name}: {a_rec['ppg']} pkt zdobytych / {a_rec['papg']} traconych  (NetRating prosty {a_rec['net_rating_simple']:+})

ADVANCED METRICS (z PulsBasketu, sezon 2025/26):
   {h_name}:
{_format_advanced(h_adv)}
   {a_name}:
{_format_advanced(a_adv)}

JAK RYWALE GRAJA PRZECIW NIM (sygnal slabosci defensywnych):
   przeciw {h_name}: {h_opp.get('points', '?')} pkt/mecz, {h_opp.get('f3p', '?')}% za 3, {h_opp.get('rebounds', '?')} reb
   przeciw {a_name}: {a_opp.get('points', '?')} pkt/mecz, {a_opp.get('f3p', '?')}% za 3, {a_opp.get('rebounds', '?')} reb

TOP SCORERZY (z players[] danego zespolu):
   {h_name}:
{_format_top_scorers(h_top)}
   {a_name}:
{_format_top_scorers(a_top)}

H2H W TYM SEZONIE (zakonczone spotkania):
   {h2h_summary['summary']}
   {h2h_lines}

KURSY BUKMACHERSKIE (jezeli dostepne dla tego meczu):
   {odds_str}

=========================================================================
PROCES (kazdy punkt - Google Search)
=========================================================================
1. KONTUZJE i ZMIANY W SKLADZIE na {today}:
   - sport.pl, plk.pl, polskikosz.pl, sportowefakty.wp.pl
   - Twitter/X klubow ({h_name}, {a_name})
   - Czy lider druzyny jest niezdolny do gry?
   - Czy ktos wraca z kontuzji?

2. FOUL-OUTY i TECHNICZNE w poprzednim meczu serii:
   - Czy lider {h_name} dostal 5 fauli/technicznego w meczu N-1?
   - Jak druzyna radzila sobie wtedy bez niego?

3. KONTEKST PLAYOFFU (jezeli faza != "Runda Zasadnicza"):
   - Stan serii (np. 2-2)? Decydujacy mecz?
   - Czy druzyna w zagrozeniu eliminacji ma "playoff desperation"?
   - Format (do 5 / do 7)?

4. FORMA 3 OSTATNICH MECZOW:
   - Czy momentum sie buduje czy rozpada?
   - Czy gra wynikla z dobrej pracy zespolu czy z formy 1 gracza?

5. KURSY BUKMACHERSKIE jako prior:
   - <1.40 = bardzo mocny faworyt, raczej szanuj
   - 1.80/1.95 = wyrownane, kazdy detal sie liczy

WAGA SYGNALOW (od najwazniejszego):
   1. Aktualne kontuzje liderow
   2. Forma 3 ostatnich meczow + streak
   3. Przewaga domowa w playoffach
   4. H2H w obecnej serii
   5. Net Rating + Advanced (ORtg/DRtg)
   6. Kursy bukmacherskie

=========================================================================
DODATKI OD ADMINA (zostaw puste albo dopisz):
=========================================================================
(brak)

=========================================================================
ODPOWIEDZ - czysty JSON, bez markdown
=========================================================================
{{
  "winner_name": "<dokladna nazwa: '{h_name}' lub '{a_name}'>",
  "confidence": <1-10>,
  "reasoning": "<2-3 zdania po polsku>",
  "key_factors": ["<czynnik 1>", "<czynnik 2>", "<czynnik 3>"],
  "injury_notes": "<co znalazles na DZIS lub 'brak istotnych braków'>",
  "agreement_with_odds": <true|false|"no_odds">
}}
"""
    return prompt


def predict_winner_ai(home, away, today, table_by_id, all_games):
    """Odpala Gemini z bogatym promptem. Zwraca dict albo None."""
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
                    print(f"   ! AI tymczasowo niedostepny ({err_str[:60]}), retry za {wait}s")
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
            "injury_notes": data.get("injury_notes", ""),
            "agreement_with_odds": data.get("agreement_with_odds"),
            "raw_winner_name": ai_winner_raw,
        }
    except Exception as e:
        print(f"   ! Blad AI predict ({a_name} vs {h_name}): {e}")
        return None


def predict_winner_formula(home, away, table_by_id):
    """Fallback formula: wins% + 5% home advantage."""
    h_name = home.get("name") or "Home"
    a_name = away.get("name") or "Away"
    h_id = home.get("team_id")
    a_id = away.get("team_id")
    h_rec = pb.get_team_record(table_by_id, h_id)
    a_rec = pb.get_team_record(table_by_id, a_id)
    h_pct = h_rec["wins"] / max(1, h_rec["wins"] + h_rec["losses"])
    a_pct = a_rec["wins"] / max(1, a_rec["wins"] + a_rec["losses"])
    return h_name if (h_pct + 0.05) > a_pct else a_name


def _is_game_started(game):
    if game.get("finished"):
        return True
    dt = pb.parse_game_date(game)
    if dt is None:
        return False
    return dt <= datetime.now(CET)


def predict_winner(home, away, table_by_id, all_games, game, today_slug, state="pre"):
    """Wybiera zwyciezce. AI tylko dla pre-game."""
    h_name = home.get("name") or "Home"
    a_name = away.get("name") or "Away"

    formula_pick = predict_winner_formula(home, away, table_by_id)

    if state == "post":
        return formula_pick

    if _is_game_started(game):
        print(f"   [TIME-skip] {a_name} vs {h_name} -> mecz w trakcie, formula")
        return formula_pick

    if USE_AI_PREDICTIONS:
        ai_result = predict_winner_ai(home, away, today_slug, table_by_id, all_games)
        if ai_result:
            print(f"   [AI] {a_name} vs {h_name} -> {ai_result['winner']} "
                  f"(conf {ai_result['confidence']}/10)")
            _ai_log.append({
                "matchup": f"{a_name} @ {h_name}",
                "phase": home.get("__stage_name"),
                "round": home.get("__round_name"),
                "date": game.get("date"),
                "ai_pick": ai_result["winner"],
                "formula_pick": formula_pick,
                "agreement": ai_result["winner"] == formula_pick,
                "confidence": ai_result["confidence"],
                "reasoning": ai_result["reasoning"],
                "key_factors": ai_result["key_factors"],
                "injury_notes": ai_result.get("injury_notes", ""),
                "agreement_with_odds": ai_result.get("agreement_with_odds"),
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


def _print_ai_summary(league_label):
    """Pretty-print analiz AI w terminalu (admin-only insight)."""
    if not _ai_log:
        return
    bar = "=" * 72
    print(f"\n{bar}")
    print(f"   ANALIZY AI / DEV PRINT  ({league_label})")
    print(f"{bar}")
    for i, m in enumerate(_ai_log, 1):
        matchup = m.get("matchup", "?")
        phase = m.get("phase") or "-"
        rnd = m.get("round") or ""
        ai_pick = m.get("ai_pick")
        formula_pick = m.get("formula_pick", "-")
        if ai_pick is None:
            print(f"\n   [{i}] {matchup}  ({phase} {rnd})")
            print(f"       AI:        BRAK ODPOWIEDZI -> fallback formula")
            print(f"       Formula:   {formula_pick}")
            note = m.get("note")
            if note:
                print(f"       Note:      {note}")
            continue
        conf = m.get("confidence", "?")
        agreement = "ZGODNE z formula" if m.get("agreement") else "ROZNI sie od formuly"
        reasoning = (m.get("reasoning") or "").strip() or "(brak)"
        factors = m.get("key_factors") or []
        injury = (m.get("injury_notes") or "").strip()
        odds_agree = m.get("agreement_with_odds")
        print(f"\n   [{i}] {matchup}  ({phase} {rnd})")
        print(f"       AI pick:   {ai_pick}   (conf {conf}/10)")
        print(f"       Formula:   {formula_pick}   [{agreement}]")
        if odds_agree is not None and odds_agree != "no_odds":
            print(f"       Vs Odds:   {'zgodne' if odds_agree else 'KONTRA bukmacherzy'}")
        print(textwrap.fill(reasoning, width=72,
                            initial_indent="       Reason:    ",
                            subsequent_indent="                  "))
        if factors:
            print(f"       Czynniki:")
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
    path = os.path.join(OUTPUT_DIR, "ai_analyses.json")
    payload = {
        "generated_at": datetime.now().isoformat(),
        "date": today_slug,
        "league": "PLK",
        "model": AI_MODEL,
        "data_source": "pulsbasketu.com",
        "matches": _ai_log,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"   Zapisano analizy AI do {path}")
    _print_ai_summary("PLK")


# ==========================================
# CSS (bez zmian)
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
# BUILDER KART MECZOW (PulsBasketu format)
# ==========================================

def build_game_cards(today_games, table_by_id, all_games, today_slug):
    cards_html = ""
    picks = []
    summaries = []

    for g in today_games:
        try:
            home = dict(g.get("home_team") or {})
            away = dict(g.get("away_team") or {})
            if not home or not away:
                continue

            # Doklejamy meta z meczu do home/away dictow zeby przekazac do AI prompta
            meta = {
                "__odds_home": g.get("odds_home"),
                "__odds_away": g.get("odds_away"),
                "__stage_name": g.get("stage_name"),
                "__round_name": g.get("round_name"),
                "__arena": g.get("arena"),
                "__city": g.get("city"),
                "__referees": g.get("referees") or [],
            }
            home.update(meta)
            away.update(meta)

            h_name = home.get("name") or "?"
            a_name = away.get("name") or "?"
            h_logo = home.get("logo") or DEFAULT_LOGO
            a_logo = away.get("logo") or DEFAULT_LOGO
            h_score = int(home.get("score") or 0)
            a_score = int(away.get("score") or 0)

            state = pb.game_status(g)
            predicted_winner = predict_winner(home, away, table_by_id, all_games, g, today_slug, state)

            if state == "pre":
                tip = pb.fmt_game_time(g)
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
            else:  # post
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
# BUILDER STRONY (bez zmian wzgledem v1)
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
            Last updated: {datetime.now().strftime("%B %d, %Y at %H:%M")} &middot; Data: pulsbasketu.com
        </div>
    </div>
</body>
</html>"""


# ==========================================
# FALLBACK SOFASCORE (legacy, na wypadek awarii pulsbasketu)
# ==========================================

SOFA_BASE = "https://api.sofascore.com/api/v1"
SOFA_TOURNAMENT_ID = 263
SOFA_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/123.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.sofascore.com/",
}


def _sofa_fetch(url):
    try:
        r = requests.get(url, headers=SOFA_HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def fallback_sofascore_today(today_slug):
    """Mininalny scenariusz: pobiera mecze sofascore, konwertuje na pulsbasketu format.
    Wywolywany gdy pulsbasketu zwroci pustke."""
    print("   [fallback] proba pobrania danych z sofascore...")
    seasons = _sofa_fetch(f"{SOFA_BASE}/unique-tournament/{SOFA_TOURNAMENT_ID}/seasons")
    if not seasons:
        print("   [fallback] sofascore /seasons -> brak odpowiedzi")
        return [], None

    # wybierz aktualny sezon
    current = None
    for s in seasons.get("seasons") or []:
        year = str(s.get("year") or "")
        if "25/26" in year or year.startswith("25"):
            current = s
            break
    if not current and (seasons.get("seasons") or []):
        current = seasons["seasons"][0]
    if not current:
        return [], None

    season_id = current.get("id")
    out_games = []
    for kind in ("next", "last"):
        d = _sofa_fetch(f"{SOFA_BASE}/unique-tournament/{SOFA_TOURNAMENT_ID}/season/{season_id}/events/{kind}/0")
        if not d:
            continue
        for ev in d.get("events") or []:
            ts = ev.get("startTimestamp")
            if not ts:
                continue
            try:
                dt = datetime.fromtimestamp(int(ts), tz=CET)
            except Exception:
                continue
            if dt.strftime("%Y-%m-%d") != today_slug:
                continue
            # konwertuj na pulsbasketu-like format
            home = ev.get("homeTeam") or {}
            away = ev.get("awayTeam") or {}
            sc_h = (ev.get("homeScore") or {}).get("current") or 0
            sc_a = (ev.get("awayScore") or {}).get("current") or 0
            status_t = ((ev.get("status") or {}).get("type") or "").lower()
            finished = status_t in ("finished", "ended", "afterextra", "afterpenalties")
            out_games.append({
                "game_id": ev.get("id"),
                "date": dt.replace(tzinfo=None).isoformat(),
                "finished": finished,
                "home_team": {
                    "team_id": None,  # sofa ID inne niz pulsbasketu
                    "name": home.get("name", "?"),
                    "score": sc_h,
                    "logo": f"https://api.sofascore.app/api/v1/team/{home.get('id')}/image" if home.get("id") else DEFAULT_LOGO,
                },
                "away_team": {
                    "team_id": None,
                    "name": away.get("name", "?"),
                    "score": sc_a,
                    "logo": f"https://api.sofascore.app/api/v1/team/{away.get('id')}/image" if away.get("id") else DEFAULT_LOGO,
                },
                "stage_name": ((ev.get("roundInfo") or {}).get("name")) or None,
                "round_name": str((ev.get("roundInfo") or {}).get("round") or "") or None,
                "city": None,
                "arena": None,
                "referees": [],
                "odds_home": None,
                "odds_away": None,
            })
    print(f"   [fallback] sofascore znalazl {len(out_games)} meczow na {today_slug}")
    return out_games, "sofascore"


# ==========================================
# MAIN
# ==========================================

def main():
    print(f"=== URUCHAMIAM PLK UPDATE ({datetime.now().strftime('%H:%M')}) ===")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    today_slug = get_today_date_str()
    today_str = datetime.now().strftime("%B %d, %Y")
    season = pb.default_season()
    print(f"   Data: {today_slug} ({today_str})")
    print(f"   Liga: {TOURNAMENT_NAME_PL}, sezon API: {season}")

    if USE_AI_PREDICTIONS and os.environ.get("GEMINI_API_KEY"):
        print(f"   Tryb predykcji: AI ({AI_MODEL} + Google Search)")
    elif USE_AI_PREDICTIONS:
        print(f"   Tryb predykcji: FORMULA W-L (brak GEMINI_API_KEY)")
    else:
        print(f"   Tryb predykcji: FORMULA W-L (USE_AI_PREDICTIONS=False)")
    print()

    # ====== PRIMARY: PulsBasketu ======
    print("=> Probuje PulsBasketu (primary):")
    all_games = pb.fetch_games_list(season)
    table_by_id = pb.fetch_table(season)

    today_games = pb.filter_games_for_date(all_games, today_slug) if all_games else []
    source = "pulsbasketu" if (all_games or table_by_id) else None

    # ====== FALLBACK: Sofascore (jak pulsbasketu padl) ======
    if not all_games and not table_by_id:
        print("=> PulsBasketu nie zwrocil danych - probuje fallback Sofascore")
        today_games, source = fallback_sofascore_today(today_slug)
        all_games = today_games  # tylko dzisiejsze (sofascore fallback)
        table_by_id = {}  # pusta tabela -> AI dostanie 0-0, formula bedzie 50/50

    print(f"\n   Zrodlo danych: {source or 'BRAK'}")
    print(f"   Mecze na {today_slug}: {len(today_games)}")
    print()

    # ====== BUILD ======
    cards_html, picks, summaries = build_game_cards(today_games, table_by_id, all_games, today_slug)

    out_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(build_page(today_str, cards_html, summaries))
    print(f"\n-> Zapisano {out_path}")

    if picks:
        save_picks_for_audit(picks, today_slug)
    else:
        print("   Brak typow pre-game (gry juz w trakcie/zakonczone albo brak meczow).")

    save_ai_log(today_slug)

    if not today_games:
        print(f"\n   Brak meczow PLK na {today_slug} (zarowno z pulsbasketu jak i sofascore).")
        print(f"   Sprawdz {DEBUG_DIR}/pb_*.json - czy w API sa mecze?")

    print(f"\n=== GOTOWE. Otworz {out_path} w przegladarce. ===")


if __name__ == "__main__":
    main()
