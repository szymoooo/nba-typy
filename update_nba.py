import os
import google.generativeai as genai

# Konfiguracja API
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("Brak klucza API!")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_nba_data():
    prompt = "Podaj szybką analizę 3 meczów NBA na dziś (29.12.2025): Knicks-Pelicans, Heat-Nuggets, Suns-Wizards. Sformatuj jako tabelę HTML (tylko <table>...</table>). Nie używaj znaczników ```."
    try:
        response = model.generate_content(prompt)
        # Czyszczenie odpowiedzi z ewentualnych znaczników markdown
        clean_html = response.text.replace('```html', '').replace('```', '').strip()
        return clean_html
    except Exception as e:
        return f"<p>Błąd połączenia z AI: {e}</p>"

def create_page(content):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ background:#111; color:#eee; text-align:center; font-family: sans-serif; padding: 20px; }}
            table {{ margin: 20px auto; border-collapse: collapse; width: 80%; background: #222; }}
            th, td {{ padding: 12px; border: 1px solid #444; text-align: left; }}
            th {{ background: #333; color: #f39c12; }}
        </style>
    </head>
    <body>
        <h1>🏀 NBA Raport Live - 19:30</h1>
        <p>Status na dzień: 29.12.2025</p>
        {content}
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    create_page(get_nba_data())
