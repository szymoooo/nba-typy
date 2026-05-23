"""
BBL (easyCredit BBL, Niemcy) Free Picks.
Sofascore tournament_id=105. Identyczna architektura co update_acb.py.

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
SOFA_TOURNAMENT_ID = 105
SOFA_SEASON_YEAR = "2025"

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
    data = _sofa_fetch(f"https://api.sofascore.com/api/v1/unique-tournament/{SOFA_TOURNAMENT_ID}/seasons")
    if not data:
        return None
    _save_debug("seasons", data)
    seasons = data.get("seasons") or []
    for s in seasons:
        year = str(s.get("year") or "")
        if "25/26" in year or year.startswith("25") or year == SOFA_SEASON_YEAR:
            print(f"   [sofa] BBL sezon: {s.get('name')} (id={s.get('id')})")
            return s.get("id")
    if seasons:
        s = seasons[0]
        print(f"   [sofa] BBL sezon (fallback): {s.get('name')} (id={s.get('id')})")
        return s.get("id")
    return None


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
    return f"https://api.sofascore.app/api/v1/team/{tid}/image" if tid else DEFAULT_LOGO


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

    prompt = f"""
Mecz BBL (easyCredit Bundesliga, Niemcy): {a_name} (gość) vs {h_name} (gospodarz)
Faza: {phase}
Dzisiejsza data: {today}

Bilans sezon 2025/26 BBL:
  - {h_name}: {h_pct:.0%} skuteczność
  - {a_name}: {a_pct:.0%} skuteczność

ZADANIE: Wytypuj zwycięzcę. Użyj Google Search:
1. Forma ostatnich 5 meczów obu drużyn w BBL
2. Aktualne kontuzje ({today}) - basketball-bundesliga.de, sport1.de
3. H2H w tym sezonie

Odpowiedz TYLKO czystym JSON (bez markdown):
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

    state = sofa_game_status(ev)
    if state == "post":
        return formula

    ts = ev.get("startTimestamp")
    if ts:
        try:
            if datetime.fromtimestamp(int(ts), tz=CET) <= datetime.now(CET):
                print(f"   [TIME-skip] {a_name} vs {h_name} -> formula")
                return formula
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
            return result["winner"]
        _ai_log.append({"matchup": f"{a_name} @ {h_name}", "ai_pick": None,
                        "formula_pick": formula, "note": "AI fallback"})
    return formula


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
            pick = predict(ev, pct_map, today_slug)

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
