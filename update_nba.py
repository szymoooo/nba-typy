import os
import google.generativeai as genai
import json
import datetime
import requests
import time

# --- KONFIGURACJA ---
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# --- LISTA MODELI (PRIORYTETY) ---
# Skrypt będzie próbował ich po kolei.
AI_MODELS = [
    "gemini-2.0-flash-exp", # 1. Najnowszy geniusz (Eksperymentalny)
    "gemini-1.5-pro",       # 2. Standardowy PRO
    "gemini-1.5-flash"      # 3. Niezawodny i szybki (Fallback)
]

# --- BAZA WIEDZY ---
TRUSTED_SOURCES = [
    "cleaningtheglass.com",
    "dunksandthrees.com",
    "rotowire.com/basketball/nba-lineups.php",
    "actionnetwork.com/nba/public-betting"
]

def get_official_schedule():
    """
    Pobiera oficjalny terminarz z API ESPN.
    """
    now = datetime.datetime.now()
    date_str = now.strftime("%Y%m%d")
    
    url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
    
    try:
        print(f"Pobieranie terminarza z ESPN dla daty: {date_str}...")
        r = requests.get(url)
        data = r.json()
        
        matches = []
        events = data.get('events', [])
        
        for event in events:
            competition = event['competitions'][0]
            competitors = competition['competitors']
            
            home_team = next(c for c in competitors if c['homeAway'] == 'home')
            away_team = next(c for c in competitors if c['homeAway'] == 'away')
            
            date_obj = datetime.datetime.strptime(competition['date'], "%Y-%m-%dT%H:%M%SZ")
            date_pl = date_obj + datetime.timedelta(hours=1)
            time_str = date_pl.strftime("%H:%M")
            
            h_logo = home_team['team'].get('logo', 'https://cdn.nba.com/logos/nba/nba-logoman-75-plus/primary/L/logo.svg')
            a_logo = away_team['team'].get('logo', 'https://cdn.nba.com/logos/nba/nba-logoman-75-plus/primary/L/logo.svg')

            match_info = {
                "home": home_team['team']['displayName'],
                "home_id": home_team['team']['abbreviation'],
                "home_logo": h_logo,
                "away": away_team['team']['displayName'],
                "away_id": away_team['team']['abbreviation'],
                "away_logo": a_logo,
                "time": time_str
            }
            matches.append(match_info)
            
        return matches
    except Exception as e:
        print(f"Błąd pobierania z ESPN: {e}")
        return []

def get_ai_analysis(schedule_list):
    """
    Wysyła mecze do analizy AI z mechanizmem FALLBACK.
    """
    if not schedule_list:
        return []

    matches_text = json.dumps(schedule_list, indent=2)
    sources_str = ", ".join(TRUSTED_SOURCES)

    prompt = f"""
    Jesteś ELITARNYM analitykiem NBA. 
    Masz tu oficjalną listę meczów (JSON):
    {matches_text}

    TWOJE ZADANIE:
    Dla każdego meczu dopisz analizę, typ i formę.
    
    WYMAGANIA:
    1. 'bet': Podaj TYP (np. "Lakers -5.5") i konkretne liczby (np. "Pace 101.2, DefRtg 109").
    2. 'last_games': Podaj formę z 5 OSTATNICH MECZÓW w formacie: "W,L,W,W,L | L,L,W,L,W" (Gospodarz | Goście). Musi być 5 wyników!
    3. 'star': Daj 'true' TYLKO dla 2-3 najlepszych typów (Sharp Plays).
    4. 'analysis': Krótka analiza taktyczna.
    
    WAŻNE:
    - Nie zmieniaj pól 'home_logo', 'away_logo', 'time'.
    - Zwróć CZYSTY JSON (listę obiektów). Bez markdowna.
    """
    
    # --- PĘTLA FALLBACK ---
    for model_name in AI_MODELS:
        print(f"🤖 Próba analizy modelem: {model_name}...")
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            content = response.text.strip()
            
            # Czyszczenie JSON
            start_idx = content.find('[')
            end_idx = content.rfind(']')
            
            if start_idx != -1 and end_idx != -1:
                content = content[start_idx : end_idx + 1]
                data = json.loads(content)
                print(f"✅ Sukces! Analiza wykonana przez {model_name}.")
                # Dodajemy info o modelu do pierwszego elementu (opcjonalnie, do debugowania)
                if data:
                    data[0]['ai_model_used'] = model_name
                return data
            else:
                print(f"⚠️ Model {model_name} zwrócił błędny format JSON. Próbuję kolejny...")
                
        except Exception as e:
            print(f"❌ Błąd modelu {model_name}: {e}")
            print("➡️ Przełączam na model zapasowy...")
            time.sleep(1) # Krótka przerwa przed kolejną próbą

    print("❌ WSZYSTKIE MODELE ZAWIODŁY. Zwracam puste dane.")
    return schedule_list

def create_page(matches):
    now_pl = datetime.datetime.now() + datetime.timedelta(hours=1)
    last_update = now_pl.strftime("%H:%M")
    date_display = now_pl.strftime("%d.%m.%Y")
    
    # Wyciągamy nazwę użytego modelu (jeśli dodaliśmy ją w funkcji get_ai_analysis)
    used_model = matches[0].get('ai_model_used', 'Gemini 1.5 Flash (Fallback)') if matches else "Brak danych"
    
    current_hour = now_pl.hour
    if current_hour < 7: next_up = "07:00 (Wyniki)"
    elif current_hour < 15: next_up = "15:10 (Analiza)"
    elif current_hour < 19: next_up = "19:30 (Update)"
    else: next_up = "Jutro 07:00"

    cards_html = ""
    for m in matches:
        is_star = m.get('star', False)
        star_class = "star-card" if is_star else ""
        star_badge = '<div class="badge">💎 SHARP PLAY</div>' if is_star else ""
        
        h_logo = m.get('home_logo', '')
        a_logo = m.get('away_logo', '')
        
        analysis = m.get('analysis', 'Oczekiwanie na dane eksperckie...')
        bet = m.get('bet', 'Analiza w toku.')
        # Domyślnie 5 kresek
        last_games = m.get('last_games', '-,-,-,-,- | -,-,-,-,-')
        
        cards_html += f"""
        <div class="card {star_class}" onclick="openModal('{m['home']}', '{m['away']}', `{analysis}`, `{last_games}`, `{bet}`, '{h_logo}', '{a_logo}')">
            <div class="card-bg-pattern"></div>
            {star_badge}
            <div class="card-header-time">🕒 {m['time']}</div>
            <div class="card-teams">
                <div class="team">
                    <img src="{h_logo}">
                    <p>{m['home']}</p>
                </div>
                <div class="vs-text">VS</div>
                <div class="team">
                    <img src="{a_logo}">
                    <p>{m['away']}</p>
                </div>
            </div>
             <div class="card-action">ANALIZA EKSPERCKA →</div>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NBA PRO ANALYTICS</title>
        <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800;900&display=swap" rel="stylesheet">
        <style>
            :root {{ --bg: #050505; --card-bg: #111; --accent: #00ff88; --gold: #ffd700; --win: #00c853; --loss: #ff3d00; --text-muted: #888; }}
            body {{ background: var(--bg); color: white; font-family: 'Montserrat', sans-serif; margin: 0; padding: 20px; }}
            h1 {{ text-align: center; color: var(--accent); text-transform: uppercase; font-weight: 900; letter-spacing: 2px; text-shadow: 0 0 15px rgba(0, 255, 136, 0.3); }}
            
            .status-bar {{ display: flex; justify-content: center; gap: 15px; margin-bottom: 40px; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; flex-wrap: wrap; }}
            .status-item {{ display: flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.03); padding: 8px 16px; border-radius: 20px; border: 1px solid #222; }}
            .dot {{ width: 6px; height: 6px; border-radius: 50%; }}
            .dot.green {{ background: var(--win); box-shadow: 0 0 8px var(--win); }}
            .dot.blue {{ background: var(--accent); box-shadow: 0 0 8px var(--accent); }}

            .container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 25px; max-width: 1200px; margin: 0 auto; }}
            
            .card {{ background: var(--card-bg); border-radius: 16px; padding: 25px; position: relative; overflow: hidden; border: 1px solid #222; transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); cursor: pointer; }}
            .card:hover {{ transform: translateY(-5px); border-color: var(--accent); box-shadow: 0 10px 30px -10px rgba(0, 255, 136, 0.2); }}
            .star-card {{ border: 1px solid var(--gold); background: linear-gradient(145deg, #1a1a10 0%, #111 100%); }}
            
            .badge {{ position: absolute; top: 15px; right: -32px; background: var(--gold); color: #000; font-size: 10px; font-weight: 900; padding: 6px 35px; transform: rotate(45deg); box-shadow: 0 2px 10px rgba(0,0,0,0.5); letter-spacing: 1px; }}
            
            .card-header-time {{ font-size: 12px; color: var(--text-muted); margin-bottom: 20px; font-weight: 700; letter-spacing: 1px; }}
            
            .card-teams {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
            
            .team {{ 
                display: flex; 
                flex-direction: column; 
                align-items: center; 
                justify-content: flex-start;
                width: 40%; 
            }}
            .team img {{ width: 80px; height: 80px; object-fit: contain; filter: drop-shadow(0 0 8px rgba(0,0,0,0.5)); margin-bottom: 10px; }}
            .team p {{ font-size: 15px; font-weight: 800; margin: 0; text-align: center; letter-spacing: -0.5px; line-height: 1.2; }}
            
            .vs-text {{ font-size: 24px; font-weight: 900; color: #333; font-style: italic; }}
            .card-action {{ text-align: center; margin-top: 25px; color: var(--accent); font-size: 11px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; }}

            .modal {{ display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.95); z-index: 1000; align-items:center; justify-content:center; padding: 10px; backdrop-filter: blur(8px); }}
            .modal-content {{ background: #0f0f0f; width: 100%; max-width: 600px; border-radius: 20px; border: 1px solid #333; position: relative; overflow: hidden; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.7); }}
            .modal-header {{ background: linear-gradient(180deg, #161616 0%, #0f0f0f 100%); padding: 40px 20px; text-align: center; border-bottom: 1px solid #222; }}
            .modal-header img {{ width: 90px; height: 90px; }}
            .modal-body {{ padding: 30px; }}
            .close-btn {{ position: absolute; top: 15px; right: 20px; cursor: pointer; color: #666; font-size: 28px; transition: 0.2s; }}
            .close-btn:hover {{ color: white; }}
            
            .info-label {{ color: var(--accent); font-size: 11px; font-weight: 800; text-transform: uppercase; display: block; margin-bottom: 12px; letter-spacing: 1px; opacity: 0.8; }}
            .analysis-box {{ color: #ccc; line-height: 1.7; font-size: 14px; background: rgba(255,255,255,0.03); padding: 20px; border-radius: 12px; margin-bottom: 30px; border-left: 2px solid var(--accent); }}
            
            .history-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 1px solid #222; }}
            .history-team-label {{ font-size: 10px; color: #666; font-weight: 900; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px; }}
            .pill-row {{ display: flex; gap: 5px; }}
            .pill {{ width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: 6px; font-size: 12px; font-weight: 800; color: white; }}
            .pill.w {{ background: var(--win); }}
            .pill.l {{ background: var(--loss); opacity: 0.4; }}

            .bet-ticket {{ background: #fff; color: #000; padding: 25px; border-radius: 12px; position: relative; border-top: 4px dashed #ccc; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
            .bet-ticket::before {{ content: 'REKOMENDACJA SYSTEMU PRO'; position: absolute; top: -10px; left: 50%; transform: translateX(-50%); background: var(--gold); padding: 4px 12px; font-size: 10px; font-weight: 900; border-radius: 10px; letter-spacing: 0.5px; white-space: nowrap; }}
            .bet-main {{ font-size: 22px; font-weight: 900; margin-bottom: 10px; color: #111; letter-spacing: -0.5px; }}
            .bet-desc {{ font-size: 13px; color: #444; line-height: 1.5; font-weight: 600; padding-top: 10px; border-top: 1px solid #eee; }}
        </style>
    </head>
    <body>
        <h1>🏀 NBA PRO ANALYTICS</h1>
        <div class="status-bar">
            <div class="status-item"><div class="dot green"></div>AI Model: {used_model}</div>
            <div class="status-item"><div class="dot blue"></div>Aktualizacja: {last_update}</div>
        </div>
        
        <div class="container">{cards_html}</div>

        <div id="modal" class="modal" onclick="this.style.display='none'">
            <div class="modal-content" onclick="event.stopPropagation()">
                <span class="close-btn" onclick="document.getElementById('modal').style.display='none'">&times;</span>
                <div class="modal-header">
                    <div style="display:flex; justify-content:center; align-items:center; gap:30px;">
                        <img id="h-logo-m" src="">
                        <span style="font-size:24px; font-weight:900; color:#333; font-style:italic;">VS</span>
                        <img id="a-logo-m" src="">
                    </div>
                </div>
                <div class="modal-body">
                    <span class="info-label">📋 Analiza Advanced Stats</span>
                    <div id="m-analysis" class="analysis-box"></div>
                    
                    <div class="history-grid">
                        <div>
                            <div class="history-team-label" id="h-name-label">Gospodarze</div>
                            <div id="h-pills" class="pill-row"></div>
                        </div>
                        <div>
                            <div class="history-team-label" id="a-name-label">Goście</div>
                            <div id="a-pills" class="pill-row"></div>
                        </div>
                    </div>

                    <div class="bet-ticket">
                        <div id="m-bet-main" class="bet-main"></div>
                        <div id="m-bet-desc" class="bet-desc"></div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            function openModal(h, a, an, hi, be, hl, al) {{
                document.getElementById('m-analysis').innerText = an;
                document.getElementById('h-name-label').innerText = h;
                document.getElementById('a-name-label').innerText = a;
                
                let [h_res, a_res] = hi.split('|');
                const h_pills = h_res ? h_res.split(',').map(r => `<div class="pill ${{r.trim().toLowerCase() === 'w' ? 'w' : 'l'}}">${{r.trim().toUpperCase()}}</div>`).join('') : '';
                const a_pills = a_res ? a_res.split(',').map(r => `<div class="pill ${{r.trim().toLowerCase() === 'w' ? 'w' : 'l'}}">${{r.trim().toUpperCase()}}</div>`).join('') : '';
                
                document.getElementById('h-pills').innerHTML = h_pills;
                document.getElementById('a-pills').innerHTML = a_pills;

                let firstPeriod = be.indexOf('.');
                if(firstPeriod !== -1) {{
                    document.getElementById('m-bet-main').innerText = be.substring(0, firstPeriod);
                    document.getElementById('m-bet-desc').innerText = be.substring(firstPeriod + 1);
                }} else {{
                    document.getElementById('m-bet-main').innerText = be;
                    document.getElementById('m-bet-desc').innerText = "";
                }}
                
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
    schedule = get_official_schedule()
    
    if schedule:
        data = get_ai_analysis(schedule)
        create_page(data)
    else:
        print("Błąd: Nie udało się pobrać danych z ESPN.")
