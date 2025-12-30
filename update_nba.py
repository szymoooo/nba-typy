import requests
import json
from datetime import datetime
import os

# ==========================================
# ⚙️ KONFIGURACJA (PUBLIC BOT)
# ==========================================
ESPN_API = "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

def get_espn_data():
    try:
        response = requests.get(ESPN_API, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Błąd połączenia z ESPN: {e}")
    return None

def parse_record(record_str):
    """Zamienia string '20-10' na procent zwycięstw."""
    try:
        w, l = map(int, record_str.split('-'))
        total = w + l
        if total == 0: return 0.0
        return w / total
    except:
        return 0.0

def generate_html():
    print("🚀 URUCHAMIAM PUBLIC BOT (GRID LAYOUT + WERYFIKACJA)...")
    
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
        <title>NBA PUBLIC HUB</title>
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
            
            /* UKŁAD GRID - 2 KOLUMNY */
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 20px;
            }}
            
            /* KARTA MECZU */
            .card {{ 
                background: var(--card-bg); 
                border: 1px solid var(--border); 
                border-radius: 16px; 
                overflow: hidden; 
                display: flex; 
                flex-direction: column;
                transition: transform 0.2s;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }}
            
            .card:hover {{ transform: translateY(-3px); border-color: var(--accent); }}
            
            .card-header {{ 
                background: rgba(0,0,0,0.2); 
                padding: 10px 20px; 
                display: flex; 
                justify-content: space-between; 
                align-items: center; 
                border-bottom: 1px solid var(--border);
            }}
            
            .status {{ font-size: 0.7rem; font-weight: 800; color: var(--subtext); text-transform: uppercase; letter-spacing: 0.5px; }}
            .live {{ color: #ef4444; animation: pulse 1.5s infinite; }}
            
            .matchup {{ display: flex; justify-content: space-between; align-items: center; padding: 25px 20px; }}
            .team {{ text-align: center; width: 40%; display: flex; flex-direction: column; align-items: center; }}
            .team-name {{ font-weight: 800; font-size: 1.1rem; display: block; margin-bottom: 4px; }}
            .team-rec {{ font-size: 0.75rem; color: var(--subtext); font-family: monospace; }}
            
            .score {{ font-size: 2rem; font-weight: 900; margin-top: 8px; }}
            .score.winner {{ color: var(--win); text-shadow: 0 0 10px rgba(16, 185, 129, 0.2); }}
            .score.loser {{ color: var(--subtext); opacity: 0.5; }}
            
            .vs {{ color: var(--border); font-style: italic; font-weight: 900; font-size: 1.2rem; }}
            
            /* SEKCJA PROGNOZY */
            .prediction-box {{ 
                background: rgba(0,0,0,0.3); 
                padding: 15px; 
                text-align: center; 
                border-top: 1px solid var(--border); 
                margin-top: auto;
            }}
            
            .pred-label {{ font-size: 0.65rem; color: var(--subtext); text-transform: uppercase; font-weight: 700; letter-spacing: 1px; }}
            .pred-val {{ font-size: 1rem; font-weight: 900; margin-top: 5px; color: var(--accent); }}
            
            /* WERYFIKACJA (WIN/LOSS) */
            .result-badge {{
                display: inline-block;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.75rem;
                font-weight: 800;
                margin-top: 8px;
            }}
            .res-win {{ background: rgba(16, 185, 129, 0.15); color: var(--win); border: 1px solid var(--win); }}
            .res-loss {{ background: rgba(239, 68, 68, 0.15); color: var(--loss); border: 1px solid var(--loss); }}
            
            .footer {{ text-align: center; color: var(--subtext); font-size: 0.75rem; margin-top: 50px; padding-bottom: 20px; }}
            
            @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} 100% {{ opacity: 1; }} }}
            @media (max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>NBA PUBLIC HUB</h1>
                <div class="subtitle">Live Scores & Automated Trend Predictions</div>
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
            
            # Rekordy i Wyniki
            h_record_str = next((s['summary'] for s in home_team.get('records', []) if s['type'] == 'total'), "0-0")
            a_record_str = next((s['summary'] for s in away_team.get('records', []) if s['type'] == 'total'), "0-0")
            
            h_score = int(home_team.get('score', 0))
            a_score = int(away_team.get('score', 0))
            
            # === LOGIKA PROGNOZY (TREND FOLLOWER) ===
            h_pct = parse_record(h_record_str)
            a_pct = parse_record(a_record_str)
            
            # Model: Home Court (+5%) + Win Percentage
            predicted_winner = ""
            if (h_pct + 0.05) > a_pct:
                predicted_winner = h_name
                prediction_reason = "Bilans + Własny Parkiet"
            else:
                predicted_winner = a_name
                prediction_reason = "Lepszy Bilans"
            
            # === LOGIKA WERYFIKACJI ===
            is_final = (state == 'post')
            actual_winner = ""
            
            h_score_class = "score"
            a_score_class = "score"
            
            if is_final:
                if h_score > a_score:
                    actual_winner = h_name
                    h_score_class += " winner"
                    a_score_class += " loser"
                else:
                    actual_winner = a_name
                    a_score_class += " winner"
                    h_score_class += " loser"

            # === BUDOWANIE ELEMENTÓW HTML ===
            
            # Status meczu
            status_text = status['detail']
            status_class = "status"
            if state == 'in': 
                status_class += " live"
                status_text = "🔴 " + status['shortDetail']

            # Pudełko z prognozą (zawsze widoczne, nawet po meczu)
            prediction_html = f'<div class="pred-val">{predicted_winner}</div>'
            
            # Jeśli mecz zakończony -> pokaż czy trafiony
            result_badge = ""
            if is_final:
                if predicted_winner == actual_winner:
                    result_badge = '<div class="result-badge res-win">TRAFIONY ✅</div>'
                else:
                    result_badge = '<div class="result-badge res-loss">PUDŁO ❌</div>'
            else:
                # Jeśli mecz trwa lub przed -> pokaż powód
                result_badge = f'<div style="font-size:0.7rem; color:#666; margin-top:4px;">({prediction_reason})</div>'

            # KARTA
            html += f"""
            <div class="card">
                <div class="card-header">
                    <span class="{status_class}">{status_text}</span>
                </div>
                
                <div class="matchup">
                    <div class="team">
                        <span class="team-name">{a_name}</span>
                        <span class="team-rec">{a_record_str}</span>
                        {f'<div class="{a_score_class}">{a_score}</div>' if state != 'pre' else ''}
                    </div>
                    <div class="vs">@</div>
                    <div class="team">
                        <span class="team-name">{h_name}</span>
                        <span class="team-rec">{h_record_str}</span>
                        {f'<div class="{h_score_class}">{h_score}</div>' if state != 'pre' else ''}
                    </div>
                </div>
                
                <div class="prediction-box">
                    <div class="pred-label">Prognoza Modelu Publicznego</div>
                    {prediction_html}
                    {result_badge}
                </div>
            </div>
            """
            count += 1
        except Exception as e:
            continue

    if count == 0:
        html += "<p style='text-align:center; color:#888;'>Brak meczów w harmonogramie ESPN.</p>"

    html += f"""
            </div>
            <div class="footer">
                Automatyczna aktualizacja: {datetime.now().strftime("%Y-%m-%d %H:%M")}
            </div>
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ Strona wygenerowana (GRID + WERYFIKACJA).")

if __name__ == "__main__":
    generate_html()
