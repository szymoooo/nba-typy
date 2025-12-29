import os
import google.generativeai as genai
import json
import datetime

# Konfiguracja API
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

def get_nba_analysis():
    # Dynamiczna data
    today = datetime.date.today().strftime("%d.%m.%Y")
    
    # Wybór modelu
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    model = genai.GenerativeModel(available_models[0] if available_models else 'gemini-1.5-flash')

    prompt = f"""
    Jesteś ekspertem NBA. DZISIAJ JEST {today}. 
    Skorzystaj z wyszukiwarki i podaj listę WSZYSTKICH meczów NBA na dziś ({today}).
    Dla każdego meczu przygotuj analizę w formacie JSON.
    
    Ważne: W polu 'home_id' i 'away_id' podaj oficjalny skrót drużyny (np. LAL, BOS, GSW, NYK, PHX).
    
    Format JSON:
    [
      {{
        "home": "Lakers", "home_id": "LAL",
        "away": "Celtics", "away_id": "BOS",
        "time": "02:00",
        "star": true,
        "analysis": "Krótki opis kontuzji i formy...",
        "last_games": "LAL: W, L, W | BOS: W, W, W",
        "bet": "Powyżej 220.5 pkt - uzasadnienie"
      }}
    ]
    Zwróć TYLKO czysty JSON.
    """
    
    try:
        response = model.generate_content(prompt)
        content = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(content)
    except:
        return []

def create_page(matches):
    cards_html = ""
    for m in matches:
        star_badge = '<div class="badge">⭐ PEWNIAK DNIA</div>' if m.get('star') else ""
        # Linki do profesjonalnych logotypów ESPN
        h_logo = f"https://a.espncdn.com/i/teamlogos/nba/500/scoreboard/{m['home_id'].lower()}.png"
        a_logo = f"https://a.espncdn.com/i/teamlogos/nba/500/scoreboard/{m['away_id'].lower()}.png"
        
        cards_html += f"""
        <div class="card" onclick="openModal('{m['home']}', '{m['away']}', `{m['analysis']}`, `{m['last_games']}`, `{m['bet']}`, '{h_logo}', '{a_logo}')">
            {star_badge}
            <div class="card-teams">
                <div class="team">
                    <img src="{h_logo}" onerror="this.src='https://via.placeholder.com/60'">
                    <p>{m['home']}</p>
                </div>
                <div class="vs">VS</div>
                <div class="team">
                    <img src="{a_logo}" onerror="this.src='https://via.placeholder.com/60'">
                    <p>{m['away']}</p>
                </div>
            </div>
            <div class="card-footer">
                <span>🕒 {m['time']}</span>
                <span class="btn-more">Szczegóły →</span>
            </div>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NBA Raport Live</title>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
        <style>
            :root {{ --bg: #050811; --card: #121826; --accent: #38bdf8; --gold: #fbbf24; }}
            body {{ background: var(--bg); color: white; font-family: 'Poppins', sans-serif; margin: 0; padding: 20px; }}
            h1 {{ text-align: center; font-weight: 600; letter-spacing: 2px; color: var(--accent); }}
            .container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto; }}
            
            .card {{ background: var(--card); border-radius: 20px; padding: 20px; border: 1px solid #2d3748; cursor: pointer; transition: 0.3s; position: relative; overflow: hidden; }}
            .card:hover {{ transform: translateY(-5px); border-color: var(--accent); box-shadow: 0 10px 30px rgba(56, 189, 248, 0.2); }}
            
            .badge {{ position: absolute; top: 10px; right: 10px; background: var(--gold); color: #000; font-size: 10px; font-weight: bold; padding: 4px 8px; border-radius: 10px; }}
            
            .card-teams {{ display: flex; justify-content: space-around; align-items: center; margin-top: 15px; }}
            .team {{ text-align: center; width: 40%; }}
            .team img {{ width: 70px; height: 70px; object-fit: contain; }}
            .team p {{ font-size: 14px; margin: 8px 0; font-weight: 600; }}
            .vs {{ font-weight: bold; color: #4a5568; font-size: 12px; }}
            
            .card-footer {{ display: flex; justify-content: space-between; align-items: center; margin-top: 20px; font-size: 12px; color: #a0aec0; border-top: 1px solid #2d3748; padding-top: 10px; }}
            .btn-more {{ color: var(--accent); font-weight: bold; }}

            /* Modal */
            .modal {{ display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index: 100; align-items:center; justify-content:center; backdrop-filter: blur(5px); }}
            .modal-content {{ background: var(--card); width: 90%; max-width: 500px; padding: 30px; border-radius: 30px; border: 1px solid var(--accent); position: relative; }}
            .modal-logos {{ display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 20px; }}
            .modal-logos img {{ width: 80px; }}
            .type-box {{ background: rgba(56, 189, 248, 0.1); border: 1px dashed var(--accent); padding: 15px; border-radius: 15px; margin-top: 20px; }}
            .close-btn {{ position: absolute; top: 20px; right: 20px; cursor: pointer; font-size: 24px; }}
        </style>
    </head>
    <body>
        <h1>🏀 NBA RAPORT LIVE</h1>
        <p style="text-align:center; color: #718096; margin-bottom: 40px;">Eksperckie analizy i typy na {datetime.date.today().strftime("%d.%m.%Y")}</p>
        
        <div class="container">{cards_html}</div>

        <div id="modal" class="modal" onclick="this.style.display='none'">
            <div class="modal-content" onclick="event.stopPropagation()">
                <span class="close-btn" onclick="document.getElementById('modal').style.display='none'">&times;</span>
                <div class="modal-logos">
                    <img id="h-logo-m" src=""> <span style="font-size: 24px; font-weight: bold;">VS</span> <img id="a-logo-m" src="">
                </div>
                <h2 id="m-title" style="text-align:center; margin-bottom: 25px;"></h2>
                <div style="font-size: 14px; line-height: 1.6;">
                    <p><strong>📋 Analiza:</strong> <span id="m-analysis"></span></p>
                    <p><strong>📈 Ostatnie mecze:</strong> <span id="m-history"></span></p>
                    <div class="type-box">
                        <strong style="color: var(--accent);">🎯 SUGEROWANY TYP:</strong><br>
                        <span id="m-bet"></span>
                    </div>
                </div>
            </div>
        </div>

        <script>
            function openModal(h, a, an, hi, be, hl, al) {{
                document.getElementById('m-title').innerText = h + ' vs ' + a;
                document.getElementById('m-analysis').innerText = an;
                document.getElementById('m-history').innerText = hi;
                document.getElementById('m-bet').innerText = be;
                document.getElementById('h-logo-m').src = hl;
                document.getElementById('a-logo-m').src = al;
                document.getElementById('modal').style.display = 'flex';
            }}
        </script>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    data = get_nba_analysis()
    create_page(data)
