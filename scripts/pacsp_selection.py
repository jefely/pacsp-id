"""Turn the reader's choices into arms and measure the curation effect.

The task: for each prompt, two model drafts were shown as 候选一 / 候选二, order
randomised, lengths matched. The reader picks the better one. That pick is a pure act
of human selection over model output -- no human writing involved -- which is exactly
the variable the paper's section 10.5 needs.

Arms produced:
    gaokao_chosen      the picked drafts
    gaokao_unchosen    the rejected drafts

Since both arms are machine-written, any C_T difference between them is attributable
to the selection step alone, with authorship held constant. That is the cleanest
contrast available from this material, and it sidesteps the writing-capacity problem
entirely.

Usage:
    python scripts/pacsp_selection.py --template     # write a fillable answer file
    python scripts/pacsp_selection.py --check        # validate what has been filled
    python scripts/pacsp_selection.py --build        # build arms and run the pipeline
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEL = DATA / "gaokao_selection"
KEY = SEL / "_key.json"
CHOICE = SEL / "_choice.json"
TEMPLATE = SEL / "_choice.template.txt"

CHOSEN = DATA / "gaokao_chosen"
UNCHOSEN = DATA / "gaokao_unchosen"


def load_key():
    if not KEY.exists():
        print(f"  missing {KEY}")
        return None
    return json.loads(KEY.read_text(encoding="utf-8"))


def parse_answers(text):
    """Accept lines like '001 A', '001: a', '1 A', '001=2'."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(\d{1,3})\s*[:=,、\s]\s*([AaBb１２]|[12]|一|二)\s*$", line)
        if not m:
            continue
        idx = int(m.group(1))
        raw = m.group(2)
        pick = 1 if raw in ("A", "a", "1", "１", "一") else 2
        out[idx] = pick
    return out


def write_template(key):
    lines = [
        "# 选择记录：每题填 A 或 B（也可写 1 或 2）",
        "# 看完 data/gaokao_selection/NNN.txt 后填对应行；不填的行会被跳过",
        "# 选择依据：哪一篇更好。请勿参考长度——两篇长度已匹配。",
        "",
    ]
    for item in key["items"]:
        lines.append(f"{item['index']:03d}    # 候选一 {item['chars_1']} 字 / "
                     f"候选二 {item['chars_2']} 字")
    TEMPLATE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"  template written: {TEMPLATE}")
    print("  fill each line as '001 A' or '001 B', save it as _choice.txt, then run --check")


def load_answers():
    for name in ("_choice.txt", "_choice.json"):
        p = SEL / name
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        if name.endswith(".json"):
            try:
                d = json.loads(text)
                return {int(k): int(v) for k, v in d.items()}
            except Exception:
                continue
        return parse_answers(text)
    return {}


def check(key):
    ans = load_answers()
    n = len(key["items"])
    have = len(ans)
    print(f"  recorded: {have}/{n}")
    if have < n:
        missing = [i["index"] for i in key["items"] if i["index"] not in ans]
        print(f"  missing : {missing[:20]}{' ...' if len(missing) > 20 else ''}")
        print("  fill those lines and re-run, or build with what is recorded")
    if have:
        picks = {"候选一": sum(1 for v in ans.values() if v == 1),
                 "候选二": sum(1 for v in ans.values() if v == 2)}
        print(f"  picks   : {picks}")
        # which model got picked, decoded
        by = {}
        for it in key["items"]:
            if it["index"] in ans:
                slot = "candidate_1" if ans[it["index"]] == 1 else "candidate_2"
                by[it[slot]] = by.get(it[slot], 0) + 1
        print(f"  by model: {by}")
    return ans


def build(key, ans):
    if not ans:
        print("  no choices recorded; nothing to build")
        return 1
    for d in (CHOSEN, UNCHOSEN):
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*.txt"):
            f.unlink()

    n = 0
    for it in key["items"]:
        idx = it["index"]
        if idx not in ans:
            continue
        sheet = (SEL / f"{idx:03d}.txt").read_text(encoding="utf-8")
        # the sheet holds the two candidates; re-read from the model arms so the
        # stored arms contain the model output, not the sheet formatting
        model = it["candidate_1"] if ans[idx] == 1 else it["candidate_2"]
        other = it["candidate_2"] if ans[idx] == 1 else it["candidate_1"]
        subs = {"qwen": DATA / "gaokao_ai_raw", "r1": DATA / "gaokao_ai_raw_b"}
        # the sheets were trimmed for length; reproduce that trim from the sheet
        parts = re.split(r"【候选[一二]】", sheet)
        if len(parts) < 3:
            continue
        body1 = parts[1].split("=" * 70)[0].strip()
        body2 = parts[2].strip()
        body1 = re.sub(r"^（\d+ 字符）\s*", "", body1).strip()
        body2 = re.sub(r"^（\d+ 字符）\s*", "", body2).strip()
        chosen = body1 if ans[idx] == 1 else body2
        unchosen = body2 if ans[idx] == 1 else body1
        (CHOSEN / f"{idx:03d}.txt").write_text(chosen + "\n", encoding="utf-8",
                                               newline="\n")
        (UNCHOSEN / f"{idx:03d}.txt").write_text(unchosen + "\n", encoding="utf-8",
                                                 newline="\n")
        n += 1

    meta = {
        "chosen_model_counts": {},
        "count": n,
        "note": ("both arms are machine-written, so a C_T difference between them "
                 "comes from the selection step, not from authorship"),
    }
    for it in key["items"]:
        idx = it["index"]
        if idx in ans:
            m = it["candidate_1"] if ans[idx] == 1 else it["candidate_2"]
            meta["chosen_model_counts"][m] = \
                meta["chosen_model_counts"].get(m, 0) + 1
    (CHOSEN / "_PROVENANCE.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    cs = [f.stat().st_size for f in CHOSEN.glob("*.txt")]
    us = [f.stat().st_size for f in UNCHOSEN.glob("*.txt")]
    print(f"  built {n} pairs")
    if cs:
        print(f"    chosen   mean {sum(cs)//len(cs)} bytes")
        print(f"    unchosen mean {sum(us)//len(us)} bytes")
    print(f"    chosen by model: {meta['chosen_model_counts']}")

    print()
    print("  running the pipeline on both arms")
    cmd = [sys.executable, "-X", "utf8", str(ROOT / "scripts" / "pacsp_build.py"),
           "--innov", "--target", "centroid",
           "--datasets", "gaokao_chosen", "gaokao_unchosen",
           "--out", str(ROOT / "records_centroid")]
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    for line in (r.stdout or "").splitlines():
        if "C_T =" in line or "DONE:" in line:
            print("   " + line.strip())
    if r.returncode != 0:
        for line in (r.stderr or "").splitlines()[-6:]:
            print("   " + line)
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--build", action="store_true")
    args = ap.parse_args()

    key = load_key()
    if not key:
        return 1
    if args.template:
        write_template(key)
        return 0
    if args.check:
        check(key)
        return 0
    if args.build:
        return build(key, load_answers())
    write_template(key)
    check(key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
