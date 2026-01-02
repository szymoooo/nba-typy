from google import genai
from google.genai import types
import os
import datetime
import pytz

# 1. Konfiguracja nowego klienta
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def run_audit():
    nba_tz = pytz.timezone('US/Eastern')
    today = datetime.datetime.now(nba_tz).strftime("%Y-%m-%d")

    if not os.path.exists('propozycje_typow.txt'):
        print("Nie znaleziono pliku propozycje_typow.txt")
        return

    with open('propozycje_typow.txt', 'r', encoding='utf-8') as f:
        typy = f.read()

    if not typy:
        print("Brak typów do analizy.")
        return

    prompt = f"""
    Dzisiejsza data (NBA Time): {today}.
    Moje statystyczne typy na dzisiaj to:
    {typy}

    Zadanie:
    1. Skorzystaj z wyszukiwarki Google, aby sprawdzić 'NBA injury report' i najświeższe newsy z ostatnich 6 godzin dla powyższych meczów.
    2. Sprawdź, czy kluczowi zawodnicy grają.
    3. Jeśli typ jest zagrożony, napisz: [⚠️ RYZYKOWNY - powód].
    4. Jeśli wszystko OK, napisz: [✅ ZATWIERDZONY].
    5. Na końcu wybierz 2 najpewniejsze typy dnia.
    
    Odpowiadaj po polsku.
    """

    # 2. Wywołanie modelu z nowym sposobem włączenia wyszukiwarki
    response = client.models.generate_content(
        model="gemini-2.0-flash", # lub gemini-1.5-flash
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearchRetrieval())]
        )
    )
    
    with open('finalny_raport_dnia.txt', 'w', encoding='utf-8') as f:
        f.write(f"--- AUDYT KONTEKSTOWY GEMINI ({today}) ---\n\n")
        f.write(response.text)
    
    print("✅ Audyt zakończony sukcesem.")

if __name__ == "__main__":
    run_audit()
