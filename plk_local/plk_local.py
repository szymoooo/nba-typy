"""
PLK LOCAL - lokalna wersja generatora typow PLK.

Odpalasz u siebie w terminalu, nie wymaga GEMINI_API_KEY, nie wymaga
GitHub Actions. Generuje plk_local/output/index.html ktory mozesz
otworzyc w przegladarce.

Roznice wzgledem produkcyjnego update_plk.py:
  - ZERO Gemini / AI (czysta formula W-L, instant, deterministyczny)
  - jak nie ma meczow na dzis, pokazuje fallback z 5 najblizszymi meczami
  - dumpuje wszystkie etapy do plk_local/_debug/ (zero magii)
  - output do plk_local/output/, nie do plk/ (nie nadpisuje produkcji)

URUCHOMIENIE:
    pip install requests
    python plk_local/plk_local.py
    open plk_local/output/index.html       # macOS
    xdg-open plk_local/output/index.html   # Linux
    start plk_local\\output\\index.html      # Windows
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    print("!! Brak biblioteki 'requests'. Zainstaluj: pip install requests")
    sys.exit(1)

# -------------------- konfig --------------------
TOURNAMENT_ID = 263
TOURNAMENT_NAME_PL = "Orlen Basket Liga"
BRAND_TITLE = "PLK LOCAL HUB"
BRAND_ACCENT = "#dc2626"

SOFA_BASE = "https://api.sofascore.com/api/v1"
SOFA_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/123.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.sofascore.com/",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
DEBUG_DIR = os.path.join(SCRIPT_DIR, "_debug")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)

DEFAULT_LOGO = (
    "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    "<circle cx='50' cy='50' r='44' fill='none' stroke='%23dc2626' stroke-width='3'/>"
    "<text y='62' x='50' text-anchor='middle' font-size='42' fill='%23dc2626'>"
    "%F0%9F%8F%80</text></svg>"
)


# -------------------- API --------------------

def fetch_json(url, label):
    try:
        r = requests.get(url, headers=SOFA_HEADERS, timeout=15)
    except Exception as e:
        print(f"   [EXCEPTION] {url} -> {type(e).__name__}: {e}")
        return None
    if r.status_code != 200:
        print(f"   [HTTP {r.status_code}] {url} :: {r.text[:200]}")
        return None
    try:
        data = r.json()
    except Exception as e:
        print(f"   [JSON] {url} -> {e}")
        return None
    try:
        with open(os.path.join(DEBUG_DIR, f"debug_{label}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    except Exception:
        pass
    return data


def fetch_current_season_id():
    data = fetch_json(f"{SOFA_BASE}/unique-tournament/{TOURNAMENT_ID}/seasons", "seasons")
    if not data:
        return None
    seasons = data.get("seasons") or []
    for s in seasons:
        year = str(s.get("year") or "")
        if "25/26" in year or "2025/26" in year or "2025-26" in year or year.startswith("25"):
            print(f"   Sezon: id={s.get('id')} year='{s.get('year')}' name='{s.get('name')}'")
            return s.get("id")
    if seasons:
        s = seasons[0]
        print(f"   Sezon (fallback - pierwszy): id={s.get('id')} name='{s.get('name')}'")
        return s.get("id")
    return None


def fetch_events(season_id, kind):
    out = []
    for page in range(20):
        d = fetch_json(
            f"{SOFA_BASE}/unique-tournament/{TOURNAMENT_ID}/season/{season_id}/events/{kind}/{page}",
            f"events_{kind}_p{page}",
        )
        if not d:
            break
        evs = d.get("events") or []
        if not evs:
            break
        out.extend(evs)
        if not d.get("hasNextPage"):
            break
        time.sleep(0.2)
    print(f"   events/{kind} -> {len(out)} meczow")
    return out


def fetch_standings(season_id):
    d = fetch_json(
        f"{SOFA_BASE}/unique-tournament/{TOURNAMENT_ID}/season/{season_id}/standings/total",
        "standings_total",
    )
    if not d:
        return {}
    pct = {}
    for table in d.get("standings") or []:
        for row in table.get("rows") or []:
            tid = (row.get("team") or {}).get("id")
            try:
                w, l = int(row.get("wins", 0) or 0), int(row.get("losses", 0) or 0)
            except Exception:
                w, l = 0, 0
            if tid:
                pct[tid] = (w / (w + l)) if (w + l) > 0 else 0.0
    print(f"   standings -> {len(pct)} druzyn")
    return pct


# -------------------- utils --------------------
CET = timezone(timedelta(hours=2))


def today_pl():
    return datetime.now(CET).strftime("%Y-%m-%d")


def filter_for_date(events, date_str):
    out = []
    for ev in events:
        ts = ev.get("startTimestamp")
        if not ts:
            continue
        try:
            if datetime.fromtimestamp(int(ts), tz=CET).strftime("%Y-%m-%d") == date_str:
                out.append(ev)
        except Exception:
            pass
    return out


def nearest_events(events, n=5):
    """Zwraca n meczow najblizszych chronologicznie do dzisiaj (przed lub po)."""
    now = datetime.now(CET)
    scored = []
    for ev in events:
        ts = ev.get("startTimestamp")
        if not ts:
            continue
        try:
            dt = datetime.fromtimestamp(int(ts), tz=CET)
            scored.append((abs((dt - now).total_seconds()), ev))
        except Exception:
            pass
    scored.sort(key=lambda x: x[0])
    return [ev for _, ev in scored[:n]]


def team_logo(team):
    tid = (team or {}).get("id")
    return f"https://api.sofascore.app/api/v1/team/{tid}/image" if tid else DEFAULT_LOGO


def map_status(ev):
    t = ((ev.get("status") or {}).get("type") or "").lower()
    if t in ("inprogress", "live"):
        return "in"
    if t in ("finished", "ended", "afterextra", "afterpenalties"):
        return "post"
    return "pre"


def get_score(ev, side):
    sc = ev.get("homeScore" if side == "home" else "awayScore") or {}
    if isinstance(sc, dict):
        v = sc.get("current") if sc.get("current") is not None else sc.get("display")
        try:
            return int(v) if v is not None else 0
        except Exception:
            return 0
    try:
        return int(sc)
    except Exception:
        return 0


def fmt_time(ts):
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts), tz=CET).strftime("%H:%M") + " CET"
    except Exception:
        return ""


def fmt_date(ts):
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts), tz=CET).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def predict_winner(home, away, pct_map):
    h_pct = pct_map.get((home or {}).get("id"), 0.0)
    a_pct = pct_map.get((away or {}).get("id"), 0.0)
    h_name = (home or {}).get("name", "Home")
    a_name = (away or {}).get("name", "Away")
    return h_name if (h_pct + 0.05) > a_pct else a_name


# -------------------- HTML --------------------

CSS = f"""
  :root {{ --bg:#0f172a; --card:#1e293b; --acc:{BRAND_ACCENT}; --tx:#f8fafc;
           --sub:#94a3b8; --win:#10b981; --br:#334155; }}
  * {{ box-sizing: border-box; }}
  body {{ background:var(--bg); color:var(--tx); font-family:'Montserrat',sans-serif;
         margin:0; padding:20px; }}
  .container {{ max-width:1200px; margin:0 auto; }}
  header {{ text-align:center; margin-bottom:30px; padding-bottom:20px;
           border-bottom:1px solid var(--br); }}
  h1 {{ font-weight:900; letter-spacing:-1px; margin:0; color:var(--acc); font-size:2.4rem; }}
  .sub {{ color:var(--sub); font-size:0.85rem; text-transform:uppercase;
         letter-spacing:1px; margin-top:10px; }}
  .banner {{ background: rgba(220,38,38,0.08); border:1px dashed var(--acc);
            border-radius:12px; padding:14px 18px; margin:0 0 24px; color:var(--tx);
            font-size:0.9rem; line-height:1.5; }}
  .banner b {{ color:var(--acc); }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(420px,1fr));
          gap:22px; }}
  .card {{ background:var(--card); border:1px solid var(--br); border-radius:18px;
          overflow:hidden; display:flex; flex-direction:column; }}
  .card-h {{ background:rgba(0,0,0,0.3); padding:10px 20px; text-align:center;
            border-bottom:1px solid var(--br); font-size:0.75rem; font-weight:900;
            color:var(--sub); text-transform:uppercase; letter-spacing:1px; }}
  .card-h.live {{ color:#ef4444; }}
  .matchup {{ display:flex; justify-content:space-between; align-items:stretch;
             padding:26px 18px; flex-grow:1; gap:12px; }}
  .team {{ text-align:center; flex:1; min-width:0; display:flex;
          flex-direction:column; align-items:center; gap:12px; }}
  .team img {{ width:90px; height:90px; object-fit:contain;
              background:rgba(255,255,255,0.04); border-radius:12px; padding:6px; }}
  .team-name {{ font-weight:900; font-size:0.85rem; text-transform:uppercase;
               line-height:1.2; word-wrap:break-word; }}
  .score {{ font-size:2.4rem; font-weight:900; line-height:1; }}
  .score.win {{ color:var(--win); }}
  .score.lose {{ color:var(--sub); opacity:0.8; }}
  .vs {{ color:var(--br); font-style:italic; font-weight:900; font-size:1.5rem; }}
  .pred {{ background:rgba(15,23,42,0.6); padding:18px; text-align:center;
          border-top:1px solid var(--br); }}
  .pred-l {{ font-size:0.7rem; color:var(--sub); text-transform:uppercase;
            font-weight:700; letter-spacing:1px; margin-bottom:6px; }}
  .pred-v {{ font-size:1.15rem; font-weight:900; }}
  .footer {{ text-align:center; color:var(--sub); font-size:0.75rem;
            margin-top:40px; padding-bottom:20px; }}
  .empty {{ text-align:center; color:#888; padding:50px 20px; line-height:1.6; }}
  .empty .ico {{ font-size:3rem; display:block; margin-bottom:14px; }}
  .nearest-list {{ background:var(--card); border:1px solid var(--br); border-radius:14px;
                  padding:18px 22px; margin-top:24px; }}
  .nearest-list h3 {{ margin:0 0 12px; color:var(--acc); font-size:1rem;
                     text-transform:uppercase; letter-spacing:1px; }}
  .nearest-list ul {{ list-style:none; padding:0; margin:0; }}
  .nearest-list li {{ padding:8px 0; border-bottom:1px dashed var(--br);
                     color:var(--sub); font-size:0.9rem; }}
  .nearest-list li:last-child {{ border-bottom:none; }}
  .nearest-list b {{ color:var(--tx); }}
  @media (max-width:768px) {{ .grid {{ grid-template-columns:1fr; }} }}
"""


def card_html(ev, pct_map):
    home = ev.get("homeTeam") or {}
    away = ev.get("awayTeam") or {}
    h_name, a_name = home.get("name", "?"), away.get("name", "?")
    state = map_status(ev)
    h_score, a_score = get_score(ev, "home"), get_score(ev, "away")
    pick = predict_winner(home, away, pct_map)

    if state == "pre":
        status_txt = fmt_time(ev.get("startTimestamp")) or "Scheduled"
        live_class = ""
        center = '<span class="vs">VS</span>'
        outcome = ""
    elif state == "in":
        status_txt = "LIVE"
        live_class = "live"
        center = f'<span class="score">{a_score}</span><span class="vs">:</span><span class="score">{h_score}</span>'
        outcome = ""
    else:
        status_txt = "Final"
        live_class = ""
        if h_score > a_score:
            actual, hc, ac = h_name, "score win", "score lose"
        elif a_score > h_score:
            actual, hc, ac = a_name, "score lose", "score win"
        else:
            actual, hc, ac = "", "score", "score"
        center = f'<span class="{ac}">{a_score}</span><span class="vs">:</span><span class="{hc}">{h_score}</span>'
        outcome = (' <span style="color:#10b981">&#10003;</span>' if actual and actual == pick
                   else ' <span style="color:#ef4444">&#10007;</span>' if actual else "")

    return f"""
      <div class="card">
        <div class="card-h {live_class}">{status_txt}</div>
        <div class="matchup">
          <div class="team">
            <img src="{team_logo(away)}" alt="{a_name}" onerror="this.src='{DEFAULT_LOGO}'">
            <span class="team-name">{a_name}</span>
          </div>
          <div style="display:flex;align-items:center;justify-content:center;gap:10px">{center}</div>
          <div class="team">
            <img src="{team_logo(home)}" alt="{h_name}" onerror="this.src='{DEFAULT_LOGO}'">
            <span class="team-name">{h_name}</span>
          </div>
        </div>
        <div class="pred">
          <div class="pred-l">Public Model Pick (formula W-L)</div>
          <div class="pred-v">{pick}{outcome}</div>
        </div>
      </div>
    """


def build_page(today_str, today_events, all_events, pct_map, season_label):
    if today_events:
        cards = "".join(card_html(ev, pct_map) for ev in today_events)
        body_grid = f'<div class="grid">{cards}</div>'
        nearest_block = ""
        banner = (f'<div class="banner">Tryb LOKALNY (bez AI). '
                  f'Sezon w API: <b>{season_label}</b>. '
                  f'Mecze na dzis: <b>{len(today_events)}</b>.</div>')
    else:
        body_grid = ('<div class="empty"><span class="ico">&#127936;</span>'
                     'Brak meczow PLK na dzis.<br>'
                     '<small>To moze byc off-day w lidze - zobacz najblizsze ponizej.</small></div>')

        items = ""
        for ev in nearest_events(all_events, n=8):
            home = (ev.get("homeTeam") or {}).get("name", "?")
            away = (ev.get("awayTeam") or {}).get("name", "?")
            when = fmt_date(ev.get("startTimestamp"))
            rnd = (ev.get("roundInfo") or {}).get("name") or (ev.get("roundInfo") or {}).get("round") or ""
            rnd_lbl = f" &middot; {rnd}" if rnd else ""
            items += f'<li><b>{when}</b> &mdash; {away} @ {home}{rnd_lbl}</li>'
        nearest_block = (
            f'<div class="nearest-list"><h3>Najblizsze mecze w sezonie {season_label}</h3>'
            f'<ul>{items or "<li>Brak danych z API.</li>"}</ul></div>'
        )
        banner = (f'<div class="banner">Tryb LOKALNY (bez AI). '
                  f'Sezon w API: <b>{season_label}</b>. '
                  f'API <b>nie ma</b> meczow PLK na dzis - sprawdz blok ponizej. '
                  f'Pelny dump: <code>plk_local/_debug/</code>.</div>')

    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{BRAND_TITLE} (local) - {today_str}</title>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800;900&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
  <div class="container">
    <header>
      <h1>{BRAND_TITLE}</h1>
      <div class="sub">{TOURNAMENT_NAME_PL} &middot; LOCAL DEBUG MODE &mdash; {today_str}</div>
    </header>
    {banner}
    {body_grid}
    {nearest_block}
    <div class="footer">Generated locally: {datetime.now().strftime("%Y-%m-%d %H:%M")} &middot; Sofascore public API</div>
  </div>
</body>
</html>"""


# -------------------- main --------------------

def main():
    print("=== PLK LOCAL (bez AI) ===")
    today_slug = today_pl()
    today_human = datetime.now(CET).strftime("%B %d, %Y")
    print(f"  Data PL: {today_slug}")

    season_id = fetch_current_season_id()
    if not season_id:
        print("!! Brak sezonu - zapisuje pusta strone z bannerem.")
        out = os.path.join(OUTPUT_DIR, "index.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(build_page(today_human, [], [], {}, "n/a"))
        print(f"  -> {out}")
        return

    pct_map = fetch_standings(season_id)
    next_evs = fetch_events(season_id, "next")
    last_evs = fetch_events(season_id, "last")
    all_evs = next_evs + last_evs

    today_evs = filter_for_date(all_evs, today_slug)
    print(f"  mecze na {today_slug}: {len(today_evs)}")

    season_label = f"id={season_id}"
    out = os.path.join(OUTPUT_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build_page(today_human, today_evs, all_evs, pct_map, season_label))

    print(f"\n=== GOTOWE ===")
    print(f"  HTML:  {out}")
    print(f"  Dumpy: {DEBUG_DIR}/")
    if not today_evs:
        print(f"  Uwaga: brak meczow na dzis - zerknij na blok 'Najblizsze' w HTML.")
        print(f"  Zeby pelna diagnostyka, odpal: python plk_local/plk_debug.py")


if __name__ == "__main__":
    main()
