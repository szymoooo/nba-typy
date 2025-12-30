import requests
import json
from datetime import datetime
import os

# ==========================================
# ⚙️ KONFIGURACJA (CYBERPUNK NEON EDITION)
# ==========================================
ESPN_API = "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

# Słownik mapujący skróty nazw drużyn na oficjalne logotypy NBA (CDN)
NBA_LOGOS = {
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

def generate_html():
    print("🚀 URUCHAMIAM PUBLIC BOT (CYBERPUNK STYLE)...")
    
    data = get_espn_data()
    if not data or 'events' not in data:
        print("❌ Brak danych.")
        return

    events = data['events']
    
    # --- NAGŁÓWEK HTML (Nowe style CSS) ---
    html = f"""
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NBA NEON HUB</title>
        <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏀</text></svg>">
        <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet">
        <style>
            :root {{ 
                --bg: #050505;
                --card-dark: #0a0a0f;
                --neon-blue: #00f3ff;
                --neon-purple: #bd00ff;
                --neon-green: #00ff9f;
                --text: #ffffff;
                --win: #10b981; 
                --loss: #ef4444; 
            }}
            
            body {{ 
                background-color: var(--bg); 
                background-image: radial-gradient(circle at 50% 50%, #111 0%, #000 100%);
                color: var(--text); 
                font-family: 'Orbitron', sans-serif; /* Główna czcionka neonowa */
                margin: 0; 
                padding: 30px 20px;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            
            header {{ text-align: center; margin-bottom: 50px; }}
            h1 {{ 
                font-weight: 900; letter-spacing: 2px; margin: 0; font-size: 2.5rem; text-transform: uppercase;
                color: var(--text);
                text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue);
            }}
            .subtitle {{ color: #888; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 15px; font-family: sans-serif; }}
            
            /* GRID */
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
                gap: 40px;
            }}
            
            /* CYBERPUNK CARD */
            .card {{ 
                background: var(--card-dark);
                border-radius: 15px;
                position: relative;
                overflow: hidden;
                /* Efekt głównej ramki neonowej */
                box-shadow: 
                    0 0 5px rgba(0, 243, 255, 0.2),
                    0 0 15px rgba(189, 0, 255, 0.2),
                    inset 0 0 20px rgba(0,0,0,0.8);
                border: 2px solid #222;
                display: flex;
                flex-direction: column;
            }}

            /* Pasek statusu na górze */
            .status-bar {{
                text-align: center;
                padding: 8px;
                font-size: 0.7rem;
                letter-spacing: 1px;
                background: rgba(0,0,0,0.5);
                color: #aaa;
                border-bottom: 1px solid #222;
            }}
            .live {{ color: var(--loss); text-shadow: 0 0 10px var(--loss); }}

            /* GŁÓWNA SEKCJA MECZU */
            .neon-matchup {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 30px 20px;
                position: relative;
            }}

            /* Zespoły - kontenery z kolorowym blaskiem */
            .team-neon-box {{
                text-align: center;
                width: 30%;
                padding: 15px;
                border-radius: 10px;
                background: rgba(255,255,255,0.03);
            }}

            /* Lewa strona - Niebieski Neon */
            .team-left {{
                border: 1px solid var(--neon-blue);
                box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.3);
            }}
            .team-left .team-name {{ color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); }}

            /* Prawa strona - Fioletowy Neon */
            .team-right {{
                border: 1px solid var(--neon-purple);
                box-shadow: inset 0 0 15px rgba(189, 0, 255, 0.3);
            }}
            .team-right .team-name {{ color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple); }}

            .team-name {{ 
                font-weight: 900; font-size: 1.2rem; display: block; margin-bottom: 15px; text-transform: uppercase; 
            }}
            
            .team-logo {{
                width: 90px; height: 90px; object-fit: contain;
                filter: drop-shadow(0 0 10px rgba(255,255,255,0.3));
            }}

            /* ŚRODEK - CYFROWY WYNIK */
            .digital-scoreboard {{
                font-family: 'Share Tech Mono', monospace; /* Czcionka cyfrowa */
                background: #000;
                padding: 15px 25px;
                border-radius: 8px;
                border: 2px solid #333;
                box-shadow: inset 0 0 20px rgba(0,0,0,0.8);
                text-align: center;
                position: relative;
            }}
            /* Efekt skanowania/siatki na ekranie */
            .digital-scoreboard::after {{
                content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
                background: repeating-linear-gradient(0deg, rgba(0,0,0,0.2) 0px, rgba(0,0,0,0.2) 2px, transparent 2px, transparent 4px);
                pointer-events: none;
            }}

            .score-line {{ font-size: 3rem; font-weight: 400; letter-spacing: 2px; display: flex; gap: 10px; justify-content: center; }}
            .digit {{ color: #fff; text-shadow: 0 0 15px #fff; }}
            .digit-sep {{ color: #555; animation: blink 1s infinite; }}
            .digit.winner {{ color: var(--neon-green); text-shadow: 0 0 20px var(--neon-green); }}
            .digit.loser {{ color: #555; text-shadow: none; }}

            /* DOLNY PANEL PROGNOZY */
            .neon-prediction-panel {{ 
                background: rgba(0,0,0,0.4);
                padding: 20px; 
                text-align: center; 
                border-top: 2px solid #222;
                position: relative;
                margin-top: auto;
            }}
            /* Zielony akcent na dole */
            .neon-prediction-panel::before {{
                content: ''; position: absolute; bottom: 0; left: 20%; right: 20%; height: 2px;
                background: var(--neon-green);
                box-shadow: 0 0 20px var(--neon-green), 0 0 40px var(--neon-green);
            }}
            
            .pred-label {{ font-size: 0.7rem; color: #888; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 10px; }}
            .pred-val {{ font-size: 1.3rem; font-weight: 900; color: var(--text); text-transform: uppercase; letter-spacing: 1px; text-shadow: 0 0 10px rgba(255,255,255,0.5); }}
            
            .result-badge {{
                display: inline-block; padding: 6px 16px; border-radius: 4px;
                font-size: 0.8rem; font-weight: 800; margin-top: 12px; text-transform: uppercase; letter-spacing: 1px;
                box-shadow: 0 0 15px currentColor;
            }}
            .res-win {{ color: var(--bg); background: var(--neon-green); }}
            .res-loss {{ color: var(--bg); background: var(--loss); }}
            
            .footer {{ text-align: center; color: #555; font-size: 0.75rem; margin-top: 60px; padding-bottom: 20px; font-family: sans-serif; }}
            @keyframes blink {{ 50% {{ opacity: 0; }} }}
            @media (max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} .neon-matchup {{ flex-direction: column; gap: 20px; }} .team-neon-box {{ width: 80%; }} .score-line {{ font-size: 2.5rem; }} }}
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
            
            # Nazwy dla wyświetlacza (krótkie, np. LAL)
            h_abbr = home_team['team']['abbreviation']
            a_abbr = away_team['team']['abbreviation']
            # Pełne nazwy dla prognozy
            h_full_name = home_team['team']['shortDisplayName']
            a_full_name = away_team['team']['shortDisplayName']

            # Loga
            h_logo_url = NBA_LOGOS.get(h_abbr, 'https://cdn.nba.com/logos/nba/nba-logoman-70x70.svg')
            a_logo_url = NBA_LOGOS.get(a_abbr, 'https://cdn.nba.com/logos/nba/nba-logoman-70x70.svg')
            
            # Rekordy do modelu
            h_record_str = next((s['summary'] for s in home_team.get('records', []) if s['type'] == 'total'), "0-0")
            a_record_str = next((s['summary'] for s in away_team.get('records', []) if s['type'] == 'total'), "0-0")
            
            # Wyniki (stringi do wyświetlacza)
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

            if state == 'pre':
                 scoreboard_content = f'<span class="digit">---</span><span class="digit-sep">:</span><span class="digit">---</span>'
            else:
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
                    <span class="digit-sep">:</span>
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

            # KARTA (CYBERPUNK LAYOUT)
            html += f"""
            <div class="card">
                <div class="status-bar {status_class}">{status_text}</div>
                
                <div class="neon-matchup">
                    <div class="team-neon-box team-left">
                        <span class="team-name">{a_abbr}</span>
                        <img src="{a_logo_url}" class="team-logo" alt="{a_abbr}">
                    </div>
                    
                    <div class="digital-scoreboard">
                        <div class="score-line">
                            {scoreboard_content}
                        </div>
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
            # print(f"Błąd: {e}")
            continue

    if count == 0:
        html += "<p style='text-align:center; color:#888;'>Brak meczów w harmonogramie ESPN.</p>"

    html += f"""
            </div>
            <div class="footer">
                SYSTEM STATUS: ONLINE | LAST UPDATE: {datetime.now().strftime("%Y-%m-%d %H:%M")} | SOURCE: ESPN API
            </div>
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ Strona wygenerowana (CYBERPUNK NEON STYLE).")

if __name__ == "__main__":
    generate_html()
