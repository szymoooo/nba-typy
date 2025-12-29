import os
import google.generativeai as genai
import json
import datetime
import requests
import time
import sys
import re

# --- KONFIGURACJA ---
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("❌ BŁĄD: Brak klucza API!")
    sys.exit(1)

genai.configure(api_key=api_key)

# --- LISTA MODELI (PRIORYTETY) ---
# Skrypt próbuje ich po kolei, aż któryś zadziała.
AI_MODELS = [
    "gemini-2.0-flash-exp", # 1. NAJNOWSZY GENIUSZ (Najlepsza analiza)
    "gemini-1.5-pro",       # 2. Bardzo mądry, ale wolniejszy (Solidna alternatywa)
    "gemini-1.5-flash"      # 3. Deska ratunku (Zawsze działa, prostszy język)
]

TRUSTED_SOURCES = [
    "cleaningtheglass.com",
    "[rotowire.com/basketball/nba-lineups.php](https://rotowire.com/basketball/nba-lineups.php)",
    "[actionnetwork.com/nba/public-betting](https://actionnetwork.com/nba/public-betting)"
]

def clean_json_string(text):
    """
    Czyści odpowiedź AI, wyciągając tylko zawartość JSON.
    """
    # 1. Usuń znaczniki markdown ```json ... ```
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```', '', text)
    
    # 2. Znajdź pierwszą klamrę [ i ostatnią ]
    start = text.find('[')
    end = text.rfind(']')
    
    if start != -1 and end != -1:
        return text[start:end+1]
    return text

def get_official_schedule():
    now = datetime.datetime.now()
    date_str = now.strftime("%Y%m%d")
    url = f"[http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=](http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=){date_str}"
    
    try:
        print(f"🔌 [ESPN] Pobieranie: {date_str}...")
        r = requests.get(url)
        data = r.json()
        matches = []
        
        for event in data.get('events', []):
            comp = event['competitions'][0]
            home = next(c for c in comp['competitors'] if c['homeAway'] == 'home')
            away = next(c for c in comp['competitors'] if c['homeAway'] == 'away')
            
            # Czas
            dt = datetime.datetime.strptime(comp['date'], "%Y-%m-%dT%H:%M%SZ")
            time_pl = (dt + datetime.timedelta(hours=1)).strftime("%H:%M")
            
            matches.append({
                "home": home['team']['displayName'],
                "home_id": home['team']['abbreviation'],
                "home_logo": home['team'].get('logo', ''),
                "away": away['team']['displayName'],
                "away_id": away['team']['abbreviation'],
                "away_logo": away['team'].get('logo', ''),
                "time": time_pl
            })
        print(f"✅ [ESPN] Znaleziono {len(matches)} meczów.")
        return matches
    except Exception as e:
        print(f"❌ [ESPN ERROR] {e}")
        return []

def get_ai_analysis(schedule_list):
    if not schedule_list: return []
    
    matches_json = json.dumps(schedule_list)
    
    prompt = f"""
    Jesteś ekspertem NBA. Masz listę meczów: {matches_json}
    
    ZADANIE: Zwróć JSON (listę), dodając do każdego meczu:
    1. "bet": Typ (np. "Lakers -5") i krótkie uzasadnienie liczbowe.
    2. "last_games": Forma 5 ostatnich meczów "W,L,W,W,L | L,L,W,L,W" (Gosp | Gość).
    3. "analysis": Krótka analiza (2 zdania).
    4. "star": true dla 2 najlepszych typów.
    
    WAŻNE: Zwróć TYLKO czysty JSON. Żadnego gadania.
    """

    for model_name in AI_MODELS:
        print(f"🤖 [AI] Próba modelu: {model_name}...")
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            clean_text = clean_json_string(response.text)
            
            try:
                data = json.loads(clean_text)
                # Walidacja: czy to lista i czy ma tyle samo elementów?
                if isinstance(data, list) and len(data) == len(schedule_list):
                    print(f"✅ [AI] Sukces modelu {model_name}!")
                    data[0]['ai_model_used'] = model_name # Zapiszmy, kto wygrał
                    return data
                else:
                    print(f"⚠️ [AI] Model {model_name} zwrócił złą strukturę danych.")
            except json.JSONDecodeError:
                print(f"⚠️ [AI] Błąd parsowania JSON od {model_name}.")
                
        except Exception as e:
            print(f"❌ [AI] Błąd połączenia z {model_name}: {e}")
            time.sleep(1)

    print("❌ [AI FATAL] Wszystkie modele zawiodły. Zwracam puste dane.")
    return schedule_list

def create_page(matches):
    now = datetime.datetime.now() + datetime.timedelta(hours=1)
    last_update = now.strftime("%H:%M")
    used_model = matches[0].get('ai_model_used', 'Błąd AI (Fallback Mode)') if matches else "Brak"

    cards_html = ""
    for m in matches:
        # Zabezpieczenie przed brakiem danych (Fallback)
        an = m.get('analysis', 'Brak analizy. Spróbuj odświeżyć później.').replace('"', '&quot;')
        bet = m.get('bet', 'Brak typu')
        lg = m.get('last_games', '?,?,?,?,? | ?,?,?,?,?')
        star_class = "star-card" if m.get('star') else ""
        badge = '<div class="badge">💎 SHARP PLAY</div>' if m.get('star') else ""
        
        # Wyciągamy nazwy drużyn (bezpiecznie)
        home_name = m.get('home', 'Gospodarze')
        away_name = m.get('away', 'Goście')

        cards_html += f"""
        <div class="card {star_class}" onclick="openModal('{home_name}', '{away_name}', `{an}`, `{lg}`, `{bet}`, '{m['home_logo']}', '{m['away_logo']}')">
            <div class="card-bg-pattern"></div>
            {badge}
            <div class="card-header-time">🕒 {m['time']}</div>
            <div class="card-teams">
                <div class="team">
                    <img src="{m['home_logo']}">
                    <p>{home_name}</p>
                </div>
                <div class="vs-text">VS</div>
                <div class="team">
                    <img src="{m['away_logo']}">
                    <p>{away_name}</p>
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
        <title>NBA PRO</title>
        <link href="[https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800;900&display=swap](https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800;900&display=swap)" rel="stylesheet">
        <style>
            :root {{ --bg: #050505; --card: #111; --accent: #00ff88; --gold: #ffd700; --win: #00c853; --loss: #d50000; }}
            body {{ background: var(--bg); color: white; font-family: 'Montserrat', sans-serif; margin: 0; padding: 20px; }}
            h1 {{ text-align: center; color: var(--accent); font-weight: 900; letter-spacing: 2px; }}
            
            .status-bar {{ display: flex; justify-content: center; gap: 10px; margin-bottom: 30px; font-size: 11px; flex-wrap: wrap; }}
            .status-item {{ background: #222; padding: 5px 15px; border-radius: 15px; border: 1px solid #333; display: flex; align-items: center; gap: 5px; }}
            .dot {{ width: 8px; height: 8px; border-radius: 50%; }}
            .green {{ background: var(--win); }} .blue {{ background: var(--accent); }}

            .container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto; }}
            
            .card {{ background: var(--card); border-radius: 15px; padding: 20px; border: 1px solid #222; position: relative; overflow: hidden; cursor: pointer; transition: 0.3s; }}
            .card:hover {{ transform: translateY(-5px); border-color: var(--accent); }}
            .star-card {{ border: 1px solid var(--gold); background: linear-gradient(160deg, #1a1a10, #111); }}
            .badge {{ position: absolute; top: 15px; right: -30px; background: var(--gold); color: #000; font-size: 9px; font-weight: 900; padding: 5px 35px; transform: rotate(45deg); }}
            
            .card-teams {{ display: flex; justify-content: space-between; align-items: center; margin-top: 15px; }}
            .team {{ display: flex; flex-direction: column; align-items: center; width: 40%; }}
            .team img {{ width: 70px; height: 70px; object-fit: contain; margin-bottom: 5px; }}
            .team p {{ font-size: 13px; font-weight: 800; text-align: center; margin: 0; }}
            .vs-text {{ font-size: 20px; font-weight: 900; color: #444; font-style: italic; }}
            .card-action {{ text-align: center; margin-top: 20px; color: var(--accent); font-size: 10px; font-weight: 800; }}

            /* MODAL */
            .modal {{ display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.95); z-index: 1000; justify-content:center; align-items:center; padding: 10px; }}
            .modal-content {{ background: #111; width: 100%; max-width: 550px; border-radius: 20px; border: 1px solid #333; }}
            .modal-header {{ background: #161616; padding: 20px; text-align: center; border-bottom: 1px solid #222; border-radius: 20px 20px 0 0; }}
            .modal-body {{ padding: 25px; }}
            
            .analysis-box {{ color: #ccc; font-size: 14px; line-height: 1.6; background: #1a1a1a; padding: 15px; border-radius: 10px; margin-bottom: 20px; border-left: 3px solid var(--accent); }}
            
            .history-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px; }}
            .pill-row {{ display: flex; gap: 4px; justify-content: center; }}
            .pill {{ width: 25px; height: 25px; display: flex; align-items: center; justify-content: center; border-radius: 5px; font-size: 11px; font-weight: 800; color: white; }}
            .pill.w {{ background: var(--win); }}
            .pill.l {{ background: var(--loss); opacity: 0.5; }}
            .team-label {{ text-align: center; font-size: 10px; color: #888; margin-bottom: 5px; font-weight: 700; text-transform: uppercase; }}

            .bet-ticket {{ background: white; color: black; padding: 20px; border-radius: 12px; border-top: 4px dashed #999; }}
            .bet-main {{ font-size: 20px; font-weight: 900; margin-bottom: 5px; }}
            .bet-desc {{ font-size: 12px; line-height: 1.4; color: #333; }}
        </style>
    </head>
    <body>
        <h1>🏀 NBA PRO</h1>
        <div class="status-bar">
            <div class="status-item"><div class="dot green"></div>Model: {used_model}</div>
            <div class="status-item"><div class="dot blue"></div>Update: {last_update}</div>
            <a href="[https://github.com/szymoooo/nba-typy/actions](https://github.com/szymoooo/nba-typy/actions)" target="_blank" class="status-item" style="text-decoration:none; color:white; cursor:pointer;">
                🔄 Wymuś Odświeżenie (GitHub)
            </a>
        </div>
        
        <div class="container">{cards_html}</div>

        <div id="modal" class="modal" onclick="this.style.display='none'">
            <div class="modal-content" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <div style="display:flex; justify-content:center; align-items:center; gap:20px;">
                        <img id="h-logo-m" style="width:60px;">
                        <span style="font-size:20px; font-weight:900; color:#333;">VS</span>
                        <img id="a-logo-m" style="width:60px;">
                    </div>
                </div>
                <div class="modal-body">
                    <div style="font-size:10px; color:var(--accent); font-weight:800; margin-bottom:10px;">ANALIZA EKSPERCKA</div>
                    <div id="m-analysis" class="analysis-box"></div>
                    
                    <div class="history-grid">
                        <div>
                            <div class="team-label" id="h-name-label"></div>
                            <div id="h-pills" class="pill-row"></div>
                        </div>
                        <div>
                            <div class="team-label" id="a-name-label"></div>
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
                // Debugging w konsoli przeglądarki
                console.log("Otwieranie meczu:", h, "vs", a);
                console.log("Analiza:", an);
                console.log("Typ:", be);

                document.getElementById('m-analysis').innerHTML = an;
                document.getElementById('h-name-label').innerText = h;
                document.getElementById('a-name-label').innerText = a;
                
                // Parsowanie formy (zabezpieczenie)
                let h_res = [], a_res = [];
                if(hi && hi.includes('|')) {{
                    let parts = hi.split('|');
                    h_res = parts[0].split(',');
                    a_res = parts[1].split(',');
                }}
                
                const renderPills = (arr) => arr.map(r => 
                    `<div class="pill ${{r.trim().toLowerCase().includes('w') ? 'w' : 'l'}}">${{r.trim().substring(0,1).toUpperCase()}}</div>`
                ).join('');

                document.getElementById('h-pills').innerHTML = renderPills(h_res);
                document.getElementById('a-pills').innerHTML = renderPills(a_res);

                // Typ i uzasadnienie
                document.getElementById('m-bet-main').innerText = be;
                document.getElementById('m-bet-desc').innerText = "Rekomendacja oparta na statystykach zaawansowanych.";

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
        print("❌ Błąd krytyczny: Nie udało się pobrać terminarza.")
