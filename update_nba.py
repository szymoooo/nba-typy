"""
NBA Free Picks - generator typow.

Zrodlo danych: ESPN Scoreboard API (publiczne, bez auth).
UI: league_ui.py (wspolny szablon dla wszystkich lig).

NBA ma unikalną architekturę:
  - Archiwum poprzednich dni (nba/archive/)
  - GA4 tracking
  - SEO meta tagi
  - Lineup Audit przez gemini_audit.py (wstrzykuje do modalu po generacji)

URUCHOMIENIE LOKALNE:
    pip install requests
    python update_nba.py

Wynik: nba/index.html
"""

import requests
import json
from datetime import datetime, timezone, timedelta
import os

# ==========================================
# KONFIGURACJA
# ==========================================
ESPN_API     = "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
GA4_ID       = "G-ZV0JG9D4QK"
BRAND_ACCENT = "#3b82f6"

NBA_LOGOS = {
    'ATL': 'https://cdn.nba.com/logos/nba/1610612737/global/L/logo.svg',
    'BOS': 'https://cdn.nba.com/logos/nba/1610612738/global/L/logo.svg',
    'CLE': 'https://cdn.nba.com/logos/nba/1610612739/global/L/logo.svg',
    'NOP': 'https://cdn.nba.com/logos/nba/1610612740/global/L/logo.svg',
    'NO':  'https://cdn.nba.com/logos/nba/1610612740/global/L/logo.svg',
    'CHI': 'https://cdn.nba.com/logos/nba/1610612741/global/L/logo.svg',
    'DAL': 'https://cdn.nba.com/logos/nba/1610612742/global/L/logo.svg',
    'DEN': 'https://cdn.nba.com/logos/nba/1610612743/global/L/logo.svg',
    'GSW': 'https://cdn.nba.com/logos/nba/1610612744/global/L/logo.svg',
    'GS':  'https://cdn.nba.com/logos/nba/1610612744/global/L/logo.svg',
    'HOU': 'https://cdn.nba.com/logos/nba/1610612745/global/L/logo.svg',
    'LAC': 'https://cdn.nba.com/logos/nba/1610612746/global/L/logo.svg',
    'LAL': 'https://cdn.nba.com/logos/nba/1610612747/global/L/logo.svg',
    'MIA': 'https://cdn.nba.com/logos/nba/1610612748/global/L/logo.svg',
    'MIL': 'https://cdn.nba.com/logos/nba/1610612749/global/L/logo.svg',
    'MIN': 'https://cdn.nba.com/logos/nba/1610612750/global/L/logo.svg',
    'BKN': 'https://cdn.nba.com/logos/nba/1610612751/global/L/logo.svg',
    'NYK': 'https://cdn.nba.com/logos/nba/1610612752/global/L/logo.svg',
    'NY':  'https://cdn.nba.com/logos/nba/1610612752/global/L/logo.svg',
    'ORL': 'https://cdn.nba.com/logos/nba/1610612753/global/L/logo.svg',
    'IND': 'https://cdn.nba.com/logos/nba/1610612754/global/L/logo.svg',
    'PHI': 'https://cdn.nba.com/logos/nba/1610612755/global/L/logo.svg',
    'PHX': 'https://cdn.nba.com/logos/nba/1610612756/global/L/logo.svg',
    'POR': 'https://cdn.nba.com/logos/nba/1610612757/global/L/logo.svg',
    'SAC': 'https://cdn.nba.com/logos/nba/1610612758/global/L/logo.svg',
    'SAS': 'https://cdn.nba.com/logos/nba/1610612759/global/L/logo.svg',
    'SA':  'https://cdn.nba.com/logos/nba/1610612759/global/L/logo.svg',
    'OKC': 'https://cdn.nba.com/logos/nba/1610612760/global/L/logo.svg',
    'TOR': 'https://cdn.nba.com/logos/nba/1610612761/global/L/logo.svg',
    'UTA': 'https://cdn.nba.com/logos/nba/1610612762/global/L/logo.svg',
    'UTAH':'https://cdn.nba.com/logos/nba/1610612762/global/L/logo.svg',
    'MEM': 'https://cdn.nba.com/logos/nba/1610612763/global/L/logo.svg',
    'WAS': 'https://cdn.nba.com/logos/nba/1610612764/global/L/logo.svg',
    'WSH': 'https://cdn.nba.com/logos/nba/1610612764/global/L/logo.svg',
    'DET': 'https://cdn.nba.com/logos/nba/1610612765/global/L/logo.svg',
    'CHA': 'https://cdn.nba.com/logos/nba/1610612766/global/L/logo.svg',
}
DEFAULT_LOGO = 'https://cdn.nba.com/logos/nba/nba-logoman-70x70.svg'


# ==========================================
# HELPERS
# ==========================================

def get_espn_data():
    try:
        response = requests.get(ESPN_API, timeout=10)
        if response.status_code == 200:
            return response.json()
        print(f"ESPN HTTP {response.status_code}")
        return None
    except Exception as e:
        print(f"ESPN error: {e}")
        return None


def parse_record(record_str):
    try:
        w, l = record_str.split('-')
        w, l = int(w), int(l)
        return w / (w + l) if (w + l) > 0 else 0.5
    except Exception:
        return 0.5


def get_team_logo(abbr):
    return NBA_LOGOS.get(abbr, DEFAULT_LOGO)


def save_picks_for_gemini(picks):
    os.makedirs("nba", exist_ok=True)
    path = "nba/propozycje_typow.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(picks))
    print(f"Zapisano {len(picks)} typow do {path}")


def load_archive_dates():
    try:
        with open("nba/archive/index.json", encoding="utf-8") as f:
            return json.load(f).get("dates", [])
    except Exception:
        return []


def save_archive_dates(dates):
    os.makedirs("nba/archive", exist_ok=True)
    with open("nba/archive/index.json", "w", encoding="utf-8") as f:
        json.dump({"dates": sorted(set(dates), reverse=True)}, f)


def generate_sitemap(all_dates):
    urls = ["https://nba-freepicks.com/nba/"]
    for d in all_dates:
        urls.append(f"https://nba-freepicks.com/nba/archive/{d}.html")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url in urls:
        xml += f"  <url><loc>{url}</loc></url>\n"
    xml += "</urlset>"
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write(xml)
    print("Zaktualizowano sitemap.xml")


def get_ga4_snippet():
    return f"""    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', '{GA4_ID}');
    </script>"""


# ==========================================
# BUILD GAME CARDS
# ==========================================

def build_game_cards(events):
    from league_ui import render_card, make_pred

    cards_html       = ""
    picks_for_gemini = []
    game_summaries   = []
    matches_data     = {}

    for event in events:
        try:
            competition = event['competitions'][0]
            competitors = competition['competitors']
            status      = event['status']['type']
            state_raw   = status['state']  # pre / in / post

            home_team = next(t for t in competitors if t['homeAway'] == 'home')
            away_team = next(t for t in competitors if t['homeAway'] == 'away')

            h_name     = home_team['team']['shortDisplayName']
            a_name     = away_team['team']['shortDisplayName']
            h_abbr     = home_team['team']['abbreviation']
            a_abbr     = away_team['team']['abbreviation']
            h_logo_url = get_team_logo(h_abbr)
            a_logo_url = get_team_logo(a_abbr)
            h_score    = int(home_team.get('score', 0))
            a_score    = int(away_team.get('score', 0))

            h_record_str = next(
                (s['summary'] for s in home_team.get('records', []) if s['type'] == 'total'), "0-0"
            )
            a_record_str = next(
                (s['summary'] for s in away_team.get('records', []) if s['type'] == 'total'), "0-0"
            )
            h_pct = parse_record(h_record_str)
            a_pct = parse_record(a_record_str)

            predicted_winner = h_name if (h_pct + 0.05) > a_pct else a_name

            # Map ESPN state to league_ui state
            if state_raw == 'pre':
                state = "pre"
            elif state_raw == 'in':
                state = "in"
            else:
                state = "post"

            # Status text
            if state == "in":
                status_text = "LIVE " + status.get('shortDetail', '')
            elif state == "pre":
                status_text = status.get('detail', 'Scheduled')
            else:
                status_text = "Final"

            # Summaries
            if state == "pre":
                picks_for_gemini.append(f"{a_name} @ {h_name} -> Typ: {predicted_winner}")
                game_summaries.append(f"{a_name} vs {h_name}: AI - {predicted_winner} to win")
            elif state == "post":
                actual = h_name if h_score > a_score else a_name
                game_summaries.append(
                    f"{a_name} vs {h_name}: AI picked {predicted_winner}, "
                    f"{actual} won {max(h_score,a_score)}-{min(h_score,a_score)}"
                )
            else:
                game_summaries.append(
                    f"{a_name} vs {h_name} (live): AI picked {predicted_winner}"
                )

            # Formula reasoning for modal
            reasoning = (
                f"{h_name} ({h_record_str}) vs {a_name} ({a_record_str}). "
                f"Typ oparty na bilansie sezonowym W-L. "
                f"Szczegółowa analiza składów dostępna w sekcji Lineup Audit."
            )

            pred = make_pred(
                winner=predicted_winner,
                reasoning=reasoning,
                key_factors=[
                    f"{h_name}: {h_record_str} ({h_pct:.0%} win rate)",
                    f"{a_name}: {a_record_str} ({a_pct:.0%} win rate)",
                    "Przewaga własnego parkietu (+5% dla gospodarza)",
                ],
                confidence=None,
                injury_notes="",
            )

            game_id     = f"nba_{event.get('id', id(event))}"
            cards_html += render_card(
                game_id, h_name, a_name, h_logo_url, a_logo_url,
                h_score, a_score, state, status_text, pred, DEFAULT_LOGO
            )
            matches_data[game_id] = {
                "matchup":      f"{a_name} @ {h_name}",
                "pick":         predicted_winner,
                "reasoning":    reasoning,
                "key_factors":  pred["key_factors"],
                "confidence":   None,
                "injury_notes": "",
                "audit":        "",  # gemini_audit.py wstrzyknie tu przez inject_audit()
            }

        except Exception as e:
            print(f"Blad przy meczu: {e}")
            continue

    return cards_html, picks_for_gemini, game_summaries, matches_data


# ==========================================
# BUILD PAGE
# ==========================================

def build_page(title_date, cards_html, game_summaries=None,
               matches_data=None, is_archive=False,
               archive_prefix="", today_slug=""):
    """
    Generuje stronę NBA. Zachowuje SEO meta tagi i GA4.
    Używa league_ui dla spójnego UI (modal, kalendarz, CSS).
    """
    from league_ui import LEAGUE_CSS, LEAGUE_JS
    import json as _json

    game_summaries = game_summaries or []
    matches_data   = matches_data or {}
    games_meta     = " | ".join(game_summaries[:5])

    if is_archive:
        meta_title    = f"NBA AI Picks {title_date} - Predictions & Results"
        meta_desc     = f"NBA AI model predictions for {title_date}. {games_meta}"
        canonical_url = f"https://nba-freepicks.com/nba/archive/{today_slug}.html"
    else:
        meta_title    = f"NBA AI Picks Today {title_date} - Free Predictions"
        meta_desc     = (f"Free NBA AI predictions for {title_date}. {games_meta}"
                         if games_meta else
                         f"Daily NBA game predictions powered by AI. Free picks - {title_date}.")
        canonical_url = "https://nba-freepicks.com/nba/"
    meta_desc = meta_desc[:160]

    back_button = ""
    if is_archive:
        back_button = f'<a href="{archive_prefix}index.html" style="display:inline-block;margin:0 0 20px 20px;color:#60a5fa;font-size:.85rem;">&#8592; Back to today</a>'

    grid = cards_html.strip() or '<p style="text-align:center;color:#888;padding:60px 0">No games scheduled.</p>'
    match_data_json = _json.dumps(matches_data, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{meta_title}</title>
    <meta name="description" content="{meta_desc}">
    <meta name="keywords" content="NBA picks, NBA predictions, NBA AI picks, free NBA picks, NBA picks today, {title_date} NBA">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="{canonical_url}">
    <meta property="og:type" content="website">
    <meta property="og:title" content="{meta_title}">
    <meta property="og:description" content="{meta_desc}">
    <meta property="og:url" content="{canonical_url}">
    <meta property="og:site_name" content="NBA Free Picks">
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="{meta_title}">
    <meta name="twitter:description" content="{meta_desc}">
{get_ga4_snippet()}
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>&#x1F3C0;</text></svg>">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;900&display=swap" rel="stylesheet">
    <style>
        :root {{ --accent: {BRAND_ACCENT}; }}
        {LEAGUE_CSS}
        .card:hover {{ border-color: {BRAND_ACCENT}40; }}
        .pred-val {{ color: {BRAND_ACCENT}; }}
    </style>
</head>
<body>

    <div class="hub-header">
        <img src="https://cdn.nba.com/logos/nba/nba-logoman-75-word_white.svg"
             alt="NBA logo" class="league-logo"
             onerror="this.src='{DEFAULT_LOGO}'">
        <h1>NBA PUBLIC HUB</h1>
        <div class="subtitle">Live Scores &amp; Public AI Model Picks &mdash; {title_date}</div>
    </div>

    {back_button}

    <div class="grid">
        {grid}
    </div>

    <!-- Historia / Kalendarz -->
    <div class="history-section" id="history">
        <h2>Prediction History</h2>
        <p class="hist-sub">Archive of previous days AI predictions</p>
        <div class="hist-picker">
            <button class="hist-btn" id="btn-yesterday" onclick="trySelectDay('yesterday')">
                <div class="btn-label">Yesterday</div>
                <div class="btn-date" id="lbl-yesterday">—</div>
            </button>
            <button class="hist-btn" id="btn-dayb4" onclick="trySelectDay('dayb4')">
                <div class="btn-label">Day before</div>
                <div class="btn-date" id="lbl-dayb4">—</div>
            </button>
            <div class="hist-divider"></div>
            <div class="hist-cal-btn" id="cal-btn">
                <svg width="20" height="20" viewBox="0 0 22 22" fill="none">
                    <rect x="2" y="4" width="18" height="16" rx="3"
                          stroke="{BRAND_ACCENT}" stroke-width="1.2" fill="none"/>
                    <line x1="2" y1="8.5" x2="20" y2="8.5"
                          stroke="{BRAND_ACCENT}" stroke-width="1.2"/>
                    <line x1="7" y1="2" x2="7" y2="6"
                          stroke="{BRAND_ACCENT}" stroke-width="1.5" stroke-linecap="round"/>
                    <line x1="15" y1="2" x2="15" y2="6"
                          stroke="{BRAND_ACCENT}" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                <div>
                    <div class="btn-label">Pick a date</div>
                    <div class="btn-date" id="cal-display" style="color:{BRAND_ACCENT}">
                        Open calendar</div>
                </div>
                <input type="date" id="hidden-date"
                       style="position:absolute;opacity:0;width:1px;height:1px;pointer-events:none"
                       onchange="selectCustom(this.value)">
            </div>
        </div>
        <div class="hist-result" id="hist-result">
            <span>Archive for <strong id="res-date"></strong></span>
            <a href="#" id="res-link">View picks →</a>
        </div>
        <div class="hist-noarchive" id="hist-noarchive">
            <span>⚠️ No archive for <strong id="noarch-date"></strong></span>
        </div>
    </div>

    <!-- Modal -->
    <div class="modal-overlay" id="modal-overlay">
        <div class="modal-box" id="modal-box"></div>
    </div>

    <div class="hub-footer">
        Last updated: {datetime.now().strftime("%B %d, %Y at %H:%M")}
    </div>

    <script>window._matchData = {match_data_json};</script>
    <script>{LEAGUE_JS}</script>
</body>
</html>"""


# ==========================================
# GLOWNA FUNKCJA
# ==========================================

def generate_html():
    print("URUCHAMIAM NBA UPDATE BOT...")

    data = get_espn_data()
    if not data or 'events' not in data:
        print("Brak danych z ESPN.")
        return

    events     = data['events']
    today_str  = datetime.now().strftime("%B %d, %Y")
    today_slug = datetime.now().strftime("%Y-%m-%d")

    cards_html, picks_for_gemini, game_summaries, matches_data = build_game_cards(events)

    # 1. nba/index.html — zawsze aktualny
    os.makedirs("nba", exist_ok=True)
    with open("nba/index.html", "w", encoding="utf-8") as f:
        f.write(build_page(
            title_date     = today_str,
            cards_html     = cards_html,
            game_summaries = game_summaries,
            matches_data   = matches_data,
            is_archive     = False,
            archive_prefix = "",
            today_slug     = today_slug
        ))
    print("Zapisano nba/index.html")

    # 2. Zapisz typy dla gemini_audit.py
    if picks_for_gemini:
        save_picks_for_gemini(picks_for_gemini)

    # 3. Archiwum — TYLKO gdy wszystkie mecze zakonczone
    archive_path = f"nba/archive/{today_slug}.html"
    if events:
        all_final = all(
            e['status']['type']['state'] == 'post' for e in events
        )
    else:
        all_final = False

    if all_final and not os.path.exists(archive_path):
        os.makedirs("nba/archive", exist_ok=True)
        with open(archive_path, "w", encoding="utf-8") as f:
            f.write(build_page(
                title_date     = today_str,
                cards_html     = cards_html,
                game_summaries = game_summaries,
                matches_data   = matches_data,
                is_archive     = True,
                archive_prefix = "../",
                today_slug     = today_slug
            ))
        print(f"Zapisano nba/archive/{today_slug}.html")
        existing = load_archive_dates()
        existing.append(today_slug)
        save_archive_dates(existing)
        generate_sitemap(load_archive_dates())

    elif all_final and os.path.exists(archive_path):
        print(f"nba/archive/{today_slug}.html juz istnieje — pomijam")
    else:
        print("Mecze jeszcze w toku — archiwum nie zapisano")


if __name__ == "__main__":
    generate_html()
