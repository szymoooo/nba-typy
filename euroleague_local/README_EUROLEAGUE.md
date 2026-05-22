# EuroLeague Free Picks - Lokalny MVP

Eksperymentalna wersja `nba-typy` dostosowana do **EuroLeague**.
Działa **całkowicie lokalnie**, nie ingeruje w działającą stronę NBA.

## Co to robi

1. Pobiera terminarz i tabelę EuroLeague z oficjalnego, darmowego API
   ([api-live.euroleague.net](https://api-live.euroleague.net))
2. Filtruje mecze na dziś
3. **Typuje zwycięzcę** — domyślnie **AI Gemini z Google Search**
   analizuje formę, head-to-head, kontuzje, specyfikę fazy.
   Fallback: formuła W-L gdy brak klucza/AI niedostępne.
4. Generuje statyczny `output/index.html` w identycznym stylu jak NBA
5. (Opcjonalnie) Drugi pass Gemini sprawdza składy i wstrzykuje raport

## Wymagania

```bash
pip install requests pytz google-generativeai
```

> Pakiet `google-generativeai` potrzebny do AI prediction i audytu kontuzji.
> Bez niego skrypt nadal działa, używa formuły W-L.

## Krok 1: Wygeneruj stronę

### Tryb AI (rekomendowany) — Gemini analizuje każdy mecz

```bash
cd euroleague_local
export GEMINI_API_KEY=twoj_klucz_z_aistudio
python update_euroleague.py
```

Output:

```
   Tryb predykcji: AI (gemini-1.5-flash + Google Search)
...
   [AI] Real Madrid vs Valencia Basket -> Real Madrid (conf 7/10)
   [AI] Olympiacos vs Fenerbahce -> Olympiacos (conf 8/10)
```

Pełne analizy AI (uzasadnienia, key factors) zapisują się do
**`output/ai_analyses.json`** — strona pokazuje **tylko nazwę zespołu**.

### Tryb formuła (bez AI)

```bash
unset GEMINI_API_KEY  # albo zmień USE_AI_PREDICTIONS=False w skrypcie
python update_euroleague.py
```

Output:

```
   Tryb predykcji: FORMULA W-L (brak GEMINI_API_KEY)
```

## Krok 2 (opcjonalnie): Audyt składów

```bash
python euroleague_audit.py
```

Pod meczami pojawi się sekcja `EuroLeague Lineup Audit AI`
z weryfikacją kontuzji dla każdego typu (✅/⚠️).

## Co się gdzie zapisuje

```
output/
├── index.html                  # WYNIK - otwórz w przeglądarce
├── propozycje_typow.txt        # input dla audytu kontuzji
├── ai_analyses.json            # PEŁNE analizy AI (reasoning, confidence,
│                                 key_factors) - tylko dla developera
├── debug_games_*.json          # surowy dump z API (debug)
├── debug_standings_*.xml       # tabela XML (debug)
└── finalny_raport_dnia.txt     # backup raportu Gemini z audytu
```

**Strona pokazuje tylko nazwę zwycięzcy.** Reasoning, confidence i key factors
trafiają wyłącznie do `ai_analyses.json` — zaglądnij tam żeby zobaczyć
co Gemini myślało o każdym meczu.

## Limity Gemini free tier

- 15 requestów na minutę (RPM)
- 1500 requestów dziennie
- W 1 dniu EuroLeague max ~10 meczów → spokojnie się mieścimy
- Skrypt robi `time.sleep(1)` między meczami żeby nie przekroczyć RPM

## Co dostosować

| Co | Gdzie |
|---|---|
| Wyłącz AI, zostaw formułę W-L | `USE_AI_PREDICTIONS = False` w `update_euroleague.py` |
| Zmień model Gemini | `AI_MODEL = "gemini-1.5-pro"` (lepszy, ale wolniejszy/droższy) |
| Sezon (po skończeniu) | `SEASON_CODE = "E2026"` |
| EuroCup zamiast EuroLeague | `COMPETITION = "U"` |

## Co dalej

Po działającym MVP:
1. Przeniesiemy do osobnego repo `euroleague-typy` lub deploy `/euroleague/` na nba-freepicks.com
2. GitHub Actions co X minut (jak `daily_update.yml` w nba-typy)
3. Powielenie schematu dla EuroCup, ACB (Hiszpania), PLK
