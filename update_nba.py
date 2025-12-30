import requests
import json
from datetime import datetime
import os

# ==========================================
# ⚙️ KONFIGURACJA (PUBLIC BOT - FINAL CLEAN)
# ==========================================
ESPN_API = "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

# Rozszerzony słownik logo (ESPN używa czasem skrótów 2-literowych)
NBA_LOGOS = {
    'ATL': 'https://cdn.nba.com/logos/nba/1610612737/global/L/logo.svg',
    'BOS': 'https://cdn.nba.com/logos/nba/1610612738/global/L/logo.svg',
    'CLE': 'https://cdn.nba.com/logos/nba/1610612739/global/L/logo.svg',
    'NOP': 'https://cdn.nba.com/logos/nba/1610612740/global/L/logo.svg',
    'NO':  'https://cdn.nba.com/logos/nba/1610612740/global/L/logo.svg', # Fix Pelicans
    'CHI': 'https://cdn.nba.com/logos/nba/1610612741/global/L/logo.svg',
    'DAL': 'https://cdn.nba.com/logos/nba/1610612742/global/L/logo.svg',
    'DEN': 'https://cdn.nba.com/logos/nba/1610612743/global/L/logo.svg',
    'GSW': 'https://cdn.nba.com/logos/nba/1610612744/global/L/logo.svg',
    'GS':  'https://cdn.nba.com/logos/nba/1610612744/global/L/logo.svg', # Fix Warriors
    'HOU': 'https://cdn.nba.com/logos/nba/1610612745/global/L/logo.svg',
    'LAC': 'https://cdn.nba.com/logos/nba/1610612746/global/L/logo.svg',
    'LAL': 'https://cdn.nba.com/logos/nba/1610612747/global/L/logo.svg',
    'MIA': 'https://cdn.nba.com/logos/nba/1610612748/global/L/logo.svg',
    'MIL': 'https://cdn.nba.com/logos/nba/1610612749/global/L/logo.svg',
    'MIN': 'https://cdn.nba.com/logos/nba/1610612750/global/L/logo.svg',
    'BKN': 'https://cdn.nba.com/logos/nba/1610612751/global/L/logo.svg',
    'NYK': 'https://cdn.nba.com/logos/nba/1610612752/global/L/logo.svg',
    'NY':  'https://cdn.nba.com/logos/nba/1610612752/global/L/logo.svg', # Fix Knicks
    'ORL': 'https://cdn.nba.com/logos/nba/1610612753/global/L/logo.svg',
    'IND': 'https://cdn.nba.com/logos/nba/1610612754/global/L/logo.svg',
    'PHI': 'https://cdn.nba.com/logos/nba/1610612755/global/L/logo.svg',
    'PHX': 'https://cdn.nba.com/logos/nba/1610612756/global/L/logo.svg',
    'POR': 'https://cdn.nba.com/logos/nba/1610612757/global/L/logo.svg',
    'SAC': 'https://cdn.nba.com/logos/nba/1610612758/global/L/logo.svg',
    'SAS': 'https://cdn.nba.com/logos/nba/1610612759/global/L/logo.svg',
    'SA':  'https://cdn.nba.com/logos/nba/1610612759/global/L/logo.svg', # Fix Spurs
    'OKC': 'https://cdn.nba.com/logos/nba/1610612760/global/L/logo.svg',
    'TOR': 'https://cdn.nba.com/logos/nba/1610612761/global/L/logo.svg',
    'UTA': 'https://cdn.nba.com/logos/nba/1610612762/global/L/logo.svg',
    'MEM': 'https://cdn.nba.com/logos/nba/1610612763/global/L/logo.svg',
    'WAS': 'https://cdn.nba.com/logos/nba/1610612764/global/L/logo.svg',
    'DET': 'https://cdn.nba.com/logos/nba/1610612765/global/L/logo.svg',
    'CHA': 'https://cdn.nba.com/logos/nba/1610612766/global/L/logo.svg',
    'WSH': 'https://cdn.nba.com/logos/nba/1610612764/global/L/logo.svg',
    'UTAH': 'https://cdn.nba.com/logos/nba/1610612762/global/L/logo.svg',
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

def get_team_logo(abbr):
    # Najpierw szukamy w słowniku po skrócie (obsługa NY, NO, GS, SA)
    if abbr in NBA_LOGOS:
        return NBA_LOGOS[abbr]
    return DEFAULT_LOGO

def generate_html():
    print("🚀 URUCHAMIAM PUBLIC BOT (FIXED LOGOS & UI)...")
    
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
        <title>NBA PUBLIC SCOREBOARD</title>
        <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏀</text></svg>">
        <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800;900&display=swap" rel="stylesheet">
        <style>
            :root {{ 
                --bg: #0f172a; 
                --card-bg: #1e293b; 
                --accent: #3b82f6; 
                --text: #f8fafc; 
                --subtext: #94a3b8;
                --win: #10b981; 
                --loss: #ef4444; 
                --border: #334155; 
            }}
            
            body {{ background-color: var(--bg); color: var(--text); font-family: 'Montserrat', sans-serif; margin: 0; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            
            header {{ text-align: center; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 1px solid var(--border); }}
            h1 {{ font-weight: 900; letter-spacing: -1px; margin: 0; color: var(--accent); font-size: 2.5rem; }}
            .subtitle {{ color: var(--subtext); font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 10px; }}
            
            /* GRID */
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
                gap: 25px;
            }}
            
            /* KARTA */
            .card {{ 
                background: var(--card-bg); 
                border: 1px solid var(--border); 
                border-radius: 20px;
                overflow: hidden; 
                display: flex; 
                flex-direction: column;
                transition: transform 0.2s, box-shadow 0.2s;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2);
            }}
            
            .card:hover {{ transform: translateY(-5px); box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.3); border-color: var(--accent); }}
            
            .card-header {{ 
                background: rgba(0,0,0,0.3); 
                padding: 12px 25px; 
                display: flex; 
                justify-content: center; 
                align-items: center; 
                border-bottom: 1px solid var(--border);
            }}
            
            .status {{ font-size: 0.75rem; font-weight: 900; color: var(--subtext); text-transform: uppercase; letter-spacing: 1px; }}
            .live {{ color: #ef4444; animation: pulse 1.5s infinite; }}
            
            /* MATCHUP */
            .matchup {{ display: flex; justify-content: space-between; align-items: center; padding: 35px 30px; }}
            
            .team {{ 
                text-align: center; 
                width: 30%; 
                display: flex; 
                flex-direction: column; 
                align-items: center; 
            }}
            
            .team-name {{ 
                font-weight: 900; 
                font-size: 1rem; 
                display: block; 
                margin-bottom: 15px; 
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            
            .team-logo {{
                width: 80px;
                height: 80px;
                object-fit: contain;
                filter: drop-shadow(0 4px 6px rgba(0,0,0,0.3));
            }}
            
            /* SCORE */
            .score-container {{
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 15px;
            }}
            
            .score {{ font-size: 2.8rem; font-weight: 900; line-height: 1; }}
            .score.winner {{ color: var(--win); text-shadow: 0 0 20px rgba(16, 185, 129, 0.4); }}
            .score.loser {{ color: var(--subtext); opacity: 0.4; }}
            
            .vs-sep {{ color: var(--border); font-style: italic; font-weight: 900; font-size: 1.5rem; }}
            
            /* PROGNOZA */
            .prediction-box {{ 
                background: rgba(15, 23, 42, 0.6);
                padding: 20px; 
                text-align: center; 
                border-top: 1px solid var(--border); 
                margin-top: auto;
            }}
            
            .pred-label {{ font-size: 0.7rem; color: var(--subtext); text-transform: uppercase; font-weight: 700; letter-spacing: 1px; margin-bottom: 8px; }}
            .pred-val {{ font-size: 1.2rem; font-weight: 900; color: var(--text); display: flex; align-items: center; justify-content: center; gap: 8px; }}
            
            /* Usunięte style badge, teraz ikona jest inline */
            
            .footer {{ text-align: center; color: var(--subtext); font-size: 0.75rem; margin-top: 50px; padding-bottom: 20px; }}
            @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} 100% {{ opacity: 1; }} }}
            @media (max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} .matchup {{ padding: 25px 15px; }} .score {{ font-size: 2.2rem; }} .team-logo {{ width: 60px; height: 60px; }} }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>NBA PUBLIC HUB</h1>
                <div class="subtitle">Live Scores & Automated Models</div>
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
            
            h_name = home_team['team']['shortDisplayName']
            a_name = away_team['team']['shortDisplayName']
            
            # Skróty dla logo
            h_abbr = home_team['team']['abbreviation']
            a_abbr = away_team['team']['abbreviation']

            # POBIERANIE LOGO Z NAPRAWIONYM SŁOWNIKIEM
            h_logo_url = get_team_logo(h_abbr)
            a_logo_url = get_team_logo(a_abbr)
            
            # Rekordy i Wyniki
            h_record_str = next((s['summary'] for s in home_team.get('records', []) if s['type'] == 'total'), "0-0")
            a_record_str = next((s['summary'] for s in away_team.get('records', []) if s['type'] == 'total'), "0-0")
            
            h_score = int(home_team.get('score', 0))
            a_score = int(away_team.get('score', 0))
            
            # === LOGIKA PROGNOZY ===
            h_pct = parse_record(h_record_str)
            a_pct = parse_record(a_record_str)
            
            predicted_winner = ""
            if (h_pct + 0.05) > a_pct:
                predicted_winner = h_name
            else:
                predicted_winner = a_name
            
            # === LOGIKA WERYFIKACJI (Inline Icon) ===
            is_final = (state == 'post')
            actual_winner = ""
            
            h_score_class = "score"
            a_score_class = "score"
            
            score_display_html = ""

            if state == 'pre':
                 score_display_html = f'<span class="vs-sep" style="font-size: 2rem;">VS</span>'
            else:
                if is_final:
                    if h_score > a_score:
                        actual_winner = h_name
                        h_score_class += " winner"
                        a_score_class += " loser"
                    else:
                        actual_winner = a_name
                        a_score_class += " winner"
                        h_score_class += " loser"
                
                score_display_html = f"""
                    <span class="{a_score_class}">{a_score}</span>
                    <span class="vs-sep">:</span>
                    <span class="{h_score_class}">{h_score}</span>
                """

            # === BUDOWANIE ELEMENTÓW HTML ===
            status_text = status['detail']
            status_class = "status"
            if state == 'in': 
                status_class += " live"
                status_text = "🔴 " + status['shortDetail']

            # TWORZENIE IKONY WYNIKU (INLINE)
            outcome_icon = ""
            if is_final:
                if predicted_winner == actual_winner:
                    outcome_icon = '<span style="color: #10b981; margin-left: 8px;">✅</span>' # Zielony ptaszek
                else:
                    outcome_icon = '<span style="color: #ef4444; margin-left: 8px;">❌</span>' # Czerwony krzyżyk
            
            # Łączymy nazwę z ikoną w jednej linii
            prediction_content = f'{predicted_winner}{outcome_icon}'

            # KARTA
            html += f"""
            <div class="card">
                <div class="card-header">
                    <span class="{status_class}">{status_text}</span>
                </div>
                
                <div class="matchup">
                    <div class="team">
                        <span class="team-name">{a_name}</span>
                        <img src="{a_logo_url}" class="team-logo" alt="{a_name}">
                    </div>
                    
                    <div class="score-container">
                        {score_display_html}
                    </div>
                    
                    <div class="team">
                        <span class="team-name">{h_name}</span>
                        <img src="{h_logo_url}" class="team-logo" alt="{h_name}">
                    </div>
                </div>
                
                <div class="prediction-box">
                    <div class="pred-label">Prognoza Modelu Publicznego</div>
                    <div class="pred-val">{prediction_content}</div>
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
                Automatyczna aktualizacja: {datetime.now().strftime("%Y-%m-%d %H:%M")} | Data Source: ESPN
            </div>
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ Strona wygenerowana (LOGO FIX + INLINE RESULTS).")

if __name__ == "__main__":
    generate_html()
