import os
import google.generativeai as genai
import json

api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

def get_nba_analysis():
    # Szukamy działającego modelu
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    model = genai.GenerativeModel(available_models[0] if available_models else 'gemini-1.5-flash')

    prompt = """
    Jesteś analitykiem NBA. Na dzień 29.12.2025 przygotuj listę WSZYSTKICH meczów.
    Dla każdego meczu podaj:
    1. Zespoły (Team A, Team B).
    2. Godzinę (EST).
    3. Czy to "Pewniak" (True/False).
    4. Krótka analiza (mocne/słabe strony).
    5. Ostatnie 3 wyniki obu drużyn.
    6. Sugerowany TYP z opisem.
    
    Zwróć dane WYŁĄCZNIE jako czysty kod JSON w formacie:
    [
      {"home": "Knicks", "away": "Pelicans", "time": "19:00", "star": true, "analysis": "...", "last_games": "...", "bet": "..."},
      ...
    ]
    Nie używaj znaczników ```json.
    """
    
    try:
        response = model.generate_content(prompt)
        return json.loads(response.text.replace('```json', '').replace('```', '').strip())
    except:
        return []

def create_page(matches):
    # Generujemy HTML z nowoczesnym wyglądem i oknami modalnymi
    cards_html = ""
    for m in matches:
        star_icon = "⭐ PEWNIAK" if m.get('star') else ""
        # Linki do logotypów (używamy cdn oficjalnego NBA)
        home_logo = f"[https://cdn.nba.com/logos/nba/](https://cdn.nba.com/logos/nba/){m['home'].lower()}/global/L/logo.svg" # To wymaga mapowania nazw, na razie damy placeholder
        
        cards_html += f"""
        <div class="match-card" onclick="openModal('{m['home']}', '{m['away']}', `{m['analysis']}`, `{m['last_games']}`, `{m['bet']}`)">
            <div class="star">{star_icon}</div>
            <div class="teams">
                <img src="[https://ui-avatars.com/api/?name=](https://ui-avatars.com/api/?name=){m['home']}&background=random" alt="{m['home']}">
                <span>vs</span>
                <img src="[https://ui-avatars.com/api/?name=](https://ui-avatars.com/api/?name=){m['away']}&background=random" alt="{m['away']}">
            </div>
            <div class="names">{m['home']} - {m['away']}</div>
            <div class="time">🕒 {m['time']} EST</div>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ background: #0f172a; color: white; font-family: 'Inter', sans-serif; text-align: center; }}
            .container {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; padding: 20px; }}
            .match-card {{ background: #1e293b; border-radius: 15px; padding: 20px; width: 280px; cursor: pointer; transition: 0.3s; border: 1px solid #334155; }}
            .match-card:hover {{ transform: translateY(-5px); border-color: #38bdf8; }}
            .teams img {{ width: 60px; height: 60px; border-radius: 50%; }}
            .star {{ color: #fbbf24; font-size: 0.8rem; height: 20px; font-weight: bold; }}
            .modal {{ display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); align-items:center; justify-content:center; }}
            .modal-content {{ background:#1e293b; padding:30px; border-radius:20px; max-width:500px; text-align:left; border: 1px solid #38bdf8; }}
        </style>
    </head>
    <body>
        <h1>🏀 NBA RAPORT LIVE</h1>
        <div class="container">{cards_html}</div>

        <div id="modal" class="modal" onclick="this.style.display='none'">
            <div class="modal-content" onclick="event.stopPropagation()">
                <h2 id="m-title"></h2>
                <p><strong>Analiza:</strong> <span id="m-analysis"></span></p>
                <p><strong>Ostatnie mecze:</strong> <span id="m-history"></span></p>
                <hr>
                <p style="color:#38bdf8"><strong>TYP:</strong> <span id="m-bet"></span></p>
                <button onclick="document.getElementById('modal').style.display='none'">Zamknij</button>
            </div>
        </div>

        <script>
            function openModal(h, a, an, hi, be) {{
                document.getElementById('m-title').innerText = h + ' vs ' + a;
                document.getElementById('m-analysis').innerText = an;
                document.getElementById('m-history').innerText = hi;
                document.getElementById('m-bet').innerText = be;
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
