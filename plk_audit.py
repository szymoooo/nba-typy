"""
PLK AI Audit (Gemini + Google Search) - v2 z bogatym kontekstem PulsBasketu.

Klon euroleague_audit.py + integracja z plk_data.py. Eliminuje halucynacje typu
"Hala Orbita w Wroclawiu" gdy mecz jest gdzie indziej - przekazuje AI:
  - arena, city (z game.arena/city w PulsBasketu)
  - stage_name + round_name (faza i runda)
  - sedziowie
  - stan serii playoff (np. "Slask 2-2 Arka, decydujacy mecz 5")
  - top scorerow W TEJ SERII (z /playoff-series/{id}/players/stat-lines)

URUCHOMIENIE:
    export GEMINI_API_KEY=...
    python plk_audit.py
"""

import os
import datetime
import re

import pytz
from google import genai
from google.genai import types

import plk_data as pb


OUTPUT_DIR = "plk"
INDEX_PATH = os.path.join(OUTPUT_DIR, "index.html")
PICKS_PATH = os.path.join(OUTPUT_DIR, "propozycje_typow.txt")
RAPORT_PATH = os.path.join(OUTPUT_DIR, "finalny_raport_dnia.txt")

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


# ==========================================
# KONTEKST MECZU - z PulsBasketu
# ==========================================

def _format_series_history(series_meta, all_games, h_id, a_id, h_name, a_name):
    """Buduje chronologiczna liste meczow w serii z wynikami."""
    if not h_id or not a_id:
        return ""
    # filtruj wszystkie mecze tej dwojki w playoffach (zakonczone)
    playoff_games = []
    for g in all_games:
        gh = (g.get("home_team") or {}).get("team_id")
        ga = (g.get("away_team") or {}).get("team_id")
        if {gh, ga} == {h_id, a_id} and (g.get("stage_name") or "").lower() not in ("runda zasadnicza", ""):
            playoff_games.append(g)
    playoff_games.sort(key=lambda g: g.get("date") or "")

    if not playoff_games:
        return "  (brak danych z playoff-series w API)"

    lines = []
    a_wins = b_wins = 0  # a = away_id, b = home_id
    for g in playoff_games:
        if not g.get("finished"):
            continue
        h = g.get("home_team") or {}
        a = g.get("away_team") or {}
        h_score = int(h.get("score", 0) or 0)
        a_score = int(a.get("score", 0) or 0)
        if h_score == 0 and a_score == 0:
            continue
        winner_id = h.get("team_id") if h_score > a_score else a.get("team_id")
        date = g.get("day") or (g.get("date") or "")[:10]
        rnd = g.get("round_name") or ""
        winner = h.get("name") if winner_id == h.get("team_id") else a.get("name")
        lines.append(f"  - {date} ({rnd}) w {g.get('city') or '?'}: "
                     f"{a.get('name', '?')} {a_score}-{h_score} {h.get('name', '?')} -> wygral {winner}")
        if winner_id == a_id:
            a_wins += 1
        elif winner_id == h_id:
            b_wins += 1

    summary = f"  STAN SERII: {a_name} {a_wins}-{b_wins} {h_name}"
    return summary + "\n" + "\n".join(lines)


def _format_series_top_scorers(series_id, h_id, a_id, h_name, a_name):
    """Per-player avg W SERII - wskazuje kto sie rozkreca, kto wypadl."""
    stats = pb.fetch_series_player_stats(series_id, stat_type="avg") if series_id else None
    if not stats:
        return ("  (brak danych /playoff-series/{id}/players/stat-lines - "
                "moze 403 z naszego IP, sprawdz przez Google Search)")

    h_top = pb.get_top_scorers_in_series(stats, h_id, 3)
    a_top = pb.get_top_scorers_in_series(stats, a_id, 3)

    lines = [f"  {h_name}:"]
    for s in h_top or [{"name": "(brak danych)", "ppg": 0}]:
        bits = [f"{s['name']}: {s['ppg']} ppg w serii"]
        if s.get("apg"):
            bits.append(f"{s['apg']} apg")
        if s.get("rpg"):
            bits.append(f"{s['rpg']} rpg")
        if s.get("fouls"):
            bits.append(f"{s['fouls']} fauli/mecz")
        lines.append("    - " + ", ".join(bits))
    lines.append(f"  {a_name}:")
    for s in a_top or [{"name": "(brak danych)", "ppg": 0}]:
        bits = [f"{s['name']}: {s['ppg']} ppg w serii"]
        if s.get("apg"):
            bits.append(f"{s['apg']} apg")
        if s.get("rpg"):
            bits.append(f"{s['rpg']} rpg")
        if s.get("fouls"):
            bits.append(f"{s['fouls']} fauli/mecz")
        lines.append("    - " + ", ".join(bits))
    return "\n".join(lines)


def build_match_context_block(game, all_games, all_series=None):
    """Buduje fragment promptu z bogatym kontekstem dla jednego meczu.
    To ten "konkret z PulsBasketu" zamiast halucynacji AI."""
    home = game.get("home_team") or {}
    away = game.get("away_team") or {}
    h_name = home.get("name", "?")
    a_name = away.get("name", "?")
    h_id = home.get("team_id")
    a_id = away.get("team_id")

    arena = game.get("arena") or "?"
    city = game.get("city") or "?"
    stage = game.get("stage_name") or "?"
    rnd = game.get("round_name") or ""
    hour = game.get("hour") or pb.fmt_game_time(game)
    referees = game.get("referees") or []
    ref_str = ", ".join(referees) if referees else "brak danych"

    is_playoff = stage.lower() not in ("runda zasadnicza", "")

    block = f"""
=========================================================================
MECZ: {a_name} (gosc) @ {h_name} (gospodarz)
=========================================================================
Faza:    {stage}
Runda:   {rnd}
Hala:    {arena}, {city}    <-- KONKRETNE MIEJSCE Z PULSBASKETU, NIE ZGADUJ
Tip-off: {hour}
Sedziowie: {ref_str}
"""

    if is_playoff:
        # spróbuj znaleźć series_id dla tej pary
        series_id, series_meta = pb.find_series_for_match(game, all_series)
        if series_id:
            block += f"\nSERIA PLAYOFF #{series_id}:\n"
            block += _format_series_history(series_meta, all_games, h_id, a_id, h_name, a_name)
            block += "\n\nTOP SCORERZY W TEJ SERII (per-player avg z /playoff-series/" \
                     f"{series_id}/players/stat-lines):\n"
            block += _format_series_top_scorers(series_id, h_id, a_id, h_name, a_name)
        else:
            block += "\nSERIA PLAYOFF: nie udalo sie zmapowac z /playoff-series. " \
                     "Polegaj na chronologii meczow z games-list:\n"
            block += _format_series_history(None, all_games, h_id, a_id, h_name, a_name)

    return block


# ==========================================
# MAIN
# ==========================================

def run_audit():
    pl_tz = pytz.timezone("Europe/Warsaw")
    now = datetime.datetime.now(pl_tz)
    today_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    if not os.path.exists(PICKS_PATH):
        print(f"Nie znaleziono {PICKS_PATH}. Uruchom najpierw update_plk.py.")
        return

    with open(PICKS_PATH, "r", encoding="utf-8") as f:
        typy = f.read()

    if not typy or len(typy.strip()) < 5:
        print("Brak typow do analizy.")
        return

    # ===== POBIERZ KONTEKST Z PULSBASKETU =====
    print(f"=> Wzbogacam audyt o kontekst z PulsBasketu:")
    all_games = pb.fetch_games_list()
    today_games = pb.filter_games_for_date(all_games, today_date) if all_games else []
    all_series = pb.fetch_playoff_series_list() or []

    if not today_games:
        print(f"   Brak dzisiejszych meczow w PulsBasketu - audyt pojdzie z gołym tekstem typow.")
        match_contexts = ""
    else:
        print(f"   {len(today_games)} mecz(y) na dzis - buduje kontekst:")
        contexts = []
        for g in today_games:
            ctx = build_match_context_block(g, all_games, all_series)
            contexts.append(ctx)
            print(f"     - {(g.get('away_team') or {}).get('name', '?')} @ "
                  f"{(g.get('home_team') or {}).get('name', '?')}: "
                  f"{g.get('arena', '?')}, {g.get('city', '?')}")
        match_contexts = "\n".join(contexts)

    # ===== PROMPT =====
    system_instruction = f"""
    Jestes rygorystycznym analitykiem polskiej PLK (Orlen Basket Liga).
    Twoja wiedza wewnetrzna jest przestarzala.
    DZISIEJSZA DATA TO: {today_date}.

    ZASADY:
    1. UZYWAJ WYLACZNIE narzedzia Google Search do sprawdzenia aktualnych skladow
       i kontuzji.
    2. IGNORUJ dane sprzed sezonu 2025-26. Interesuje Cie {today_date}.
    3. Sprawdzaj zrodla: plk.pl, polskikosz.pl, sportowefakty.wp.pl,
       sport.pl/koszykowka, eurosport.pl, oficjalne profile klubow PLK na X/Twitter,
       lokalne portale (np. nto.pl, gloswielkopolski.pl).
    4. **WAZNE: Hala i miasto meczu sa podane w sekcji KONTEKST. NIE WYMYSLAJ ich.**
       Jezeli kontekst mowi "Hala Orbita, Wroclaw" - to JEST tam mecz, nie pisz inaczej.
    5. Jesli nie znajdziesz potwierdzonych informacji o kontuzjach z DZISIAJ ({today_date}),
       napisz "Brak aktualnych raportow o brakach w skladzie".
    6. NIE ZGADUJ. Sprawdzaj statusy: kontuzja (uraz/injured), niedyspozycja, zawieszenie.
    7. Odpowiadaj krotko, w punktach, uzywaj emoji.
    """

    prompt = f"""
KONTEKST DZISIEJSZYCH MECZOW (dane z PulsBasketu - to fakty, nie zgaduj):
{match_contexts}

=========================================================================
TYPY DO AUDYTU:
=========================================================================
{typy}

=========================================================================
ZADANIE
=========================================================================
Dla kazdego meczu okresl:
  1. Kluczowe braki w skladach (kontuzje, brak w kadrze, zawieszenie, foul-out
     z poprzedniego meczu serii) - sprawdz Google Search.
  2. Aktualna forma top scorerow (jezeli mam dane W SERII powyzej, uwzglednij je).
  3. Werdykt: [✅ ZATWIERDZONY] albo [⚠️ RYZYKOWNY].

PAMIETAJ:
  - Hala/miasto z KONTEKSTU = fakt, nie zmieniaj.
  - Faza play-off + decydujacy mecz (np. mecz 5/5 lub 7/7) = wieksza waga
    przewagi wlasnego parkietu i kontuzji liderow.
"""

    print(f"\nUruchamiam rygorystyczny audyt PLK ({today_date})...")

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
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

    # ===== ZAPIS BACKUP =====
    with open(RAPORT_PATH, "w", encoding="utf-8") as f:
        f.write(f"--- AUDYT PLK LIVE ({today_date} {current_time} CET) ---\n")
        f.write(tekst_analizy)
    print(f"Zapisano backup: {RAPORT_PATH}")

    # ===== WSTRZYK DO HTML =====
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
            <div style="background: #0f172a; border: 2px solid #dc2626; border-radius: 20px; padding: 30px; box-shadow: 0 0 25px rgba(220, 38, 38, 0.18); border-left: 10px solid #dc2626;">
                <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
                    <span style="font-size: 2.5rem;">\U0001f6e1\ufe0f</span>
                    <div>
                        <h2 style="margin: 0; font-weight: 900; color: #dc2626; text-transform: uppercase; font-family: 'Montserrat', sans-serif; letter-spacing: -1px;">PLK Lineup Audit AI</h2>
                        <div style="color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; font-family: 'Montserrat', sans-serif;">
                            STATUS: Google Search Live + PulsBasketu | {today_date} {current_time} CET
                        </div>
                    </div>
                </div>
                <div style="color: #f8fafc; line-height: 1.8; font-family: 'Montserrat', sans-serif; font-size: 1rem; background: rgba(0,0,0,0.2); padding: 20px; border-radius: 12px; border: 1px dashed #334155;">
                    {formatowany_tekst}
                </div>
                <div style="margin-top: 15px; text-align: right; color: #475569; font-size: 0.65rem; font-family: 'Montserrat', sans-serif; font-weight: 700;">
                    AI AGENT ENFORCEMENT v2.1 - PLK + Series Context
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
