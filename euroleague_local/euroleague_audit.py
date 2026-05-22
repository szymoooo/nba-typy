"""
EuroLeague AI Audit (Gemini + Google Search).

Klon gemini_audit.py - sprawdza składy/kontuzje na dziś dla typów EuroLeague
i wstrzykuje raport do output/index.html.

URUCHOMIENIE:
    export GEMINI_API_KEY=...
    python euroleague_audit.py
"""

from google import genai
from google.genai import types
import os
import datetime
import pytz
import re

OUTPUT_DIR = "output"
INDEX_PATH = os.path.join(OUTPUT_DIR, "index.html")
PICKS_PATH = os.path.join(OUTPUT_DIR, "propozycje_typow.txt")

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def run_audit():
    # CET/CEST - kontekst europejski
    eu_tz = pytz.timezone("Europe/Madrid")
    now = datetime.datetime.now(eu_tz)
    today_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    if not os.path.exists(PICKS_PATH):
        print(f"Nie znaleziono {PICKS_PATH}. Uruchom najpierw update_euroleague.py.")
        return

    with open(PICKS_PATH, "r", encoding="utf-8") as f:
        typy = f.read()

    if not typy or len(typy.strip()) < 5:
        print("Brak typow do analizy.")
        return

    system_instruction = f"""
    Jestes rygorystycznym analitykiem koszykarskiej EuroLeague.
    Twoja wiedza wewnetrzna jest przestarzala.
    DZISIEJSZA DATA TO: {today_date}.

    ZASADY:
    1. UZYWAJ WYLACZNIE narzedzia Google Search do sprawdzenia aktualnych skladow.
    2. IGNORUJ dane sprzed sezonu 2025-26. Interesuje Cie {today_date}.
    3. Sprawdzaj zrodla: euroleaguebasketball.net, oficjalne profile klubow,
       sport.pl, eurohoops.net, basketnews.com, twitter klubow.
    4. Jesli nie znajdziesz potwierdzonych informacji o kontuzjach z DZISIAJ ({today_date}),
       napisz "Brak aktualnych raportow o brakach w skladzie".
    5. NIE ZGADUJ. Sprawdzaj statusy: kontuzja (injured), niedyspozycja, zawieszenie.
    6. Odpowiadaj krotko, w punktach, uzywaj emoji.
    """

    prompt = f"""
    Na podstawie DZISIEJSZYCH danych z sieci ({today_date}), sprawdz moje typy EuroLeague:
    {typy}

    Dla kazdego meczu okresl:
    - Kluczowe braki w skladach (kontuzje, brak w kadrze, zawieszenie).
    - Werdykt: [\u2705 ZATWIERDZONY] lub [\u26a0\ufe0f RYZYKOWNY].
    """

    print(f"Uruchamiam rygorystyczny audyt EuroLeague live ({today_date})...")

    try:
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
        print(f"Blad API Gemini: {e}")
        return

    # Backup raportu
    raport_path = os.path.join(OUTPUT_DIR, "finalny_raport_dnia.txt")
    with open(raport_path, "w", encoding="utf-8") as f:
        f.write(f"--- AUDYT EUROLEAGUE LIVE ({today_date} {current_time} CET) ---\n")
        f.write(tekst_analizy)
    print(f"Zapisano backup: {raport_path}")

    # Wstrzykiwanie do HTML
    if not os.path.exists(INDEX_PATH):
        print(f"Brak {INDEX_PATH}, pomijam wstrzyk HTML.")
        return

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()

    formatowany_tekst = tekst_analizy.replace("\n", "<br>")
    start_tag = "<!--AI_AUDIT_START-->"
    end_tag = "<!--AI_AUDIT_END-->"

    analiza_html = f"""{start_tag}
        <div style="margin: 40px auto; max-width: 1100px; padding: 0 20px;">
            <div style="background: #0f172a; border: 2px solid #ff6600; border-radius: 20px; padding: 30px; box-shadow: 0 0 25px rgba(255, 102, 0, 0.18); border-left: 10px solid #ff6600;">
                <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
                    <span style="font-size: 2.5rem;">\U0001f6e1\ufe0f</span>
                    <div>
                        <h2 style="margin: 0; font-weight: 900; color: #ff6600; text-transform: uppercase; font-family: 'Montserrat', sans-serif; letter-spacing: -1px;">EuroLeague Lineup Audit AI</h2>
                        <div style="color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; font-family: 'Montserrat', sans-serif;">
                            STATUS: Google Search Live | {today_date} {current_time} CET
                        </div>
                    </div>
                </div>
                <div style="color: #f8fafc; line-height: 1.8; font-family: 'Montserrat', sans-serif; font-size: 1rem; background: rgba(0,0,0,0.2); padding: 20px; border-radius: 12px; border: 1px dashed #334155;">
                    {formatowany_tekst}
                </div>
                <div style="margin-top: 15px; text-align: right; color: #475569; font-size: 0.65rem; font-family: 'Montserrat', sans-serif; font-weight: 700;">
                    AI AGENT ENFORCEMENT v2.0 - EUROLEAGUE
                </div>
            </div>
        </div>{end_tag}"""

    if start_tag in html_content:
        pattern = f"{re.escape(start_tag)}.*?{re.escape(end_tag)}"
        html_content = re.sub(pattern, analiza_html, html_content, flags=re.DOTALL)
    else:
        if '<div class="footer">' in html_content:
            html_content = html_content.replace('<div class="footer">', analiza_html + '<div class="footer">')
        else:
            html_content = html_content.replace("</body>", analiza_html + "</body>")

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Raport wstrzyknieto do {INDEX_PATH}")
    print("Audyt zakonczony sukcesem.")


if __name__ == "__main__":
    run_audit()
