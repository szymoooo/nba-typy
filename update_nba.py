import os
import google.generativeai as genai
import json
import datetime

# Konfiguracja API
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

def get_nba_analysis():
    today = datetime.date.today().strftime("%d.%m.%Y")
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    model = genai.GenerativeModel(available_models[0] if available_models else 'gemini-1.5-flash')

    prompt = f"""
    Jesteś ekspertem NBA. DZISIAJ JEST {today}. 
    Skorzystaj z wyszukiwarki i podaj listę WSZYSTKICH meczów NBA na dziś ({today}).
    
    W polu 'home_id' i 'away_id' podaj oficjalny skrót drużyny (np. LAL, BOS, GSW, NYK, PHX, DEN, LAC, MIL).
    
    Format JSON:
    [
      {{
        "home": "Nuggets", "home_id": "DEN",
        "away": "Suns", "away_id": "PHX",
        "time": "22:00",
        "star": true,
        "analysis": "Krótki, merytoryczny opis sytuacji kadrowej i formy obu drużyn.",
        "last_games": "W, L, W | W, W, L",
        "bet": "Nikola Jokic Over 26.5 pkt + asysty. Uzasadnienie: ..."
      }}
    ]
    WAŻNE: W polu 'bet' nie wpisuj słowa 'TYP:', zacznij od razu od treści. 
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
        is_star = m.get('star')
        star_class = "star-card" if is_star else ""
        star_badge = '<div class="badge">🔥 PEWNIAK DNIA</div>' if is_star else ""
        
        h_logo = f"https://a.espncdn.com/i/teamlogos/nba/500/scoreboard/{m['home_id'].lower()}.png"
        a_logo = f"https://a.espncdn.com/i/teamlogos/nba/500/scoreboard/{m['away_id'].lower()}.png"
        
        cards_html += f"""
        <div class="card {star_class}" onclick="openModal('{m['home']}', '{m['away']}', `{m['analysis']}`, `{m['last_games']}`, `{m['bet']}`, '{h_logo}', '{a_logo}')">
            <div class="card-bg-pattern"></div>
            {star_badge}
            <div class="card-header-time">🕒 {m['time']}</div>
            <div class="card-teams">
                <div class="team team-home">
                    <img src="{h_logo}" onerror="this.src='https://cdn.nba.com/logos/nba/{m['home_id'].upper()}/global/L/logo.svg'">
                    <p>{m['home']}</p>
                </div>
                <div class="vs-container">
                    <span class="vs-text">VS</span>
                </div>
                <div class="team team-away">
                    <img src="{a_logo}" onerror="this.src='https://cdn.nba.com/logos/nba/{m['away_id'].upper()}/global/L/logo.svg'">
                    <p>{m['away']}</p>
                </div>
            </div>
             <div class="card-action">
                Kliknij po analizę i typ
            </div>
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
            h1 {{ text-align: center; color: var(--accent); text-transform: uppercase; letter-spacing: 3px; font-weight: 900; margin-bottom: 10px; text-shadow: 0 0 20px rgba(0, 242, 255, 0.3); }}
            .subtitle {{ text-align: center; color: var(--text-muted); margin-bottom: 50px; font-size: 14px; }}
            
            .container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 30px; max-width: 1200px; margin: 0 auto; padding-bottom: 50px; }}
            
            /* --- NOWY STYL KART (HUD) --- */
            .card {{ background: var(--card-bg); border-radius: 20px; padding: 25px; position: relative; overflow: hidden; border: 1px solid #2a2a2a; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); cursor: pointer; }}
            .card:hover {{ transform: translateY(-7px) scale(1.02); border-color: var(--accent); box-shadow: 0 15px 35px rgba(0, 242, 255, 0.15); }}
            
            .card-bg-pattern {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; background-image: linear-gradient(45deg, #1a1a1a 25%, transparent 25%), linear-gradient(-45deg, #1a1a1a 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #1a1a1a 75%), linear-gradient(-45deg, transparent 75%, #1a1a1a 75%); background-size: 20px 20px; opacity: 0.05; z-index: 0; pointer-events: none; }}
            
            /* Styl dla Pewniaka */
            .star-card {{ border-color: var(--gold); box-shadow: 0 0 25px rgba(255, 189, 0, 0.15); }}
            .star-card:hover {{ box-shadow: 0 15px 40px rgba(255, 189, 0, 0.3); border-color: var(--gold); }}
            .badge {{ position: absolute; top: 20px; right: -35px; background: var(--gold); color: #000; font-size: 12px; font-weight: 900; padding: 8px 40px; transform: rotate(45deg); box-shadow: 0 5px 10px rgba(0,0,0,0.2); z-index: 2; }}
            
            .card-header-time {{ font-size: 13px; color: var(--text-muted); font-weight: 600; margin-bottom: 20px; position: relative; z-index: 1; }}
            
            .card-teams {{ display: flex; justify-content: space-between; align-items: center; position: relative; z-index: 1; }}
            .team {{ text-align: center; width: 35%; }}
            .team img {{ width: 90px; height: 90px; object-fit: contain; filter: drop-shadow(0 10px 10px rgba(0,0,0,0.5)); transition: 0.3s; }}
            .card:hover .team img {{ transform: scale(1.1); }}
            .team p {{ font-size: 18px; margin: 15px 0 0 0; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; }}
            
            .vs-container {{ display: flex; justify-content: center; align-items: center; width: 30%; }}
            .vs-text {{ font-size: 24px; font-weight: 900; color: #333; text-shadow: 1px 1px 2px rgba(255,255,255,0.1); font-style: italic; }}
            
            .card-action {{ text-align: center; margin-top: 25px; color: var(--accent); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; opacity: 0.7; transition: 0.3s; }}
            .card:hover .card-action {{ opacity: 1; letter-spacing: 2px; }}

            /* --- NOWY STYL MODALA (Betting Ticket) --- */
            .modal {{ display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.92); z-index: 1000; align-items:center; justify-content:center; backdrop-filter: blur(15px); padding: 20px; }}
            .modal-content {{ background: #1a1a1a; width: 100%; max-width: 600px; border-radius: 25px; border: 1px solid #333; position: relative; overflow: hidden; box-shadow: 0 30px 60px rgba(0,0,0,0.5); }}
            
            .modal-header-banner {{ background: linear-gradient(90deg, #141414, #222, #141414); padding: 30px; text-align: center; border-bottom: 1px solid #333; }}
            .modal-logos-container {{ display: flex; justify-content: center; align-items: center; gap: 30px; }}
            .modal-logos-container img {{ width: 80px; }}
            .modal-vs {{ font-size: 32px; font-weight: 900; color: var(--accent); opacity: 0.5; font-style: italic; }}

            .modal-body {{ padding: 30px; }}
            .close-btn {{ position: absolute; top: 15px; right: 20px; cursor: pointer; color: white; font-size: 32px; z-index: 10; }}
            
            .info-block {{ margin-bottom: 30px; }}
            .block-title {{ display: flex; align-items: center; gap: 10px; color: var(--accent); font-size: 14px; font-weight: 800; text-transform: uppercase; margin-bottom: 15px; }}
            .analysis-content {{ color: #ccc; line-height: 1.7; font-size: 15px; background: rgba(255,255,255,0.03); padding: 20px; border-radius: 15px; }}
            
            .history-pills {{ display: flex; gap: 10px; }}
            .pill {{ padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 800; }}
            .pill.w {{ background: var(--win); color: white; box-shadow: 0 5px 15px -5px var(--win); }}
            .pill.l {{ background: var(--loss); color: white; box-shadow: 0 5px 15px -5px var(--loss); }}

            /* KUPON BUKMACHERSKI */
            .bet-ticket {{ background: #fff; color: #000; padding: 25px; position: relative; margin-top: 40px; clip-path: polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%); background-image: radial-gradient(#e0e0e0 1px, transparent 0); background-size: 10px 10px; border-top: 3px dashed #ccc; }}
            .bet-ticket::before {{ content: 'KUPON EKSPERTA'; position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: var(--gold); color: #000; padding: 4px 15px; font-size: 11px; font-weight: 900; letter-spacing: 1px; border-radius: 20px; }}
            .bet-main {{ font-size: 18px; font-weight: 800; margin-bottom: 10px; color: #000; }}
            .bet-desc {{ font-size: 14px; color: #555; line-height: 1.5; font-weight: 500; }}
            .ticket-stub {{ position: absolute; bottom: -10px; left: 0; width: 100%; height: 15px; background: #fff; clip-path: polygon(0% 0%, 5% 100%, 10% 0%, 15% 100%, 20% 0%, 25% 100%, 30% 0%, 35% 100%, 40% 0%, 45% 100%, 50% 0%, 55% 100%, 60% 0%, 65% 100%, 70% 0%, 75% 100%, 80% 0%, 85% 100%, 90% 0%, 95% 100%, 100% 0%); }}

            @media (max-width: 480px) {{ .team img {{ width: 70px; height: 70px; }} .team p {{ font-size: 16px; }} .modal-body {{ padding: 20px; }} }}
        </style>
    </head>
    <body>
        <h1>🏀 NBA RAPORT PRO</h1>
        <p class="subtitle">Analiza i typy na dzień: {datetime.date.today().strftime("%d.%m.%Y")}</p>
        
        <div class="container">{cards_html}</div>

        <div id="modal" class="modal" onclick="this.style.display='none'">
            <div class="modal-content" onclick="event.stopPropagation()">
                <span class="close-btn" onclick="document.getElementById('modal').style.display='none'">&times;</span>
                
                <div class="modal-header-banner">
                     <div class="modal-logos-container">
                        <img id="h-logo-m" src=""> 
                        <span class="modal-vs">VS</span>
                        <img id="a-logo-m" src="">
                    </div>
                </div>

                <div class="modal-body">
                    <div class="info-block">
                        <span class="block-title">📋 Analiza Przedmeczowa</span>
                        <div id="m-analysis" class="analysis-text analysis-content"></div>
                    </div>

                    <div class="info-block">
                        <span class="block-title">📈 Forma (Ostatnie 3 mecze)</span>
                        <div id="m-history" class="history-pills"></div>
                    </div>

                    <div class="bet-ticket">
                        <div id="m-bet-main" class="bet-main"></div>
                        <div id="m-bet-desc" class="bet-desc"></div>
                        <div class="ticket-stub"></div>
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
                
                // Rozdzielamy typ na główny i opis (jeśli jest kropka)
                let betParts = be.split('. ');
                document.getElementById('m-bet-main').innerText = betParts[0];
                document.getElementById('m-bet-desc').innerText = betParts.slice(1).join('. ');

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
