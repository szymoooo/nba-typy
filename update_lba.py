"""
LBA (Lega Basket Serie A) Free Picks - generator typow.

Zrodlo danych: legabasket.it public API (no-auth, odkryte DevTools).
Endpointy: /api/championships/..., /api/statistics/..., /api/teams/...

URUCHOMIENIE LOKALNE:
    pip install requests google-genai pytz
    export GEMINI_API_KEY=...   # opcjonalne, wlacza AI
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
LEAGUE_NAME = "Lega Basket Serie A"
OUTPUT_DIR = "lba"
DEBUG_DIR = "lba/_debug"

USE_AI_PREDICTIONS = os.environ.get("PLK_LIVE_MODE", "").lower() not in ("true", "1", "yes")
AI_MODEL = "gemini-2.5-flash"

BRAND_TITLE = "LBA PUBLIC HUB"
BRAND_ACCENT = "#006db7"   # niebieski LBA

DEFAULT_LOGO = (
    "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    "<circle cx='50' cy='50' r='44' fill='none' stroke='%23006db7' stroke-width='3'/>"
    "<text y='62' x='50' text-anchor='middle' font-size='42' fill='%23006db7'>"
    "%F0%9F%8F%80</text></svg>"
)

CET = timezone(timedelta(hours=2))

_gemini_client = None
_ai_log = []


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


def build_prompt(match, table, all_matches, player_stats, today):
    h_id = match.get("h_team_id")
    v_id = match.get("v_team_id")
    h_name = match.get("h_team_name") or "Home"
    v_name = match.get("v_team_name") or "Away"

    # --- Bilans ogólny ---
    h_row = table.get(h_id) or {}
    v_row = table.get(v_id) or {}
    h_w, h_l = h_row.get("wins", 0), h_row.get("losses", 0)
    v_w, v_l = v_row.get("wins", 0), v_row.get("losses", 0)
    h_pct = round(100 * h_w / max(1, h_w + h_l))
    v_pct = round(100 * v_w / max(1, v_w + v_l))

    # --- Bilans dom/wyjazd ---
    h_ha = ld.get_home_away_record(table, h_id)
    v_ha = ld.get_home_away_record(table, v_id)

    # --- PPG / PAPG / NetRtg ---
    h_ppg, h_papg, h_net = ld.get_ppg_papg(table, h_id)
    v_ppg, v_papg, v_net = ld.get_ppg_papg(table, v_id)

    # --- Forma: streak 15 + ostatnie 5 meczów ---
    h_streak = ld.get_streak(table, h_id, 15)
    v_streak = ld.get_streak(table, v_id, 15)
    h_recent = ld.get_recent_games(table, h_id, 5)
    v_recent = ld.get_recent_games(table, v_id, 5)

    # --- Top scorerzy z APG/RPG/SPG ---
    h_top = ld.get_top_scorers_by_team(player_stats, h_id, 3)
    v_top = ld.get_top_scorers_by_team(player_stats, v_id, 3)

    # --- H2H ---
    h2h_text = ld.format_h2h(
        ld.get_h2h_in_season(all_matches, h_id, v_id),
        h_id, h_name, v_id, v_name
    )

    # --- Metadane meczu ---
    arena = match.get("plant_name") or "?"
    city = match.get("town_name") or "?"
    day_name = match.get("day_name") or "?"
    hour = ld.fmt_match_time(match)

    # --- Stan serii playoff ---
    match_serie = match.get("match_serie") or ""
    serie_wins = match.get("match_hw", 0) or 0
    serie_losses = match.get("match_vw", 0) or 0
    series_text = ""
    if match_serie:
        series_text = (
            f"\nSTAN SERII PLAYOFF:\n"
            f"  {h_name}: {serie_wins} wygrane\n"
            f"  {v_name}: {serie_losses} wygrane\n"
            f"  Format meczu: {match_serie}"
        )

    prompt = f"""
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

BILANS OGOLNY:
   {h_name}: {h_w}-{h_l} ({h_pct}%)
   {v_name}: {v_w}-{v_l} ({v_pct}%)

BILANS DOM / WYJAZD:
   {h_name} u siebie:    {h_ha['wins_home']}-{h_ha['losses_home']}
   {v_name} na wyjezdzie: {v_ha['wins_away']}-{v_ha['losses_away']}

ATAK / OBRONA (srednie na mecz, sezon zasadniczy):
   {h_name}: {h_ppg} pkt zdobytych / {h_papg} traconych  (NetRtg {h_net:+})
   {v_name}: {v_ppg} pkt zdobytych / {v_papg} traconych  (NetRtg {v_net:+})
{series_text}
FORMA - ostatnie 15 wynikow (W=wygrana, najnowszy z prawej):
   {h_name}: {h_streak}
   {v_name}: {v_streak}

OSTATNIE 5 MECZOW:
   {h_name}:
{ld.format_recent_games(h_recent)}
   {v_name}:
{ld.format_recent_games(v_recent)}

TOP SCORERZY (statystyki sezonowe):
   {h_name}:
{ld.format_top_scorers(h_top)}
   {v_name}:
{ld.format_top_scorers(v_top)}

H2H W TYM SEZONIE (zakonczone spotkania):
   {h2h_text}

=========================================================================
ZADANIE - Google Search dla kazdego punktu:
=========================================================================
1. KONTUZJE na {today}:
   - legabasket.it, basketinside.com, gazzetta.it, X/Twitter klubow
   - WAZNE: filtruj tylko koszykowke (nie pilka nozna)
   - Czy lider druzyny jest niezdolny do gry?

2. FOUL-OUTY i TECHNICZNE w poprzednim meczu serii:
   - Czy ktos dostal 5 fauli lub technicznego w ostatnim meczu?

3. KONTEKST PLAYOFFU (jezeli faza != sezon zasadniczy):
   - Decydujacy mecz? Druzyna w zagrozeniu eliminacji?
   - Efekt "playoff desperation" - druzyna eliminowana gra agresywniej

4. FORMA 3 OSTATNICH MECZOW + momentum:
   - Czy forma pochodzi z gry zespolowej czy z jednego gracza?

WAGA SYGNALOW (od najwazniejszego):
   1. Aktualne kontuzje liderow
   2. Forma 3 ostatnich meczow + streak
   3. Przewaga domowa (LBA: ~60% wygranych u siebie)
   4. H2H w obecnej serii playoff
   5. NetRtg + bilans dom/wyjazd

=========================================================================
ODPOWIEDZ - czysty JSON, bez markdown:
=========================================================================
{{
  "winner_name": "<dokladna nazwa: '{h_name}' lub '{v_name}'>",
  "confidence": <1-10>,
  "reasoning": "<2-3 zdania po polsku>",
  "key_factors": ["<czynnik 1>", "<czynnik 2>", "<czynnik 3>"],
  "injury_notes": "<co znalazles na DZIS lub 'brak istotnych brakow'>",
  "agreement_with_odds": "no_odds"
}}
"""
    return prompt


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
                    model=AI_MODEL,
                    contents=prompt,
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
        winner = _norm_name(data.get("winner_name"), h_name, v_name)
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
        print(f"   ! AI LBA: {e}")
        return None


def predict_formula(match, table):
    h_id = match.get("h_team_id")
    v_id = match.get("v_team_id")
    h_name = match.get("h_team_name") or "Home"
    v_name = match.get("v_team_name") or "Away"
    h_pct = ld.get_win_pct(table, h_id)
    v_pct = ld.get_win_pct(table, v_id)
    return h_name if (h_pct + 0.05) > v_pct else v_name


def predict(match, table, all_matches, player_stats, today):
    h_name = match.get("h_team_name") or "Home"
    v_name = match.get("v_team_name") or "Away"
    h_id = match.get("h_team_id")
    v_id = match.get("v_team_id")
    formula = predict_formula(match, table)
    state = ld.match_status(match)

    if state == "post":
        return formula

    dt = ld.parse_match_dt(match)
    if dt and dt <= datetime.now(CET):
        print(f"   [TIME-skip] {v_name} vs {h_name} -> mecz w trakcie, formula")
        return formula

    if USE_AI_PREDICTIONS:
        result = predict_ai(match, table, all_matches, player_stats, today)
        if result:
            print(f"   [AI] {v_name} vs {h_name} -> {result['winner']} (conf {result['confidence']}/10)")
            _ai_log.append({
                "matchup": f"{v_name} @ {h_name}",
                "day": match.get("day_name"),
                "date": match.get("match_datetime"),
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
        print(f"   [FORMULA-fallback] {v_name} vs {h_name} -> {formula}")
        _ai_log.append({"matchup": f"{v_name} @ {h_name}", "ai_pick": None,
                        "formula_pick": formula, "note": "AI fallback"})
    return formula


def save_ai_log(today_slug):
    if not _ai_log:
        return
    path = os.path.join(OUTPUT_DIR, "ai_analyses.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now().isoformat(), "date": today_slug,
                   "league": "LBA", "model": AI_MODEL, "matches": _ai_log},
                  f, indent=2, ensure_ascii=False)
    print(f"   Zapisano ai_analyses.json")

    # pretty print
    if not _ai_log:
        return
    bar = "=" * 72
    print(f"\n{bar}\n   ANALIZY AI / DEV PRINT  (LBA)\n{bar}")
    for i, m in enumerate(_ai_log, 1):
        ai = m.get("ai_pick")
        if not ai:
            print(f"\n   [{i}] {m['matchup']}: BRAK AI -> {m.get('formula_pick')}")
            continue
        conf = m.get("confidence", "?")
        ag = "ZGODNE" if m.get("agreement") else "ROZNI sie od formuly"
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
# HTML
# ==========================================

CSS = f"""
  :root {{--bg:#0f172a;--card:#1e293b;--acc:{BRAND_ACCENT};--tx:#f8fafc;
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
  .card:hover{{transform:translateY(-5px);box-shadow:0 20px 25px -5px rgba(0,0,0,.3);border-color:var(--acc);}}
  .card-h{{background:rgba(0,0,0,.3);padding:12px 25px;text-align:center;border-bottom:1px solid var(--br);
           font-size:.75rem;font-weight:900;color:var(--sub);text-transform:uppercase;letter-spacing:1px;}}
  .card-h.live{{color:#ef4444;animation:pulse 1.5s infinite;}}
  .matchup{{display:flex;justify-content:space-between;align-items:stretch;padding:30px 20px;flex-grow:1;gap:12px;}}
  .team{{text-align:center;flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;gap:14px;}}
  .team img{{width:100px;height:100px;object-fit:contain;background:rgba(255,255,255,.04);
             border-radius:12px;padding:6px;}}
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


def build_cards(today_matches, table, all_matches, player_stats, today_slug):
    cards = picks = summaries = ""
    cards_list = []
    picks_list = []
    summaries_list = []
    cdn_url = None  # będzie ustawiony z pierwszego meczu

    for m in today_matches:
        try:
            h_name = m.get("h_team_name") or "?"
            v_name = m.get("v_team_name") or "?"
            h_logo_key = m.get("home_logo_key") or ""
            v_logo_key = m.get("v_logo_key") or ""
            h_logo = ld.logo_url(h_logo_key, cdn_url) or DEFAULT_LOGO
            v_logo = ld.logo_url(v_logo_key, cdn_url) or DEFAULT_LOGO
            h_score = int(m.get("home_final_score") or 0)
            v_score = int(m.get("visitor_final_score") or 0)

            state = ld.match_status(m)
            pick = predict(m, table, all_matches, player_stats, today_slug)

            if state == "pre":
                tip = ld.fmt_match_time(m)
                status = tip or "Scheduled"
                score_html = '<span class="vs">VS</span>'
                picks_list.append(f"{v_name} @ {h_name} -> Typ: {pick}")
                summaries_list.append(f"{v_name} vs {h_name}: AI prediction - {pick} to win")
                outcome = ""
            elif state == "in":
                status = "LIVE"
                score_html = f'<span class="score">{v_score}</span><span class="vs">:</span><span class="score">{h_score}</span>'
                summaries_list.append(f"{v_name} vs {h_name} (live): picked {pick}")
                outcome = ""
            else:
                status = "Final"
                actual = h_name if h_score > v_score else (v_name if v_score > h_score else "")
                hc = "score win" if h_score > v_score else ("score lose" if h_score < v_score else "score")
                vc = "score win" if v_score > h_score else ("score lose" if v_score < h_score else "score")
                score_html = f'<span class="{vc}">{v_score}</span><span class="vs">:</span><span class="{hc}">{h_score}</span>'
                if actual:
                    summaries_list.append(f"{v_name} vs {h_name}: picked {pick}, {actual} won")
                    outcome = (' <span style="color:#10b981">&#10003;</span>' if pick == actual
                               else ' <span style="color:#ef4444">&#10007;</span>')
                else:
                    outcome = ""

            live_class = " live" if state == "in" else ""
            cards_list.append(f"""
            <div class="card">
              <div class="card-h{live_class}">{status}</div>
              <div class="matchup">
                <div class="team">
                  <img src="{v_logo}" alt="{v_name}" onerror="this.src='{DEFAULT_LOGO}'">
                  <span class="team-name">{v_name}</span>
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
            print(f"   Blad przy meczu LBA: {e}")

    return "".join(cards_list), picks_list, summaries_list


def build_page(title_date, cards_html, summaries):
    desc = " | ".join(summaries[:4]) or f"LBA AI picks for {title_date}"
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>LBA AI Picks {title_date} - Serie A Basket</title>
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
      {cards_html or '<div class="empty"><span class="ico">&#127936;</span>Brak meczow LBA na dzis.</div>'}
    </div>
    <div class="footer">
      Last updated: {datetime.now().strftime("%B %d, %Y at %H:%M")} &middot; Data: legabasket.it
    </div>
  </div>
</body>
</html>"""


# ==========================================
# MAIN
# ==========================================

def main():
    print(f"=== URUCHAMIAM LBA UPDATE ({datetime.now().strftime('%H:%M')}) ===")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    today_slug = get_today_str()
    today_str = datetime.now().strftime("%B %d, %Y")
    print(f"   Data: {today_slug}")

    if USE_AI_PREDICTIONS and os.environ.get("GEMINI_API_KEY"):
        print(f"   Tryb: AI ({AI_MODEL})")
    elif USE_AI_PREDICTIONS:
        print(f"   Tryb: FORMULA W-L (brak GEMINI_API_KEY)")
    else:
        print(f"   Tryb: LIVE (PLK_LIVE_MODE, bez AI)")
    print()

    # -- Wykryj sezony --
    season = ld.get_season_ids()
    regular_id = season["regular"]
    playoff_id = season["playoff"]

    # -- Tabela z Regular Season --
    table = {}
    if regular_id:
        table = ld.build_table_from_matches(regular_id)

    # -- Wszystkie mecze (regular + playoff) dla H2H --
    all_matches = []
    cal_regular = ld.fetch_calendar(regular_id) if regular_id else {}
    cal_playoff = ld.fetch_calendar(playoff_id) if playoff_id else {}
    all_matches = (cal_regular.get("matches") or []) + (cal_playoff.get("matches") or [])

    # -- Dzisiejsze mecze --
    today_matches = []
    for c_id in filter(None, [playoff_id, regular_id]):
        cal = ld.fetch_calendar(c_id)
        found = ld.filter_matches_for_date(cal.get("matches") or [], today_slug)
        today_matches.extend(found)

    print(f"\n   Mecze na {today_slug}: {len(today_matches)}")
    if not today_matches:
        print("   Brak meczow LBA dzisiaj.")

    # -- Statystyki graczy --
    player_stats = []
    for c_id in filter(None, [playoff_id, regular_id]):
        ps = ld.fetch_player_stats(c_id)
        player_stats.extend(ps)
        if ps:
            break  # wystarczy jeden zestaw

    print()

    # -- Build --
    cards_html, picks, summaries = build_cards(
        today_matches, table, all_matches, player_stats, today_slug
    )

    out = os.path.join(OUTPUT_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build_page(today_str, cards_html, summaries))
    print(f"\n-> Zapisano {out}")

    if picks:
        save_picks(picks, today_slug)
    else:
        print("   Brak typow pre-game.")

    save_ai_log(today_slug)
    print(f"\n=== GOTOWE. Otworz {out} w przegladarce. ===")


if __name__ == "__main__":
    main()
