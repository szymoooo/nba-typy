import google.generativeai as genai
import os
import datetime
import pytz

# Konfiguracja
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    tools=[{"google_search": {}}] 
)

def run_audit():
    nba_tz = pytz.timezone('US/Eastern')
    today = datetime.datetime.now(nba_tz).strftime("%Y-%m-%d")

    if not os.path.exists('propozycje_typow.txt'):
        print("Brak pliku z typami.")
        return

    with open('propozycje_typow.txt', 'r', encoding='utf-8') as f:
        typy = f.read()

    if not typy:
        print("Plik z typami jest pusty.")
        return

    prompt = f"""
    Dzisiejsza data: {today}. 
    Mój algorytm wytypował następujące zwycięstwa w NBA:
    {typy}

    Użyj wyszukiwarki Google, aby sprawdzić najnowsze raporty kontuzji (NBA Injury Report) na dzień {today}.
    Skoncentruj się na tym, czy kluczowi gracze (liderzy) nie dostali wolnego w ostatniej chwili.
    
    Dla każdego meczu:
    1. Napisz [✅ ZATWIERDZONY] lub [⚠️ RYZYKOWNY - powód].
    2. Na końcu wybierz 2 najpewniejsze typy (tzw. Lock of the Day).
    
    Odpowiadaj krótko i konkretnie po polsku.
    """

    response = model.generate_content(prompt)
    
    with open('finalny_raport_dnia.txt', 'w', encoding='utf-8') as f:
        f.write(response.text)
    print("✅ Audyt Gemini zakończony.")

if __name__ == "__main__":
    run_audit()
