from google import genai
from google.genai import types
import os
import datetime
import pytz
import re

# Konfiguracja klienta
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def run_audit():
    # Pobieranie precyzyjnego czasu systemowego (NBA Eastern Time)
    nba_tz = pytz.timezone('US/Eastern')
    now = datetime.datetime.now(nba_tz)
    today_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    # Sprawdzenie czy plik z typami istnieje
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
    5. Odpowiadaj krótko, w punktach, używaj emoji.
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
        # Wywołanie modelu Gemini 1.5 Flash (stabilne limity darmowe)
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

    # Zapis do pliku tekstowego (backup)
    with open('finalny_raport_dnia.txt', 'w', encoding='utf-8') as f:
        f.write(f"--- KRYTYCZNY AUDYT LIVE ({today_date} {current_time} ET) ---\n")
        f.write(tekst_analizy)

    # Wstrzykiwanie do HTML
    if os.path.exists('index.html'):
        try:
            with open('index.html', 'r', encoding='utf-8') as f:
                html_content = f.read()

            formatowany_tekst = tekst_analizy.replace('\n', '<br>')
            
            # UNIKALNE ZNACZNIKI DLA REGEX
            start_tag = ""
            end_tag = ""
            
            analiza_html = f"""{start_tag}
            <div style="margin: 40px auto; max-width: 1100px; padding: 0 20px;">
                <div style="background: #0f172a; border: 2px solid #ef4444; border-radius: 20px; padding: 30px; box-shadow: 0 0 25px rgba(239, 68, 68, 0.15); border-left: 10px solid #ef4444;">
                    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
                        <span style="font-size: 2.5rem;">🛡️</span>
                        <div>
                            <h2 style="margin: 0; font-weight: 900; color: #ef4444; text-transform: uppercase; font-family: 'Montserrat', sans-serif; letter-spacing: -1px;">Weryfikator Składów AI</h2>
                            <div style="color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; font-family: 'Montserrat', sans-serif;">
                                STATUS: Google Search Live | {today_date} {current_time} ET
                            </div>
                        </div>
                    </div>
                    <div style="color: #f8fafc; line-height: 1.8; font-family: 'Montserrat', sans-serif; font-size: 1rem; background: rgba(0,0,0,0.2); padding: 20px; border-radius: 12px; border: 1px dashed #334155;">
                        {formatowany_tekst}
                    </div>
                    <div style="margin-top: 15px; text-align: right; color: #475569; font-size: 0.65rem; font-family: 'Montserrat', sans-serif; font-weight: 700;">
                        AI AGENT ENFORCEMENT v2.0
                    </div>
                </div>
            </div>{end_tag}"""

            # Jeśli raport już istnieje, podmieniamy go. Jeśli nie, wstawiamy przed footerem.
            if start_tag in html_content:
                # re.escape chroni znaki specjalne w tagach komentarza
                pattern = f"{re.escape(start_tag)}.*?{re.escape(end_tag)}"
                html_content = re.sub(pattern, analiza_html, html_content, flags=re.DOTALL)
            else:
                # Jeśli to pierwsze uruchomienie, wstawiamy nad stopkę
                if '<div class="footer">' in html_content:
                    html_content = html_content.replace('<div class="footer">', analiza_html + '<div class="footer">')
                else:
                    html_content = html_content.replace('</body>', analiza_html + '</body>')

            with open('index.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print("✅ Raport pomyślnie wstrzyknięty do index.html")
        except Exception as e:
            print(f"Błąd podczas edycji HTML: {e}")
    
    print("✅ Audyt zakończony sukcesem.")

if __name__ == "__main__":
    run_audit()
