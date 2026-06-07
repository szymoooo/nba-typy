"""
league_ui.py — Wspólny szablon UI dla wszystkich lig.

UŻYCIE w skrypcie ligi:
    from league_ui import render_card, render_page, make_pred

DODAWANIE NOWEJ LIGI:
    1. Skopiuj NEW_LEAGUE_TEMPLATE.py
    2. Ustaw stałe LEAGUE_*
    3. predict() zawsze zwraca make_pred(...)
    4. build_cards() używa render_card(...) i zbiera matches_data
    5. build_page() używa render_page(...)
"""

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
LEAGUE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #020817; color: #f8fafc;
       font-family: 'Montserrat', 'Inter', sans-serif; min-height: 100vh; }

/* HEADER */
.hub-header { text-align: center; padding: 40px 20px 28px; }
.hub-header img.league-logo { height: 72px; object-fit: contain;
                               display: block; margin: 0 auto 16px; }
.hub-header h1 { font-size: clamp(1.6rem,4vw,2.4rem); font-weight: 900;
                 letter-spacing: -1px; color: #f8fafc; }
.hub-header .subtitle { margin-top: 6px; color: #64748b; font-size: .8rem;
                         text-transform: uppercase; letter-spacing: 1px; }

/* GRID */
.grid { display: grid;
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        gap: 20px; max-width: 1100px; margin: 0 auto; padding: 0 20px 40px; }

/* CARD */
.card { background: #0f172a; border: 1px solid #1e293b; border-radius: 16px;
        overflow: hidden; cursor: pointer;
        transition: border-color .2s, box-shadow .2s, transform .15s; }
.card:hover { border-color: #334155; box-shadow: 0 8px 32px rgba(0,0,0,.5);
              transform: translateY(-2px); }
.card-header { padding: 8px 16px; background: #1e293b; font-size: .68rem;
               color: #94a3b8; text-transform: uppercase; letter-spacing: 1px;
               display: flex; justify-content: space-between; align-items: center; }
.card-header.live { background: #7f1d1d; color: #fca5a5; }
.click-hint { font-size: .6rem; color: #475569; }
.matchup { display: flex; align-items: center;
           justify-content: space-between; padding: 20px 16px; gap: 8px; }
.team { display: flex; flex-direction: column; align-items: center;
        gap: 8px; flex: 1; text-align: center; }
.team img { width: 56px; height: 56px; object-fit: contain; }
.team-name { font-size: .8rem; font-weight: 700; color: #e2e8f0;
             line-height: 1.2; max-width: 90px; }
.score-wrap { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.score { font-size: 2.2rem; font-weight: 900; color: #e2e8f0; font-family: monospace; }
.score.win  { color: #10b981; }
.score.loss { color: #ef4444; }
.vs { font-size: 1.4rem; color: #475569; font-weight: 700; }
.pred-box { border-top: 1px solid #1e293b; padding: 14px 20px;
            display: flex; justify-content: space-between; align-items: center; }
.pred-label { font-size: .62rem; color: #64748b;
              text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }
.pred-val { font-size: 1rem; font-weight: 900; color: #f8fafc; }
.outcome-ok  { color: #10b981; }
.outcome-bad { color: #ef4444; }

/* EMPTY */
.empty { text-align: center; color: #64748b; padding: 60px 20px;
         grid-column: 1/-1; }
.empty .ico { font-size: 3rem; display: block; margin-bottom: 16px; }

/* MODAL */
.modal-overlay { display: none; position: fixed; inset: 0;
                 background: rgba(2,8,23,.85); backdrop-filter: blur(4px);
                 z-index: 1000; align-items: center; justify-content: center; padding: 20px; }
.modal-overlay.open { display: flex; }
.modal-box { background: #0f172a; border: 1px solid #334155; border-radius: 20px;
             max-width: 620px; width: 100%; max-height: 90vh; overflow-y: auto;
             padding: 28px; position: relative; }
.modal-close { position: absolute; top: 16px; right: 16px; background: #1e293b;
               border: none; color: #94a3b8; cursor: pointer; border-radius: 8px;
               width: 32px; height: 32px; font-size: 1.1rem;
               display: flex; align-items: center; justify-content: center; }
.modal-close:hover { background: #334155; color: #f8fafc; }
.modal-matchup { font-size: .72rem; color: #64748b; text-transform: uppercase;
                 letter-spacing: 1px; margin-bottom: 8px; }
.modal-pick { font-size: 1.15rem; font-weight: 900; color: #f8fafc; margin-bottom: 24px; }
.modal-section { font-size: .65rem; color: #64748b; text-transform: uppercase;
                 letter-spacing: 1px; font-weight: 700; margin-bottom: 8px;
                 display: flex; align-items: center; gap: 8px; }
.modal-conf { background: #1e3a5f; color: #60a5fa; font-size: .7rem;
              font-weight: 900; padding: 3px 8px; border-radius: 20px; }
.modal-text { color: #cbd5e1; font-size: .88rem; line-height: 1.7; margin-bottom: 16px; }
.modal-factors { padding-left: 20px; color: #94a3b8; font-size: .82rem;
                 line-height: 1.6; margin-bottom: 16px; }
.modal-factors li { margin-bottom: 6px; }
.modal-injury { padding: 12px 14px; background: rgba(239,68,68,.08);
                border-radius: 10px; color: #fca5a5; font-size: .8rem;
                line-height: 1.6; margin-bottom: 20px; }
.modal-divider { border: none; border-top: 1px solid #1e293b; margin: 20px 0; }
.modal-audit { padding: 16px; background: rgba(0,0,0,.3); border-radius: 12px;
               border: 1px dashed #334155; color: #f8fafc; font-size: .85rem;
               line-height: 1.8; white-space: pre-wrap; }

/* CALENDAR / HISTORY */
.history-section { max-width: 1100px; margin: 0 auto 40px; padding: 0 20px; }
.history-section h2 { font-size: 1.1rem; font-weight: 800; color: #e2e8f0; margin-bottom: 4px; }
.hist-sub { color: #64748b; font-size: .78rem; margin-bottom: 16px; }
.hist-picker { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.hist-btn { background: #0f172a; border: 1px solid #1e293b; border-radius: 12px;
            padding: 10px 16px; cursor: pointer; color: #e2e8f0;
            transition: border-color .2s; min-width: 120px; text-align: left; }
.hist-btn.disabled { opacity: .4; cursor: default; }
.hist-btn.active { border-color: var(--accent,#3b82f6); background: rgba(59,130,246,.08); }
.hist-btn:hover:not(.disabled) { border-color: var(--accent,#3b82f6); }
.btn-label { font-size: .7rem; color: #64748b; text-transform: uppercase;
             letter-spacing: 1px; font-weight: 700; }
.btn-date { font-size: .82rem; color: #e2e8f0; font-weight: 600; margin-top: 2px; }
.hist-divider { width: 1px; height: 40px; background: #1e293b; }
.hist-cal-btn { background: #0f172a; border: 1px solid #1e293b; border-radius: 12px;
                padding: 10px 16px; cursor: pointer; display: flex;
                align-items: center; gap: 10px; position: relative;
                transition: border-color .2s; }
.hist-cal-btn:hover { border-color: var(--accent,#3b82f6); }
.hist-cal-btn.active { border-color: var(--accent,#3b82f6); background: rgba(59,130,246,.08); }
.hist-result, .hist-noarchive { display: none; margin-top: 12px; padding: 12px 16px;
    border-radius: 10px; font-size: .85rem; align-items: center; gap: 10px; }
.hist-result.show, .hist-noarchive.show { display: flex; }
.hist-result { background: rgba(59,130,246,.08); border: 1px solid #1e3a5f; color: #93c5fd; }
.hist-result a { color: var(--accent,#60a5fa); font-weight: 700; margin-left: auto; }
.hist-noarchive { background: rgba(245,158,11,.08); border: 1px solid #78350f; color: #fcd34d; }

/* FOOTER */
.hub-footer { text-align: center; padding: 20px; color: #334155;
              font-size: .72rem; border-top: 1px solid #0f172a; }
"""

# ─────────────────────────────────────────────────────────────────────────────
# MODAL + CALENDAR JS
# ─────────────────────────────────────────────────────────────────────────────
LEAGUE_JS = """
// MODAL
function openModal(id) {
    const data = window._matchData && window._matchData[id];
    if (!data) return;
    const box = document.getElementById('modal-box');
    let html = '';

    // Nagłówek
    html += `<button class="modal-close" onclick="closeModal()">✕</button>`;
    html += `<div class="modal-matchup">${data.matchup || ''}</div>`;
    html += `<div class="modal-pick">Typ: <span style="color:var(--accent,#60a5fa)">${data.pick || ''}</span></div>`;

    // AI Reasoning
    if (data.reasoning) {
        const conf = data.confidence
            ? `<span class="modal-conf">Pewność: ${data.confidence}/10</span>` : '';
        html += `<div class="modal-section">🤖 AI Reasoning ${conf}</div>`;
        html += `<div class="modal-text">${data.reasoning}</div>`;
        if (data.key_factors && data.key_factors.length) {
            html += '<ul class="modal-factors">' +
                data.key_factors.map(f => `<li>${f}</li>`).join('') +
                '</ul>';
        }
        if (data.injury_notes) {
            html += `<div class="modal-injury">🩹 ${data.injury_notes}</div>`;
        }
    }

    // Lineup Audit
    if (data.audit) {
        html += '<hr class="modal-divider">';
        html += '<div class="modal-section">🛡️ Lineup Audit AI</div>';
        html += `<div class="modal-audit">${data.audit}</div>`;
    }

    if (!data.reasoning && !data.audit) {
        html += '<div class="modal-text" style="color:#64748b">Brak analizy AI dla tego meczu.</div>';
    }

    box.innerHTML = html;
    document.getElementById('modal-overlay').classList.add('open');
}
function closeModal() {
    document.getElementById('modal-overlay').classList.remove('open');
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
document.getElementById('modal-overlay').addEventListener('click', function(e) {
    if (e.target === this) closeModal();
});

// CALENDAR
const _archivePrefix = '';
let _availDates = new Set();
let _pickerReady = false;
const _today = new Date();
function _fmtDisp(d) {
    return d.toLocaleDateString('en-US', {month:'long', day:'numeric', year:'numeric'});
}
function _fmtSlug(d) {
    return d.getFullYear() + '-' +
           String(d.getMonth()+1).padStart(2,'0') + '-' +
           String(d.getDate()).padStart(2,'0');
}
function _off(n) { const d = new Date(_today); d.setDate(d.getDate()+n); return d; }
const _yday = _off(-1);
const _db4  = _off(-2);
fetch(_archivePrefix + 'archive/index.json?v=' + Date.now())
    .then(r => r.json())
    .then(data => { _availDates = new Set(data.dates || []); })
    .catch(() => {})
    .finally(() => { _pickerReady = true; _initPicker(); });
function _initPicker() {
    const e1 = document.getElementById('lbl-yesterday');
    const e2 = document.getElementById('lbl-dayb4');
    if (e1) e1.textContent = _fmtDisp(_yday);
    if (e2) e2.textContent = _fmtDisp(_db4);
    const b1 = document.getElementById('btn-yesterday');
    const b2 = document.getElementById('btn-dayb4');
    if (b1 && !_availDates.has(_fmtSlug(_yday))) b1.classList.add('disabled');
    if (b2 && !_availDates.has(_fmtSlug(_db4)))  b2.classList.add('disabled');
}
function _clearActive() {
    ['btn-yesterday','btn-dayb4','cal-btn'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.remove('active');
    });
    ['hist-result','hist-noarchive'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.remove('show');
    });
}
function trySelectDay(which) {
    const btn = document.getElementById('btn-' + which);
    if (btn && btn.classList.contains('disabled')) return;
    _clearActive();
    const d = which === 'yesterday' ? _yday : _db4;
    if (btn) btn.classList.add('active');
    const cd = document.getElementById('cal-display');
    if (cd) cd.textContent = 'Open calendar';
    _showResult(_fmtDisp(d), _fmtSlug(d));
}
function selectCustom(val) {
    if (!val) return;
    _clearActive();
    const p = val.split('-');
    const d = new Date(+p[0], +p[1]-1, +p[2]);
    const slug = _fmtSlug(d), label = _fmtDisp(d);
    const cd = document.getElementById('cal-display');
    if (cd) cd.textContent = label;
    const cb = document.getElementById('cal-btn');
    if (cb) cb.classList.add('active');
    if (_pickerReady && _availDates.size > 0 && !_availDates.has(slug)) {
        _showNoArchive(label);
    } else {
        _showResult(label, slug);
    }
}
function _showResult(label, slug) {
    document.getElementById('res-date').textContent = label;
    document.getElementById('res-link').href = _archivePrefix + 'archive/' + slug + '.html';
    document.getElementById('hist-result').classList.add('show');
    document.getElementById('hist-noarchive').classList.remove('show');
}
function _showNoArchive(label) {
    document.getElementById('noarch-date').textContent = label;
    document.getElementById('hist-noarchive').classList.add('show');
    document.getElementById('hist-result').classList.remove('show');
}
const _calBtn = document.getElementById('cal-btn');
if (_calBtn) {
    _calBtn.addEventListener('click', function() {
        const inp = document.getElementById('hidden-date');
        if (inp) { if (inp.showPicker) inp.showPicker(); else inp.click(); }
    });
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def make_pred(winner, reasoning="", key_factors=None, confidence=None, injury_notes=""):
    """
    Tworzy ustandaryzowany dict predykcji.
    Zawsze zwracaj to z predict() — nigdy surowego stringa.
    """
    return {
        "winner":       winner,
        "reasoning":    reasoning or "",
        "key_factors":  key_factors or [],
        "confidence":   confidence,
        "injury_notes": injury_notes or "",
    }


def render_card(game_id, home_name, away_name, home_logo, away_logo,
                home_score, away_score, state, status_text, pred, default_logo):
    """
    Renderuje czystą kartę meczu bez reasoning inline.
    Kliknięcie otwiera modal z AI reasoning + audit.

    game_id:     unikalny string np. "plk_37304"
    state:       "pre" | "in" | "post"
    status_text: np. "20:15 CET" / "LIVE 3Q" / "Final"
    pred:        dict z make_pred()
    """
    winner = pred.get("winner", "")
    header_cls = "card-header live" if state == "in" else "card-header"
    has_data = bool(pred.get("reasoning") or pred.get("audit"))
    hint = '<span class="click-hint">Kliknij po analizę →</span>' if has_data else ""

    if state == "pre":
        score_html = '<span class="vs" style="font-size:2rem">VS</span>'
        outcome = ""
    elif state == "in":
        score_html = (f'<span class="score">{away_score}</span>'
                      f'<span class="vs">:</span>'
                      f'<span class="score">{home_score}</span>')
        outcome = ""
    else:
        if home_score > away_score:
            actual, hc, ac = home_name, "score win", "score loss"
        elif away_score > home_score:
            actual, hc, ac = away_name, "score loss", "score win"
        else:
            actual, hc, ac = "", "score", "score"
        score_html = (f'<span class="{ac}">{away_score}</span>'
                      f'<span class="vs">:</span>'
                      f'<span class="{hc}">{home_score}</span>')
        if actual:
            outcome = (' <span class="outcome-ok">&#10003;</span>'
                       if winner == actual else
                       ' <span class="outcome-bad">&#10007;</span>')
        else:
            outcome = ""

    return f"""
    <div class="card" onclick="openModal('{game_id}')">
        <div class="{header_cls}">
            <span>{status_text}</span>{hint}
        </div>
        <div class="matchup">
            <div class="team">
                <img src="{away_logo}" alt="{away_name}"
                     onerror="this.src='{default_logo}'">
                <span class="team-name">{away_name}</span>
            </div>
            <div class="score-wrap">{score_html}</div>
            <div class="team">
                <img src="{home_logo}" alt="{home_name}"
                     onerror="this.src='{default_logo}'">
                <span class="team-name">{home_name}</span>
            </div>
        </div>
        <div class="pred-box">
            <span class="pred-label">Public AI Model Picks</span>
            <span class="pred-val">{winner}{outcome}</span>
        </div>
    </div>"""


def render_page(league_logo_url, league_title, league_subtitle,
                cards_html, matches_data, last_updated, data_source,
                default_logo, league_accent="#3b82f6"):
    """
    Renderuje pełną stronę ligi.
    Zawiera: header, grid, kalendarz, modal, footer.

    matches_data: dict {game_id: {matchup, pick, reasoning, key_factors,
                                   confidence, injury_notes, audit}}
    """
    import json

    grid = cards_html.strip() or (
        '<div class="empty"><span class="ico">🏀</span>'
        'Brak meczów na dziś.<br>'
        '<small>Sprawdź później lub wybierz inną datę.</small></div>'
    )
    match_data_json = json.dumps(matches_data, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{league_title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;900&display=swap" rel="stylesheet">
    <style>
        :root {{ --accent: {league_accent}; }}
        {LEAGUE_CSS}
        .card:hover {{ border-color: {league_accent}40; }}
        .pred-val {{ color: {league_accent}; }}
    </style>
</head>
<body>

    <div class="hub-header">
        <img src="{league_logo_url}" alt="{league_title} logo" class="league-logo"
             onerror="this.style.display='none'">
        <h1>{league_title}</h1>
        <div class="subtitle">{league_subtitle}</div>
    </div>

    <div class="grid">
        {grid}
    </div>

    <div class="history-section" id="history">
        <h2>Prediction History</h2>
        <p class="hist-sub">Archive of previous days AI predictions</p>
        <div class="hist-picker">
            <button class="hist-btn" id="btn-yesterday" onclick="trySelectDay('yesterday')">
                <div class="btn-label">Yesterday</div>
                <div class="btn-date" id="lbl-yesterday">—</div>
            </button>
            <button class="hist-btn" id="btn-dayb4" onclick="trySelectDay('dayb4')">
                <div class="btn-label">Day before</div>
                <div class="btn-date" id="lbl-dayb4">—</div>
            </button>
            <div class="hist-divider"></div>
            <div class="hist-cal-btn" id="cal-btn">
                <svg width="20" height="20" viewBox="0 0 22 22" fill="none">
                    <rect x="2" y="4" width="18" height="16" rx="3"
                          stroke="{league_accent}" stroke-width="1.2" fill="none"/>
                    <line x1="2" y1="8.5" x2="20" y2="8.5"
                          stroke="{league_accent}" stroke-width="1.2"/>
                    <line x1="7" y1="2" x2="7" y2="6"
                          stroke="{league_accent}" stroke-width="1.5" stroke-linecap="round"/>
                    <line x1="15" y1="2" x2="15" y2="6"
                          stroke="{league_accent}" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                <div>
                    <div class="btn-label">Pick a date</div>
                    <div class="btn-date" id="cal-display" style="color:{league_accent}">
                        Open calendar</div>
                </div>
                <input type="date" id="hidden-date"
                       style="position:absolute;opacity:0;width:1px;height:1px;pointer-events:none"
                       onchange="selectCustom(this.value)">
            </div>
        </div>
        <div class="hist-result" id="hist-result">
            <span>Archive for <strong id="res-date"></strong></span>
            <a href="#" id="res-link">View picks →</a>
        </div>
        <div class="hist-noarchive" id="hist-noarchive">
            <span>⚠️ No archive for <strong id="noarch-date"></strong></span>
        </div>
    </div>

    <!-- Modal -->
    <div class="modal-overlay" id="modal-overlay">
        <div class="modal-box" id="modal-box"></div>
    </div>

    <div class="hub-footer">
        Last updated: {last_updated} &middot; Data: {data_source}
    </div>

    <script>window._matchData = {match_data_json};</script>
    <script>{LEAGUE_JS}</script>
</body>
</html>"""


def inject_audit(index_html_path, audit_text):
    """
    Wstrzykuje tekst audytu do modalu w istniejącym index.html.
    Wywołaj po render_page() z plk_audit.py / euroleague_audit.py / gemini_audit.py.
    """
    import re
    if not audit_text or not audit_text.strip():
        return

    try:
        with open(index_html_path, "r", encoding="utf-8") as f:
            html = f.read()

        escaped = (audit_text
                   .replace("\\", "\\\\")
                   .replace('"', '\\"')
                   .replace("\n", "\\n"))

        html = html.replace('"audit": ""', f'"audit": "{escaped}"')

        with open(index_html_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"   [audit] Wstrzyknięto do modalu: {index_html_path}")
    except Exception as e:
        print(f"   [audit] Błąd wstrzykiwania: {e}")
