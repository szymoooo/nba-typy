import requests
import json
from datetime import datetime, timedelta
import os

# ==========================================
# ⚙️ KONFIGURACJA (MEDIA MODEL - FREE)
# ==========================================
# Używamy dynamicznego endpointu scoreboard, który sam ogarnia "dzisiaj"
ESPN_API = "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

def get_espn_data():
    try:
        # Pobieramy dane bez filtrów daty - ESPN domyślnie zwraca najciekawsze/bieżące
        response = requests.get(ESPN_API, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Błąd połączenia z ESPN: {e}")
    return None

def generate_html():
    print("🚀 URUCHAMIAM MEDIA MODEL (SMART SCORES)...")
    
    data = get_espn_data()
    if not data or 'events' not in data:
        print("❌ Brak danych lub meczów.")
        return

    events = data['events']
    
    # 1. GENEROWANIE HTML
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
            :root {{ --bg: #09090b; --card: #18181b; --accent: #3b82f6; --text: #fff; --win: #22c55e; --loss: #ef4444; --border: #27272a; }}
            body {{ background-color: var(--bg); color: var(--text); font-family: 'Montserrat', sans-serif; margin: 0; padding: 20px; }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            
            header {{ text-align: center; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 1px solid #333; }}
            h1 {{ font-weight: 900; letter-spacing: -1px; margin: 0; color: var(--accent); }}
            .subtitle {{ color: #71717a; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 10px; }}
            
            .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; margin-bottom: 20px; overflow: hidden; display: flex; flex-direction: column; }}
            
            .card-header {{ background: #27272a; padding: 10px 15px; display: flex; justify-content: space-between; align-items: center; }}
            .status {{ font-size: 0.7rem; font-weight: bold; color: #a1a1aa; text-transform: uppercase; }}
            .live {{ color: #ef4444; animation: pulse 2s infinite; }}
            
            .matchup {{ display: flex; justify-content: space-between; align-items: center; padding: 20px; flex-grow: 1; }}
            .team {{ text-align: center; width: 45%; display: flex; flex-direction: column; align-items: center; }}
            .team-name {{ font-weight: 800; font-size: 1.1rem; display: block; margin-bottom: 5px; }}
            .team-rec {{ font-size: 0.75rem; color: #71717a; }}
            .score {{ font-size: 1.8rem; font-weight: 900; margin-top: 5px; }}
            .score.winner {{ color: var(--win); }}
            .score.loser {{ color: #71717a; opacity: 0.6; }}
            
            .vs {{ color: #52525b; font-style: italic; font-weight: 900; font-size: 0.9rem; }}
            
            .prediction {{ background: rgba(59, 130, 246, 0.1); padding: 15px; text-align: center; border-top: 1px solid var(--border); }}
            .pred-label {{ font-size: 0.65rem; color: var(--accent); text-transform: uppercase; font-weight: 700; letter-spacing: 1px; }}
            .pred-val {{ font-size: 1rem; font-weight: 900; margin-top: 5px; }}
            
            .footer {{ text-align: center; color: #52525b; font-size: 0.7rem; margin-top: 40px; }}
            
            @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} 100% {{ opacity: 1; }} }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>NBA PUBLIC HUB</h1>
                <div class="subtitle">Dane: ESPN API &bull; Live Scores & Predictions</div>
            </header>
    """

    count = 0
    for event in events:
        try:
            competition = event['competitions'][0]
            competitors = competition['competitors']
            status = event['status']['type']
            state = status['state'] # 'pre', 'in', 'post'
            
            # Sortowanie: Home vs Away
            home_team = next(t for t in competitors if t['homeAway'] == 'home')
            away_team = next(t for t in competitors if t['homeAway'] == 'away')
            
            h_name = home_team['team']['shortDisplayName']
            a_name = away_team['team']['shortDisplayName']
            
            # Wyniki (Score)
            h_score = int(home_team.get('score', 0))
            a_score = int(away_team.get('score', 0))
            
            # Rekordy
            h_record = next((s['summary'] for s in home_team.get('records', []) if s['type'] == 'total'), "")
            a_record = next((s['summary'] for s in away_team.get('records', []) if s['type'] == 'total'), "")

            # LOGIKA WYŚWIETLANIA (SCORE vs PREDICTION)
            
            # Czy mecz się skończył?
            is_final = (state == 'post')
            status_text = status['detail']
            status_class = "status"
            if state == 'in': 
                status_class += " live"
                status_text = "🔴 LIVE " + status['shortDetail']

            # Kolorowanie wyników
            h_score_class = "score"
            a_score_class = "score"
            
            if is_final:
                if h_score > a_score: h_score_class += " winner"; a_score_class += " loser"
                else: a_score_class += " winner"; h_score_class += " loser"

            # Sekcja Dolna: Wynik (jeśli koniec) lub Prognoza (jeśli przed)
            bottom_section = ""
            
            if is_final:
                # Jeśli koniec -> brak prognozy, tylko czysta karta wyniku
                pass 
            else:
                # Jeśli przed meczem -> Generujemy prognozę
                # Prosta logika na bilansach
                def parse_rec(rec):
                    try:
                        w, l = map(int, rec.split('-'))
                        return w / (w+l) if (w+l) > 0 else 0
                    except: return 0
                
                h_pct = parse_rec(h_record)
                a_pct = parse_rec(a_record)
                
                # +5% za własny parkiet
                if (h_pct + 0.05) > a_pct:
                    fav = f"{h_name} (Home Court)"
                else:
                    fav = f"{a_name} (Better Record)"
                
                bottom_section = f"""
                <div class="prediction">
                    <div class="pred-label">WSKAZANIE MODELU PUBLICZNEGO</div>
                    <div class="pred-val">{fav}</div>
                </div>
                """

            # BUDOWA KARTY
            html += f"""
            <div class="card">
                <div class="card-header">
                    <span class="{status_class}">{status_text}</span>
                </div>
                <div class="matchup">
                    <div class="team">
                        <span class="team-name">{a_name}</span>
                        <span class="team-rec">{a_record}</span>
                        {f'<div class="{a_score_class}">{a_score}</div>' if (state != 'pre') else ''}
                    </div>
                    <div class="vs">@</div>
                    <div class="team">
                        <span class="team-name">{h_name}</span>
                        <span class="team-rec">{h_record}</span>
                        {f'<div class="{h_score_class}">{h_score}</div>' if (state != 'pre') else ''}
                    </div>
                </div>
                {bottom_section}
            </div>
            """
            count += 1
        except Exception as e:
            continue

    if count == 0:
        html += "<p style='text-align:center'>Brak danych z ESPN.</p>"

    html += f"""
            <div class="footer">
                Automatyczna aktualizacja: {datetime.now().strftime("%Y-%m-%d %H:%M")}
            </div>
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ Strona wygenerowana (WYNIKI + PROGNOZY).")

if __name__ == "__main__":
    generate_html()
