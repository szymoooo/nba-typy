"""
league_ui.py — Wspólny szablon UI dla wszystkich lig.

UŻYCIE w skrypcie ligi:
    from league_ui import render_card, render_reasoning, CARD_CSS

Każda liga wywołuje render_card() z ujednoliconym dict predykcji:
    pred = {
        "winner":       "Nazwa drużyny",
        "reasoning":    "2-3 zdania uzasadnienia (po polsku)",
        "key_factors":  ["czynnik 1", "czynnik 2", "czynnik 3"],
        "confidence":   7,          # 1-10, None jeśli brak
        "injury_notes": "...",      # "" jeśli brak
    }

render_card() zwraca gotowy HTML dla jednego meczu.
Obsługuje stany: pre / in / post

DODAWANIE NOWEJ LIGI:
    1. Zaimportuj render_card, render_page_header, render_no_games
    2. Wywołaj predict() → zwróć zawsze dict (nie string!)
    3. Przekaż dict do render_card()
    4. Gotowe — UI jest spójne z resztą lig
"""

# ── CSS dla kart meczów (wklejaj w <style> każdej ligi) ──────────────────────
CARD_CSS = """
.card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 16px;
    overflow: hidden;
    transition: border-color .2s, box-shadow .2s;
}
.card:hover { border-color: #334155; box-shadow: 0 8px 32px rgba(0,0,0,.4); }
.card-header { padding: 8px 16px; background: #1e293b; font-size: .7rem;
               color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; }
.card-header.live { background: #7f1d1d; color: #fca5a5; }
.matchup { display: flex; align-items: center; justify-content: space-between;
           padding: 20px 16px; gap: 8px; }
.team { display: flex; flex-direction: column; align-items: center;
        gap: 8px; flex: 1; text-align: center; }
.team img { width: 56px; height: 56px; object-fit: contain; }
.team-name { font-size: .8rem; font-weight: 700; color: #e2e8f0;
             line-height: 1.2; max-width: 90px; }
.score-container { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.score { font-size: 2.2rem; font-weight: 900; color: #e2e8f0; font-family: monospace; }
.score.winner { color: #10b981; }
.score.loser  { color: #ef4444; }
.vs-sep { font-size: 1.4rem; color: #475569; font-weight: 700; }
.prediction-box { border-top: 1px solid #1e293b; padding: 14px 20px;
                  display: flex; justify-content: space-between; align-items: center; }
.pred-label { font-size: .65rem; color: #64748b; text-transform: uppercase;
              letter-spacing: 1px; font-weight: 700; }
.pred-val { font-size: 1rem; font-weight: 900; color: #f8fafc; }
.ai-reasoning { background: rgba(15,23,42,.8); border-top: 1px solid #334155; padding: 16px 20px; }
.ai-reasoning-title { font-size: .65rem; color: #64748b; text-transform: uppercase;
                      font-weight: 700; letter-spacing: 1px; margin-bottom: 8px;
                      display: flex; align-items: center; gap: 8px; }
.ai-conf-badge { background: #1e3a5f; color: #60a5fa; font-size: .7rem;
                 font-weight: 900; padding: 3px 8px; border-radius: 20px; }
.ai-reasoning-text { color: #cbd5e1; font-size: .82rem; line-height: 1.6; }
.ai-factors { margin: 10px 0 0 0; padding-left: 18px; color: #94a3b8;
              font-size: .78rem; line-height: 1.5; }
.ai-injury { margin-top: 8px; padding: 8px 10px;
             background: rgba(239,68,68,.08); border-radius: 8px;
             color: #fca5a5; font-size: .75rem; }
.empty { text-align: center; color: #64748b; padding: 60px 20px; }
.empty .ico { font-size: 3rem; display: block; margin-bottom: 16px; }
"""


def _make_pred(winner, reasoning="", key_factors=None, confidence=None, injury_notes=""):
    """Tworzy ustandaryzowany dict predykcji."""
    return {
        "winner":       winner,
        "reasoning":    reasoning or "",
        "key_factors":  key_factors or [],
        "confidence":   confidence,
        "injury_notes": injury_notes or "",
    }


def render_reasoning(pred, state):
    """
    Renderuje blok AI Reasoning dla meczu pre-game.
    Zwraca HTML string (pusty jeśli brak reasoning lub mecz w toku/skończony).
    """
    if state != "pre":
        return ""
    reasoning = (pred.get("reasoning") or "").strip()
    if not reasoning:
        return ""

    confidence  = pred.get("confidence")
    key_factors = pred.get("key_factors") or []
    injury      = (pred.get("injury_notes") or "").strip()

    conf_badge = ""
    if confidence:
        conf_badge = f'<span class="ai-conf-badge">Pewność: {confidence}/10</span>'

    factors_html = ""
    if key_factors:
        items = "".join(f"<li style='margin-bottom:4px'>{f}</li>" for f in key_factors)
        factors_html = f'<ul class="ai-factors">{items}</ul>'

    injury_html = ""
    if injury:
        injury_html = f'<div class="ai-injury">🩹 {injury}</div>'

    return f"""
    <div class="ai-reasoning">
        <div class="ai-reasoning-title">
            🤖 AI Reasoning {conf_badge}
        </div>
        <div class="ai-reasoning-text">{reasoning}</div>
        {factors_html}
        {injury_html}
    </div>"""


def render_card(
    home_name, away_name,
    home_logo, away_logo,
    home_score, away_score,
    state,          # "pre" | "in" | "post"
    status_text,    # np. "20:15 CET" / "LIVE 3Q 5:23" / "Final"
    pred,           # dict z _make_pred()
    default_logo,
):
    """
    Renderuje kartę meczu z ustandaryzowanym UI.
    Identyczny wygląd dla wszystkich lig.
    """
    winner = pred.get("winner", "")

    # Status header
    header_class = "card-header live" if state == "in" else "card-header"

    # Score HTML
    if state == "pre":
        score_html = '<span class="vs-sep" style="font-size:2rem">VS</span>'
        outcome_icon = ""
    elif state == "in":
        score_html = (f'<span class="score">{away_score}</span>'
                      f'<span class="vs-sep">:</span>'
                      f'<span class="score">{home_score}</span>')
        outcome_icon = ""
    else:  # post
        if home_score > away_score:
            actual, hc, ac = home_name, "score winner", "score loser"
        elif away_score > home_score:
            actual, hc, ac = away_name, "score loser", "score winner"
        else:
            actual, hc, ac = "", "score", "score"

        score_html = (f'<span class="{ac}">{away_score}</span>'
                      f'<span class="vs-sep">:</span>'
                      f'<span class="{hc}">{home_score}</span>')

        if actual:
            outcome_icon = (' <span style="color:#10b981">&#10003;</span>'
                            if winner == actual else
                            ' <span style="color:#ef4444">&#10007;</span>')
        else:
            outcome_icon = ""

    reasoning_html = render_reasoning(pred, state)

    return f"""
    <div class="card">
        <div class="{header_class}">{status_text}</div>
        <div class="matchup">
            <div class="team">
                <img src="{away_logo}" alt="{away_name}"
                     onerror="this.src='{default_logo}'">
                <span class="team-name">{away_name}</span>
            </div>
            <div class="score-container">{score_html}</div>
            <div class="team">
                <img src="{home_logo}" alt="{home_name}"
                     onerror="this.src='{default_logo}'">
                <span class="team-name">{home_name}</span>
            </div>
        </div>
        <div class="prediction-box">
            <span class="pred-label">Public AI Model Picks</span>
            <span class="pred-val">{winner}{outcome_icon}</span>
        </div>
        {reasoning_html}
    </div>"""


def render_no_games(league_name):
    """Placeholder gdy brak meczów danej ligi na dziś."""
    return (f'<div class="empty">'
            f'<span class="ico">🏀</span>'
            f'Brak meczów {league_name} na dziś.<br>'
            f'<small>Sprawdź później lub wybierz inną datę.</small>'
            f'</div>')


def make_pred(winner, reasoning="", key_factors=None, confidence=None, injury_notes=""):
    """Publiczny alias dla _make_pred — używaj w skryptach lig."""
    return _make_pred(winner, reasoning, key_factors, confidence, injury_notes)
