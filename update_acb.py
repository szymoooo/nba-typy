"""
ACB (Liga Endesa, Hiszpania) Free Picks.

Zrodlo danych: TheSportsDB public API (key=123, brak auth, nie blokuje CI).
https://www.thesportsdb.com/league/4408-spanish-liga-acb

URUCHOMIENIE LOKALNE:
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

import tsdb_data as td

LEAGUE_NAME = "Liga Endesa (ACB)"
OUTPUT_DIR = "acb"
DEBUG_DIR = "acb/_debug"
TSDB_LEAGUE_ID = "4408"
TSDB_SEASON = "2025-2026"

USE_AI_PREDICTIONS = os.environ.get("PLK_LIVE_MODE", "").lower() not in ("true", "1", "yes")
AI_MODEL = "gemini-2.5-flash"
BRAND_TITLE = "ACB PUBLIC HUB"
BRAND_ACCENT = "#c8102e"

DEFAULT_LOGO = (
    "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    "<circle cx='50' cy='50' r='44' fill='none' stroke='%23c8102e' stroke-width='3'/>"
    "<text y='62' x='50' text-anchor='middle' font-size='42' fill='%23c8102e'>"
    "%F0%9F%8F%80</text></svg>"
)

CET = timezone(timedelta(hours=2))
_gemini_client = None
_ai_log = []


def get_today_str():
    return datetime.now(CET).strftime("%Y-%m-%d")


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
            if w in h.lower():
                return h
            if w in a.lower():
                return a
    return None


def build_prompt(ev, table, season_events, today):
    h_name = ev.get("strHomeTeam", "Home")
    a_name = ev.get("strAwayTeam", "Away")
    phase = ev.get("strRound") or ev.get("intRound") or "Sezon zasadniczy"
    venue = ev.get("strVenue") or "?"
    city = ev.get("strCity") or ""

    # Bilans ogolny
    h_row = td.get_team_row(table, h_name)
    a_row = td.get_team_row(table, a_name)
    h_w, h_l = h_row.get("wins", 0), h_row.get("losses", 0)
    a_w, a_l = a_row.get("wins", 0), a_row.get("losses", 0)
    h_pct = round(100 * h_w / max(1, h_w + h_l))
    a_pct = round(100 * a_w / max(1, a_w + a_l))

    # Dom/wyjazd
    h_ha = td.get_home_away_record(table, h_name)
    a_ha = td.get_home_away_record(table, a_name)

    # PPG / PAPG / NetRtg
    h_ppg, h_papg, h_net = td.get_ppg_papg(table, h_name)
    a_ppg, a_papg, a_net = td.get_ppg_papg(table, a_name)

    # Forma: streak 15 + ostatnie 5
    h_streak = td.get_streak(table, h_name, 15)
    a_streak = td.get_streak(table, a_name, 15)
    h_recent = td.get_recent_games(table, h_name, 5)
    a_recent = td.get_recent_games(table, a_name, 5)

    # H2H
    h2h = td.get_h2h(season_events, h_name, a_name)
    h2h_text = td.format_h2h(h2h, h_name, a_name)

    return f"""
=========================================================================
SYSTEM
=========================================================================
Jestes ekspertem koszykarskim ACB (Liga Endesa, Hiszpania).
DZISIEJSZA DATA: {today}. Twoja wiedza jest przestarzala - sprawdzaj przez
Google Search. NIE ZGADUJ. Brak danych = "brak danych".

=========================================================================
MECZ DZISIAJ
=========================================================================
Liga:    {LEAGUE_NAME}
Runda:   {phase}
Hala:    {venue}{', ' + city if city else ''}
Tip-off: {td.fmt_time_cet(ev)}

GOSPODARZ: {h_name}
GOSC:      {a_name}

=========================================================================
DANE Z THESPORTSDB (sezon {TSDB_SEASON})
=========================================================================

BILANS OGOLNY:
   {h_name}: {h_w}-{h_l} ({h_pct}%)
   {a_name}: {a_w}-{a_l} ({a_pct}%)

BILANS DOM / WYJAZD:
   {h_name} u siebie:    {h_ha['wins_home']}-{h_ha['losses_home']}
   {a_name} na wyjezdzie: {a_ha['wins_away']}-{a_ha['losses_away']}

ATAK / OBRONA (srednie na mecz):
   {h_name}: {h_ppg} pkt zdobytych / {h_papg} traconych  (NetRtg {h_net:+})
   {a_name}: {a_ppg} pkt zdobytych / {a_papg} traconych  (NetRtg {a_net:+})

FORMA - ostatnie 15 wynikow (W=wygrana, najnowszy z prawej):
   {h_name}: {h_streak}
   {a_name}: {a_streak}

OSTATNIE 5 MECZOW:
   {h_name}:
{td.format_recent_games(h_recent)}
   {a_name}:
{td.format_recent_games(a_recent)}

H2H W TYM SEZONIE (zakonczone spotkania):
   {h2h_text}

=========================================================================
ZADANIE - Google Search dla kazdego punktu:
=========================================================================
1. KONTUZJE na {today}:
   - acb.com, marca.com, sport.es, as.com, X/Twitter klubow
   - Czy lider druzyny jest niezdolny do gry?
   - Czy ktos wraca z kontuzji?

2. FOUL-OUTY i TECHNICZNE w poprzednim meczu:
   - Czy ktos dostal 5 fauli lub technicznego w ostatnim meczu?

3. KONTEKST PLAYOFFU (jezeli faza != sezon zasadniczy):
   - Stan serii? Decydujacy mecz?
   - Efekt "playoff desperation" - druzyna zagroziona eliminacja gra agresywniej
   - ACB playoff format do 3 wygranych

4. FORMA 3 OSTATNICH MECZOW + momentum:
   - Czy forma pochodzi z gry zespolowej czy z jednego gracza?

WAGA SYGNALOW (od najwazniejszego):
   1. Aktualne kontuzje liderow
   2. Forma 3 ostatnich meczow + streak
   3. Przewaga domowa (ACB: ~60% wygranych u siebie)
   4. H2H w tym sezonie
   5. NetRtg + bilans dom/wyjazd

=========================================================================
ODPOWIEDZ - czysty JSON, bez markdown:
=========================================================================
{{
  "winner_name": "<dokladna nazwa: '{h_name}' lub '{a_name}'>",
  "confidence": <1-10>,
  "reasoning": "<2-3 zdania po polsku>",
  "key_factors": ["<czynnik 1>", "<czynnik 2>", "<czynnik 3>"],
  "injury_notes": "<co znalazles na DZIS lub 'brak istotnych brakow'>",
  "agreement_with_odds": "no_odds"
}}
"""


def predict_ai(ev, table, season_events, today):
    client = _get_gemini()
    if not client:
        return None
    h_name = ev.get("strHomeTeam", "Home")
    a_name = ev.get("strAwayTeam", "Away")
    prompt = build_prompt(ev, table, season_events, today)
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
        print(f"   ! AI ACB: {e}")
        return None


def predict(ev, table, season_events, today_slug):
    h_name = ev.get("strHomeTeam", "Home")
    a_name = ev.get("strAwayTeam", "Away")
    h_pct = td.get_win_pct(table, h_name)
    a_pct = td.get_win_pct(table, a_name)
    formula = h_name if (h_pct + 0.05) > a_pct else a_name

    status = td.game_status(ev)
    if status == "post":
        return formula

    ts = ev.get("strTimestamp") or f"{today_slug}T00:00:00"
    try:
        game_dt = datetime.fromisoformat(ts).replace(tzinfo=CET)
        if game_dt <= datetime.now(CET):
            print(f"   [TIME-skip] {a_name} vs {h_name} -> formula")
            return formula
    except Exception:
        pass

    if USE_AI_PREDICTIONS:
        result = predict_ai(ev, table, season_events, today_slug)
        if result:
            print(f"   [AI] {a_name} vs {h_name} -> {result['winner']} (conf {result['confidence']}/10)")
            _ai_log.append({
                "matchup": f"{a_name} @ {h_name}",
                "phase": str(ev.get("strRound") or ev.get("intRound") or "?"),
                "ai_pick": result["winner"],
                "formula_pick": formula,
                "agreement": result["winner"] == formula,
                "confidence": result["confidence"],
                "reasoning": result["reasoning"],
                "key_factors": result["key_factors"],
                "injury_notes": result.get("injury_notes", ""),
            })
            time.sleep(1)
            return result["winner"]
        print(f"   [FORMULA-fallback] {a_name} vs {h_name} -> {formula}")
        _ai_log.append({"matchup": f"{a_name} @ {h_name}", "ai_pick": None,
                        "formula_pick": formula, "note": "AI fallback"})
    return formula


def save_ai_log(today_slug):
    if not _ai_log:
        return
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "ai_analyses.json"), "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now().isoformat(), "date": today_slug,
                   "league": "ACB", "model": AI_MODEL, "matches": _ai_log},
                  f, indent=2, ensure_ascii=False)
    bar = "=" * 72
    print(f"\n{bar}\n   ANALIZY AI / DEV PRINT  (ACB)\n{bar}")
    for i, m in enumerate(_ai_log, 1):
        ai = m.get("ai_pick")
        if not ai:
            print(f"\n   [{i}] {m['matchup']}: BRAK AI -> {m.get('formula_pick')}")
            continue
        ag = "ZGODNE" if m.get("agreement") else "ROZNI sie od formuly"
        print(f"\n   [{i}] {m['matchup']}  ({m.get('phase') or '-'})")
        print(f"       AI pick:  {ai}  (conf {m.get('confidence')}/10)  [{ag}]")
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


def save_picks(picks, today_slug):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "propozycje_typow.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# ACB typy na {today_slug}\n")
        f.write("\n".join(picks))
    print(f"   Zapisano {len(picks)} typow do {path}")


# ==========================================
# HTML
# ==========================================

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
       transition:transform .2s,box-shadow .2s;}}
.card:hover{{transform:translateY(-5px);border-color:var(--acc);}}
.card-h{{background:rgba(0,0,0,.3);padding:12px 25px;text-align:center;border-bottom:1px solid var(--br);
         font-size:.75rem;font-weight:900;color:var(--sub);text-transform:uppercase;letter-spacing:1px;}}
.card-h.live{{color:#ef4444;animation:pulse 1.5s infinite;}}
.matchup{{display:flex;justify-content:space-between;align-items:stretch;padding:30px 20px;flex-grow:1;gap:12px;}}
.team{{text-align:center;flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;gap:14px;}}
.team img{{width:100px;height:100px;object-fit:contain;background:rgba(255,255,255,.04);border-radius:12px;padding:6px;}}
.team-name{{font-weight:900;font-size:.85rem;text-transform:uppercase;word-wrap:break-word;}}
.scores{{display:flex;align-items:center;justify-content:center;gap:15px;}}
.score{{font-size:2.8rem;font-weight:900;line-height:1;}}
.score.win{{color:var(--win);}}
.score.lose{{color:var(--sub);opacity:.8;}}
.vs{{color:var(--br);font-style:italic;font-weight:900;font-size:1.5rem;}}
.pred{{background:rgba(15,23,42,.6);padding:20px;text-align:center;border-top:1px solid var(--br);margin-top:auto;}}
.pred-l{{font-size:.7rem;color:var(--sub);text-transform:uppercase;font-weight:700;letter-spacing:1px;margin-bottom:8px;}}
.pred-v{{font-size:1.2rem;font-weight:900;}}
.empty{{text-align:center;color:#888;padding:60px 20px;line-height:1.6;}}
.empty .ico{{font-size:3rem;display:block;margin-bottom:16px;}}
.footer{{text-align:center;color:var(--sub);font-size:.75rem;margin-top:50px;padding-bottom:20px;}}
@keyframes pulse{{0%,100%{{opacity:1;}}50%{{opacity:.5;}}}}
@media(max-width:768px){{.grid{{grid-template-columns:1fr;}}.score{{font-size:2.2rem;}}}}
"""


def build_cards(games, table, season_events, today_slug):
    cards = []
    picks = []
    summaries = []
    for ev in games:
        try:
            h_name = ev.get("strHomeTeam", "?")
            a_name = ev.get("strAwayTeam", "?")
            h_logo = td.team_logo(ev, "home", DEFAULT_LOGO)
            a_logo = td.team_logo(ev, "away", DEFAULT_LOGO)
            h_score = td.score(ev, "home")
            a_score = td.score(ev, "away")
            status = td.game_status(ev)
            pick = predict(ev, table, season_events, today_slug)

            if status == "pre":
                tip = td.fmt_time_cet(ev)
                status_label = tip or "Scheduled"
                score_html = '<span class="vs">VS</span>'
                picks.append(f"{a_name} @ {h_name} -> Typ: {pick}")
                summaries.append(f"{a_name} vs {h_name}: AI prediction - {pick} to win")
                outcome = ""
            elif status == "in":
                status_label = "LIVE"
                score_html = (f'<span class="score">{a_score}</span>'
                              f'<span class="vs">:</span>'
                              f'<span class="score">{h_score}</span>')
                outcome = ""
            else:
                status_label = "Final"
                actual = h_name if h_score > a_score else (a_name if a_score > h_score else "")
                hc = "score win" if h_score > a_score else ("score lose" if h_score < a_score else "score")
                ac = "score win" if a_score > h_score else ("score lose" if a_score < h_score else "score")
                score_html = (f'<span class="{ac}">{a_score}</span>'
                              f'<span class="vs">:</span>'
                              f'<span class="{hc}">{h_score}</span>')
                if actual:
                    outcome = (' <span style="color:#10b981">&#10003;</span>' if pick == actual
                               else ' <span style="color:#ef4444">&#10007;</span>')
                else:
                    outcome = ""

            live_class = " live" if status == "in" else ""
            cards.append(f"""
            <div class="card">
              <div class="card-h{live_class}">{status_label}</div>
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
            </div>""")
        except Exception as e:
            print(f"   Blad przy meczu ACB: {e}")
    return "".join(cards), picks, summaries


def build_page(title_date, cards_html, summaries):
    desc = " | ".join(summaries[:4]) or f"ACB AI picks for {title_date}"
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>ACB AI Picks {title_date} - Liga Endesa</title>
  <meta name="description" content="{desc[:160]}">
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800;900&display=swap" rel="stylesheet">
  <style>{CSS}</style>
</head>
<body>
  <div class="container">
    <header>
      <h1>{BRAND_TITLE}</h1>
      <div class="sub">{LEAGUE_NAME} &middot; Live Scores &amp; AI Model Picks &mdash; {title_date}</div>
    </header>
    <div class="grid">
      {cards_html or '<div class="empty"><span class="ico">&#127936;</span>Brak meczow ACB na dzis.</div>'}
    </div>
    <div class="footer">
      Last updated: {datetime.now().strftime("%B %d, %Y at %H:%M")} &middot; Data: TheSportsDB
    </div>
  </div>
</body>
</html>"""


# ==========================================
# MAIN
# ==========================================

def main():
    print(f"=== URUCHAMIAM ACB UPDATE ({datetime.now().strftime('%H:%M')}) ===")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    today_slug = get_today_str()
    today_str = datetime.now().strftime("%B %d, %Y")
    print(f"   Data: {today_slug}")
    print(f"   Tryb: {'AI (' + AI_MODEL + ')' if USE_AI_PREDICTIONS and os.environ.get('GEMINI_API_KEY') else 'FORMULA W-L'}")
    print(f"   Zrodlo: TheSportsDB (league {TSDB_LEAGUE_ID})")

    # Pelny sezon -> tabela + H2H
    season_events = td.fetch_season_events(TSDB_LEAGUE_ID, TSDB_SEASON, DEBUG_DIR)
    if season_events:
        table = td.build_table_from_events(season_events)
    else:
        print("   [warn] Brak eventow sezonu, fallback na lookuptable")
        table = td.fetch_table(TSDB_LEAGUE_ID, TSDB_SEASON, DEBUG_DIR)

    # Mecze na dzis
    games = td.fetch_games_today(TSDB_LEAGUE_ID, today_slug, DEBUG_DIR)

    cards_html, picks, summaries = build_cards(games, table, season_events, today_slug)

    out = os.path.join(OUTPUT_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build_page(today_str, cards_html, summaries))
    print(f"\n-> Zapisano {out}")

    if picks:
        save_picks(picks, today_slug)
    else:
        print("   Brak typow pre-game.")

    save_ai_log(today_slug)
    print(f"\n=== GOTOWE. Otworz {out} ===")


if __name__ == "__main__":
    main()
