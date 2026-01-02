import google.generativeai as genai
import os
import datetime
import pytz

# 1. Konfiguracja Gemini
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Używamy modelu z dostępem do wyszukiwarki Google
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    tools=[{"google_search": {}}] 
)

def audit_typow():
    # Pobierz dzisiejszą datę w czasie NBA (Eastern Time)
    nba_tz = pytz.timezone('US/Eastern')
    today = datetime.datetime.now(nba_tz).strftime("%Y-%m-%d")

    # 2. Odczyt Twoich typów (zakładam, że masz je w pliku tekstowym lub zmiennej)
    # Tutaj skrypt powinien wczytać wynik Twojego głównego modelu
    try:
        with open('propozycje_typow.txt', 'r') as f:
            moje_typy = f.read()
    except FileNotFoundError:
        print("Nie znaleziono pliku z typami.")
        return

    prompt = f"""
    Dzisiejsza data (NBA Time): {today}.
    Moje statystyczne typy na dzisiaj to:
    {moje_typy}

    Zadanie:
    1. Przeszukaj internet (NBA Injury Reports, Twitter/X, ESPN) pod kątem nagłych kontuzji lub 'load management' na dzień {today}.
    2. Sprawdź, czy kluczowi zawodnicy (Top 3 punktujących drużyny) grają w tych meczach.
    3. Jeśli mój typ jest zagrożony (np. gwiazda nie gra), napisz: [⚠️ RYZYKOWNY - powód].
    4. Jeśli wszystko wygląda dobrze, napisz: [✅ ZATWIERDZONY].
    5. Na końcu wybierz 2 "Najpewniejsze Typy Dnia" (Best Bets).
    
    Odpowiadaj po polsku.
    """

    response = model.generate_content(prompt)
    
    # 3. Zapisanie raportu końcowego
    with open('finalny_raport_dnia.txt', 'w', encoding='utf-8') as f:
        f.write(f"--- ANALIZA GEMINI NA DZIEŃ {today} ---\n")
        f.write(response.text)
    
    print("Analiza zakończona. Sprawdź finalny_raport_dnia.txt")

if __name__ == "__main__":
    audit_typow()
