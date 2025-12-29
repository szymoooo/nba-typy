import os
import google.generativeai as genai
import json
import datetime

# --- KONFIGURACJA API ---
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

def get_nba_analysis():
    # Pobieramy czas serwera i korygujemy na polski (UTC+1)
    now_pl = datetime.datetime.now() + datetime.timedelta(hours=1)
    today_str = now_pl.strftime("%d.%m.%Y")
    
    # Wybór modelu
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        model_name = available_models[0] if available_models else 'gemini-1.5-flash'
        model = genai.GenerativeModel(model_name)
    except:
        model = genai.GenerativeModel('gemini-1.5-flash')

    # Prompt z wymogiem JSON i wyszukiwania
    prompt = f"""
    Jesteś ekspertem NBA. DZISIAJ JEST {today_str}. 
    Skorzystaj z wyszukiwarki i podaj listę WSZYSTKICH meczów NBA na dziś ({today_str}).
    Jeśli mecze z nocy już się odbyły, podaj ich wyniki. Jeśli dopiero będą, podaj analizę.
    
    W polu 'home_id' i 'away_id' podaj oficjalny skrót drużyny (np. LAL, BOS, GSW, NYK, PHX, DEN, LAC, MIL, PHI, MIA).
    
    Format JSON:
    [
      {{
        "home": "Nuggets", "home_id": "DEN",
        "away": "Suns", "away_id": "PHX",
        "time": "22:00",
        "star": true,
        "analysis": "Krótki, merytoryczny opis sytuacji kadrowej i formy obu drużyn.",
        "last_games": "W, L, W | W, W, L",
        "bet": "Nikola Jokic Over 26.5 pkt + asysty. Uzasadnienie: Twoja krótka analiza dlaczego to dobry typ."
      }}
    ]
    WAŻNE: W polu 'bet' nie wpisuj słowa 'TYP:', zacznij od razu od treści. 
    Zwróć TYLKO czysty JSON bez żadnych znaczników markdown.
    """
    
    try:
        response = model.generate_content(prompt)
        # Czyszczenie odpowiedzi z ewentualnych znaczników markdown
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"Błąd pobierania danych: {e}")
        return []

def create_page(matches):
    # Logika czasu dla paska statusu
    now_pl = datetime.datetime.now() + datetime.timedelta(hours=1)
    last_update = now_pl.strftime("%H:%M")
    date_display = now_pl.strftime("%d.%m.%Y")
    
    current_hour = now_pl.hour
    if current_hour < 7: next_up = "07:00"
    elif current_hour < 15: next_up = "15:10"
    elif current_hour < 19: next_up = "19:30"
    elif current_hour < 23: next_up = "23:00"
    else: next_up = "Jutro 07:00"

    cards_html = ""
    for m in matches:
        is_star = m.get('star', False)
        star_class = "star-card" if is_star else ""
        star_badge = '<div class="badge">🔥 PEWNIAK DNIA</div>' if is_star else ""
        
        # Loga z ESPN z fallbackiem na NBA.com
        h_id = m.get('home_id', 'NBA').lower()
        a_id = m.get('away_id', 'NBA').lower()
        h_logo = f"https://a.espncdn.com/i/teamlogos/nba/500/scoreboard/{h_id}.png"
        a_logo = f"https://a.espncdn.com/i/teamlogos/nba/500/scoreboard/{a_id}.png"
        
        cards_html += f"""
        <div class="card {star_class}" onclick="openModal('{m['home']}', '{m['away']}', `{m['analysis']}`, `{m['last_games']}`, `{m['bet']}`, '{h_logo}', '{a_logo}')">
            <div class="card-bg-pattern"></div>
            {star_badge}
            <div class="card-header-time">🕒 {m['time']}</div>
            <div class="card-teams">
                <div class="team team-home">
                    <img src="{h_logo}" onerror="this.src='https://cdn.nba.com/logos/nba/{h_id.upper()}/global/L/logo.svg'">
                    <p>{m['home']}</p>
                </div>
                <div class="vs-container">
                    <span class="vs-text">VS</span>
                </div>
                <div class="team team-away">
                    <img src="{a_logo}" onerror="this.src='https://cdn.nba.com/logos/nba/{a_id.upper()}/global/L/logo.svg'">
                    <p>{m['away']}</p>
                </div>
            </div>
             <div class="card-action">Szczegóły i analiza →</div>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NBA Raport Pro</title>
        <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800;900&display=swap" rel="stylesheet">
        <style>
            :root {{ --bg: #0a0a0a; --card-bg: #141414; --accent: #00f2ff; --gold: #ffbd00; --win: #00c853; --loss: #d50000; --text-muted: #a0a0a0; }}
            body {{ background: var(--bg); color: white; font-family: 'Montserrat', sans-serif; margin: 0; padding: 20px; background-image: radial-gradient(circle at top center, #1a1a1a 0%, #0a0a0a 70%); min-height: 100vh; }}
            h1 {{ text-align: center; color: var(--accent); text-transform: uppercase; letter-spacing: 3px; font-weight: 900; margin-bottom: 5px; }}
            
            .status-bar {{ display: flex; justify-content: center; gap: 15px; margin-bottom: 40px; font-size: 11px; flex-wrap: wrap; }}
            .status-item {{ display: flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.05); padding: 8px 16px; border-radius: 20px; border: 1px solid #333; color: #aaa; }}
            .dot {{ width: 8px; height: 8px; border-radius: 50%; }}
            .dot.green {{ background: var(--win); box-shadow: 0 0 10px var(--win); }}
            .dot.blue {{ background: var(--accent); box-shadow: 0 0 10px var(--accent); }}

            .container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 30px; max-width: 1200px; margin: 0 auto; }}
            
            .card {{ background: var(--card-bg); border-radius: 20px; padding: 25px; position: relative; overflow: hidden; border: 1px solid #2a2a2a; transition: all 0.3s ease; cursor: pointer; }}
            .card:hover {{ transform: translateY(-7px); border-color: var(--accent); box-shadow: 0 15px 35px rgba(0, 242, 255, 0.1); }}
            .star-card {{ border-color: var(--gold); }}
            .badge {{ position: absolute; top: 20px; right: -35px; background: var(--gold); color: #000; font-size: 10px; font-weight: 900; padding: 8px 40px; transform: rotate(45deg); }}
            
            .card-header-time {{ font-size: 12px; color: var(--text-muted); margin-bottom: 15px; font-weight: 600; }}
            .card-teams {{ display: flex; justify-content: space-between; align-items: center; }}
            .team {{ text-align: center; width: 40%; }}
            .team img {{ width: 80px; height: 80px; object-fit: contain; }}
            .team p {{ font-size: 16px; font-weight: 800; margin-top: 10px; text-transform: uppercase; }}
            .vs-text {{ font-size: 20px; font-weight: 900; color: #333; font-style: italic; }}
            .card-action {{ text-align: center; margin-top: 20px; color: var(--accent); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }}

            /* Modal */
            .modal {{ display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.95); z-index: 1000; align-items:center; justify-content:center; backdrop-filter: blur(10px); padding: 20px; }}
            .modal-content {{ background: #1a1a1a; width: 100%; max-width: 550px; border-radius: 25px; border: 1px solid #333; position: relative; overflow: hidden; }}
            .modal-header {{ background: #111; padding: 30px; text-align: center; border-bottom: 1px solid #333; }}
            .modal-body {{ padding: 30px; }}
            .close-btn {{ position: absolute; top: 15px; right: 20px; cursor: pointer; color: white; font-size: 30px; z-index: 11; }}
            
            .info-label {{ color: var(--accent); font-size: 11px; font-weight: 800; text-transform: uppercase; display: block; margin-bottom: 10px; }}
            .analysis-box {{ color: #ccc; line-height: 1.6; font-size: 14px; background: rgba(255,255,255,0.03); padding: 15px; border-radius: 12px; margin-bottom: 20px; }}
            
            .history-pills {{ display: flex; gap: 8px; margin-bottom: 20px; }}
            .pill {{ padding: 5px 12px; border-radius: 6px; font-size: 11px; font-weight: 900; }}
            .pill.w {{ background: var(--win); color: white; }}
            .pill.l {{ background: var(--loss); color: white; }}

            .bet-ticket {{ background: #fff; color: #000; padding: 20px; position: relative; margin-top: 30px; border-top: 3px dashed #ccc; }}
            .bet-ticket::before {{ content: 'REKOMENDACJA'; position: absolute; top: -10px; left: 50%; transform: translateX(-50%); background: var(--gold); padding: 2px 12px; font-size: 10px; font-weight: 900; border-radius: 10px; }}
            .bet-main {{ font-size: 17px; font-weight: 900; margin-bottom: 5px; }}
            .bet-desc {{ font-size: 13px; color: #444; line-height: 1.4; }}
        </style>
    </head>
    <body>
        <h1>🏀 NBA RAPORT PRO</h1>
        <div class="status-bar">
            <div class="status-item"><div class="dot green"></div>Aktualizacja: {last_update} ({date_display})</div>
            <div class="status-item"><div class="dot blue"></div>Następna: {next_up}</div>
        </div>
        
        <div class="container">{cards_html}</div>

        <div id="modal" class="modal" onclick="this.style.display='none'">
            <div class="modal-content" onclick="event.stopPropagation()">
                <span class="close-btn" onclick="document.getElementById('modal').style.display='none'">&times;</span>
                <div class="modal-header">
                    <div style="display:flex; justify-content:center; align-items:center; gap:20px;">
                        <img id="h-logo-m" style="width:70px;">
                        <span style="font-size:24px; font-weight:900; color:#333;">VS</span>
                        <img id="a-logo-m" style="width:70px;">
                    </div>
                </div>
                <div class="modal-body">
                    <span class="info-label">📋 Analiza meczu</span>
                    <div id="m-analysis" class="analysis-box"></div>
                    <span class="info-label">📈 Ostatnia forma</span>
                    <div id="m-history" class="history-pills"></div>
                    <div class="bet-ticket">
                        <div id="m-bet-main" class="bet-main"></div>
                        <div id="m-bet-desc" class="bet-desc"></div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            function formatHistory(text) {{
                return text.split(',').map(res => {{
                    const r = res.trim().toLowerCase();
                    if(r.includes('w')) return `<span class="pill w">W</span>`;
                    if(r.includes('l')) return `<span class="pill l">L</span>`;
                    return res;
                }}).join('');
            }}
            function openModal(h, a, an, hi, be, hl, al) {{
                document.getElementById('m-analysis').innerText = an;
                document.getElementById('m-history').innerHTML = formatHistory(hi);
                let parts = be.split('. ');
                document.getElementById('m-bet-main').innerText = parts[0];
                document.getElementById('m-bet-desc').innerText = parts.slice(1).join('. ');
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
