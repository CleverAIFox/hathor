import re
import unicodedata as u
from pathlib import Path

from mutagen import File

ROOT = Path("/mnt/d/노래/노래")
EXT = {".mp3", ".flac", ".m4a", ".wav", ".ogg"}
PAT = re.compile(r"^([^(（]+)[(（]([^)）]+)[)）]\s*$")


def script(s):
    k = set()
    for c in s:
        if not c.isalnum():
            continue
        n = u.name(c, "")
        if n.startswith("HANGUL"):
            k.add("KO")
        elif n.startswith("LATIN"):
            k.add("LA")
        elif c.isdigit():
            k.add("NUM")
        else:
            k.add("ETC")
    return "+".join(sorted(k)) or "?"


seen = set()
for p in ROOT.rglob("*"):
    if p.suffix.lower() not in EXT:
        continue
    try:
        f = File(p, easy=True)
    except Exception:
        continue
    if f and f.tags:
        seen.update(f.tags.get("artist", []))

Path("/tmp/artists.txt").write_text("\n".join(sorted(seen)), encoding="utf-8")
print("unique:", len(seen))
for a in sorted(seen):
    m = PAT.match(a.strip())
    if m:
        print(f"{script(m.group(1))}|{script(m.group(2))}\t{a}")
