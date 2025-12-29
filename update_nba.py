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
    print("❌ BŁĄD KRYTYCZNY: Brak klucza API w zmiennych środowiskowych!")
    sys.exit(1)

genai.configure(api_key=api_key)

# --- LISTA MODELI (PRIORYTETY WG TWOJEGO ŻYCZENIA) ---
AI_MODELS = [
    "gemini-2.0-flash-exp", # 1. NAJNOWSZY GENIUSZ (Eksperymentalny - głęboka analiza)
    "gemini-1.5-pro",       # 2. PRO (Solidna alternatywa)
    "gemini-1.5-flash"      # 3. FLASH (Szybki i niezawodny - deska ratunku)
]

# --- BAZA WIEDZY DLA AGENTA ---
TRUSTED_SOURCES = [
    "cleaningtheglass.com",
    "rotowire.com/basketball/nba-lineups.php", # Źródło kontuzji
    "actionnetwork.com/nba/public-betting",
    "basketball-reference.com"
]

def clean_json_string(text):
    """Czyści odpowiedź AI z markdowna, zostawiając czysty JSON."""
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```', '', text)
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1:
        return text[start:end+1]
    return text

def get_official_schedule():
    """Pobiera oficjalny terminarz z API ESPN."""
    now = datetime.datetime.now()
    date_str = now.strftime("%Y%m%d")
    url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
    
    try:
        print(f"🔌 [ESPN] Pobieranie terminarza na dzień: {date_str}...")
        r = requests.get(url)
        data = r.json()
        matches = []
        
        for event in data.get('events', []):
            comp = event['competitions'][0]
            home = next(c for c in comp['competitors'] if c['homeAway'] == 'home')
            away = next(c for c in comp['competitors'] if c['homeAway'] == 'away')
            
            # Konwersja czasu
            dt = datetime.datetime.strptime(comp['date'], "%Y-%m-%dT%H:%M%SZ")
            time_pl = (dt + datetime.timedelta(hours=1)).strftime("%H:%M")
            
            # Pobranie pewnych logotypów z ESPN
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
    """Analiza z Smart Fallback i sprawdzaniem kontuzji."""
    if not schedule_list: return []
    
    matches_json = json.dumps(schedule_list)
    sources_str = ", ".join(TRUSTED_SOURCES)
    
    prompt = f"""
    Jesteś GEOMETRYCZNYM analitykiem NBA (Sports Data Scientist).
    Masz tu oficjalną listę meczów na dziś: {matches_json}

    TWOJE ZADANIE: Przeprowadź symulację każdego meczu, uwzględniając LIVE NEWS.

    KROK 1: RESEARCH (Użyj Google Search w tle):
    1. Sprawdź "NBA Injury Report" na dziś. Kto jest "OUT" lub "GTD"?
       - Jeśli gwiazda (np. Giannis, Luka, Curry) nie gra -> uwzględnij to w typie!
    2. Sprawdź "Schedule Spot":
       - Czy drużyna gra B2B (dzień po dniu)? Zmęczenie = gorsza obrona.
       - Czy była długa podróż?
    
    KROK 2: GENEROWANIE JSON:
    Dla każdego meczu dodaj pola:
    - "bet": Typ (np. "Knicks -4.5") + Uzasadnienie liczbowe (np. "Brak Brunsona, Pace 98.2").
    - "last_games": Forma 5 OSTATNICH MECZÓW w formacie "W,L,W,L,W | W,W,L,L,W" (Gosp | Gość).
    - "analysis": Krótka, gęsta analiza taktyczna. Wspomnij o kontuzjach!
    - "star": true/false (tylko dla 2-3 najpewniejszych typów).

    WAŻNE: Zwróć TYLKO czysty JSON. Nie zmieniaj danych wejściowych (logo/time).
    """

    for model_name in AI_MODELS:
        print(f"🤖 [AI] Próba analizy modelem: {model_name}...")
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            clean_text = clean_json_string(response.text)
            
            try:
                data = json.loads(clean_text)
                # Walidacja: czy otrzymaliśmy listę o tej samej długości?
                if isinstance(data, list) and len(data) == len(schedule_list):
                    print(f"✅ [AI] Sukces! Analiza wykonana przez {model_name}.")
                    data[0]['ai_model_used'] = model_name # Znacznik dla UI
                    return data
                else:
                    print(f"⚠️ [AI] Model {model_name} zwrócił niepoprawną strukturę danych.")
            except json.JSONDecodeError:
                print(f"⚠️ [AI] Błąd parsowania JSON od {model_name}.")
                
        except Exception as e:
            print(f"❌ [AI] Błąd połączenia z {model_name}: {e}")
            time.sleep(1) # Krótka pauza przed zmianą modelu

    print("❌ [AI FATAL] Wszystkie modele zawiodły. Zwracam dane bez analizy.")
    return schedule_list

def create_page(matches):
    now = datetime.datetime.now() + datetime.timedelta(hours=1)
    last_update = now.strftime("%H:%M")
    date_display = now.strftime("%d.%m.%Y")
    
    # Wyciągamy informację o użytym modelu
    used_model = matches[0].get('ai_model_used', 'Błąd AI (Fallback Mode)') if matches else "Brak"

    cards_html = ""
    for m in matches:
        # Zabezpieczenia na wypadek braku danych
        an = m.get('analysis', 'System AI nie zwrócił danych. Sprawdź logi.').replace('"', '&quot;')
        bet = m.get('bet', 'Brak typu')
        lg = m.get('last_games', '?,?,?,?,? | ?,?,?,?,?') # 5 pytajników jako placeholder
        
        star_class = "star-card" if m.get('star') else ""
        badge = '<div class="badge">💎 SHARP PLAY</div>' if m.get('star') else ""
        
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
        <title>NBA PRO ANALYTICS</title>
        <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800;900&display=swap" rel="stylesheet">
        <style>
            :root {{ --bg: #050505; --card: #111; --accent: #00ff88; --gold: #ffd700; --win: #00c853; --loss: #d50000; --text-muted: #888; }}
            body {{ background: var(--bg); color: white; font-family: 'Montserrat', sans-serif; margin: 0; padding: 20px; }}
            h1 {{ text-align: center; color: var(--accent); font-weight: 900; letter-spacing: 2px; text-shadow: 0 0 15px rgba(0, 255, 136, 0.3); }}
            
            .status-bar {{ display: flex; justify-content: center; gap: 10px; margin-bottom: 30px; font-size: 11px; flex-wrap: wrap; }}
            .status-item {{ background: #222; padding: 5px 15px; border-radius: 15px; border: 1px solid #333; display: flex; align-items: center; gap: 5px; }}
            .dot {{ width: 8px; height: 8px; border-radius: 50%; }}
            .green {{ background: var(--win); }} .blue {{ background: var(--accent); }}

            .container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto; }}
            
            /* KARTA MECZU */
            .card {{ background: var(--card); border-radius: 15px; padding: 20px; border: 1px solid #222; position: relative; overflow: hidden; cursor: pointer; transition: 0.3s; }}
            .card:hover {{ transform: translateY(-5px); border-color: var(--accent); }}
            .star-card {{ border: 1px solid var(--gold); background: linear-gradient(160deg, #1a1a10, #111); }}
            .badge {{ position: absolute; top: 15px; right: -30px; background: var(--gold); color: #000; font-size: 9px; font-weight: 900; padding: 5px 35px; transform: rotate(45deg); }}
            
            .card-header-time {{ font-size: 12px; color: var(--text-muted); margin-bottom: 15px; font-weight: 700; }}
            
            .card-teams {{ display: flex; justify-content: space-between; align-items: center; margin-top: 10px; }}
            
            /* CSS FIX: Wycentrowanie logo i tekstu w karcie */
            .team {{ 
                display: flex; 
                flex-direction: column; 
                align-items: center; 
                justify-content: flex-start;
                width: 40%; 
            }}
            .team img {{ width: 70px; height: 70px; object-fit: contain; margin-bottom: 8px; filter: drop-shadow(0 0 8px rgba(0,0,0,0.5)); }}
            .team p {{ font-size: 14px; font-weight: 800; text-align: center; margin: 0; line-height: 1.2; }}
            
            .vs-text {{ font-size: 20px; font-weight: 900; color: #444; font-style: italic; }}
            .card-action {{ text-align: center; margin-top: 20px; color: var(--accent); font-size: 10px; font-weight: 800; letter-spacing: 1px; }}

            /* MODAL SYSTEM */
            .modal {{ display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.95); z-index: 1000; justify-content:center; align-items:center; padding: 10px; backdrop-filter: blur(5px); }}
            .modal-content {{ background: #111; width: 100%; max-width: 550px; border-radius: 20px; border: 1px solid #333; box-shadow: 0 20px 50px rgba(0,0,0,0.8); }}
            .modal-header {{ background: #161616; padding: 25px; text-align: center; border-bottom: 1px solid #222; border-radius: 20px 20px 0 0; }}
            .modal-body {{ padding: 25px; }}
            
            .analysis-box {{ color: #ddd; font-size: 14px; line-height: 1.6; background: #1a1a1a; padding: 15px; border-radius: 10px; margin-bottom: 25px; border-left: 3px solid var(--accent); }}
            
            /* CSS FIX: Wycentrowanie formy w modalu */
            .history-grid {{ 
                display: grid; 
                grid-template-columns: 1fr 1fr; 
                gap: 15px; 
                margin-bottom: 20px; 
            }}
            .history-grid > div {{
                display: flex;
                flex-direction: column;
                align-items: center;
            }}
            .team-label {{ text-align: center; font-size: 11px; color: #888; margin-bottom: 8px; font-weight: 800; text-transform: uppercase; }}
            .pill-row {{ display: flex; gap: 4px; justify-content: center; }}
            
            /* CSS FIX: Sztywne wymiary kafelków W/L */
            .pill {{ 
                width: 28px; 
                height: 28px; 
                min-width: 28px; 
                max-width: 28px; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                border-radius: 6px; 
                font-size: 12px; 
                font-weight: 900; 
                color: white; 
                flex-shrink: 0;
            }}
            .pill.w {{ background: var(--win); }}
            .pill.l {{ background: var(--loss); opacity: 0.6; }}

            .bet-ticket {{ background: white; color: black; padding: 20px; border-radius: 12px; border-top: 4px dashed #999; position: relative; }}
            .bet-main {{ font-size: 22px; font-weight: 900; margin-bottom: 8px; }}
            .bet-desc {{ font-size: 13px; line-height: 1.4; color: #333; font-weight: 500; }}
        </style>
    </head>
    <body>
        <h1>🏀 NBA PRO ANALYTICS</h1>
        <div class="status-bar">
            <div class="status-item"><div class="dot green"></div>Model: {used_model}</div>
            <div class="status-item"><div class="dot blue"></div>Update: {last_update}</div>
            <a href="https://github.com/szymoooo/nba-typy/actions" target="_blank" class="status-item" style="text-decoration:none; color:white;">🔄 Odśwież</a>
        </div>
        
        <div class="container">{cards_html}</div>

        <div id="modal" class="modal" onclick="closeModal()">
            <div class="modal-content" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <div style="display:flex; justify-content:center; align-items:center; gap:20px;">
                        <img id="h-logo-m" style="width:70px;">
                        <span style="font-size:24px; font-weight:900; color:#333;">VS</span>
                        <img id="a-logo-m" style="width:70px;">
                    </div>
                </div>
                <div class="modal-body">
                    <div style="font-size:10px; color:var(--accent); font-weight:800; margin-bottom:10px;">ANALIZA TAKTYCZNA + KONTUZJE</div>
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
                document.getElementById('m-analysis').innerHTML = an;
                document.getElementById('h-name-label').innerText = h;
                document.getElementById('a-name-label').innerText = a;
                
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

                document.getElementById('m-bet-main').innerText = be;
                document.getElementById('m-bet-desc').innerText = "Typ oparty na symulacji AI z uwzględnieniem absencji.";

                document.getElementById('h-logo-m').src = hl;
                document.getElementById('a-logo-m').src = al;
                
                // OTWÓRZ MODAL I ZABLOKUJ SCROLL
                document.getElementById('modal').style.display = 'flex';
                document.body.style.overflow = 'hidden';
            }}

            function closeModal() {{
                // ZAMKNIJ MODAL I ODBLOKUJ SCROLL
                document.getElementById('modal').style.display = 'none';
                document.body.style.overflow = 'auto';
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
