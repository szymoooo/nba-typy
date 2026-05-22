# EuroLeague Free Picks - Notatka historyczna

> ⚠️ **TEN FOLDER JEST HISTORIA.**
>
> Skrypty `update_euroleague.py` i `euroleague_audit.py` zostały
> przeniesione do roota repo (obok `update_nba.py`) i piszą do
> folderu `/euroleague/` (serwowany przez GitHub Pages jako
> `nba-freepicks.com/euroleague/`).

## Jak teraz uruchomić lokalnie

Z roota repo:

```bash
export GEMINI_API_KEY=twoj_klucz   # opcjonalnie - dla AI predictions
python update_euroleague.py        # generuje euroleague/index.html
python euroleague_audit.py         # opcjonalnie - audyt skladow

open euroleague/index.html         # otworz w przegladarce
```

## Jak działa w produkcji

GitHub Actions (`.github/workflows/daily_update.yml`) odpala oba skrypty
codziennie razem z NBA. Wynik trafia do `euroleague/` w repo i jest
serwowany przez GitHub Pages.

## Co AI bierze pod uwagę

Gemini 2.5 Flash + Google Search analizuje dla każdego meczu:
- forme ostatnich 5 spotkan
- bezposrednie spotkania w sezonie
- aktualne kontuzje (Google Search live)
- specyfike fazy (Final Four != sezon zasadniczy)
- historyczne osiagniecia w tej fazie

Pelne uzasadnienia AI (reasoning, confidence, key factors) trafiają do
`euroleague/ai_analyses.json` - dla developera, na stronie pokazujemy
tylko nazwę zwycięskiej drużyny.

## Bezpiecznik

Jesli `GEMINI_API_KEY` brak / Gemini niedostepny / mecz juz sie zaczal
-> automatyczny fallback na formule W-L (jak w NBA). Strona zawsze dziala.
