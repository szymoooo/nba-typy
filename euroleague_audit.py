"""
EuroLeague AI Audit (Gemini + Google Search).

Sprawdza sklady/kontuzje na dzis dla typow EuroLeague
i wstrzykuje raport do modalu w euroleague/index.html.

URUCHOMIENIE:
    export GEMINI_API_KEY=...
    python euroleague_audit.py
"""

import os
import re
import datetime
import pytz

OUTPUT_DIR = "euroleague"
INDEX_PATH = os.path.join(OUTPUT_DIR, "index.html")
PICKS_PATH = os.path.join(OUTPUT_DIR, "propozycje_typow.txt")


def run_audit():
    if not os.environ.get("GEMINI_API_KEY"):
        print("Brak GEMINI_API_KEY - pomijam audyt EuroLeague.")
        return

    from google import genai
    from google.genai import types

    eu_tz      = pytz.timezone("Europe/Madrid")
    now        = datetime.datetime.now(eu_tz)
    today_date = now.strftime("%Y-%m-%d")
    curr_time  = now.strftime("%H:%M")

    # Sprawdz czy sa typy z dzisiaj
    if not os.path.exists(PICKS_PATH):
        print(f"Brak {PICKS_PATH} - pomijam audyt.")
        return

    with open(PICKS_PATH, "r", encoding="utf-8") as f:
        typy = f.read().strip()

    if not typy or len(typy) < 5:
        print("Brak typow do analizy.")
        return

    if today_date not in typy:
        print(f"Typy nie sa z dzisiaj ({today_date}) - pomijam audyt.")
        return

    print(f"Uruchamiam audyt EuroLeague ({today_date} {curr_time})...")

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    system_instruction = f"""
    Jestes rygorystycznym analitykiem koszykarskiej EuroLeague.
    Twoja wiedza wewnetrzna jest przestarzala.
    DZISIEJSZA DATA TO: {today_date}.

    ZASADY:
    1. UZYWAJ WYLACZNIE narzedzia Google Search do sprawdzenia aktualnych skladow.
    2. IGNORUJ dane sprzed sezonu 2025-26. Interesuje Cie {today_date}.
    3. Sprawdzaj zrodla: euroleaguebasketball.net, oficjalne profile klubow,
       eurohoops.net, basketnews.com, twitter/X klubow.
    4. Jesli nie znajdziesz potwierdzonych informacji o kontuzjach z DZISIAJ,
       napisz "Brak aktualnych raportow o brakach w skladzie".
    5. NIE ZGADUJ. Sprawdzaj statusy: injured, suspended, questionable.
    6. Odpowiadaj krotko, w punktach, uzywaj emoji.
    """

    prompt = f"""
    Na podstawie DZISIEJSZYCH danych z sieci ({today_date}), sprawdz moje typy EuroLeague:

    {typy}

    Dla kazdego meczu okresl:
    - Kluczowe braki w skladach (kontuzje, zawieszenie, brak w kadrze).
    - Werdykt: [✅ ZATWIERDZONY] lub [⚠️ RYZYKOWNY].
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        tekst = response.text
    except Exception as e:
        print(f"Blad API Gemini: {e}")
        return

    # Backup raportu
    backup = os.path.join(OUTPUT_DIR, "finalny_raport_dnia.txt")
    with open(backup, "w", encoding="utf-8") as f:
        f.write(f"--- AUDYT EUROLEAGUE ({today_date} {curr_time} CET) ---\n")
        f.write(tekst)
    print(f"Zapisano backup: {backup}")

    # Wstrzyknij do modalu przez league_ui.inject_audit
    from league_ui import inject_audit
    inject_audit(INDEX_PATH, tekst)


if __name__ == "__main__":
    run_audit()
