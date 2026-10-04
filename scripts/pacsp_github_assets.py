"""Update the v7.0.0 release assets with the cross-referenced build."""

import json
import mimetypes
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN = os.environ.pop("PACSP_TOKEN", "")
OWNER, REPO, TAG = "jefely", "pacsp-id", "v7.0.0"
ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def api(method, path, body=None, raw=None, ctype=None, absolute=False):
    url = path if absolute else ("https://api.github.com" + path)
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + TOKEN,
        "User-Agent": "dsh-release",
        "Accept": "application/vnd.github+json",
        "Content-Type": ctype or "application/json",
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
    code, rel = api("GET", f"/repos/{OWNER}/{REPO}/releases/tags/{TAG}")
    if code != 200:
        print(f"release not found: HTTP {code}")
        return 1
    print(f"  release id {rel['id']}")

    for asset in rel.get("assets", []):
        print(f"  deleting old asset {asset['name']} ({asset['size']:,} bytes)")
        api("DELETE", f"/repos/{OWNER}/{REPO}/releases/assets/{asset['id']}")

    print()
    # upload_url is on uploads.github.com, NOT api.github.com -- concatenating the
    # two gives a non-existent host and the upload fails after the old assets have
    # already been deleted, so use the absolute URL as returned.
    upload_url = rel["upload_url"].split("{")[0]
    print(f"  upload endpoint: {upload_url}")
    for f in sorted(DIST.glob("PACSP-ID-7.0.0-preprint.*")):
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        url = f"{upload_url}?name={urllib.parse.quote(f.name)}"
        code, resp = api("POST", url, raw=f.read_bytes(), ctype=ctype, absolute=True)
        status = "ok" if code in (200, 201) else f"FAILED HTTP {code} {resp.get('message')}"
        print(f"  {f.name:42} {f.stat().st_size:>10,} bytes  {status}")

    print()
    code, rel = api("GET", f"/repos/{OWNER}/{REPO}/releases/tags/{TAG}")
    if code == 200:
        print("=== final state ===")
        print(f"  {rel['html_url']}")
        for a in rel.get("assets", []):
            print(f"    {a['name']:42} {a['size']:>10,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
