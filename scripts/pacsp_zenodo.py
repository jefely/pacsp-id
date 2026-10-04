"""Attach the typeset preprint (PDF, DOCX) to the Zenodo record behind the DOI.

Why this is needed: Zenodo's GitHub integration archives the repository snapshot
only. The observed record for v7.0.0 contains a single file,
`jefely/pacsp-id-v7.0.0.zip`; the PDF and DOCX exist only on the GitHub release and
therefore do not travel with the DOI.

Usage:
    $env:ZENODO_TOKEN = "<personal access token>"
    python scripts/pacsp_zenodo.py                 # attach assets to the latest record
    python scripts/pacsp_zenodo.py --record 23138538
    python scripts/pacsp_zenodo.py --dry-run       # probe endpoints, upload nothing

The token is read from the environment, used only in request headers, and never
written to disk. Zenodo exposes two API generations; this script probes both and
uses whichever answers for the target record:

  legacy  /api/deposit/depositions/{id}/files
  modern  /api/records/{id}/draft/files      (InvenioRDM)

If neither is writable with the supplied token, the record must be edited in the
Zenodo web UI instead; the script prints the exact steps for that case.
"""

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
ZENODO = "https://zenodo.org"
TIMEOUT = 300


def token():
    t = os.environ.get("ZENODO_TOKEN") or os.environ.get("ZENODO_PAT")
    return t.strip() if t else ""


def request(method, url, tok=None, data=None, ctype=None, accept="application/json"):
    headers = {"User-Agent": "pacsp-zenodo", "Accept": accept}
    if tok:
        headers["Authorization"] = "Bearer " + tok
    if ctype:
        headers["Content-Type"] = ctype
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read()
            try:
                return r.status, json.loads(body)
            except Exception:
                return r.status, body
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, None
    except Exception as e:
        return 0, {"message": f"{type(e).__name__}: {e}"}


def latest_record(tok):
    code, d = request("GET", f"{ZENODO}/api/records/22801604/versions/latest", tok)
    if code == 200 and isinstance(d, dict):
        return d
    return None


def list_files(rec_id, tok):
    code, d = request("GET", f"{ZENODO}/api/records/{rec_id}/files", tok)
    if code == 200 and isinstance(d, dict):
        return d.get("entries", [])
    return None


def probe_legacy(rec_id, tok):
    """Return (ok, deposition_id) for the legacy deposit API."""
    code, d = request("GET", f"{ZENODO}/api/deposit/depositions/{rec_id}", tok)
    if code == 200 and isinstance(d, dict):
        return True, d.get("id"), d
    code2, d2 = request("GET", f"{ZENODO}/api/deposit/depositions", tok)
    msg = ""
    if isinstance(d2, (dict, list)):
        msg = json.dumps(d2)[:160]
    return False, None, {"first": (code, d), "list": (code2, msg)}


def probe_modern(rec_id, tok):
    """Return (ok, url) if a draft/edit endpoint answers."""
    for path in (f"/api/records/{rec_id}/draft", f"/api/records/{rec_id}/edit"):
        code, d = request("GET", ZENODO + path, tok)
        if code == 200 and isinstance(d, dict):
            return True, ZENODO + path, d
    return False, None, None


def upload_legacy(dep_id, tok, files):
    ok = 0
    for f in files:
        # the legacy API needs the file sent as multipart form data
        boundary = "----pacspboundary"
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        body = b"".join([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{f.name}"\r\n'.encode(),
            f"Content-Type: {ctype}\r\n\r\n".encode(),
            f.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ])
        code, d = request("POST", f"{ZENODO}/api/deposit/depositions/{dep_id}/files",
                          tok, data=body,
                          ctype=f"multipart/form-data; boundary={boundary}")
        status = "ok" if code in (200, 201) else f"FAILED HTTP {code}"
        print(f"    {f.name:42} {f.stat().st_size:>10,} bytes  {status}")
        if code in (200, 201):
            ok += 1
        elif isinstance(d, dict) and d.get("message"):
            print(f"      {d['message'][:120]}")
    return ok


def upload_modern(rec_id, tok, files):
    """InvenioRDM flow: create/refresh a draft, upload, then publish."""
    print("    creating a draft of the record...")
    code, d = request("POST", f"{ZENODO}/api/records/{rec_id}/draft", tok,
                      data=b"{}", ctype="application/json")
    if code not in (200, 201):
        print(f"    draft creation HTTP {code}: "
              f"{(d or {}).get('message', '')[:140]}")
        return 0
    files_url = (d.get("links", {}).get("files")
                 or f"{ZENODO}/api/records/{rec_id}/draft/files")
    ok = 0
    for f in files:
        init = f"{files_url}"
        code, r = request("POST", init, tok,
                          data=json.dumps([{"key": f.name}]).encode(),
                          ctype="application/json")
        if code not in (200, 201):
            print(f"    {f.name}: init HTTP {code} "
                  f"{(r or {}).get('message', '')[:100]}")
            continue
        entry = None
        if isinstance(r, dict):
            entry = (r.get("entries") or [None])[0]
        content_url = ((entry or {}).get("links", {}).get("content")
                       or f"{init}/{urllib.parse.quote(f.name)}/content")
        code, r = request("PUT", content_url, tok, data=f.read_bytes(),
                          ctype=mimetypes.guess_type(f.name)[0]
                          or "application/octet-stream")
        if code not in (200, 201):
            print(f"    {f.name}: upload HTTP {code} "
                  f"{(r or {}).get('message', '')[:100]}")
            continue
        code, r = request("POST", f"{content_url}/commit", tok,
                          data=b"{}", ctype="application/json")
        status = "ok" if code in (200, 201) else f"commit HTTP {code}"
        print(f"    {f.name:42} {f.stat().st_size:>10,} bytes  {status}")
        if code in (200, 201):
            ok += 1
    if ok:
        print("    publishing the draft...")
        code, r = request("POST", f"{ZENODO}/api/records/{rec_id}/draft/publish",
                          tok, data=b"{}", ctype="application/json")
        print(f"    publish HTTP {code} {(r or {}).get('message', '')[:120] if isinstance(r, dict) else ''}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", type=int, default=None,
                    help="version record id (default: latest version)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--manual-only", action="store_true",
                    help="print the web-UI steps and exit")
    args = ap.parse_args()

    if args.manual_only:
        print_manual()
        return 0

    tok = token()
    files = sorted(p for p in DIST.glob("PACSP-ID-*-preprint.*"))
    if not files:
        print(f"no preprint assets in {DIST}")
        return 1
    print(f"assets: {len(files)}")
    for f in files:
        print(f"  {f.name:42} {f.stat().st_size:>10,} bytes")

    rec_id = args.record
    if rec_id is None:
        d = latest_record(tok or None)
        if d:
            rec_id = d.get("id")
            print(f"latest record: {rec_id}  doi={d.get('doi')}")
    if rec_id is None:
        rec_id = 23138538
        print(f"falling back to record {rec_id}")

    print()
    print(f"=== current files on record {rec_id} ===")
    entries = list_files(rec_id, tok or None)
    if entries is None:
        print("  could not list (needs a token)")
    else:
        for e in entries:
            print(f"  {e.get('key')}  {e.get('size', 0):,} bytes")

    if not tok:
        print()
        print("no ZENODO_TOKEN set.")
        print_manual()
        return 2

    print()
    print("=== probing write endpoints ===")
    l_ok, dep_id, l_info = probe_legacy(rec_id, tok)
    print(f"  legacy  /api/deposit/depositions/{rec_id}: {'writable' if l_ok else 'not writable'}")
    if not l_ok:
        print(f"          {json.dumps(l_info)[:150]}")
    m_ok, m_url, _ = probe_modern(rec_id, tok)
    print(f"  modern  draft endpoint: {'available' if m_ok else 'not available'}")

    if args.dry_run:
        print()
        print("dry run: nothing uploaded")
        return 0

    print()
    if l_ok:
        print("=== uploading via the legacy deposit API ===")
        n = upload_legacy(dep_id, tok, files)
    elif m_ok:
        print("=== uploading via the InvenioRDM draft API ===")
        n = upload_modern(rec_id, tok, files)
    else:
        print("neither write endpoint accepted the token.")
        print_manual()
        return 1

    print()
    print(f"uploaded {n}/{len(files)}")
    entries = list_files(rec_id, tok)
    if entries:
        print("=== record files now ===")
        for e in entries:
            print(f"  {e.get('key')}  {e.get('size', 0):,} bytes")
    return 0 if n == len(files) else 1


def print_manual():
    print()
    print("Manual alternative (no scripting needed):")
    print("  1. open https://zenodo.org/records/23138538")
    print("  2. click Edit")
    print("  3. Files -> Upload, add both files from PACSP-ID/dist/:")
    print("       PACSP-ID-7.0.0-preprint.pdf")
    print("       PACSP-ID-7.0.0-preprint.docx")
    print("  4. Save (the DOI stays the same)")
    print()
    print("To automate this instead, create a token with deposit:write at")
    print("  https://zenodo.org/account/settings/applications/")
    print("then run:  $env:ZENODO_TOKEN = '<token>'; python scripts/pacsp_zenodo.py")


if __name__ == "__main__":
    import urllib.parse  # noqa: E402
    sys.exit(main())
