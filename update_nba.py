import os
import google.generativeai as genai

# Pobieranie klucza z sekretów GitHuba
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_nba_data():
    prompt = "Podaj szybką analizę 3 meczów NBA na dziś (29.12.2025): Knicks-Pelicans, Heat-Nuggets, Suns-Wizards. Sformatuj to jako tabelę HTML."
    try:
        response = model.generate_content(prompt)
        return response.text.replace('```html', '').replace('```', '')
    except:
        return "<p>Błąd danych.</p>"

def create_page(content):
    html = f"<html><body style='background:#111;color:#eee;text-align:center;'><h1>NBA Raport 14:10</h1>{content}</body></html>"
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    create_page(get_nba_data())