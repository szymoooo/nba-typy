import os
import glob

# Usuwa target="_blank" ze wszystkich istniejących plików archiwum

files = glob.glob("archive/*.html") + ["index.html"]
fixed = 0

for path in files:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if 'target="_blank"' in content:
        content = content.replace(' target="_blank"', '')
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Poprawiono: {path}")
        fixed += 1
    else:
        print(f"⏭️  OK już: {path}")

print(f"\n🏀 Gotowe! Poprawiono {fixed} z {len(files)} plików.")
