"""
fix_archive.py
--------------
Naprawia wszystkie pliki w archive/*.html:
1. Podmienia podwojne sciezki archive/archive/ -> ../archive/
2. Dodaje tag GA4 jesli go nie ma
"""

import os
import re

ARCHIVE_DIR = "archive"
GA4_ID      = "G-ZV0JG9D4QK"

GA4_SNIPPET = f"""    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', '{GA4_ID}');
    </script>"""


def fix_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    changed = False

    # ── 1. Napraw podwojne archive/archive/ ──
    # Dotyczy fetch('archive/archive/index.json') w starych plikach
    if "archive/archive/" in html:
        html = html.replace("archive/archive/", "../archive/")
        changed = True
        print(f"  [FIX path] {os.path.basename(path)}")

    # ── 2. Dodaj GA4 jesli brak ──
    if GA4_ID not in html:
        # Wstaw przed </head>
        if "</head>" in html:
            html = html.replace("</head>", GA4_SNIPPET + "\n</head>", 1)
            changed = True
            print(f"  [ADD GA4] {os.path.basename(path)}")
        else:
            print(f"  [SKIP no </head>] {os.path.basename(path)}")

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    return changed


def main():
    print("=" * 50)
    print("  fix_archive.py — naprawianie plikow archiwum")
    print("=" * 50)

    if not os.path.isdir(ARCHIVE_DIR):
        print(f"Brak katalogu {ARCHIVE_DIR}/ — nic do naprawy.")
        return

    html_files = sorted([
        f for f in os.listdir(ARCHIVE_DIR)
        if f.endswith(".html")
    ])

    if not html_files:
        print("Brak plikow .html w archive/")
        return

    print(f"Znaleziono {len(html_files)} plikow HTML\n")

    fixed = 0
    for fname in html_files:
        path = os.path.join(ARCHIVE_DIR, fname)
        if fix_file(path):
            fixed += 1

    print(f"\nGotowe! Naprawiono {fixed}/{len(html_files)} plikow.")


if __name__ == "__main__":
    main()
