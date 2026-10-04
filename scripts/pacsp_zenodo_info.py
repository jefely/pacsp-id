"""Fetch the Zenodo record that the release produced, and verify what it archived."""

import json
import urllib.request

UA = {"User-Agent": "dsh-verify", "Accept": "application/json"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.status, r.url, json.load(r)


print("=== DOI resolution chain ===")
for url in ("https://doi.org/10.5281/zenodo.22801604",
            "https://zenodo.org/api/records/22801604"):
    try:
        code, final, data = get(url)
        print(f"  {url}")
        print(f"    -> {final}")
    except Exception as e:
        print(f"  {url}: {type(e).__name__} {e}")

print()
print("=== record 23138930 metadata (corrected version) ===")
try:
    code, final, d = get("https://zenodo.org/api/records/23138930")
    md = d.get("metadata", {})
    print(f"  doi          : {d.get('doi')}")
    print(f"  concept doi  : {d.get('conceptdoi')}")
    print(f"  record id    : {d.get('id')}")
    print(f"  concept recid: {d.get('conceptrecid')}")
    print(f"  created      : {d.get('created')}")
    print(f"  title        : {md.get('title')}")
    print(f"  version      : {md.get('version')}")
    print(f"  publication  : {md.get('publication_date')}")
    print(f"  resource type: {md.get('resource_type')}")
    print(f"  license      : {md.get('license')}")
    creators = md.get("creators", [])
    print(f"  creators ({len(creators)}):")
    for c in creators:
        print(f"     {c.get('name')}  orcid={c.get('orcid')}")
    print(f"  description  : {(md.get('description') or '')[:160]}")
    print(f"  keywords     : {md.get('keywords')}")
    rel = md.get("related_identifiers", [])
    print(f"  related ids ({len(rel)}):")
    for r in rel:
        print(f"     {r.get('relation')}  {r.get('identifier')}")
    files = d.get("files", [])
    print(f"  files ({len(files)}):")
    for f in files:
        print(f"     {f.get('key'):44} {f.get('size', 0):>10,} bytes")
    print(f"  html         : {d.get('links', {}).get('self_html') or d.get('links', {}).get('doi')}")
except Exception as e:
    print(f"  fetch failed: {type(e).__name__}: {e}")

print()
print("=== what the concept DOI points to ===")
try:
    code, final, d = get("https://zenodo.org/api/records/22801604")
    print(f"  resolved id  : {d.get('id')}")
    print(f"  doi          : {d.get('doi')}")
    print(f"  version      : {d.get('metadata', {}).get('version')}")
except Exception as e:
    print(f"  {type(e).__name__}: {e}")
