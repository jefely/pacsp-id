"""Create the GitHub release for 7.0.0 and upload the preprint assets.

Steps: push main, push the tag, create the release, upload the DOCX and PDF.
The token is held only in this process's environment and never written to disk or
to any git config.
"""

import json
import mimetypes
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

TOKEN = os.environ.pop("PACSP_TOKEN", "")
OWNER = "jefely"
REPO = "pacsp-id"
TAG = "v7.0.0"
ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
NOTES = ROOT / "docs" / "RELEASE-7.0.0.md"
PROXY = "http://127.0.0.1:7897"

leaked = []


def scrub(t):
    if TOKEN and TOKEN in t:
        leaked.append(True)
        return t.replace(TOKEN, "<TOKEN>")
    return t


def run(args, env=None):
    e = os.environ.copy()
    e.update(env or {})
    r = subprocess.run(args, cwd=str(ROOT), env=e, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, scrub(r.stdout or ""), scrub(r.stderr or "")


def api(method, path, body=None):
    url = "https://api.github.com" + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + TOKEN,
        "User-Agent": "dsh-release",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except Exception:
            return e.code, {"message": e.reason}
    except Exception as e:
        return 0, {"message": str(e)}


def upload(rel, asset: Path):
    """Upload one asset via the uploads endpoint (raw body, not JSON)."""
    upload_url = rel["upload_url"].split("{")[0]
    ctype = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
    url = f"{upload_url}?name={urllib.parse.quote(asset.name)}"
    data = asset.read_bytes()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": "Bearer " + TOKEN,
        "User-Agent": "dsh-release",
        "Content-Type": ctype,
        "Content-Length": str(len(data)),
    })
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except Exception:
            return e.code, {"message": e.reason}
    except Exception as e:
        return 0, {"message": str(e)}


def main():
    if not TOKEN:
        print("no token in environment")
        return 2

    ASKPASS = ROOT.parent / "chrome-debug" / "_askpass_rel"
    ASKPASS.mkdir(parents=True, exist_ok=True)
    (ASKPASS / "askpass.py").write_text(
        'import os,sys\np=(sys.argv[1] if len(sys.argv)>1 else "").lower()\n'
        'print("jefely" if "username" in p else os.environ.get("_T",""))\n',
        encoding="utf-8", newline="\n")
    (ASKPASS / "askpass.cmd").write_text(
        "@echo off\r\n"
        '"C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python310\\python.exe" '
        '"%~dp0askpass.py" %*\r\n', encoding="utf-8", newline="\n")
    genv = {"GIT_ASKPASS": str(ASKPASS / "askpass.cmd"), "_T": TOKEN,
            "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}

    for k, v in (("http.sslBackend", "openssl"), ("http.proxy", PROXY),
                 ("https.proxy", PROXY), ("credential.helper", "")):
        run(["git", "config", k, v])

    print("== 1. commit the release notes ==")
    rc, out, err = run(["git", "add", "-A"])
    rc, out, err = run(["git", "commit", "-q", "-m",
                        "docs: add the 7.0.0 release notes"])
    rc, out, _ = run(["git", "log", "--oneline", "-1"])
    print(f"  HEAD: {out.strip()}")

    print()
    print("== 2. push main ==")
    rc, out, err = run(["git", "push", "origin", "main"], env=genv)
    for line in (out + err).splitlines()[:8]:
        if line.strip():
            print("  " + line)
    print(f"  exit {rc}")
    if rc != 0:
        print("  push failed; stopping")
        return 1

    print()
    print("== 3. tag ==")
    rc, out, _ = run(["git", "tag", "-a", TAG, "-m",
                      "PACSP-ID 7.0.0 — public preprint"])
    print(f"  git tag {TAG}: exit {rc}{' (may already exist)' if rc else ''}")
    rc, out, err = run(["git", "push", "origin", TAG], env=genv)
    for line in (out + err).splitlines()[:6]:
        if line.strip():
            print("  " + line)
    print(f"  exit {rc}")

    print()
    print("== 4. create the release ==")
    body = NOTES.read_text(encoding="utf-8")
    code, resp = api("GET", f"/repos/{OWNER}/{REPO}/releases/tags/{TAG}")
    if code == 200:
        rel = resp
        print(f"  release already exists (id {rel['id']})")
    else:
        code, rel = api("POST", f"/repos/{OWNER}/{REPO}/releases", {
            "tag_name": TAG,
            "name": "PACSP-ID 7.0.0 — 公开预印本",
            "body": body,
            "draft": False,
            "prerelease": False,
        })
        if code != 201:
            print(f"  create failed: HTTP {code} {rel.get('message')}")
            return 1
        print(f"  created (id {rel['id']})")
    print(f"  url: {rel.get('html_url')}")

    print()
    print("== 5. upload assets ==")
    existing = {a["name"] for a in rel.get("assets", [])}
    for asset in sorted(DIST.glob("PACSP-ID-7.0.0-preprint.*")):
        if asset.name in existing:
            print(f"  {asset.name}: already uploaded")
            continue
        code, resp = upload(rel, asset)
        if code in (201, 200):
            print(f"  {asset.name}: uploaded ({resp.get('size', 0):,} bytes)")
        else:
            print(f"  {asset.name}: FAILED HTTP {code} {resp.get('message')}")

    print()
    print("== 6. verify ==")
    code, rel = api("GET", f"/repos/{OWNER}/{REPO}/releases/tags/{TAG}")
    if code == 200:
        print(f"  release: {rel['html_url']}")
        print(f"  published: {rel['published_at']}")
        for a in rel.get("assets", []):
            print(f"    {a['name']:42} {a['size']:>10,} bytes")

    import shutil
    shutil.rmtree(ASKPASS, ignore_errors=True)
    print()
    print(f"  askpass helper removed: {not ASKPASS.exists()}")
    print(f"  token appeared in output: {'YES' if leaked else 'no'}")
    return 0


if __name__ == "__main__":
    import urllib.parse  # noqa: E402  (used by upload)
    sys.exit(main())
