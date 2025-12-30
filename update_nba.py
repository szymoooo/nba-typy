import requests
import json
from datetime import datetime
import os

# ==========================================
# ⚙️ KONFIGURACJA (ULTIMATE NEON CYBERPUNK)
# ==========================================
ESPN_API = "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

# Zapasowy słownik logo (używany tylko gdy ESPN nie poda swojego)
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
    'NOP': 'https://cdn.nba.com/logos/nba/1610612740/global/L/logo.svg', # Dodatkowe dla New Orleans
    'NO': 'https://cdn.nba.com/logos/nba/1610612740/global/L/logo.svg',
    'UTAH': 'https://cdn.nba.com/logos/nba/1610612762/global/L/logo.svg', # Dodatkowe dla Utah
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

# Funkcja pomocnicza do pobierania logo
def get_team_logo(team_data):
    # 1. Próba pobrania z danych ESPN
    if 'logo' in team_data:
        return team_data['logo']
    # 2. Próba pobrania ze słownika fallback na podstawie skrótu
    abbr = team_data.get('abbreviation')
    if abbr in NBA_LOGOS_FALLBACK:
        return NBA_LOGOS_FALLBACK[abbr]
    # 3. Ostateczność
    return DEFAULT_LOGO

def generate_html():
    print("🚀 URUCHAMIAM CYBERPUNK ENGINE (FIXED LOGOS)...")
    
    data = get_espn_data()
    if not data or 'events' not in data:
        print("❌ Brak danych.")
        return

    events = data['events']
    
    # --- NAGŁÓWEK HTML ---
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
                --bg: #020205;
                --card-dark: #0a0a12;
                --neon-blue: #00f3ff;
                --neon-purple: #d400ff;
                --neon-green: #00ff9f;
                --text: #ffffff;
                --loss: #ff2a6d; 
            }}
            
            body {{ 
                background-color: var(--bg); 
                /* Tło jak płyta główna */
                background-image: 
                    linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
                background-size: 20px 20px;
                color: var(--text); 
                font-family: 'Orbitron', sans-serif;
                margin: 0; 
                padding: 30px 20px;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            
            header {{ text-align: center; margin-bottom: 60px; position: relative; }}
            h1 {{ 
                font-weight: 900; letter-spacing: 3px; margin: 0; font-size: 2.8rem; text-transform: uppercase;
                color: var(--neon-blue);
                text-shadow: 0 0 15px var(--neon-blue), 0 0 30px var(--neon-blue);
                display: inline-block;
                padding: 10px 30px;
                border: 2px solid var(--neon-blue);
                border-radius: 50px;
                box-shadow: inset 0 0 20px var(--neon-blue), 0 0 20px var(--neon-blue);
            }}
            .subtitle {{ color: #888; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 2px; margin-top: 25px; font-family: sans-serif; }}
            
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(550px, 1fr));
                gap: 50px;
            }}
            
            /* --- CYBERPUNK CARD DESIGN --- */
            .card {{ 
                background: var(--card-dark);
                border-radius: 20px;
                position: relative;
                overflow: hidden;
                box-shadow: 0 0 30px rgba(0,0,0,0.5);
                display: flex;
                flex-direction: column;
                border: 1px solid #1a1a2e;
            }}

            /* Efekt "tłoczenia" i linii na karcie */
            .card::before {{
                content: ''; position: absolute; top: 0; left: 0; right: 0; height: 100%;
                background: 
                    linear-gradient(90deg, transparent 49%, rgba(0, 243, 255, 0.03) 50%, transparent 51%),
                    linear-gradient(transparent 49%, rgba(212, 0, 255, 0.03) 50%, transparent 51%);
                background-size: 30px 30px;
                pointer-events: none;
            }}

            .status-bar {{
                text-align: center; padding: 10px; font-size: 0.75rem; letter-spacing: 2px;
                background: rgba(0,0,0,0.6); color: #aaa; border-bottom: 1px solid #222;
                font-weight: 700;
            }}
            .live {{ color: var(--loss); text-shadow: 0 0 15px var(--loss); }}

            .neon-matchup {{
                display: flex; justify-content: space-between; align-items: center;
                padding: 40px 30px; position: relative;
            }}

            /* KONTENERY ZESPOŁÓW */
            .team-neon-box {{
                text-align: center; width: 28%; padding: 20px 15px; border-radius: 15px;
                background: rgba(0,0,0,0.4);
                display: flex; flex-direction: column; align-items: center;
            }}

            /* Lewa (Goście) - Niebieski */
            .team-left {{
                border: 2px solid var(--neon-blue);
                box-shadow: inset 0 0 25px rgba(0, 243, 255, 0.2), 0 0 15px rgba(0, 243, 255, 0.1);
            }}
            .team-left .team-name {{ color: var(--neon-blue); text-shadow: 0 0 15px var(--neon-blue); }}

            /* Prawa (Gospodarze) - Fioletowy */
            .team-right {{
                border: 2px solid var(--neon-purple);
                box-shadow: inset 0 0 25px rgba(212, 0, 255, 0.2), 0 0 15px rgba(212, 0, 255, 0.1);
            }}
            .team-right .team-name {{ color: var(--neon-purple); text-shadow: 0 0 15px var(--neon-purple); }}

            .team-name {{ 
                font-weight: 900; font-size: 1.4rem; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 1px;
            }}
            .team-logo {{
                width: 100px; height: 100px; object-fit: contain;
                filter: drop-shadow(0 0 15px rgba(255,255,255,0.2));
            }}

            /* ŚRODEK - WYNIK */
            .scoreboard-container {{
                display: flex; flex-direction: column; align-items: center; justify-content: center;
            }}
            
            .digital-scoreboard {{
                font-family: 'Share Tech Mono', monospace;
                background: #000; padding: 15px 30px; border-radius: 10px;
                border: 3px solid #333;
                box-shadow: inset 0 0 30px rgba(0,0,0,0.9), 0 0 20px rgba(0,243,255,0.1);
                text-align: center; position: relative;
            }}
            .score-line {{ font-size: 3.5rem; font-weight: 400; letter-spacing: 3px; display: flex; gap: 15px; justify-content: center; }}
            .digit {{ color: #fff; text-shadow: 0 0 20px #fff; }}
            .digit.winner {{ color: var(--neon-green); text-shadow: 0 0 25px var(--neon-green); }}
            .digit.loser {{ color: #666; text-shadow: none; opacity: 0.7; }}
            
            .vs-neon {{
                font-size: 1.8rem; font-weight: 900; color: #fff; margin-top: 20px;
                text-shadow: 0 0 10px #fff, 0 0 20px var(--neon-blue), 0 0 30px var(--neon-purple);
            }}

            /* DOLNY PANEL */
            .neon-prediction-panel {{ 
                background: rgba(0,0,0,0.5); padding: 25px; text-align: center; 
                border-top: 2px solid #222; position: relative; margin-top: auto;
            }}
            .neon-prediction-panel::before {{
                content: ''; position: absolute; bottom: 0; left: 30%; right: 30%; height: 3px;
                background: var(--neon-green);
                box-shadow: 0 0 25px var(--neon-green), 0 0 50px var(--neon-green);
            }}
            
            .pred-label {{ font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 12px; }}
            .pred-val {{ font-size: 1.5rem; font-weight: 900; color: var(--text); text-transform: uppercase; letter-spacing: 1px; text-shadow: 0 0 15px rgba(255,255,255,0.4); }}
            
            .result-badge {{
                display: inline-block; padding: 8px 20px; border-radius: 50px;
                font-size: 0.9rem; font-weight: 800; margin-top: 15px; text-transform: uppercase; letter-spacing: 1px;
            }}
            .res-win {{ color: #000; background: var(--neon-green); box-shadow: 0 0 20px var(--neon-green); }}
            .res-loss {{ color: #fff; background: var(--loss); box-shadow: 0 0 20px var(--loss); }}
            
            .footer {{ text-align: center; color: #555; font-size: 0.75rem; margin-top: 80px; padding-bottom: 30px; font-family: sans-serif; letter-spacing: 1px; }}
            
            @media (max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} .neon-matchup {{ flex-direction: column; gap: 30px; }} .team-neon-box {{ width: 80%; }} .score-line {{ font-size: 3rem; }} }}
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
            
            # Nazwy
            h_abbr = home_team['team']['abbreviation']
            a_abbr = away_team['team']['abbreviation']
            h_full_name = home_team['team']['shortDisplayName']
            a_full_name = away_team['team']['shortDisplayName']

            # LOGA - Nowa logika pobierania
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
                vs_element = '<div class="vs-neon" style="font-size:1.2rem; margin-top:10px;">FINAL</div>'
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

            # KARTA (ULTIMATE CYBERPUNK LAYOUT)
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
        <div style="grid-column: 1/-1; text-align:center; padding: 50px; background: rgba(0,0,0,0.5); border-radius: 20px; border: 1px solid #333;">
            <h2 style="color: #888; text-transform: uppercase; letter-spacing: 2px;">System Standby</h2>
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
    print("✅ Strona wygenerowana (ULTIMATE NEON FIX).")

if __name__ == "__main__":
    generate_html()
