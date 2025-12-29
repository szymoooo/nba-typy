import os
import google.generativeai as genai

# Konfiguracja API
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

def get_nba_data():
    # KROK 1: Sprawdźmy co w ogóle działa na Twoim kluczu
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    
    if not available_models:
        return "<p>Błąd: Twój klucz API nie ma dostępu do żadnych modeli generatywnych.</p>"
    
    # Wybieramy pierwszy dostępny model (zazwyczaj gemini-pro lub gemini-1.5-flash)
    model_name = available_models[0]
    model = genai.GenerativeModel(model_name)

    prompt = "Podaj tabelę HTML z analizą 3 meczów NBA na dziś: Knicks, Nuggets, Suns. Krótko o kontuzjach i kto wygra."
    
    try:
        response = model.generate_content(prompt)
        return response.text.replace('```html', '').replace('```', '').strip()
    except Exception as e:
        return f"<p>Błąd modelu {model_name}: {e}</p>"

def create_page(content):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><style>
        body {{ background:#111; color:#eee; font-family:sans-serif; text-align:center; padding:20px; }}
        table {{ margin:20px auto; border-collapse:collapse; width:90%; background:#222; border:1px solid #444; }}
        th, td {{ padding:12px; border:1px solid #444; text-align:left; }}
    </style></head>
    <body>
        <h1>🏀 NBA RAPORT LIVE (Auto-Select Model)</h1>
        <p>Aktualizacja: {os.popen('date').read()}</p>
        {content}
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    create_page(get_nba_data())
