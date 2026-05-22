"""
EuroLeague Free Picks - lokalny generator typów.

Klon mechaniki update_nba.py, ale dla EuroLeague.
Źródło danych: oficjalne API api-live.euroleague.net (free, no-auth).

URUCHOMIENIE LOKALNE:
    cd euroleague_local
    pip install requests pytz
    python update_euroleague.py

Wynik: output/index.html (otwórz w przeglądarce)
"""

import requests
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# ==========================================
# KONFIGURACJA
# ==========================================
SEASON_CODE = "E2025"  # E2025 = sezon 2025-26 (E2026 dla nast.)
COMPETITION = "E"      # "E" = EuroLeague, "U" = EuroCup
OUTPUT_DIR = "output"

# Lista kandydatow dla GAMES (probujemy po kolei, uzywamy pierwszego ktory odpowie 200 + JSON)
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
BRAND_TITLE = "EUROLEAGUE PUBLIC HUB"
BRAND_ACCENT = "#ff6600"   # pomarańcz EuroLeague
BRAND_DOMAIN = "https://euroleague-freepicks.com"  # placeholder

# Słownik logosów - awaryjny fallback jeśli API nie zwróci imageUrls.crest
# Pierwsze uruchomienie pokaże co naprawdę przychodzi z API; uzupełnimy potem.
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
    "DUB": "",  # Dubai BC - nowy klub 25/26, brak stabilnego URL
    "HTA": "",  # Hapoel Tel Aviv - nowy w EL 25/26
    "ASV": "https://upload.wikimedia.org/wikipedia/en/3/35/ASVEL_Basket_logo.svg",
    "MTA": "https://upload.wikimedia.org/wikipedia/en/8/8e/Maccabi_Tel_Aviv_BC_logo.svg",
    "TEL": "https://upload.wikimedia.org/wikipedia/en/8/8e/Maccabi_Tel_Aviv_BC_logo.svg",
    "PRS": "https://upload.wikimedia.org/wikipedia/en/0/00/Paris_Basketball_logo.svg",
    "PAR": "https://upload.wikimedia.org/wikipedia/en/0/02/KK_Partizan_logo.svg",
    "VAL": "https://upload.wikimedia.org/wikipedia/en/2/2a/Valencia_Basket_logo.svg",
    "PAM": "https://upload.wikimedia.org/wikipedia/en/2/2a/Valencia_Basket_logo.svg",
    "VIR": "https://upload.wikimedia.org/wikipedia/en/3/35/Virtus_Pallacanestro_Bologna_logo.svg",
    "ZAL": "https://upload.wikimedia.org/wikipedia/en/c/c1/BC_%C5%BDalgiris_logo.svg",
}
DEFAULT_LOGO = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='44' fill='none' stroke='%23ff6600' stroke-width='3'/><text y='62' x='50' text-anchor='middle' font-size='42' fill='%23ff6600'>%F0%9F%8F%80</text></svg>"


# ==========================================
# API CLIENT
# ==========================================

def fetch_json(url, params=None, timeout=15):
    """Bezpieczne pobranie JSON z fallbackiem na XML."""
    try:
        r = requests.get(url, params=params or {},
                         headers={"Accept": "application/json",
                                  "User-Agent": "Mozilla/5.0 (euroleague-freepicks/0.2)"},
                         timeout=timeout)
        if r.status_code != 200:
            return None, r.status_code, r.text[:300]
        ct = r.headers.get("Content-Type", "")
        if "json" in ct or r.text.lstrip().startswith(("{", "[")):
            return r.json(), 200, None
        # fallback - probujemy XML
        return ("XML", r.text), 200, None
    except Exception as e:
        return None, None, str(e)[:300]


def try_endpoints(endpoints, kind):
    """Probuje kandydatow po kolei. Zwraca (label, data) gdzie data to dict/list (JSON) albo ('XML', text)."""
    print(f"-> Probuje endpointy ({kind}):")
    for label, url, params in endpoints:
        result, status, err = fetch_json(url, params)
        if result is None:
            print(f"   [FAIL] {label} -> HTTP {status} {err if err else ''}")
            continue
        # XML response
        if isinstance(result, tuple) and result[0] == "XML":
            print(f"   [OK-XML] {label} -> {url} (HTTP {status})")
            debug_path = os.path.join(OUTPUT_DIR, f"debug_{kind}_{label}.xml")
            try:
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(result[1])
                print(f"        zapisano dump XML: {debug_path}")
            except Exception:
                pass
            return label, result
        # JSON response
        print(f"   [OK] {label} -> {url} (HTTP {status})")
        debug_path = os.path.join(OUTPUT_DIR, f"debug_{kind}_{label}.json")
        try:
            with open(debug_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            print(f"        zapisano dump: {debug_path}")
        except Exception:
            pass
        return label, result
    return None, None


def parse_standings_xml(xml_text):
    """Parser XML EuroLeague v1/standings -> {code: win_pct}."""
    pct_map = {}
    try:
        root = ET.fromstring(xml_text)
        for team in root.iter("team"):
            code = (team.findtext("code") or "").strip().upper()
            try:
                wins = int(team.findtext("wins") or 0)
                losses = int(team.findtext("losses") or 0)
            except (TypeError, ValueError):
                wins, losses = 0, 0
            total = wins + losses
            if code and total > 0:
                pct_map[code] = wins / total
    except Exception as e:
        print(f"   Blad parsowania XML standings: {e}")
    return pct_map


def get_today_date_str():
    """Lokalna data UTC+1/+2 (Europa). Zwraca YYYY-MM-DD."""
    cet = timezone(timedelta(hours=2))  # CEST uproszczone
    return datetime.now(cet).strftime("%Y-%m-%d")


def fetch_games_for_date(date_str):
    """Pobiera mecze, filtruje na dana date. Zwraca (lista, label_zrodla)."""
    label, data = try_endpoints(GAMES_ENDPOINTS, "games")
    if data is None:
        print("   ZADEN endpoint games nie zwrocil JSONa.")
        return [], None

    # Normalizacja: rozne API zwracaja rozna strukture
    games = []
    if isinstance(data, dict):
        games = (data.get("data") or data.get("games") or
                 data.get("schedule") or data.get("results") or [])
    elif isinstance(data, list):
        games = data

    if not isinstance(games, list):
        print(f"   Nieoczekiwana struktura games z {label}: {type(games)}")
        games = []

    print(f"   {label} zwrocil {len(games)} meczow")

    today_games = []
    for g in games:
        if not isinstance(g, dict):
            continue
        gdate_raw = (g.get("date") or g.get("utcDate") or
                     g.get("startDate") or g.get("gameDate") or "")
        gdate = gdate_raw[:10] if isinstance(gdate_raw, str) else ""
        if gdate == date_str:
            today_games.append(g)
    print(f"   Mecze na {date_str}: {len(today_games)}")
    return today_games, label


def fetch_standings_map():
    """Zwraca {team_code: win_pct} dla wszystkich druzyn."""
    label, data = try_endpoints(STANDINGS_ENDPOINTS, "standings")
    if data is None:
        print("   ZADEN endpoint standings nie zwrocil danych. Predykcje beda 50/50.")
        return {}

    # XML path (v1/standings zwraca XML)
    if isinstance(data, tuple) and data[0] == "XML":
        pct_map = parse_standings_xml(data[1])
        print(f"   {label}: zaladowano statystyki dla {len(pct_map)} druzyn (XML)")
        return pct_map

    # JSON path - probujemy roznych ksztaltow odpowiedzi
    teams = []
    if isinstance(data, dict):
        d = data.get("data", data)
        if isinstance(d, dict):
            teams = d.get("teams") or d.get("standings") or []
        elif isinstance(d, list):
            teams = d
    elif isinstance(data, list):
        teams = data

    pct_map = {}
    for t in teams:
        if not isinstance(t, dict):
            continue
        team_obj = t.get("team", t)
        if isinstance(team_obj, dict):
            code = (team_obj.get("code") or team_obj.get("tvCode")
                    or team_obj.get("clubCode") or "").upper()
        else:
            code = ""
        if not code:
            code = (t.get("teamCode") or t.get("code") or "").upper()
        if not code:
            continue
        wins = t.get("won") or t.get("wins") or t.get("gamesWon") or 0
        losses = t.get("lost") or t.get("losses") or t.get("gamesLost") or 0
        try:
            wins, losses = int(wins), int(losses)
        except Exception:
            wins, losses = 0, 0
        total = wins + losses
        pct_map[code] = (wins / total) if total > 0 else 0.0
    print(f"   {label}: zaladowano statystyki dla {len(pct_map)} druzyn")
    return pct_map


# ==========================================
# HELPERS
# ==========================================

def get_team_logo(team_obj):
    """API odpowiedz -> logo URL z fallbackami."""
    if not isinstance(team_obj, dict):
        return DEFAULT_LOGO
    img = team_obj.get("imageUrls") or {}
    crest = img.get("crest") or team_obj.get("logo") or team_obj.get("crest")
    if crest:
        return crest
    code = (team_obj.get("code") or team_obj.get("tvCode") or "").upper()
    return EUROLEAGUE_LOGOS.get(code) or DEFAULT_LOGO


def map_status(status_raw):
    """API status -> ('pre'|'in'|'post', display_text)."""
    s = (status_raw or "").lower()
    if s in ("scheduled", "pre", "upcoming", "notstarted", "confirmed", ""):
        return "pre", "Scheduled"
    if s in ("live", "in_progress", "inplay", "started", "playing"):
        return "in", "LIVE"
    if s in ("result", "finished", "post", "ended", "final", "played"):
        return "post", "Final"
    return "pre", "Scheduled"


def fmt_game_time(date_raw):
    """ISO date -> '19:00 CET' (lokalny CEST)."""
    if not date_raw:
        return ""
    try:
        # Akceptuj zarowno "...Z" jak i "..." bez Z
        s = date_raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            # API "date" zwykle jest lokalne CET
            return dt.strftime("%H:%M") + " CET"
        return dt.astimezone(timezone(timedelta(hours=2))).strftime("%H:%M") + " CET"
    except Exception:
        return ""


def save_picks_for_audit(picks, today_slug):
    """Zapisuje typy do propozycje_typow.txt (dla euroleague_audit.py)."""
    path = os.path.join(OUTPUT_DIR, "propozycje_typow.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# EuroLeague typy na {today_slug}\n")
        f.write("\n".join(picks))
    print(f"   Zapisano {len(picks)} typow do {path}")


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
        .team-logo {{ width: 100px; height: 100px; object-fit: contain; opacity: 0.95; }}
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

def build_game_cards(games, pct_map):
    cards_html = ""
    picks = []
    summaries = []

    for g in games:
        try:
            home = g.get("homeTeam") or g.get("home") or {}
            away = g.get("awayTeam") or g.get("away") or {}
            if not home or not away:
                continue

            h_name = home.get("name") or home.get("tvCode") or home.get("code") or "?"
            a_name = away.get("name") or away.get("tvCode") or away.get("code") or "?"
            h_code = (home.get("code") or "").upper()
            a_code = (away.get("code") or "").upper()
            h_logo = get_team_logo(home)
            a_logo = get_team_logo(away)

            try:
                h_score = int(home.get("score") or 0)
                a_score = int(away.get("score") or 0)
            except Exception:
                h_score, a_score = 0, 0

            state, status_text_raw = map_status(g.get("status") or g.get("statusType"))

            # Predykcja: home advantage 0.05 (jak NBA)
            h_pct = pct_map.get(h_code, 0.0)
            a_pct = pct_map.get(a_code, 0.0)
            predicted_winner = h_name if (h_pct + 0.05) > a_pct else a_name

            if state == "pre":
                tip = fmt_game_time(g.get("date") or g.get("utcDate"))
                status_text = tip if tip else "Scheduled"
                picks.append(f"{a_name} @ {h_name} -> Typ: {predicted_winner}")
                score_html = '<span class="vs-sep" style="font-size:2rem;">VS</span>'
                summaries.append(f"{a_name} vs {h_name}: AI prediction - {predicted_winner} to win")
                outcome_icon = ""
                h_class, a_class = "score", "score"
            elif state == "in":
                status_text = "LIVE " + (g.get("clock") or "")
                score_html = f'<span class="score">{a_score}</span><span class="vs-sep">:</span><span class="score">{h_score}</span>'
                summaries.append(f"{a_name} vs {h_name} (live): AI picked {predicted_winner}")
                outcome_icon = ""
                h_class, a_class = "score", "score"
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
                score_html = f'<span class="{a_class}">{a_score}</span><span class="vs-sep">:</span><span class="{h_class}">{h_score}</span>'
                if actual:
                    summaries.append(f"{a_name} vs {h_name}: AI picked {predicted_winner}, {actual} won {max(h_score,a_score)}-{min(h_score,a_score)}")
                    outcome_icon = ' <span style="color:#10b981;">&#10003;</span>' if predicted_winner == actual else ' <span style="color:#ef4444;">&#10007;</span>'
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
    meta_title = f"EuroLeague AI Picks Today {title_date} - Free Predictions"
    meta_desc = (f"Free EuroLeague AI predictions for {title_date}. {games_meta}"
                 if games_meta else
                 f"Daily EuroLeague game predictions powered by AI. Free picks for every game - {title_date}.")
    meta_desc = meta_desc[:160]

    return f"""<!DOCTYPE html>
<html lang="en">
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
            <div class="subtitle">Live Scores &amp; Public AI Model Picks &mdash; {title_date}</div>
        </header>

        <div class="grid">
            {cards_html if cards_html.strip() else '<div class="empty"><span class="ico">&#127936;</span>No EuroLeague games scheduled for today.<br><small>Check back later or pick another date.</small></div>'}
        </div>

        <div class="footer">
            Last updated: {datetime.now().strftime("%B %d, %Y at %H:%M")} &middot; Local MVP build
        </div>
    </div>
</body>
</html>"""


# ==========================================
# MAIN
# ==========================================

def main():
    print(f"=== URUCHAMIAM EUROLEAGUE UPDATE ({datetime.now().strftime('%H:%M')}) ===")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    today_slug = get_today_date_str()
    today_str = datetime.now().strftime("%B %d, %Y")
    print(f"   Data: {today_slug} ({today_str})")
    print(f"   Sezon: {SEASON_CODE}, Liga: {COMPETITION}")
    print()

    pct_map = fetch_standings_map()
    print()
    games, src_label = fetch_games_for_date(today_slug)

    cards_html, picks, summaries = build_game_cards(games, pct_map)

    out_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(build_page(today_str, cards_html, summaries))
    print(f"\n-> Zapisano {out_path}")

    if picks:
        save_picks_for_audit(picks, today_slug)
    else:
        print("   Brak typow pre-game (gry juz w trakcie/zakonczone albo brak meczow).")

    if not pct_map and not games:
        print("\n!! ZADEN endpoint nie zadzialal. Sprawdz pliki output/debug_*.json")
        print("   lub wyslij wynik tego skryptu do supportu.")
    elif not games:
        print(f"\n   Brak meczow EuroLeague na {today_slug}.")
        print(f"   Mozliwe ze dzis nie ma kolejki, albo trzeba zmienic SEASON_CODE.")
        print(f"   Aktualnie: {SEASON_CODE}. Sprawdz output/debug_games_*.json - czy sa tam mecze?")

    print(f"\n=== GOTOWE. Otworz {out_path} w przegladarce. ===")


if __name__ == "__main__":
    main()
