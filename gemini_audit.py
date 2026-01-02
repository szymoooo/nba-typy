from google import genai
from google.genai import types
import os
import datetime
import pytz
import re

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

    if not typy or len(typy.strip()) < 5:
        print("Brak typów do analizy.")
        return

    # INSTRUKCJA SYSTEMOWA - BLOKADA HALUCYNACJI
    system_instruction = f"""
    Jesteś rygorystycznym analitykiem NBA. Twoja wiedza wewnętrzna jest przestarzała. 
    DZISIEJSZA DATA TO: {today_date}.
    
    ZASADY:
    1. UŻYWAJ WYŁĄCZNIE narzędzia Google Search do sprawdzenia aktualnych składów. 
    2. IGNORUJ dane z lat 2024, 2025. Interesuje Cię tylko STYCZEŃ 2026.
    3. Jeśli nie znajdziesz potwierdzonych informacji o kontuzjach z DZISIAJ ({today_date}), napisz 'Brak aktualnych raportów (Injury Report) na tę chwilę'. 
    4. NIE ZGADUJ. Sprawdzaj statusy: 'Out', 'Questionable', 'GTD'.
    5. Odpowiadaj krótko, w punktach.
    """

    prompt = f"""
    Na podstawie DZISIEJSZYCH danych z sieci ({today_date}), sprawdź moje typy:
    {typy}

    Dla każdego meczu określ:
    - Kluczowe braki w składach.
    - Werdykt: [✅ ZATWIERDZONY] lub [⚠️ RYZYKOWNY].
    """

    print(f"🚀 Uruchamiam rygorystyczny audyt live ({today_date})...")

    try:
        # Zmieniamy na 1.5-flash (stabilniejszy darmowy limit) i poprawiamy Tool
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        
        tekst_analizy = response.text
    except Exception as e:
        print(f"Błąd API Gemini: {e}")
        return

    # Zapis do pliku tekstowego
    with open('finalny_raport_dnia.txt', 'w', encoding='utf-8') as f:
        f.write(f"--- KRYTYCZNY AUDYT LIVE ({today_date} {current_time} ET) ---\n")
        f.write(tekst_analizy)

    # Wstrzykiwanie do HTML
    if os.path.exists('index.html'):
        try:
            with open('index.html', 'r', encoding='utf-8') as f:
                html_content = f.read()

            formatowany_tekst = tekst_analizy.replace('\n', '<br>')
            
            # Unikalne znaczniki, żeby skrypt mógł podmieniać raport, a nie dodawać nowe
            start_tag = ""
            end_tag = ""
            
            analiza_html = f"""
            {start_tag}
            <div class="container" style="margin-top: 40px; margin-bottom: 40px;">
                <div style="background: #0f172a; border: 2px solid #ef4444; border-radius: 20px; padding: 30px; box-shadow: 0 0 20px rgba(239, 68, 68, 0.2);">
                    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
                        <span style="font-size: 2rem;">🛡️</span>
                        <h2 style="margin: 0; font-weight: 900; color: #ef4444; text-transform: uppercase; font-family: 'Montserrat', sans-serif;">Weryfikator Składów AI (LIVE 2026)</h2>
                    </div>
                    <div style="color: #94a3b8; font-size: 0.8rem; border-bottom: 1px solid #334155; padding-bottom: 10px; margin-bottom: 20px; font-family: 'Montserrat', sans-serif;">
                        DANE Z DNIA: {today_date} | STATUS: Google Search Live
                    </div>
                    <div style="color: #f8fafc; line-height: 1.8; font-family: 'Montserrat', sans-serif;">
                        {formatowany_tekst}
                    </div>
                </div>
            </div>
            {end_tag}
            """

            # Jeśli raport już istnieje, podmiana. Jeśli nie, wstawienie przed </body>
            if start_tag in html_content:
                html_content = re.sub(f'{start_tag}.*?{end_tag}', analiza_html, html_content, flags=re.DOTALL)
            else:
                html_content = html_content.replace('</body>', analiza_html + '</body>')

            with open('index.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print("✅ Raport dodany do index.html")
        except Exception as e:
            print(f"Błąd HTML: {e}")
    
    print("✅ Audyt zakończony sukcesem.")

if __name__ == "__main__":
    run_audit()
