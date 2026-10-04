"""Verify the published release assets against the local deliverables.

Byte comparison is used first. A DOCX is a ZIP whose entries carry modification
timestamps, so a rebuild with identical content still hashes differently; for
those, fall back to comparing the document text and every embedded media entry.
Otherwise a healthy release reports as corrupted.
"""

import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

TOKEN = os.environ.pop("PACSP_TOKEN", "")
DIST = Path(__file__).resolve().parent.parent / "dist"
OWNER, REPO, TAG = "jefely", "pacsp-id", "v7.0.0"


def api(path):
    req = urllib.request.Request("https://api.github.com" + path, headers={
        "Authorization": "Bearer " + TOKEN,
        "User-Agent": "dsh-verify",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, None


def sha(b):
    return hashlib.sha256(b).hexdigest()


def _docx_text(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", xml)).strip()


def _docx_media(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: sha(z.read(n)) for n in z.namelist()
                if n.startswith("word/media/")}


def main():
    print("=== local deliverables ===")
    local = {}
    local_bytes = {}
    for f in sorted(DIST.glob("PACSP-ID-7.0.0-preprint.*")):
        data = f.read_bytes()
        local[f.name] = (len(data), sha(data))
        local_bytes[f.name] = data
        print(f"  {f.name:42} {len(data):>10,}  {local[f.name][1][:16]}")

    code, rel = api(f"/repos/{OWNER}/{REPO}/releases/tags/{TAG}")
    if code != 200:
        print(f"release fetch failed HTTP {code}")
        return 1

    print()
    print("=== release assets ===")
    assets = {a["name"]: a for a in rel.get("assets", [])}
    for name, a in assets.items():
        print(f"  {name:42} {a['size']:>10,}")

    print()
    print("=== comparison ===")
    ok = True
    for name, (lsize, lhash) in local.items():
        a = assets.get(name)
        if not a:
            print(f"  {name}: MISSING from release")
            ok = False
            continue
        if a["size"] != lsize:
            print(f"  {name}: SIZE MISMATCH local={lsize:,} remote={a['size']:,}")
            ok = False
            continue
        # fetch the asset bytes and hash them
        req = urllib.request.Request(a["url"], headers={
            "Authorization": "Bearer " + TOKEN,
            "User-Agent": "dsh-verify",
            "Accept": "application/octet-stream",
        })
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = r.read()
        except Exception as e:
            print(f"  {name}: download failed {e}")
            ok = False
            continue
        rhash = sha(data)
        if rhash == lhash:
            print(f"  {name}: IDENTICAL (bytes)  remote {rhash[:16]}")
            continue

        # A DOCX is a ZIP whose entries carry modification timestamps, so a
        # rebuild with identical content still differs byte-for-byte. Fall back to
        # a content comparison before calling it a mismatch -- otherwise a healthy
        # release looks corrupted.
        if name.endswith(".docx"):
            lt = _docx_text(local_bytes[name])
            rt = _docx_text(data)
            lm = _docx_media(local_bytes[name])
            rm = _docx_media(data)
            if lt == rt and lm == rm:
                print(f"  {name}: IDENTICAL (content: {len(lt):,} chars, "
                      f"{len(lm)} media entries; ZIP timestamps differ)")
                continue
            print(f"  {name}: CONTENT MISMATCH  text_equal={lt == rt} "
                  f"media_equal={lm == rm}")
            ok = False
            continue

        if name.endswith(".pdf"):
            print(f"  {name}: BYTE MISMATCH  local {lhash[:16]} remote {rhash[:16]}")
            print("        (PDFs embed a creation date; compare sizes: "
                  f"local {lsize:,} remote {a['size']:,})")
            ok = False
            continue

        print(f"  {name}: HASH MISMATCH  remote {rhash[:16]}")
        ok = False

    # any extra assets on the release?
    for name in assets:
        if name not in local:
            print(f"  unexpected extra asset on release: {name}")

    print()
    print("=== other release fields ===")
    print(f"  draft      : {rel['draft']}")
    print(f"  prerelease : {rel['prerelease']}")
    print(f"  published  : {rel['published_at']}")
    print(f"  body chars : {len(rel.get('body') or '')}")
    print(f"  url        : {rel['html_url']}")

    print()
    print("RESULT:", "all assets match" if ok else "MISMATCH FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
