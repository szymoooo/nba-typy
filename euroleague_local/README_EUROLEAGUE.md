# EuroLeague Free Picks - Lokalny MVP

Eksperymentalna wersja `nba-typy` dostosowana do **EuroLeague**.
Działa **całkowicie lokalnie**, nie ingeruje w działającą stronę NBA.

## Co to robi

1. Pobiera terminarz i tabelę EuroLeague z oficjalnego, darmowego API
   ([api-live.euroleague.net](https://api-live.euroleague.net))
2. Filtruje mecze na dziś
3. Liczy typ na podstawie bilansu W-L (jak w NBA)
4. Generuje statyczny `output/index.html` w identycznym stylu jak NBA
5. (Opcjonalnie) Gemini z Google Search sprawdza składy/kontuzje
   i wstrzykuje raport do strony

## Wymagania

```bash
pip install requests pytz google-generativeai
```

> Pakiet Gemini potrzebny tylko do audytu kontuzji. Sam scraper potrzebuje tylko `requests` i `pytz`.

## Krok 1: Wygeneruj stronę

```bash
cd euroleague_local
python update_euroleague.py
```

Po sukcesie zobaczysz logi typu:

```
=== URUCHAMIAM EUROLEAGUE UPDATE (19:42) ===
   Data: 2026-05-22 (May 22, 2026)
-> Pobieram tabele EuroLeague...
   Zaladowano statystyki dla 20 druzyn
-> Pobieram terminarz EuroLeague (sezon E2025)...
   API zwrocilo 380 meczow w sezonie
   Mecze na 2026-05-22: 4
-> Zapisano output/index.html
   Zapisano 4 typow do output/propozycje_typow.txt
=== GOTOWE. Otworz output/index.html w przegladarce. ===
```

Otwórz `output/index.html` w przeglądarce - powinieneś zobaczyć siatkę meczów EuroLeague.

## Krok 2 (opcjonalnie): Audyt Gemini

```bash
export GEMINI_API_KEY=twoj_klucz_z_aistudio
python euroleague_audit.py
```

Pod meczami pojawi się sekcja `EuroLeague Lineup Audit AI`
z weryfikacją składów dla każdego typu (✅/⚠️).

## Co dostosować po pierwszym teście

| Co | Gdzie | Kiedy |
|---|---|---|
| Logo brakującej drużyny | `update_euroleague.py` -> `EUROLEAGUE_LOGOS` | Jeśli na karcie wisi pomarańczowa kulka zamiast logo |
| Mapowanie statusu API | `update_euroleague.py` -> `map_status()` | Jeśli wszystkie mecze pokazują się jako "Scheduled" mimo że są live/final |
| Strefa czasowa | `update_euroleague.py` -> `get_today_date_str()` | Jeśli "dziś" nie pasuje do prawdziwej daty meczów |
| Endpoint sezonu | `SEASON_CODE = "E2025"` | Po sezonie, na nowy: `E2026` |

## Struktura plików

```
euroleague_local/
├── update_euroleague.py    # główny skrypt, generator HTML
├── euroleague_audit.py     # audyt Gemini (kontuzje/składy)
├── README_EUROLEAGUE.md    # ten plik
└── output/
    ├── index.html          # WYNIK - otwórz w przeglądarce
    ├── propozycje_typow.txt  # input dla Gemini audit
    └── finalny_raport_dnia.txt  # backup raportu Gemini
```

## Co dalej

Po działającym MVP:
1. Przeniesiemy do osobnego repo `euroleague-typy`
2. Dodamy GitHub Actions (jak `daily_update.yml` w nba-typy)
3. Deploy na GitHub Pages + opcjonalna domena
4. Powielenie schematu dla EuroCup (jedna zmiana: `COMPETITION = "U"`)
5. Powielenie dla ACB (Hiszpania) - inny adapter API
6. Powielenie dla PLK - scraper plk.pl + strefabasketu fallback

## Znane ograniczenia

- **Brak archiwum** - MVP generuje tylko dzisiejsze mecze, bez historii.
  Jak NBA, dodamy gdy potwierdzimy że dane się zgadzają.
- **Logos jako Wikipedia URL** - prymarnie API daje crest URL,
  Wikipedia tylko jako fallback. Mogą być przerwy w niektórych klubach.
- **Brak GA4 / sitemap / robots** - bo to lokalny test, nie prod.
  Dodamy przy deploy.
