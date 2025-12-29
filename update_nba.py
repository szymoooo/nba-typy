import os
import google.generativeai as genai

# Konfiguracja API
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# Zmieniamy na model 'gemini-1.0-pro' lub spróbujemy bez wersji beta
# To jest najbardziej stabilna konfiguracja dla skryptów automatycznych
model = genai.GenerativeModel('gemini-pro')

def get_nba_data():
    prompt = """
    Jesteś ekspertem NBA. Przygotuj krótką analizę 3 meczów na dziś (29.12.2025): 
    Knicks-Pelicans, Heat-Nuggets, Suns-Wizards. 
    Skup się na kontuzjach i typie (kto wygra). 
    Zwróć TYLKO tabelę HTML (tag <table>). 
    Użyj stylu: tabela z obramowaniem, ciemne tło.
    """
    try:
        # Próba wygenerowania treści
        response = model.generate_content(prompt)
        return response.text.replace('```html', '').replace('```', '').strip()
    except Exception as e:
        # Jeśli gemini-pro też zawiedzie, spróbujemy ostatniej szansy
        try:
            model_fallback = genai.GenerativeModel('gemini-1.5-flash')
            response = model_fallback.generate_content(prompt)
            return response.text.replace('```html', '').replace('```', '').strip()
        except Exception as e2:
            return f"<p>Błąd krytyczny modeli AI: {e2}</p>"

def create_page(content):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ background:#111; color:#eee; text-align:center; font-family: sans-serif; padding: 20px; }}
            table {{ margin: 20px auto; border-collapse: collapse; width: 90%; background: #222; }}
            th, td {{ padding: 12px; border: 1px solid #444; text-align: left; }}
            th {{ background: #333; color: #f39c12; }}
            .highlight {{ color: #2ecc71; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>🏀 NBA RAPORT LIVE</h1>
        <p>Ostatnia aktualizacja: {os.popen('date').read()}</p>
        <div style="max-width: 800px; margin: 0 auto;">
            {content}
        </div>
        <p style="color: #666;">Dane pobierane automatycznie przez Agenta Gemini</p>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    create_page(get_nba_data())
