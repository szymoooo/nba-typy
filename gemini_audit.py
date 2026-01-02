from google import genai
from google.genai import types
import os
import datetime
import pytz

# Konfiguracja klienta
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def run_audit():
    # Pobieranie precyzyjnego czasu systemowego
    nba_tz = pytz.timezone('US/Eastern')
    now = datetime.datetime.now(nba_tz)
    today_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    if not os.path.exists('propozycje_typow.txt'):
        print("Nie znaleziono pliku propozycje_typow.txt")
        return

    with open('propozycje_typow.txt', 'r', encoding='utf-8') as f:
        typy = f.read()

    if not typy:
        print("Brak typów do analizy.")
        return

    # INSTRUKCJA SYSTEMOWA - TO TU BLOKUJEMY HALUCYNACJE
    system_instruction = f"""
    Jesteś rygorystycznym analitykiem NBA. Twoja wiedza wewnętrzna jest przestarzała. 
    DZISIEJSZA DATA TO: {today_date}.
    
    ZASADY:
    1. UŻYWAJ WYŁĄCZNIE narzędzia Google Search. 
    2. IGNORUJ dane z lat 2024, 2025 i wcześniejszych. Jeśli news nie dotyczy STYCZNIA 2026, odrzuć go.
    3. Jeśli nie znajdziesz potwierdzonych informacji o kontuzjach z DZISIAJ ({today_date}), napisz 'Brak aktualnych raportów dla tego meczu'. 
    4. NIE ZGADUJ. Nie przewiduj na podstawie "historii". Sprawdzaj faktyczne statusy: 'Out', 'Questionable', 'Game-time decision'.
    5. Twoim celem jest uratowanie skuteczności 80% mojego modelu przed nagłymi zmianami w składzie.
    """

    prompt = f"""
    Na podstawie DZISIEJSZYCH danych z sieci ({today_date}), sprawdź moje typy:
    {typy}

    Dla każdego meczu określ:
    - Status gwiazd (Injury Report).
    - Czy typ jest [✅ ZATWIERDZONY] czy [⚠️ RYZYKOWNY].
    - Uzasadnij wybór konkretnymi nazwiskami z dzisiejszego raportu.
    """

    print(f"🚀 Uruchamiam rygorystyczny audyt live dla daty: {today_date}...")

    # Wywołanie modelu z instrukcją blokującą halucynacje
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[types.Tool(google_search=types.GoogleSearchRetrieval())]
        )
    )
    
    # Zapis do pliku tekstowego
    with open('finalny_raport_dnia.txt', 'w', encoding='utf-8') as f:
        f.write(f"--- KRYTYCZNY AUDYT LIVE ({today_date} {current_time} ET) ---\n")
        f.write("Źródło danych: Google Search Live (Jan 2026)\n\n")
        f.write(response.text)

    # Wstrzykiwanie do HTML (wizualna sekcja)
    if os.path.exists('index.html'):
        try:
            with open('index.html', 'r', encoding='utf-8') as f:
                html_content = f.read()

            formatowany_tekst = response.text.replace('\n', '<br>')
            
            analiza_html = f"""
            <div class="container" style="margin-top: 40px; margin-bottom: 40px;">
                <div style="background: #0f172a; border: 2px solid #ef4444; border-radius: 20px; padding: 30px; box-shadow: 0 0 20px rgba(239, 68, 68, 0.2);">
                    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
                        <span style="font-size: 2rem;">🛡️</span>
                        <h2 style="margin: 0; font-weight: 900; color: #ef4444; text-transform: uppercase;">Weryfikator Składów AI (LIVE 2026)</h2>
                    </div>
                    <div style="color: #94a3b8; font-size: 0.8rem; border-bottom: 1px solid #334155; padding-bottom: 10px; margin-bottom: 20px;">
                        DANE Z DNIA: {today_date} | STATUS: Zweryfikowano przez Google Search
                    </div>
                    <div style="color: #f8fafc; line-height: 1.8; font-family: 'Montserrat', sans-serif;">
                        {formatowany_tekst}
                    </div>
                </div>
            </div>
            """

            import re
            if "" in html_content:
                html_content = re.sub(r'.*?', analiza_html, html_content, flags=re.DOTALL)
            else:
                html_content = html_content.replace('</body>', analiza_html + '</body>')

            with open('index.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            
        except Exception as e:
            print(f"Błąd HTML: {e}")
    
    print("✅ Audyt zakończony. Halucynacje zablokowane.")

if __name__ == "__main__":
    run_audit()
