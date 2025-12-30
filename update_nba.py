import requests
import json
from datetime import datetime
import os

# ==========================================
# ⚙️ KONFIGURACJA (MEDIA MODEL - FREE)
# ==========================================
# Źródło: Oficjalne publiczne API ESPN (nie wymaga klucza)
ESPN_API = "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

def get_espn_data():
    try:
        response = requests.get(ESPN_API, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Błąd połączenia z ESPN: {e}")
    return None

def generate_html():
    print("🚀 URUCHAMIAM MEDIA MODEL (ESPN DATA)...")
    
    data = get_espn_data()
    if not data or 'events' not in data:
        print("❌ Brak danych lub meczów.")
        return

    events = data['events']
    today_str = datetime.now().strftime("%Y-%m-%d")

    # NAGŁÓWEK HTML
    html = f"""
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NBA MEDIA PICKS</title>
        <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800;900&display=swap" rel="stylesheet">
        <style>
            :root {{ --bg: #09090b; --card: #18181b; --accent: #3b82f6; --text: #fff; --win: #22c55e; --loss: #ef4444; }}
            body {{ background-color: var(--bg); color: var(--text); font-family: 'Montserrat', sans-serif; margin: 0; padding: 20px; }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            
            header {{ text-align: center; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 1px solid #333; }}
            h1 {{ font-weight: 900; letter-spacing: -1px; margin: 0; color: var(--accent); }}
            .subtitle {{ color: #71717a; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 10px; }}
            
            .card {{ background: var(--card); border: 1px solid #27272a; border-radius: 12px; margin-bottom: 20px; overflow: hidden; }}
            .card-header {{ background: #27272a; padding: 15px; display: flex; justify-content: space-between; align-items: center; }}
            .status {{ font-size: 0.7rem; font-weight: bold; color: #a1a1aa; }}
            
            .matchup {{ display: flex; justify-content: space-between; align-items: center; padding: 20px; }}
            .team {{ text-align: center; width: 45%; }}
            .team-name {{ font-weight: 800; font-size: 1.2rem; display: block; }}
            .team-rec {{ font-size: 0.8rem; color: #71717a; }}
            .vs {{ color: #52525b; font-style: italic; font-weight: 900; }}
            
            .prediction {{ background: rgba(59, 130, 246, 0.1); padding: 15px; text-align: center; border-top: 1px solid #27272a; }}
            .pred-label {{ font-size: 0.7rem; color: var(--accent); text-transform: uppercase; font-weight: 700; }}
            .pred-val {{ font-size: 1.1rem; font-weight: 900; margin-top: 5px; }}
            
            .footer {{ text-align: center; color: #52525b; font-size: 0.7rem; margin-top: 40px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>NBA PUBLIC BOT</h1>
                <div class="subtitle">Źródło danych: ESPN API &bull; Model: Trend Follower</div>
            </header>
    """

    count = 0
    for event in events:
        try:
            competition = event['competitions'][0]
            competitors = competition['competitors']
            
            # Sortowanie: Away jest zwykle pierwszy w ESPN, ale sprawdzamy homeAway
            home_team = next(t for t in competitors if t['homeAway'] == 'home')
            away_team = next(t for t in competitors if t['homeAway'] == 'away')
            
            h_name = home_team['team']['displayName']
            a_name = away_team['team']['displayName']
            
            # Rekordy (Bilanse)
            h_record = next((s['summary'] for s in home_team.get('records', []) if s['type'] == 'total'), "0-0")
            a_record = next((s['summary'] for s in away_team.get('records', []) if s['type'] == 'total'), "0-0")

            # Prosta logika "Publiczna"
            # ESPN często podaje "probability" - spróbujmy to wykorzystać jeśli jest, lub zróbmy prosty model
            
            win_prob = 0.0
            fav_team = "TBD"
            
            # Spróbujmy znaleźć szansę wygranej w danych ESPN (często jest w odds)
            if 'odds' in competition and competition['odds']:
                details = competition['odds'][0].get('details', 'Brak kursów')
                fav_team = f"Ruch kursów: {details}"
            else:
                # Prosty model na bilansach
                # Parsowanie "20-10" na liczby
                def parse_rec(rec):
                    try:
                        w, l = map(int, rec.split('-'))
                        return w / (w+l) if (w+l) > 0 else 0
                    except: return 0
                
                h_pct = parse_rec(h_record)
                a_pct = parse_rec(a_record)
                
                # Dodajemy +5% za własny parkiet
                h_score = h_pct + 0.05
                a_score = a_pct
                
                if h_score > a_score:
                    fav_team = f"{h_name} (Bilans + Home Court)"
                else:
                    fav_team = f"{a_name} (Lepszy Bilans)"

            status_str = event['status']['type']['shortDetail']

            html += f"""
            <div class="card">
                <div class="card-header">
                    <span class="status">{status_str}</span>
                </div>
                <div class="matchup">
                    <div class="team">
                        <span class="team-name">{a_name}</span>
                        <span class="team-rec">{a_record}</span>
                    </div>
                    <div class="vs">@</div>
                    <div class="team">
                        <span class="team-name">{h_name}</span>
                        <span class="team-rec">{h_record}</span>
                    </div>
                </div>
                <div class="prediction">
                    <div class="pred-label">WSKAZANIE MODELU PUBLICZNEGO</div>
                    <div class="pred-val">{fav_team}</div>
                </div>
            </div>
            """
            count += 1
        except Exception as e:
            print(f"Błąd przy meczu: {e}")
            continue

    if count == 0:
        html += "<p style='text-align:center'>Brak zaplanowanych meczów na dziś.</p>"

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
    print("✅ Strona wygenerowana (ESPN Data).")

if __name__ == "__main__":
    generate_html()
