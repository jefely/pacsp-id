"""Add the paper (PDF, DOCX) to the Zenodo record behind the DOI.

Two constraints shape this:

1. Zenodo's GitHub integration archives the repository snapshot only. The v7.0.0
   record holds a single file, `jefely/pacsp-id-v7.0.0.zip`; the PDF and DOCX live
   only on the GitHub release and so do not travel with the DOI.

2. A *published* deposition is immutable: files cannot be added to it. The only
   route is to create a new version, which mints a NEW version DOI. The concept
   DOI (10.5281/zenodo.22801604) keeps resolving to the newest version, so an
   existing citation stays valid -- but the version DOI changes.

Usage:
    $env:ZENODO_TOKEN = "<token with deposit:write AND deposit:actions>"
    python scripts/pacsp_zenodo.py --status
    python scripts/pacsp_zenodo.py --add-new-version --yes

Scope requirement, from the Zenodo API docs:
    deposit:write    write access to depositions, but cannot publish the upload
    deposit:actions  publish, edit and discard edits for depositions
Both are needed: with write alone the upload succeeds but stays an unpublished
draft.
"""

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
API = "https://zenodo.org/api"
CONCEPT = "10.5281/zenodo.22801604"
TIMEOUT = 600


def token():
    return (os.environ.get("ZENODO_TOKEN") or os.environ.get("ZENODO_PAT") or "").strip()


def call(method, url, tok, data=None, ctype=None, accept="application/json"):
    h = {"User-Agent": "pacsp-zenodo", "Accept": accept}
    if tok:
        h["Authorization"] = "Bearer " + tok
    if ctype:
        h["Content-Type"] = ctype
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            try:
                return r.status, json.loads(raw)
            except Exception:
                return r.status, raw[:400]
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, None
    except Exception as e:
        return 0, {"message": f"{type(e).__name__}: {e}"}


def assets():
    return sorted(p for p in DIST.glob("PACSP-ID-*-preprint.*"))


def show_status(tok):
    print("=== depositions on this account ===")
    code, deps = call("GET", f"{API}/deposit/depositions", tok)
    if code != 200 or not isinstance(deps, list):
        print(f"  cannot list (HTTP {code}) -- is the token valid?")
        return None
    latest = None
    for d in deps:
        md = d.get("metadata", {}) or {}
        print()
        print(f"  id        : {d.get('id')}")
        print(f"  state     : {'published' if d.get('submitted') else 'draft'}")
        print(f"  title     : {(md.get('title') or '(empty)')[:66]}")
        print(f"  doi       : {d.get('doi')}")
        for f in d.get("files", []):
            print(f"  file      : {f.get('filename') or f.get('key')}  "
                  f"{f.get('filesize') or f.get('size', 0):,} bytes")
        if d.get("submitted") and md.get("title"):
            latest = d
    return latest


def upload_to_bucket(bucket, tok, files):
    ok = 0
    for f in files:
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        url = f"{bucket}/{urllib.parse.quote(f.name)}"
        code, d = call("PUT", url, tok, data=f.read_bytes(), ctype=ctype)
        if code in (200, 201):
            print(f"    {f.name:42} {f.stat().st_size:>10,} bytes  uploaded")
            ok += 1
        else:
            msg = (d or {}).get("message", "") if isinstance(d, dict) else str(d)[:90]
            print(f"    {f.name:42} FAILED HTTP {code}  {msg[:90]}")
    return ok


def add_new_version(tok, files, rec_id, yes):
    code, d = call("GET", f"{API}/deposit/depositions/{rec_id}", tok)
    if code != 200 or not isinstance(d, dict):
        print(f"  cannot read deposition {rec_id} (HTTP {code})")
        return 1
    print(f"  current DOI : {d.get('doi')}")
    print(f"  published   : {d.get('submitted')}")

    print()
    print("=== creating a new version (mints a NEW version DOI) ===")
    code, nv = call("POST", f"{API}/deposit/depositions/{rec_id}/actions/newversion",
                    tok, data=b"", ctype="application/json")
    if code not in (200, 201):
        print(f"  newversion failed HTTP {code} "
              f"{(nv or {}).get('message', '') if isinstance(nv, dict) else ''}")
        return 1
    draft_url = (nv or {}).get("links", {}).get("latest_draft")
    print(f"  new version draft: {draft_url}")
    if not draft_url:
        print("  no draft link returned")
        return 1

    code, draft = call("GET", draft_url, tok)
    if code != 200 or not isinstance(draft, dict):
        print(f"  cannot read the draft (HTTP {code})")
        return 1
    draft_id = draft.get("id")
    bucket = draft.get("links", {}).get("bucket")
    print(f"  draft id: {draft_id}")
    print(f"  bucket  : {bucket}")

    code, existing = call("GET", f"{API}/deposit/depositions/{draft_id}/files", tok)
    have = set()
    if isinstance(existing, list):
        have = {f.get("filename") for f in existing}
        print(f"  files carried over: {sorted(have)}")

    print()
    print("=== uploading the paper ===")
    todo = [f for f in files if f.name not in have]
    n = upload_to_bucket(bucket, tok, todo) if bucket else 0

    if not yes:
        print()
        print("  NOT PUBLISHED (pass --yes to publish).")
        print(f"  review it at: https://zenodo.org/deposit/{draft_id}")
        return 0

    print()
    print("=== publishing ===")
    code, r = call("POST", f"{API}/deposit/depositions/{draft_id}/actions/publish",
                   tok, data=b"", ctype="application/json")
    if code not in (200, 201, 202):
        print(f"  publish failed HTTP {code} "
              f"{(r or {}).get('message', '') if isinstance(r, dict) else ''}")
        print(f"  the draft is intact at https://zenodo.org/deposit/{draft_id}")
        return 1
    new_doi = (r or {}).get("doi") if isinstance(r, dict) else None
    print(f"  published. new version DOI: {new_doi}")
    print(f"  concept DOI unchanged    : {CONCEPT}")
    return 0


def print_manual():
    print()
    print("Manual alternative (no token needed):")
    print("  1. open https://zenodo.org/records/23138538")
    print("  2. click 'New version'")
    print("  3. upload both files from PACSP-ID/dist/:")
    for f in assets():
        print(f"       {f.name}")
    print("  4. Publish")
    print()
    print("NOTE: a published record cannot take new files in place. Publishing a")
    print("new version mints a new version DOI; the concept DOI continues to")
    print(f"resolve to the newest version, so citations of {CONCEPT} stay valid.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true", help="list depositions and exit")
    ap.add_argument("--add-new-version", action="store_true",
                    help="create a new version of the latest published record")
    ap.add_argument("--record", type=int, default=None)
    ap.add_argument("--yes", action="store_true", help="publish without asking")
    ap.add_argument("--manual-only", action="store_true")
    args = ap.parse_args()

    tok = token()
    if args.manual_only or not tok:
        if not tok:
            print("no ZENODO_TOKEN set.")
        print_manual()
        return 2 if not tok else 0

    files = assets()
    print(f"assets: {len(files)}")
    for f in files:
        print(f"  {f.name:42} {f.stat().st_size:>10,} bytes")

    latest = show_status(tok)
    if args.status:
        return 0

    rec = args.record or (latest or {}).get("id")
    if not rec:
        print("no published deposition found")
        return 1
    if not files:
        print(f"no preprint assets in {DIST}")
        return 1

    print()
    if not args.add_new_version:
        print("a published record cannot receive files in place.")
        print("re-run with --add-new-version to create a new version (new DOI),")
        print("or use --manual-only for the web-UI steps.")
        return 0

    return add_new_version(tok, files, rec, args.yes)


if __name__ == "__main__":
    sys.exit(main())
