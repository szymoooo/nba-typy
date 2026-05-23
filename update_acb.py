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

LEAGUE_NAME = "Liga Endesa (ACB)"
OUTPUT_DIR = "acb"
DEBUG_DIR = "acb/_debug"

# TheSportsDB - darmowe API, nie blokuje GitHub Actions
# https://www.thesportsdb.com/league/4408-spanish-liga-acb
TSDB_LEAGUE_ID = "4408"
TSDB_API_KEY = "123"  # publiczny darmowy klucz
TSDB_BASE = f"https://www.thesportsdb.com/api/v1/json/{TSDB_API_KEY}"

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
TSDB_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/123.0.0.0 Safari/537.36"),
    "Accept": "application/json",
}

_gemini_client = None
_ai_log = []


# ==========================================
# THESPORTSDB HELPERS
# ==========================================

def _tsdb_fetch(url):
    try:
        r = requests.get(url, headers=TSDB_HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"   [tsdb] HTTP {r.status_code}: {url}")
            return None
        return r.json()
    except Exception as e:
        print(f"   [tsdb-EXC] {type(e).__name__}: {e}")
        return None


def _save_debug(name, data):
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        with open(os.path.join(DEBUG_DIR, f"tsdb_{name}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    except Exception:
        pass


def get_today_str():
    return datetime.now(CET).strftime("%Y-%m-%d")


def fetch_games_today(today_slug):
    """Pobiera mecze ACB na dzis z TheSportsDB.
    Laczy next + last 15 eventow i filtruje po dacie."""
    games = []
    seen = set()

    for endpoint in ("eventsnextleague", "eventspastleague"):
        data = _tsdb_fetch(f"{TSDB_BASE}/{endpoint}.php?id={TSDB_LEAGUE_ID}")
        if not data:
            continue
        if endpoint == "eventsnextleague":
            _save_debug("next", data)
        for ev in data.get("events") or []:
            eid = ev.get("idEvent")
            if eid in seen:
                continue
            seen.add(eid)
            if ev.get("dateEvent") == today_slug:
                games.append(ev)

    print(f"   [tsdb] ACB mecze na {today_slug}: {len(games)}")
    return games


def fetch_standings():
    """Pobiera tabele ACB z TheSportsDB -> {team_name: win_pct}."""
    data = _tsdb_fetch(
        f"{TSDB_BASE}/lookuptable.php?l={TSDB_LEAGUE_ID}&s=2025-2026"
    )
    if not data:
        return {}
    _save_debug("table", data)
    pct_map = {}
    for row in data.get("table") or []:
        name = row.get("strTeam") or ""
        played = int(row.get("intPlayed") or 0)
        wins = int(row.get("intWin") or 0)
        if name and played > 0:
            pct_map[name] = wins / played
    print(f"   [tsdb] ACB standings: {len(pct_map)} druzyn")
    return pct_map


def game_status(ev):
    """Zwraca 'pre' | 'in' | 'post'."""
    status = (ev.get("strStatus") or ev.get("strProgress") or "").lower()
    if status in ("match finished", "ft", "aet", "finished"):
        return "post"
    if status in ("", "not started", "ns"):
        return "pre"
    return "in"


def fmt_time(ev):
    """Godzina CET z pola strTimeLocal np. '20:30:00' -> '20:30 CET'."""
    t = (ev.get("strTimeLocal") or ev.get("strTime") or "")
    if t and len(t) >= 5:
        return t[:5] + " CET"
    return ""


def team_logo(ev, side):
    key = "strHomeTeamBadge" if side == "home" else "strAwayTeamBadge"
    return ev.get(key) or DEFAULT_LOGO


def score(ev, side):
    key = "intHomeScore" if side == "home" else "intAwayScore"
    val = ev.get(key)
    try:
        return int(val) if val is not None else 0
    except Exception:
        return 0


def pct_for_team(pct_map, team_name):
    """Szuka win% dla druzyny - dopasowanie po nazwie."""
    if team_name in pct_map:
        return pct_map[team_name]
    tl = team_name.lower()
    for k, v in pct_map.items():
        if k.lower() == tl or k.lower() in tl or tl in k.lower():
            return v
    return 0.0


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


def predict_ai(h_name, a_name, h_pct, a_pct, ev, today):
    client = _get_gemini()
    if not client:
        return None
    phase = ev.get("strRound") or ev.get("intRound") or "Sezon zasadniczy"

    prompt = f"""
Mecz ACB (Liga Endesa, Hiszpania): {a_name} (gosc) vs {h_name} (gospodarz)
Faza: {phase}
Dzisiejsza data: {today}

Bilans sezon 2025/26 ACB:
  - {h_name}: {h_pct:.0%} skutecznosc
  - {a_name}: {a_pct:.0%} skutecznosc

ZADANIE: Wytypuj zwyciezce. Uzyj Google Search:
1. Forma ostatnich 5 meczow obu druzyn w ACB
2. Aktualne kontuzje ({today}) - acb.com, marca.com, sport.es, as.com
3. H2H w tym sezonie
4. Kontekst fazy (playoff = home court silniejsze)

Odpowiedz TYLKO czystym JSON (bez markdown):
{{
  "winner_name": "<dokladna nazwa: '{h_name}' lub '{a_name}'>",
  "confidence": <1-10>,
  "reasoning": "<2-3 zdania po polsku>",
  "key_factors": ["<czynnik 1>", "<czynnik 2>", "<czynnik 3>"],
  "injury_notes": "<co znalazles na dzis lub 'brak istotnych brakow'>"
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
        print(f"   ! AI ACB: {e}")
        return None


def predict(ev, pct_map, today_slug):
    h_name = ev.get("strHomeTeam", "Home")
    a_name = ev.get("strAwayTeam", "Away")
    h_pct = pct_for_team(pct_map, h_name)
    a_pct = pct_for_team(pct_map, a_name)
    formula = h_name if (h_pct + 0.05) > a_pct else a_name

    status = game_status(ev)
    if status == "post":
        return formula

    date_str = ev.get("strTimestamp") or f"{today_slug}T00:00:00"
    try:
        game_dt = datetime.fromisoformat(date_str).replace(tzinfo=CET)
        if game_dt <= datetime.now(CET):
            print(f"   [TIME-skip] {a_name} vs {h_name} -> formula")
            return formula
    except Exception:
        pass

    if USE_AI_PREDICTIONS:
        result = predict_ai(h_name, a_name, h_pct, a_pct, ev, today_slug)
        if result:
            print(f"   [AI] {a_name} vs {h_name} -> {result['winner']} (conf {result['confidence']}/10)")
            _ai_log.append({
                "matchup": f"{a_name} @ {h_name}",
                "phase": str(ev.get("strRound") or "?"),
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


def build_cards(games, pct_map, today_slug):
    cards = []
    picks = []
    summaries = []
    for ev in games:
        try:
            h_name = ev.get("strHomeTeam", "?")
            a_name = ev.get("strAwayTeam", "?")
            h_logo = team_logo(ev, "home")
            a_logo = team_logo(ev, "away")
            h_score = score(ev, "home")
            a_score = score(ev, "away")
            status = game_status(ev)
            pick = predict(ev, pct_map, today_slug)

            if status == "pre":
                tip = fmt_time(ev)
                status_label = tip or "Scheduled"
                score_html = '<span class="vs">VS</span>'
                picks.append(f"{a_name} @ {h_name} -> Typ: {pick}")
                summaries.append(f"{a_name} vs {h_name}: AI prediction - {pick} to win")
                outcome = ""
            elif status == "in":
                status_label = "LIVE"
                score_html = f'<span class="score">{a_score}</span><span class="vs">:</span><span class="score">{h_score}</span>'
                outcome = ""
            else:
                status_label = "Final"
                actual = h_name if h_score > a_score else (a_name if a_score > h_score else "")
                hc = "score win" if h_score > a_score else ("score lose" if h_score < a_score else "score")
                ac = "score win" if a_score > h_score else ("score lose" if a_score < h_score else "score")
                score_html = f'<span class="{ac}">{a_score}</span><span class="vs">:</span><span class="{hc}">{h_score}</span>'
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

    if USE_AI_PREDICTIONS and os.environ.get("GEMINI_API_KEY"):
        print(f"   Tryb: AI ({AI_MODEL})")
    else:
        print(f"   Tryb: FORMULA W-L")
    print(f"   Zrodlo: TheSportsDB (league {TSDB_LEAGUE_ID})")

    pct_map = fetch_standings()
    games = fetch_games_today(today_slug)

    cards_html, picks, summaries = build_cards(games, pct_map, today_slug)

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
