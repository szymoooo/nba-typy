import requests
import json
from datetime import datetime
import os

# ==========================================
# KONFIGURACJA
# ==========================================
ESPN_API = "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
GA4_ID   = "G-ZV0JG9D4QK"

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
    except Exception as e:
        print(f"Blad polaczenia z ESPN: {e}")
    return None

def parse_record(record_str):
    try:
        w, l = map(int, record_str.split('-'))
        total = w + l
        if total == 0: return 0.0
        return w / total
    except:
        return 0.0

def get_team_logo(abbr):
    return NBA_LOGOS.get(abbr, DEFAULT_LOGO)

def save_picks_for_gemini(picks):
    os.makedirs("nba", exist_ok=True)
    with open("nba/propozycje_typow.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(picks))
    print(f"Zapisano {len(picks)} typow do nba/propozycje_typow.txt")

def load_archive_dates():
    index_path = "nba/archive/index.json"
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f).get("dates", [])
    return []

def save_archive_dates(dates):
    os.makedirs("nba/archive", exist_ok=True)
    sorted_dates = sorted(set(dates), reverse=True)
    with open("nba/archive/index.json", "w", encoding="utf-8") as f:
        json.dump({"dates": sorted_dates}, f, indent=2)
    print(f"Zaktualizowano nba/archive/index.json ({len(sorted_dates)} dat)")


# ==========================================
# SITEMAP + ROBOTS
# ==========================================

def generate_sitemap(all_dates):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    # Hub
    lines.append('  <url>')
    lines.append('    <loc>https://nba-freepicks.com/</loc>')
    lines.append('    <changefreq>daily</changefreq>')
    lines.append('    <priority>1.0</priority>')
    lines.append('  </url>')
    # NBA root
    lines.append('  <url>')
    lines.append('    <loc>https://nba-freepicks.com/nba/</loc>')
    lines.append('    <changefreq>daily</changefreq>')
    lines.append('    <priority>0.9</priority>')
    lines.append('  </url>')
    # EuroLeague root
    lines.append('  <url>')
    lines.append('    <loc>https://nba-freepicks.com/euroleague/</loc>')
    lines.append('    <changefreq>daily</changefreq>')
    lines.append('    <priority>0.9</priority>')
    lines.append('  </url>')
    # NBA archive
    for d in sorted(set(all_dates), reverse=True):
        lines.append('  <url>')
        lines.append(f'    <loc>https://nba-freepicks.com/nba/archive/{d}.html</loc>')
        lines.append(f'    <lastmod>{d}</lastmod>')
        lines.append('    <changefreq>never</changefreq>')
        lines.append('    <priority>0.7</priority>')
        lines.append('  </url>')
    lines.append('</urlset>')
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Zapisano sitemap.xml ({len(all_dates)} archiwalnych URL + hub + 2 ligi)")

def generate_robots():
    robots = (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        "Sitemap: https://nba-freepicks.com/sitemap.xml\n"
    )
    with open("robots.txt", "w", encoding="utf-8") as f:
        f.write(robots)
    print("Zapisano robots.txt")


# ==========================================
# CSS
# ==========================================

def get_shared_styles():
    return """
        :root {
            --bg: #0f172a;
            --card-bg: #1e293b;
            --accent: #3b82f6;
            --text: #f8fafc;
            --subtext: #94a3b8;
            --win: #10b981;
            --loss: #ef4444;
            --border: #334155;
        }
        * { box-sizing: border-box; }
        body {
            background-color: var(--bg);
            color: var(--text);
            font-family: 'Montserrat', sans-serif;
            margin: 0;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }
        h1 {
            font-weight: 900;
            letter-spacing: -1px;
            margin: 0;
            color: var(--accent);
            font-size: 2.5rem;
        }
        .subtitle {
            color: var(--subtext);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 10px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 25px;
        }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 20px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            transition: transform 0.2s, box-shadow 0.2s;
            box-shadow: 0 10px 15px -3px rgba(0,0,0,0.2);
        }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3);
            border-color: var(--accent);
        }
        .card-header {
            background: rgba(0,0,0,0.3);
            padding: 12px 25px;
            display: flex;
            justify-content: center;
            align-items: center;
            border-bottom: 1px solid var(--border);
        }
        .status { font-size: 0.75rem; font-weight: 900; color: var(--subtext); text-transform: uppercase; letter-spacing: 1px; }
        .live { color: #ef4444; animation: pulse 1.5s infinite; }
        .matchup {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 30px 20px;
            flex-grow: 1;
        }
        .team {
            text-align: center;
            width: 30%;
            height: 140px;
            position: relative;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .team-name {
            font-weight: 900;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            position: absolute;
            bottom: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 100%;
            text-shadow: 0 2px 4px rgba(0,0,0,1);
            padding-bottom: 5px;
        }
        .team-logo {
            width: 120px;
            height: 120px;
            object-fit: contain;
            opacity: 0.9;
            margin-bottom: 15px;
        }
        .score-container {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
        }
        .score { font-size: 2.8rem; font-weight: 900; line-height: 1; text-shadow: 0 2px 5px rgba(0,0,0,0.8); }
        .score.winner { color: var(--win); }
        .score.loser   { color: var(--subtext); opacity: 0.8; }
        .vs-sep { color: var(--border); font-style: italic; font-weight: 900; font-size: 1.5rem; }
        .prediction-box {
            background: rgba(15,23,42,0.6);
            padding: 20px;
            text-align: center;
            border-top: 1px solid var(--border);
            margin-top: auto;
        }
        .pred-label { font-size: 0.7rem; color: var(--subtext); text-transform: uppercase; font-weight: 700; letter-spacing: 1px; margin-bottom: 8px; }
        .pred-val { font-size: 1.2rem; font-weight: 900; color: var(--text); display: flex; align-items: center; justify-content: center; gap: 8px; }
        .history-section {
            margin-top: 80px;
            padding-top: 40px;
            border-top: 1px solid var(--border);
        }
        .history-section h2 {
            text-align: center;
            color: var(--accent);
            font-size: 1.6rem;
            font-weight: 900;
            margin-bottom: 6px;
        }
        .hist-sub {
            text-align: center;
            color: var(--subtext);
            font-size: 0.9rem;
            margin-bottom: 32px;
        }
        .hist-picker {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            align-items: stretch;
            max-width: 720px;
            margin: 0 auto;
        }
        .hist-btn {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 16px 24px;
            cursor: pointer;
            font-family: 'Montserrat', sans-serif;
            color: var(--text);
            display: flex;
            flex-direction: column;
            gap: 5px;
            min-width: 150px;
            flex: 1;
            transition: background 0.15s, border-color 0.15s, transform 0.15s;
            text-align: left;
        }
        .hist-btn:hover:not(.disabled), .hist-btn.active {
            background: #1e3a5f;
            border-color: var(--accent);
            transform: translateY(-2px);
        }
        .hist-btn.disabled { opacity: 0.35; cursor: not-allowed; filter: grayscale(1); }
        .btn-label { font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--subtext); }
        .hist-btn.active .btn-label { color: #60a5fa; }
        .btn-date { font-size: 0.92rem; font-weight: 800; color: var(--text); }
        .hist-btn.disabled .btn-date { color: var(--subtext); }
        .hist-cal-btn {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 16px 24px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 12px;
            flex: 1;
            min-width: 190px;
            position: relative;
            transition: background 0.15s, border-color 0.15s, transform 0.15s;
        }
        .hist-cal-btn:hover, .hist-cal-btn.active {
            background: #1e3a5f;
            border-color: var(--accent);
            transform: translateY(-2px);
        }
        .hist-cal-btn.active .btn-label { color: #60a5fa; }
        .hist-cal-btn .btn-date { color: #60a5fa; font-size: 0.92rem; font-weight: 800; }
        .hist-divider { width: 1px; background: var(--border); align-self: stretch; flex-shrink: 0; margin: 0 2px; }
        .hist-result, .hist-noarchive {
            max-width: 720px;
            margin: 20px auto 0;
            border-radius: 14px;
            padding: 16px 22px;
            font-size: 0.9rem;
            display: none;
            align-items: center;
            gap: 12px;
        }
        .hist-result { background: var(--card-bg); border: 1px solid var(--border); color: var(--subtext); }
        .hist-noarchive { background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.25); color: #fca5a5; }
        .hist-result.show, .hist-noarchive.show { display: flex; }
        .hist-result .arrow { color: var(--accent); font-size: 1.2rem; }
        .hist-result strong { color: var(--text); }
        .hist-result a {
            margin-left: auto;
            background: var(--accent);
            color: #fff;
            font-weight: 700;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 8px 18px;
            border-radius: 10px;
            text-decoration: none;
            white-space: nowrap;
            transition: background 0.15s;
        }
        .hist-result a:hover { background: #2563eb; }
        .back-btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: var(--card-bg);
            border: 1px solid var(--border);
            color: #60a5fa;
            font-family: 'Montserrat', sans-serif;
            font-size: 0.85rem;
            font-weight: 700;
            text-decoration: none;
            padding: 10px 20px;
            border-radius: 12px;
            margin-bottom: 30px;
            transition: background 0.15s, border-color 0.15s;
        }
        .back-btn:hover { background: #1e3a5f; border-color: var(--accent); }
        .footer {
            text-align: center;
            color: var(--subtext);
            font-size: 0.75rem;
            margin-top: 50px;
            padding-bottom: 20px;
        }
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.5; } }
        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
            .matchup { padding: 25px 15px; }
            .score { font-size: 2.2rem; }
            .hist-picker { flex-direction: column; }
            .hist-divider { display: none; }
        }
    """


# ==========================================
# HISTORY HTML + JS
# ==========================================

def get_history_html_block():
    return """
        <div id="history" class="history-section">
            <h2>Prediction History</h2>
            <p class="hist-sub">Archive of previous days AI predictions</p>
            <div class="hist-picker">
                <button class="hist-btn" id="btn-yesterday" onclick="trySelectDay('yesterday')">
                    <span class="btn-label">Yesterday</span>
                    <span class="btn-date" id="lbl-yesterday">Loading...</span>
                </button>
                <button class="hist-btn" id="btn-dayb4" onclick="trySelectDay('dayb4')">
                    <span class="btn-label">Day before</span>
                    <span class="btn-date" id="lbl-dayb4">Loading...</span>
                </button>
                <div class="hist-divider"></div>
                <div class="hist-cal-btn" id="cal-btn">
                    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" style="flex-shrink:0">
                        <rect x="2" y="4" width="18" height="16" rx="3" stroke="#60a5fa" stroke-width="1.2" fill="none"/>
                        <line x1="2" y1="8.5" x2="20" y2="8.5" stroke="#60a5fa" stroke-width="1.2"/>
                        <line x1="7" y1="2" x2="7" y2="6" stroke="#60a5fa" stroke-width="1.5" stroke-linecap="round"/>
                        <line x1="15" y1="2" x2="15" y2="6" stroke="#60a5fa" stroke-width="1.5" stroke-linecap="round"/>
                    </svg>
                    <div>
                        <div class="btn-label">Pick a date</div>
                        <div class="btn-date" id="cal-display" style="color:#60a5fa;">Open calendar</div>
                    </div>
                    <input type="date" id="hidden-date"
                           style="position:absolute;opacity:0;width:1px;height:1px;pointer-events:none;"
                           onchange="selectCustom(this.value)">
                </div>
            </div>
            <div class="hist-result" id="hist-result">
                <span class="arrow">&#8594;</span>
                <span>Archive for <strong id="res-date"></strong></span>
                <a href="#" id="res-link">View picks</a>
            </div>
            <div class="hist-noarchive" id="hist-noarchive">
                <span>&#9888;&#65039;</span>
                <span>No archive for <strong id="noarch-date"></strong> — no picks were generated for this date.</span>
            </div>
        </div>
    """

def get_history_js(archive_prefix=""):
    return f"""
    <script>
        const ARCHIVE_PREFIX = '{archive_prefix}';
        let availableDates = new Set();
        let pickerReady = false;
        const today = new Date();
        function fmtDisplay(d) {{
            return d.toLocaleDateString('en-US', {{ month: 'long', day: 'numeric', year: 'numeric' }});
        }}
        function fmtSlug(d) {{
            const y = d.getFullYear();
            const m = String(d.getMonth()+1).padStart(2,'0');
            const dd = String(d.getDate()).padStart(2,'0');
            return y+'-'+m+'-'+dd;
        }}
        function offsetDay(n) {{
            const d = new Date(today);
            d.setDate(d.getDate() + n);
            return d;
        }}
        const yday = offsetDay(-1);
        const db4  = offsetDay(-2);
        fetch(ARCHIVE_PREFIX + 'archive/index.json?v=' + Date.now())
            .then(r => r.json())
            .then(data => {{ availableDates = new Set(data.dates || []); }})
            .catch(() => {{}})
            .finally(() => {{ pickerReady = true; initPicker(); }});
        function initPicker() {{
            document.getElementById('lbl-yesterday').textContent = fmtDisplay(yday);
            document.getElementById('lbl-dayb4').textContent     = fmtDisplay(db4);
            if (!availableDates.has(fmtSlug(yday))) document.getElementById('btn-yesterday').classList.add('disabled');
            if (!availableDates.has(fmtSlug(db4)))  document.getElementById('btn-dayb4').classList.add('disabled');
        }}
        function clearActive() {{
            ['btn-yesterday','btn-dayb4','cal-btn'].forEach(id => document.getElementById(id).classList.remove('active'));
            document.getElementById('hist-result').classList.remove('show');
            document.getElementById('hist-noarchive').classList.remove('show');
        }}
        function showResult(label, slug) {{
            document.getElementById('res-date').textContent = label;
            document.getElementById('res-link').href = ARCHIVE_PREFIX + 'archive/' + slug + '.html';
            document.getElementById('hist-result').classList.add('show');
            document.getElementById('hist-noarchive').classList.remove('show');
        }}
        function showNoArchive(label) {{
            document.getElementById('noarch-date').textContent = label;
            document.getElementById('hist-noarchive').classList.add('show');
            document.getElementById('hist-result').classList.remove('show');
        }}
        function trySelectDay(which) {{
            const btn = document.getElementById('btn-' + which);
            if (btn.classList.contains('disabled')) return;
            clearActive();
            const d = which === 'yesterday' ? yday : db4;
            btn.classList.add('active');
            document.getElementById('cal-display').textContent = 'Open calendar';
            document.getElementById('cal-btn').classList.remove('active');
            showResult(fmtDisplay(d), fmtSlug(d));
        }}
        function selectCustom(val) {{
            if (!val) return;
            clearActive();
            const parts = val.split('-');
            const d     = new Date(+parts[0], +parts[1]-1, +parts[2]);
            const slug  = fmtSlug(d);
            const label = fmtDisplay(d);
            document.getElementById('cal-display').textContent = label;
            document.getElementById('cal-btn').classList.add('active');
            if (pickerReady && availableDates.size > 0 && !availableDates.has(slug)) {{
                showNoArchive(label);
            }} else {{
                showResult(label, slug);
            }}
        }}
        document.getElementById('cal-btn').addEventListener('click', function() {{
            const inp = document.getElementById('hidden-date');
            if (inp.showPicker) inp.showPicker(); else inp.click();
        }});
    </script>
    """


# ==========================================
# BUDOWANIE KART MECZOW
# ==========================================

def build_game_cards(events):
    cards_html       = ""
    picks_for_gemini = []
    game_summaries   = []

    for event in events:
        try:
            competition = event['competitions'][0]
            competitors  = competition['competitors']
            status       = event['status']['type']
            state        = status['state']

            home_team = next(t for t in competitors if t['homeAway'] == 'home')
            away_team = next(t for t in competitors if t['homeAway'] == 'away')

            h_name  = home_team['team']['shortDisplayName']
            a_name  = away_team['team']['shortDisplayName']
            h_abbr  = home_team['team']['abbreviation']
            a_abbr  = away_team['team']['abbreviation']

            h_logo_url = get_team_logo(h_abbr)
            a_logo_url = get_team_logo(a_abbr)

            h_score = int(home_team.get('score', 0))
            a_score = int(away_team.get('score', 0))
            h_record_str = next((s['summary'] for s in home_team.get('records', []) if s['type'] == 'total'), "0-0")
            a_record_str = next((s['summary'] for s in away_team.get('records', []) if s['type'] == 'total'), "0-0")

            h_pct = parse_record(h_record_str)
            a_pct = parse_record(a_record_str)
            predicted_winner = h_name if (h_pct + 0.05) > a_pct else a_name

            if state == 'pre':
                picks_for_gemini.append(f"{a_name} @ {h_name} -> Typ: {predicted_winner}")

            is_final = (state == 'post')
            h_score_class = "score"
            a_score_class = "score"
            actual_winner = ""

            if state == 'pre':
                score_display_html = '<span class="vs-sep" style="font-size:2rem;">VS</span>'
                game_summaries.append(f"{a_name} vs {h_name}: AI prediction - {predicted_winner} to win")
            else:
                if is_final:
                    if h_score > a_score:
                        actual_winner  = h_name
                        h_score_class += " winner"
                        a_score_class += " loser"
                    else:
                        actual_winner  = a_name
                        a_score_class += " winner"
                        h_score_class += " loser"
                    result_txt = f"{actual_winner} won {max(h_score,a_score)}-{min(h_score,a_score)}"
                    game_summaries.append(f"{a_name} vs {h_name}: AI picked {predicted_winner}, {result_txt}")
                else:
                    game_summaries.append(f"{a_name} vs {h_name} (live): AI picked {predicted_winner}")

                score_display_html = f"""
                    <span class="{a_score_class}">{a_score}</span>
                    <span class="vs-sep">:</span>
                    <span class="{h_score_class}">{h_score}</span>
                """

            status_text  = status['detail']
            status_class = "status"
            if state == 'in':
                status_class += " live"
                status_text   = "LIVE " + status['shortDetail']

            outcome_icon = ""
            if is_final:
                outcome_icon = ' <span style="color:#10b981;">&#10003;</span>' if predicted_winner == actual_winner else ' <span style="color:#ef4444;">&#10007;</span>'

            cards_html += f"""
            <div class="card">
                <div class="card-header">
                    <span class="{status_class}">{status_text}</span>
                </div>
                <div class="matchup">
                    <div class="team">
                        <img src="{a_logo_url}" class="team-logo" alt="{a_name}">
                        <span class="team-name">{a_name}</span>
                    </div>
                    <div class="score-container">
                        {score_display_html}
                    </div>
                    <div class="team">
                        <img src="{h_logo_url}" class="team-logo" alt="{h_name}">
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
            print(f"Blad przy meczu: {e}")
            continue

    return cards_html, picks_for_gemini, game_summaries


# ==========================================
# GA4
# ==========================================

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
# BUDOWANIE STRONY
# ==========================================

def build_page(title_date, cards_html, game_summaries=None, is_archive=False, archive_prefix="", today_slug=""):
    game_summaries = game_summaries or []
    games_meta = " | ".join(game_summaries[:5])

    if is_archive:
        meta_title    = f"NBA AI Picks {title_date} - Predictions & Results"
        meta_desc     = f"NBA AI model predictions for {title_date}. {games_meta}"
        canonical_url = f"https://nba-freepicks.com/nba/archive/{today_slug}.html"
    else:
        meta_title    = f"NBA AI Picks Today {title_date} - Free Predictions"
        meta_desc     = (f"Free NBA AI predictions for {title_date}. {games_meta}"
                         if games_meta else
                         f"Daily NBA game predictions powered by AI. Free picks for every game - {title_date}.")
        canonical_url = "https://nba-freepicks.com/nba/"

    meta_desc = meta_desc[:160]

    back_button = ""
    if is_archive:
        back_button = f'<a href="{archive_prefix}index.html" class="back-btn">&#8592; Back to today</a>'

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
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800;900&display=swap" rel="stylesheet">
    <style>{get_shared_styles()}</style>
</head>
<body>
    <div class="container">
        <header>
            <h1>NBA PUBLIC HUB</h1>
            <div class="subtitle">Live Scores &amp; Public AI Model Picks &mdash; {title_date}</div>
        </header>

        {back_button}

        <div class="grid">
            {cards_html if cards_html.strip() else '<p style="text-align:center;color:#888;">No games scheduled.</p>'}
        </div>

        {get_history_html_block()}

        <div class="footer">
            Last updated: {datetime.now().strftime("%B %d, %Y at %H:%M")}
        </div>
    </div>
    {get_history_js(archive_prefix=archive_prefix)}
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

    cards_html, picks_for_gemini, game_summaries = build_game_cards(events)

    # ── 1. nba/index.html — zawsze aktualny ──
    os.makedirs("nba", exist_ok=True)
    with open("nba/index.html", "w", encoding="utf-8") as f:
        f.write(build_page(
            title_date     = today_str,
            cards_html     = cards_html,
            game_summaries = game_summaries,
            is_archive     = False,
            archive_prefix = "",
            today_slug     = today_slug
        ))
    print("Zapisano nba/index.html")

    # ── 2. archive — TYLKO gdy wszystkie mecze zakonczone ──
    archive_path = f"nba/archive/{today_slug}.html"

    if events:
        all_final = all(
            e['status']['type']['state'] == 'post'
            for e in events
        )
    else:
        all_final = False

    if all_final and not os.path.exists(archive_path):
        # Wszystkie mecze Final i plik jeszcze nie istnieje — zapisujemy
        os.makedirs("nba/archive", exist_ok=True)
        with open(archive_path, "w", encoding="utf-8") as f:
            f.write(build_page(
                title_date     = today_str,
                cards_html     = cards_html,
                game_summaries = game_summaries,
                is_archive     = True,
                archive_prefix = "../",
                today_slug     = today_slug
            ))
        print(f"Zapisano nba/archive/{today_slug}.html (wszystkie mecze Final)")

        # Zaktualizuj nba/archive/index.json i sitemap tylko gdy nowy plik
        existing = load_archive_dates()
        existing.append(today_slug)
        save_archive_dates(existing)
        generate_sitemap(load_archive_dates())

    elif all_final and os.path.exists(archive_path):
        print(f"nba/archive/{today_slug}.html juz istnieje — pomijam")

    else:
        states = [e['status']['type']['state'] for e in events]
        print(f"Archiwum NIE zapisane — mecze w toku: {states}")

    # ── 3. robots.txt ── (zawsze)
    generate_robots()

    # ── 4. Typy dla Gemini ── (tylko gdy mecze przed rozpoczeciem)
    if picks_for_gemini:
        save_picks_for_gemini(picks_for_gemini)
    else:
        print("Brak typow pre-game do zapisania")

    print("Wszystkie zadania zakonczone.")


if __name__ == "__main__":
    generate_html()
