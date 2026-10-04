"""Stage 3 of the gaokao three-arm corpus: check the arms and run the pipeline.

The corpus is three arms over the same 31 prompts:

    gaokao_human_only      a person writes from the prompt, no model involved
    gaokao_ai_raw          one shot from the prompt, untouched
    gaokao_human_curated   a person revises the ai_raw draft

Because the prompts are shared, topic is held constant across all three arms; the
only thing that varies is who produced the text and whether a person exercised
selection over model output. That is the design the paper's section 10.5 needs and
that no public corpus supplies.

Usage:
    python scripts/pacsp_gaokao.py --status
    python scripts/pacsp_gaokao.py --build          # run the pipeline on all arms
    python scripts/pacsp_gaokao.py --compare        # print the arm table

Curation distance is also reported: how far the human edit moved the text from the
raw draft. That is the quantity the curated arm is supposed to capture.
"""

import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ARMS = ["gaokao_human_only", "gaokao_ai_raw", "gaokao_human_curated"]
PY = sys.executable
SENT = re.compile(r"[。！？；!?;]")


def arm_files(arm):
    d = DATA / arm
    return sorted(d.glob("*.txt")) if d.exists() else []


def status():
    print(f"  {'arm':<24} {'files':>6} {'chars tot':>10} {'mean':>7} {'min':>6} {'max':>6}")
    print("  " + "-" * 66)
    for arm in ARMS:
        fs = arm_files(arm)
        if not fs:
            print(f"  {arm:<24} {0:>6}  (empty)")
            continue
        sizes = [f.stat().st_size for f in fs]
        print(f"  {arm:<24} {len(fs):>6} {sum(sizes):>10,} "
              f"{sum(sizes)//len(sizes):>7} {min(sizes):>6} {max(sizes):>6}")

    # per-prompt coverage
    present = {arm: {f.stem for f in arm_files(arm)} for arm in ARMS}
    if all(present.values()):
        common = set.intersection(*present.values())
        print(f"\n  prompts covered by all three arms: {len(common)}/31")
        missing = {a: sorted(set.intersection(*present.values()) ^ v)
                   for a, v in present.items()}
        for a, m in missing.items():
            if m:
                print(f"    {a} missing vs intersection: {m[:8]}")
    return present


def edit_distance():
    """How much the human edit moved each draft, as a similarity ratio."""
    raw = {f.stem: f.read_text(encoding="utf-8").strip()
           for f in arm_files("gaokao_ai_raw")}
    cur = {f.stem: f.read_text(encoding="utf-8").strip()
           for f in arm_files("gaokao_human_curated")}
    pairs = sorted(set(raw) & set(cur))
    if not pairs:
        return []
    out = []
    for k in pairs:
        r = difflib.SequenceMatcher(None, raw[k], cur[k]).ratio()
        out.append({"prompt": k, "similarity": round(r, 4),
                    "raw_chars": len(raw[k]), "curated_chars": len(cur[k])})
    return out


def build():
    arms = [a for a in ARMS if arm_files(a)]
    if not arms:
        print("no arms have content yet; nothing to build")
        return 1
    print(f"  running the pipeline on: {', '.join(arms)}")
    cmd = [PY, "-X", "utf8", str(ROOT / "scripts" / "pacsp_build.py"),
           "--innov", "--target", "centroid", "--datasets", *arms,
           "--out", str(ROOT / "records_centroid")]
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    for line in (r.stdout or "").splitlines():
        if any(k in line for k in ("C_T =", "DONE:", "ERROR", "L6 ")):
            print("   " + line.strip())
    if r.returncode != 0:
        print(f"  pipeline exit {r.returncode}")
        for line in (r.stderr or "").splitlines()[-8:]:
            print("   " + line)
    return r.returncode


def compare():
    js = ROOT / "records_centroid" / "_comparison.json"
    if js.exists():
        d = json.loads(js.read_text(encoding="utf-8"))
        print("  stored comparison:")
        for k, v in d.items():
            print(f"    {k:<26} {v}")
    print()
    recs = {}
    for f in sorted((ROOT / "records_centroid").glob("gaokao_*.pacsp")):
        m = re.match(r"(gaokao_[a-z_]+)_epoch1_base_CT([\d.]+)Se", f.name)
        if m:
            recs.setdefault(m.group(1), []).append(float(m.group(2)))
    print(f"  {'arm':<24} {'C_T (Se)':>10}")
    for a in ARMS:
        for v in recs.get(a, []):
            print(f"  {a:<24} {v:>10.4f}")
    if "gaokao_human_only" in recs and "gaokao_ai_raw" in recs \
            and "gaokao_human_curated" in recs:
        h = recs["gaokao_human_only"][0]
        a = recs["gaokao_ai_raw"][0]
        c = recs["gaokao_human_curated"][0]
        print()
        print("  same-prompt three-arm contrast:")
        print(f"    ai_raw / human_only      = {a/h:.2f}")
        print(f"    human_curated / ai_raw   = {c/a:.2f}   <- the curation effect")
        print(f"    human_curated / human_only = {c/h:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--edit-distance", action="store_true")
    args = ap.parse_args()

    if args.status or not any(vars(args).values()):
        status()
        return 0
    if args.edit_distance:
        rows = edit_distance()
        if not rows:
            print("  no ai_raw/human_curated pairs yet")
            return 0
        print(f"  {'prompt':<8} {'similarity':>11} {'raw':>7} {'curated':>8}")
        for r in rows:
            print(f"  {r['prompt']:<8} {r['similarity']:>11.4f} "
                  f"{r['raw_chars']:>7} {r['curated_chars']:>8}")
        mean = sum(r["similarity"] for r in rows) / len(rows)
        print(f"\n  mean similarity {mean:.4f} "
              f"(1.0 = untouched, lower = heavier revision)")
        (ROOT / "records_centroid").mkdir(parents=True, exist_ok=True)
        (ROOT / "records_centroid" / "curation_distance.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0
    if args.build:
        rc = build()
        compare()
        return rc
    if args.compare:
        compare()
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
