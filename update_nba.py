import os
import google.generativeai as genai
import json
import datetime

# --- KONFIGURACJA API ---
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

def get_nba_analysis():
    now_pl = datetime.datetime.now() + datetime.timedelta(hours=1)
    today_str = now_pl.strftime("%d.%m.%Y")
    
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        model_name = available_models[0] if available_models else 'gemini-1.5-flash'
        model = genai.GenerativeModel(model_name)
    except:
        model = genai.GenerativeModel('gemini-1.5-flash')

    # WZMOCNIONY PROMPT: Wymuszamy wszystkie mecze i korektę czasu
    prompt = f"""
    Jesteś ekspertem NBA. DZISIAJ JEST {today_str}. 
    SKORZYSTAJ Z WYSZUKIWARKI I PODAJ LISTĘ WSZYSTKICH MECZÓW NBA NA NAJBLIŻSZĄ NOC (NAJLEPIEJ 10-15 MECZÓW).
    
    WAŻNE WYMAGANIA:
    1. 'time': Podaj czas rozpoczęcia meczu (np. 01:00, 02:30). Pamiętaj o korekcie na czas polski (+1h względem standardowych wyników Google jeśli są w UTC).
    2. 'last_games': Podaj formę osobno dla gospodarzy i gości w formacie: "Gosp: W,L,W | Goście: L,W,W".
    3. 'home_id' / 'away_id': Oficjalne skróty (np. OKC, MEM, LAL).
    
    Format JSON:
    [
      {{
        "home": "Cavaliers", "home_id": "CLE",
        "away": "Celtics", "away_id": "BOS",
        "time": "01:30",
        "star": true,
        "analysis": "Krótki opis...",
        "last_games": "Gosp: W,W,L | Goście: W,L,W",
        "bet": "Nazwa typu. Uzasadnienie..."
      }}
    ]
    Zwróć TYLKO czysty JSON.
    """
    
    try:
        response = model.generate_content(prompt)
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"Błąd: {e}")
        return []

def create_page(matches):
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
        h_id, a_id = m.get('home_id', 'NBA').lower(), m.get('away_id', 'NBA').lower()
        h_logo = f"https://a.espncdn.com/i/teamlogos/nba/500/scoreboard/{h_id}.png"
        a_logo = f"https://a.espncdn.com/i/teamlogos/nba/500/scoreboard/{a_id}.png"
        
        cards_html += f"""
        <div class="card {star_class}" onclick="openModal('{m['home']}', '{m['away']}', `{m['analysis']}`, `{m['last_games']}`, `{m['bet']}`, '{h_logo}', '{a_logo}')">
            <div class="card-bg-pattern"></div>
            {star_badge}
            <div class="card-header-time">🕒 {m['time']}</div>
            <div class="card-teams">
                <div class="team"><img src="{h_logo}"><p>{m['home']}</p></div>
                <div class="vs-text">VS</div>
                <div class="team"><img src="{a_logo}"><p>{m['away']}</p></div>
            </div>
             <div class="card-action">SZCZEGÓŁY ANALIZY →</div>
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
            body {{ background: var(--bg); color: white; font-family: 'Montserrat', sans-serif; margin: 0; padding: 20px; min-height: 100vh; }}
            h1 {{ text-align: center; color: var(--accent); text-transform: uppercase; font-weight: 900; font-size: 28px; }}
            
            .status-bar {{ display: flex; justify-content: center; gap: 15px; margin-bottom: 40px; font-size: 12px; }}
            .status-item {{ display: flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.05); padding: 8px 16px; border-radius: 20px; border: 1px solid #333; }}
            .dot {{ width: 8px; height: 8px; border-radius: 50%; }}
            .dot.green {{ background: var(--win); box-shadow: 0 0 10px var(--win); }}
            .dot.blue {{ background: var(--accent); box-shadow: 0 0 10px var(--accent); }}

            .container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 30px; max-width: 1200px; margin: 0 auto; }}
            
            .card {{ background: var(--card-bg); border-radius: 20px; padding: 25px; position: relative; overflow: hidden; border: 1px solid #2a2a2a; transition: 0.3s; cursor: pointer; }}
            .card:hover {{ transform: translateY(-5px); border-color: var(--accent); }}
            .badge {{ position: absolute; top: 20px; right: -35px; background: var(--gold); color: #000; font-size: 11px; font-weight: 900; padding: 8px 40px; transform: rotate(45deg); }}
            
            .card-header-time {{ font-size: 13px; color: var(--text-muted); margin-bottom: 15px; font-weight: 700; }}
            .card-teams {{ display: flex; justify-content: space-between; align-items: center; }}
            .team {{ text-align: center; width: 40%; }}
            .team img {{ width: 85px; height: 85px; object-fit: contain; }}
            .team p {{ font-size: 17px; font-weight: 800; margin-top: 10px; }}
            .vs-text {{ font-size: 22px; font-weight: 900; color: #333; }}
            .card-action {{ text-align: center; margin-top: 20px; color: var(--accent); font-size: 12px; font-weight: 700; letter-spacing: 1px; }}

            /* POPRAWIONY MODAL */
            .modal {{ display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.96); z-index: 1000; align-items:center; justify-content:center; backdrop-filter: blur(10px); padding: 15px; }}
            .modal-content {{ background: #1a1a1a; width: 100%; max-width: 650px; border-radius: 25px; border: 1px solid #333; position: relative; }}
            .modal-header {{ background: #111; padding: 35px; text-align: center; border-bottom: 1px solid #333; border-radius: 25px 25px 0 0; }}
            .modal-header img {{ width: 80px; height: 80px; }} /* LOGA +10% */
            .modal-body {{ padding: 35px; }}
            .close-btn {{ position: absolute; top: 15px; right: 20px; cursor: pointer; color: white; font-size: 35px; z-index: 11; }}
            
            .info-label {{ color: var(--accent); font-size: 12px; font-weight: 800; text-transform: uppercase; display: block; margin-bottom: 12px; }}
            .analysis-box {{ color: #ddd; line-height: 1.7; font-size: 15px; background: rgba(255,255,255,0.04); padding: 20px; border-radius: 15px; margin-bottom: 25px; }}
            
            .history-row {{ margin-bottom: 20px; }}
            .history-pills {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 5px; }}
            .pill {{ padding: 6px 14px; border-radius: 8px; font-size: 12px; font-weight: 900; }}
            .pill.w {{ background: var(--win); color: white; }}
            .pill.l {{ background: var(--loss); color: white; }}

            .bet-ticket {{ background: #fff; color: #000; padding: 25px; position: relative; margin-top: 30px; border-top: 4px dashed #ccc; border-radius: 0 0 15px 15px; }}
            .bet-ticket::before {{ content: 'REKOMENDACJA EKSPERTA'; position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: var(--gold); padding: 4px 15px; font-size: 11px; font-weight: 900; border-radius: 15px; }}
            .bet-main {{ font-size: 19px; font-weight: 900; margin-bottom: 8px; color: #000; }}
            .bet-desc {{ font-size: 14px; color: #333; line-height: 1.5; font-weight: 500; }}
        </style>
    </head>
    <body>
        <h1>🏀 NBA RAPORT PRO</h1>
        <div class="status-bar">
            <div class="status-item"><div class="dot green"></div>Aktualizacja: {last_update}</div>
            <div class="status-item"><div class="dot blue"></div>Następna: {next_up}</div>
        </div>
        <div class="container">{cards_html}</div>

        <div id="modal" class="modal" onclick="this.style.display='none'">
            <div class="modal-content" onclick="event.stopPropagation()">
                <span class="close-btn" onclick="document.getElementById('modal').style.display='none'">&times;</span>
                <div class="modal-header">
                    <div style="display:flex; justify-content:center; align-items:center; gap:30px;">
                        <img id="h-logo-m" src="">
                        <span style="font-size:28px; font-weight:900; color:#333;">VS</span>
                        <img id="a-logo-m" src="">
                    </div>
                </div>
                <div class="modal-body">
                    <span class="info-label">📋 Analiza taktyczna</span>
                    <div id="m-analysis" class="analysis-box"></div>
                    
                    <span class="info-label">📈 Ostatnie mecze (Forma)</span>
                    <div id="m-history" class="history-row"></div>

                    <div class="bet-ticket">
                        <div id="m-bet-main" class="bet-main"></div>
                        <div id="m-bet-desc" class="bet-desc"></div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            function formatHistory(text) {{
                // Rozdzielamy na Gosp i Goście
                let teams = text.split('|');
                return teams.map(team => {{
                    let parts = team.split(':');
                    let name = parts[0] || '';
                    let results = parts[1] || '';
                    let pills = results.split(',').map(res => {{
                        let r = res.trim().toLowerCase();
                        if(r.includes('w')) return `<span class="pill w">W</span>`;
                        if(r.includes('l')) return `<span class="pill l">L</span>`;
                        return res;
                    }}).join('');
                    return `<div style="margin-bottom:10px;"><small style="color:#888;">${{name.toUpperCase()}}:</small><div class="history-pills">${{pills}}</div></div>`;
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
