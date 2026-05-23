# PLK Local Debug

Wersja lokalna dla zakladki **PLK** (Orlen Basket Liga). Sluzy do
ustalenia dlaczego `plk/index.html` na produkcji pokazuje
"Brak meczow PLK na dzis" i czy zrodlo (Sofascore Public API) faktycznie
nie ma meczu, czy cos sie sypie po drodze.

Wszystko jest zaprojektowane do uruchamiania w **terminalu**, bez
GitHub Actions, bez Gemini, bez kluczy API.

## Pliki

- `plk_debug.py`  - czysty diagnostyk. Tylko stdout, bez HTML, bez AI.
  Pokazuje: liste sezonow, wybor sezonu, najblizsze mecze, ostatnie
  mecze, mecze na dzis, najblizsze N w czasie. Dumpuje JSON-y.
- `plk_local.py`  - lokalny generator. Tworzy `plk_local/output/index.html`
  na bazie formuly W-L (zero AI). Jak nie ma meczow na dzis - dokleja
  liste 8 najblizszych meczow w sezonie (zeby bylo wiadomo co jest blisko).
- `_debug/`       - dumpy JSON ze wszystkich endpointow Sofascore.
- `output/`       - lokalna strona PLK (otwierasz w przegladarce).

## Wymagania

- Python 3.9+
- `pip install requests`
- Internet (Sofascore API)
- **NIE** wymaga `GEMINI_API_KEY`

## Quick start

```bash
# 1. krok diagnostyczny - czysto w terminalu
python plk_local/plk_debug.py

# 2. krok wizualny - generuje HTML
python plk_local/plk_local.py

# 3. otworz w przegladarce (jeden z trzech, zaleznie od OS)
open plk_local/output/index.html        # macOS
xdg-open plk_local/output/index.html    # Linux
start plk_local\output\index.html       # Windows
```

## Co czytac w wyniku `plk_debug.py`

Skrypt drukuje 4 sekcje:

1. **Lista sezonow** - powinno byc widac sezon 2025/26 (lub najnowszy).
   Jesli wybrany sezon to cos z lat poprzednich - mamy bug w wyborze
   sezonu w `update_plk.py` (logika `fetch_current_season_id`).

2. **events/next/0** - ile meczow nadchodzacych zwraca API. W srodku
   sezonu/playoffow powinno byc kilka. W finalach moze byc 1-2. Jesli
   `0` w sezonie 25/26 - cos jest nie tak.

3. **events/last/0** - ostatnie rozegrane. Sluzy do potwierdzenia, ze
   API w ogole odpowiada na ten sezon.

4. **Filtrowanie na dzis** - werdykt:
   - znaleziono mecze -> zrodlo OK, mozesz odpalic produkcyjny
     `python update_plk.py` z roota repo
   - 0 dopasowan + najblizsze mecze sa za 1-3 dni -> normalny off-day
     w lidze, strona slusznie pokazuje pustke
   - 0 dopasowan + najblizsze mecze >30 dni / ostatnie >30 dni temu
     -> bug w wyborze sezonu albo Sofascore zablokowal

## Jak interpretowac brak meczow

PLK rozgrywa zwykle co 2-3 dni, w playoffs co 2 dni. To NORMALNE, ze
w danym dniu nie ma meczu. Strona produkcyjna swiadomie pokazuje wtedy
"Brak meczow" - to nie blad.

Bug bylby gdyby:
- API zwraca mecze na dzis, a strona ich nie pokazuje
- API zwraca caly sezon, a `update_plk.py` filtruje wszystko
- Sofascore odpowiada 403 / 429 i `update_plk.py` to zjada po cichu

Wszystkie te trzy przypadki `plk_debug.py` jasno wskaze.

## Jak naprawic, jesli sezon byl zly

Otworz `update_plk.py` na poziomie roota repo i edytuj funkcje
`fetch_current_season_id()` - tam jest heurystyka wyboru sezonu po
fragmencie stringa `25/26`. Jesli Sofascore podpisuje sezony inaczej
(np. `2025`, `2025/2026`), dopisz odpowiedni warunek.

Po edycji:

```bash
python plk_local/plk_debug.py     # potwierdz, ze teraz sezon sie zgadza
python update_plk.py              # uruchom produkcyjny generator
```

## Uwagi

- `output/` i `_debug/` sa w `.gitignore` - nie commituj.
- `plk_local.py` daje formula-only picki (bez Gemini); w produkcji
  jest AI, wiec wyniki mogą sie roznic (i to ok - to tylko podglad).
