import requests
import json
from datetime import datetime
import os

# ==========================================
# ⚙️ KONFIGURACJA (ULTRA-NEON PLASMA EDITION)
# ==========================================
ESPN_API = "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

# Zapasowy słownik logo
NBA_LOGOS_FALLBACK = {
    'ATL': 'https://cdn.nba.com/logos/nba/1610612737/global/L/logo.svg',
    'BOS': 'https://cdn.nba.com/logos/nba/1610612738/global/L/logo.svg',
    'CLE': 'https://cdn.nba.com/logos/nba/1610612739/global/L/logo.svg',
    'NOP': 'https://cdn.nba.com/logos/nba/1610612740/global/L/logo.svg',
    'CHI': 'https://cdn.nba.com/logos/nba/1610612741/global/L/logo.svg',
    'DAL': 'https://cdn.nba.com/logos/nba/1610612742/global/L/logo.svg',
    'DEN': 'https://cdn.nba.com/logos/nba/1610612743/global/L/logo.svg',
    'GSW': 'https://cdn.nba.com/logos/nba/1610612744/global/L/logo.svg',
    'HOU': 'https://cdn.nba.com/logos/nba/1610612745/global/L/logo.svg',
    'LAC': 'https://cdn.nba.com/logos/nba/1610612746/global/L/logo.svg',
    'LAL': 'https://cdn.nba.com/logos/nba/1610612747/global/L/logo.svg',
    'MIA': 'https://cdn.nba.com/logos/nba/1610612748/global/L/logo.svg',
    'MIL': 'https://cdn.nba.com/logos/nba/1610612749/global/L/logo.svg',
    'MIN': 'https://cdn.nba.com/logos/nba/1610612750/global/L/logo.svg',
    'BKN': 'https://cdn.nba.com/logos/nba/1610612751/global/L/logo.svg',
    'NYK': 'https://cdn.nba.com/logos/nba/1610612752/global/L/logo.svg',
    'ORL': 'https://cdn.nba.com/logos/nba/1610612753/global/L/logo.svg',
    'IND': 'https://cdn.nba.com/logos/nba/1610612754/global/L/logo.svg',
    'PHI': 'https://cdn.nba.com/logos/nba/1610612755/global/L/logo.svg',
    'PHX': 'https://cdn.nba.com/logos/nba/1610612756/global/L/logo.svg',
    'POR': 'https://cdn.nba.com/logos/nba/1610612757/global/L/logo.svg',
    'SAC': 'https://cdn.nba.com/logos/nba/1610612758/global/L/logo.svg',
    'SAS': 'https://cdn.nba.com/logos/nba/1610612759/global/L/logo.svg',
    'OKC': 'https://cdn.nba.com/logos/nba/1610612760/global/L/logo.svg',
    'TOR': 'https://cdn.nba.com/logos/nba/1610612761/global/L/logo.svg',
    'UTA': 'https://cdn.nba.com/logos/nba/1610612762/global/L/logo.svg',
    'MEM': 'https://cdn.nba.com/logos/nba/1610612763/global/L/logo.svg',
    'WAS': 'https://cdn.nba.com/logos/nba/1610612764/global/L/logo.svg',
    'DET': 'https://cdn.nba.com/logos/nba/1610612765/global/L/logo.svg',
    'CHA': 'https://cdn.nba.com/logos/nba/1610612766/global/L/logo.svg',
}
DEFAULT_LOGO = 'https://cdn.nba.com/logos/nba/nba-logoman-70x70.svg'

def get_espn_data():
    try:
        response = requests.get(ESPN_API, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Błąd połączenia z ESPN: {e}")
    return None

def parse_record(record_str):
    try:
        w, l = map(int, record_str.split('-'))
        total = w + l
        if total == 0: return 0.0
        return w / total
    except:
        return 0.0

def get_team_logo(team_data):
    if 'logo' in team_data: return team_data['logo']
    abbr = team_data.get('abbreviation')
    if abbr in NBA_LOGOS_FALLBACK: return NBA_LOGOS_FALLBACK[abbr]
    return DEFAULT_LOGO

def generate_html():
    print("🚀 URUCHAMIAM ULTRA-NEON ENGINE...")
    
    data = get_espn_data()
    if not data or 'events' not in data:
        print("❌ Brak danych.")
        return

    events = data['events']
    
    # --- NAGŁÓWEK HTML (ULTRA NEON CSS) ---
    html = f"""
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PRO ANALYTICS HUB</title>
        <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏀</text></svg>">
        <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet">
        <style>
            :root {{ 
                --bg: #010103;
                --card-dark: #07070a;
                /* Ultra nasycone kolory */
                --neon-cyan: #00ffff;
                --neon-magenta: #ff00ff;
                --neon-gold: #ffcc00;
                --neon-green: #39ff14;
                --text: #ffffff;
                --loss: #ff0055; 
            }}
            
            body {{ 
                background-color: var(--bg); 
                /* Tło circuit board */
                background-image: url("data:image/svg+xml,%3Csvg width='100' height='100' viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M10 10h80v80h-80z' fill='none' stroke='%23111' stroke-width='1'/%3E%3Cpath d='M30 10v20h-20' fill='none' stroke='%23222' stroke-width='2'/%3E%3Cpath d='M70 10v30h20' fill='none' stroke='%23222' stroke-width='2'/%3E%3Cpath d='M10 70h30v20' fill='none' stroke='%23222' stroke-width='2'/%3E%3Ccircle cx='30' cy='30' r='3' fill='%231a1a1a'/%3E%3Ccircle cx='70' cy='40' r='3' fill='%231a1a1a'/%3E%3C/svg%3E");
                color: var(--text); 
                font-family: 'Orbitron', sans-serif;
                margin: 0; 
                padding: 40px 20px;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            
            /* Animacja pulsowania prądu */
            @keyframes electricity-pulse {{
                0% {{ box-shadow: inset 0 0 10px var(--neon-color), 0 0 10px var(--neon-color); opacity: 0.8; }}
                100% {{ box-shadow: inset 0 0 25px var(--neon-color), 0 0 30px var(--neon-color), 0 0 50px var(--neon-color); opacity: 1; }}
            }}

            header {{ text-align: center; margin-bottom: 70px; position: relative; }}
            h1 {{ 
                font-weight: 900; letter-spacing: 4px; margin: 0; font-size: 3rem; text-transform: uppercase;
                color: #fff;
                /* Efekt złotego neonu na górze */
                text-shadow: 
                    0 0 5px #fff,
                    0 0 10px var(--neon-gold),
                    0 0 30px var(--neon-gold),
                    0 0 50px var(--neon-gold);
                border: 3px solid #fff;
                padding: 15px 40px;
                border-radius: 10px;
                box-shadow: 
                    inset 0 0 20px var(--neon-gold),
                    0 0 20px var(--neon-gold);
            }}
            .subtitle {{ color: #aaa; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 2px; margin-top: 30px; }}
            
            .grid {{
                display: grid; grid-template-columns: repeat(auto-fit, minmax(550px, 1fr)); gap: 60px;
            }}
            
            /* === KARTA GŁÓWNA === */
            .card {{ 
                background: var(--card-dark); border-radius: 25px; position: relative; overflow: hidden;
                border: 2px solid #222;
                box-shadow: 0 0 50px rgba(0,0,0,0.8);
            }}
            /* Subtelne linie tła na karcie */
            .card::after {{
                content: ''; position: absolute; inset: 0;
                background: linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
                background-size: 20px 20px; pointer-events: none; z-index: 0;
            }}

            .status-bar {{
                text-align: center; padding: 12px; font-size: 0.8rem; letter-spacing: 2px; z-index: 2; position: relative;
                background: rgba(0,0,0,0.8); color: #888; border-bottom: 2px solid #222; font-weight: 700;
            }}
            .live {{ color: var(--loss); text-shadow: 0 0 20px var(--loss); }}

            .neon-matchup {{
                display: flex; justify-content: space-between; align-items: center;
                padding: 50px 30px; position: relative; z-index: 2;
            }}

            /* === KONTENERY ZESPOŁÓW (RURY Z PRĄDEM) === */
            .team-neon-box {{
                text-align: center; width: 28%; padding: 25px 15px; border-radius: 20px;
                background: rgba(0,0,0,0.6);
                display: flex; flex-direction: column; align-items: center;
                /* Imitacja szklanej rury */
                border: 3px solid rgba(255,255,255,0.8); 
                animation: electricity-pulse 2s infinite alternate ease-in-out;
            }}

            /* Lewa (Goście) - Cyjan */
            .team-left {{ --neon-color: var(--neon-cyan); }}
            .team-left .team-name {{ color: var(--neon-cyan); text-shadow: 0 0 20px var(--neon-cyan); }}

            /* Prawa (Gospodarze) - Magenta */
            .team-right {{ --neon-color: var(--neon-magenta); }}
            .team-right .team-name {{ color: var(--neon-magenta); text-shadow: 0 0 20px var(--neon-magenta); }}

            .team-name {{ 
                font-weight: 900; font-size: 1.6rem; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 1px;
            }}
            /* Loga świecące */
            .team-logo {{
                width: 110px; height: 110px; object-fit: contain;
                filter: drop-shadow(0 0 20px var(--neon-color));
            }}

            /* === ŚRODEK - WYNIK === */
            .scoreboard-container {{ display: flex; flex-direction: column; align-items: center; }}
            
            .digital-scoreboard {{
                font-family: 'Share Tech Mono', monospace;
                background: #000; padding: 20px 35px; border-radius: 15px;
                border: 4px solid #fff;
                /* Efekt niebieskiego ekranu */
                box-shadow: inset 0 0 40px var(--neon-cyan), 0 0 30px var(--neon-cyan);
                text-align: center; position: relative;
            }}
            .score-line {{ font-size: 4rem; font-weight: 400; letter-spacing: 4px; display: flex; gap: 15px; justify-content: center; }}
            .digit {{ color: #fff; text-shadow: 0 0 25px #fff; }}
            .digit.winner {{ color: var(--neon-green); text-shadow: 0 0 40px var(--neon-green); }}
            .digit.loser {{ color: #444; text-shadow: none; opacity: 0.6; }}
            
            .vs-neon {{
                font-size: 2rem; font-weight: 900; color: #fff; margin-top: 25px;
                text-shadow: 0 0 10px #fff, 0 0 30px var(--neon-cyan), 0 0 50px var(--neon-magenta);
            }}

            /* === DOLNY PANEL (ZŁOTY AKCENT) === */
            .neon-prediction-panel {{ 
                background: rgba(0,0,0,0.7); padding: 30px; text-align: center; 
                border-top: 3px solid #fff; position: relative; margin-top: auto; z-index: 2;
                box-shadow: inset 0 0 30px var(--neon-gold);
            }}
            
            .pred-label {{ font-size: 0.8rem; color: #aaa; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 15px; }}
            .pred-val {{ 
                font-size: 1.8rem; font-weight: 900; color: #fff; text-transform: uppercase; letter-spacing: 2px; 
                text-shadow: 0 0 20px var(--neon-gold), 0 0 40px var(--neon-gold);
            }}
            
            .result-badge {{
                display: inline-block; padding: 10px 25px; border-radius: 50px;
                font-size: 1rem; font-weight: 800; margin-top: 20px; text-transform: uppercase; letter-spacing: 1px;
                color: #000; border: 2px solid #fff;
            }}
            .res-win {{ background: var(--neon-green); box-shadow: 0 0 30px var(--neon-green); }}
            .res-loss {{ background: var(--loss); color: #fff; box-shadow: 0 0 30px var(--loss); }}
            
            .footer {{ text-align: center; color: #666; font-size: 0.8rem; margin-top: 80px; padding-bottom: 40px; letter-spacing: 1px; }}
            
            @media (max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} .neon-matchup {{ flex-direction: column; gap: 40px; }} .team-neon-box {{ width: 90%; }} .score-line {{ font-size: 3.5rem; }} }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>PRO ANALYTICS HUB</h1>
                <div class="subtitle">Automated Public Trends & Live Data Engine</div>
            </header>
            
            <div class="grid">
    """

    count = 0
    for event in events:
        try:
            competition = event['competitions'][0]
            competitors = competition['competitors']
            status = event['status']['type']
            state = status['state'] # 'pre', 'in', 'post'
            
            # Pobieranie drużyn
            home_team = next(t for t in competitors if t['homeAway'] == 'home')
            away_team = next(t for t in competitors if t['homeAway'] == 'away')
            
            h_abbr = home_team['team']['abbreviation']
            a_abbr = away_team['team']['abbreviation']
            h_full_name = home_team['team']['shortDisplayName']
            a_full_name = away_team['team']['shortDisplayName']

            # Loga
            h_logo_url = get_team_logo(home_team['team'])
            a_logo_url = get_team_logo(away_team['team'])
            
            # Rekordy
            h_record_str = next((s['summary'] for s in home_team.get('records', []) if s['type'] == 'total'), "0-0")
            a_record_str = next((s['summary'] for s in away_team.get('records', []) if s['type'] == 'total'), "0-0")
            
            # Wyniki
            h_score_str = home_team.get('score', '0')
            a_score_str = away_team.get('score', '0')
            
            # === LOGIKA PROGNOZY ===
            h_pct = parse_record(h_record_str)
            a_pct = parse_record(a_record_str)
            
            predicted_winner_abbr = ""
            predicted_winner_full = ""

            if (h_pct + 0.05) > a_pct:
                predicted_winner_abbr = h_abbr
                predicted_winner_full = h_full_name
            else:
                predicted_winner_abbr = a_abbr
                predicted_winner_full = a_full_name
            
            # === LOGIKA WYŚWIETLACZA WYNIKÓW ===
            is_final = (state == 'post')
            actual_winner_abbr = ""
            
            a_digit_class = "digit"
            h_digit_class = "digit"
            
            scoreboard_content = ""
            vs_element = ""

            if state == 'pre':
                 scoreboard_content = f'<span class="digit">---</span><span style="color:#555">:</span><span class="digit">---</span>'
                 vs_element = '<div class="vs-neon">VS</div>'
            else:
                vs_element = '<div class="vs-neon" style="font-size:1.4rem; margin-top:15px; color:#aaa; text-shadow:none;">FINAL</div>'
                if is_final:
                    if int(h_score_str) > int(a_score_str):
                        actual_winner_abbr = h_abbr
                        h_digit_class += " winner"
                        a_digit_class += " loser"
                    else:
                        actual_winner_abbr = a_abbr
                        a_digit_class += " winner"
                        h_digit_class += " loser"
                
                scoreboard_content = f"""
                    <span class="{a_digit_class}">{a_score_str}</span>
                    <span style="color:#555">:</span>
                    <span class="{h_digit_class}">{h_score_str}</span>
                """

            # === BUDOWANIE HTML KARTY ===
            status_text = status['detail']
            status_class = ""
            if state == 'in': 
                status_class = "live"
                status_text = "🔴 LIVE: " + status['shortDetail']

            result_badge = ""
            if is_final:
                if predicted_winner_abbr == actual_winner_abbr:
                    result_badge = '<div class="result-badge res-win">TRAFIONY ✅</div>'
                else:
                    result_badge = '<div class="result-badge res-loss">PUDŁO ❌</div>'

            # KARTA (ULTRA NEON LAYOUT)
            html += f"""
            <div class="card">
                <div class="status-bar {status_class}">{status_text}</div>
                
                <div class="neon-matchup">
                    <div class="team-neon-box team-left">
                        <span class="team-name">{a_abbr}</span>
                        <img src="{a_logo_url}" class="team-logo" alt="{a_abbr}">
                    </div>
                    
                    <div class="scoreboard-container">
                        <div class="digital-scoreboard">
                            <div class="score-line">
                                {scoreboard_content}
                            </div>
                        </div>
                        {vs_element}
                    </div>
                    
                    <div class="team-neon-box team-right">
                        <span class="team-name">{h_abbr}</span>
                        <img src="{h_logo_url}" class="team-logo" alt="{h_abbr}">
                    </div>
                </div>
                
                <div class="neon-prediction-panel">
                    <div class="pred-label">PROGNOZA MODELU PUBLICZNEGO</div>
                    <div class="pred-val">{predicted_winner_full}</div>
                    {result_badge}
                </div>
            </div>
            """
            count += 1
        except Exception as e:
            continue

    if count == 0:
        html += """
        <div style="grid-column: 1/-1; text-align:center; padding: 50px; background: rgba(0,0,0,0.6); border-radius: 20px; border: 2px solid #333; box-shadow: 0 0 30px rgba(0,243,255,0.2);">
            <h2 style="color: #888; text-transform: uppercase; letter-spacing: 2px; text-shadow: 0 0 10px var(--neon-cyan);">System Standby</h2>
            <p style="color: #666;">Brak zaplanowanych meczów w strumieniu danych ESPN.</p>
        </div>
        """

    html += f"""
            </div>
            <div class="footer">
                SYSTEM STATUS: ONLINE | LAST SCAN: {datetime.now().strftime("%Y-%m-%d %H:%M")} | SOURCE: ESPN API
            </div>
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ Strona wygenerowana (ULTRA-NEON PLASMA).")

if __name__ == "__main__":
    generate_html()
