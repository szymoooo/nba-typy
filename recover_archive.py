import requests
import json
import os
import re
from datetime import datetime, timezone
from collections import defaultdict

# ==========================================
# ⚙️ KONFIGURACJA
# ==========================================
GITHUB_USER  = "szymoooo"
GITHUB_REPO  = "nba-typy"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# ==========================================
# 🔧 HELPERS
# ==========================================

def github_headers():
    h = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h

def get_all_commits():
    """Pobiera wszystkie commity które zmieniały index.html"""
    print("📡 Pobieram listę commitów z GitHub...")
    commits = []
    page = 1
    while True:
        url = (f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}"
               f"/commits?path=index.html&per_page=100&page={page}")
        r = requests.get(url, headers=github_headers(), timeout=15)
        if r.status_code != 200:
            print(f"❌ Błąd GitHub API: {r.status_code} — {r.text}")
            break
        data = r.json()
        if not data:
            break
        commits.extend(data)
        print(f"   Strona {page}: {len(data)} commitów")
        if len(data) < 100:
            break
        page += 1
    print(f"✅ Znaleziono {len(commits)} commitów łącznie\n")
    return commits

def group_by_date(commits):
    """
    Logika archiwum:
    - Mecze NBA grają się w nocy polskiego czasu
    - 23:00 CET (21:00 UTC) = propozycje PRZED meczami danego dnia
    - Rano następnego dnia 07:00 lub 11:00 UTC = rozliczone wyniki (Final)

    Dla archiwum dnia X chcemy PIERWSZY commit dnia X+1 (rano) =
    rozliczone wyniki z nocy X na X+1.

    Wyjątek: dla ostatniego dnia bierzemy ostatni dostępny commit.
    """
    by_date = defaultdict(list)
    for c in commits:
        dt_str = c["commit"]["committer"]["date"]
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        day = dt.strftime("%Y-%m-%d")
        by_date[day].append((dt, c["sha"]))

    for day in by_date:
        by_date[day].sort(key=lambda x: x[0])

    all_days = sorted(by_date.keys())
    result   = {}

    for i, day in enumerate(all_days):
        next_day = all_days[i + 1] if i + 1 < len(all_days) else None

        if next_day:
            best_dt, best_sha = by_date[next_day][0]
            result[day] = best_sha
            print(f"   {day} → commit z {next_day} {best_dt.strftime('%H:%M')} UTC (poranne rozliczenie) ✓")
        else:
            best_dt, best_sha = by_date[day][-1]
            result[day] = best_sha
            print(f"   {day} → commit z {best_dt.strftime('%H:%M')} UTC (ostatni dostępny)")

    return result

def fetch_index_html_at_commit(sha):
    """Pobiera zawartość index.html dla konkretnego commita"""
    import base64, time
    url = (f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}"
           f"/contents/index.html?ref={sha}")
    r = requests.get(url, headers=github_headers(), timeout=15)
    if r.status_code == 403:
        reset = int(r.headers.get("X-RateLimit-Reset", 0))
        wait  = max(reset - int(datetime.now(timezone.utc).timestamp()), 0) + 5
        print(f"   ⏳ Rate limit! Czekam {wait}s...")
        time.sleep(wait)
        r = requests.get(url, headers=github_headers(), timeout=15)
    if r.status_code != 200:
        print(f"   ⚠️  HTTP {r.status_code}: {r.json().get('message', '')}")
        return None
    content_b64 = r.json().get("content", "")
    return base64.b64decode(content_b64).decode("utf-8", errors="replace")

def patch_html_for_archive(html, date_str, archive_prefix="../"):
    """Patchuje stary index.html żeby działał jako strona archiwalna"""

    back_btn = (
        f'<a href="{archive_prefix}index.html" '
        f'style="display:inline-flex;align-items:center;gap:8px;background:#1e293b;'
        f'border:1px solid #334155;color:#60a5fa;font-family:\'Montserrat\',sans-serif;'
        f'font-size:.85rem;font-weight:700;text-decoration:none;padding:10px 20px;'
        f'border-radius:12px;margin-bottom:30px;" '
        f'onmouseover="this.style.background=\'#1e3a5f\';this.style.borderColor=\'#3b82f6\'" '
        f'onmouseout="this.style.background=\'#1e293b\';this.style.borderColor=\'#334155\'">'
        f'← Back to today</a>'
    )

    # Wstaw back button po pierwszym <div class="container">
    html = html.replace('<div class="container">', f'<div class="container">\n        {back_btn}', 1)

    # Podmień <title>
    html = re.sub(r'<title>.*?</title>', f'<title>NBA Public AI Picks — {date_str}</title>', html)

    # Usuń target="_blank" z linków archiwum (otwierać w tej samej karcie)
    html = html.replace(' target="_blank"', '')

    return html

def load_archive_index():
    os.makedirs("archive", exist_ok=True)
    path = "archive/index.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("dates", [])
    return []

def save_archive_index(dates):
    sorted_dates = sorted(set(dates), reverse=True)
    with open("archive/index.json", "w", encoding="utf-8") as f:
        json.dump({"dates": sorted_dates}, f, indent=2)
    print(f"\n✅ Zapisano archive/index.json z {len(sorted_dates)} datami:")
    for d in sorted_dates:
        print(f"   • {d}")

# ==========================================
# 🚀 GŁÓWNA FUNKCJA
# ==========================================

def recover_archive():
    print("=" * 55)
    print("  NBA ARCHIVE RECOVERY — GitHub History Importer")
    print("=" * 55)
    print(f"  Repo: {GITHUB_USER}/{GITHUB_REPO}\n")

    os.makedirs("archive", exist_ok=True)

    commits = get_all_commits()

    print("\n📅 Wybieram najlepszy commit dla każdego dnia:")
    by_date = group_by_date(commits)

    existing = set(load_archive_index())
    saved    = []
    skipped  = []

    print(f"\n⬇️  Pobieram pliki HTML ({len(by_date)} dni)...\n")

    for day in sorted(by_date.keys()):
        archive_path = f"archive/{day}.html"

        if os.path.exists(archive_path):
            print(f"⏭️  {day} — już istnieje, pomijam")
            skipped.append(day)
            saved.append(day)
            continue

        sha = by_date[day]
        print(f"⬇️  {day} — SHA: {sha[:8]}...")

        html = fetch_index_html_at_commit(sha)
        if not html:
            print(f"   ❌ Nie udało się pobrać")
            continue

        dt           = datetime.strptime(day, "%Y-%m-%d")
        date_display = dt.strftime("%B %d, %Y")
        patched      = patch_html_for_archive(html, date_display)

        with open(archive_path, "w", encoding="utf-8") as f:
            f.write(patched)

        print(f"   ✅ Zapisano {archive_path}")
        saved.append(day)

    save_archive_index(saved)

    print(f"\n🏀 Gotowe! Odzyskano {len(saved) - len(skipped)} nowych dni,")
    print(f"   pominięto {len(skipped)} już istniejących.")

if __name__ == "__main__":
    recover_archive()
