"""Formula rendering for the publication build.

Approach: give the seven Chinese subscript terms an ASCII notation, so every
formula renders through plain mathtext. This is also what a formal paper requires
-- a journal will not typeset \\mu_{本能}. Each affected formula gets an auto-grown
notation legend printed beneath it, and docs/PUBLICATION-NOTES.md records the
1:1 mapping.

Rejected alternative: composing formulas from mathtext + CJK TextAreas with
HPacker. Splitting LaTeX at arbitrary offsets (e.g. between "\\left[" and "\\mu_")
produces invalid fragments that silently degrade to rendering raw source text.
"""

import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib import mathtext

DOC = Path(r"D:\myproject\PACSP-ID\docs\PACSP-ID-7.0.0-COMPLETE.md")
OUT = Path(r"D:\myproject\PACSP-ID\cache\formulas")
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams["figure.max_open_warning"] = 0
parser = mathtext.MathTextParser("path")

CJK_FONT = "SimHei"
for _f in fm.fontManager.ttflist:
    if _f.name == CJK_FONT:
        break

# Chinese term -> ASCII notation used inside formulas
NOTATION = {
    "本能": "instinct",
    "技术": "technique",
    "路径": "path",
    "跳跃": "jump",
    "深度": "depth",
    "偏见": "bias",
    "无外部奖励": "noReward",
}

TOKEN = re.compile(r"\\text\{([^{}]*)\}")
CJK = re.compile(r"[\u4e00-\u9fff]")


def normalize(e):
    """Single pass over the original expression: mechanical mathtext fixes plus
    replacement of every \\text{...} group.

    \\text{...} must be rewritten here rather than in two steps, because a first
    pass turning it into \\mathrm{...} would hide it from the notation pass that
    follows. Note also that mathtext *parses* \\mathrm{本能} happily and only fails
    at draw time, producing tofu boxes -- so parsing success is not a usable test
    for "renderable".
    """
    e = " ".join(e.split())
    e = re.sub(r"\\le(?![a-zA-Z])", r"\\leq", e)
    e = re.sub(r"\\[bB]igg?[glr]?", "", e)
    e = e.replace("\\;", "\\,")
    used = []

    def sub(m):
        inner = m.group(1).strip()
        if inner in NOTATION:
            ascii_form = NOTATION[inner]
            used.append((inner, ascii_form))
            return r"\mathrm{" + ascii_form + "}"
        if CJK.search(inner):
            used.append((inner, "?"))
            return r"\mathrm{?}"
        return r"\mathrm{" + inner + "}"

    return TOKEN.sub(sub, e), used


def parses(e):
    try:
        parser.parse("$" + e + "$", dpi=72, prop=None)
        return True, ""
    except Exception as ex:
        return False, str(ex).split("\n")[-1][:120]


def render(e, path, fontsize=15):
    """Render a normalised, CJK-free expression."""
    ok, err = parses(e)
    if not ok:
        raise ValueError(f"unparseable: {err} | {e[:70]}")
    fig = plt.figure(figsize=(7.4, 1.4), dpi=220)
    fig.text(0.5, 0.5, "$" + e + "$", fontsize=fontsize, ha="center", va="center")
    fig.savefig(path, bbox_inches="tight", facecolor="white", pad_inches=0.10)
    plt.close(fig)


def render_legend(pairs, path, fontsize=9):
    """Render the Chinese-to-notation legend for one formula, in SimHei."""
    line = "　".join(f"{cn} = {asc}" for cn, asc in pairs)
    fig = plt.figure(figsize=(7.4, 0.5), dpi=220)
    fig.text(0.5, 0.5, line, fontsize=fontsize, ha="center", va="center",
             fontfamily=CJK_FONT, color="#444444")
    fig.savefig(path, bbox_inches="tight", facecolor="white", pad_inches=0.06)
    plt.close(fig)


def build():
    text = DOC.read_text(encoding="utf-8")
    display = re.findall(r"\\\[(.*?)\\\]", text, re.S)
    inline = re.findall(r"\\\((.*?)\\\)", text, re.S)

    manifest = {"display": [], "inline": [], "notation": NOTATION}
    fails = []

    for i, f in enumerate(display, 1):
        e, used = normalize(f)
        p = OUT / f"eq_display_{i:02d}.png"
        try:
            render(e, p, 15)
            legend = None
            if used:
                lp = OUT / f"legend_display_{i:02d}.png"
                render_legend(used, lp)
                legend = lp.name
            manifest["display"].append({
                "index": i, "file": p.name,
                "source": " ".join(f.split()), "rendered": e,
                "notation": used, "legend": legend,
            })
        except Exception as ex:
            fails.append((f"display {i}", str(ex)[:110], e[:80]))

    for i, f in enumerate(inline, 1):
        e, used = normalize(f)
        p = OUT / f"eq_inline_{i:03d}.png"
        try:
            render(e, p, 13)
            manifest["inline"].append({
                "index": i, "file": p.name,
                "source": " ".join(f.split()), "rendered": e, "notation": used,
            })
        except Exception as ex:
            fails.append((f"inline {i}", str(ex)[:110], e[:80]))

    return manifest, fails


if __name__ == "__main__":
    import json

    manifest, fails = build()
    print(f"display rendered: {len(manifest['display'])}")
    print(f"inline  rendered: {len(manifest['inline'])}")
    print(f"files: {len(list(OUT.glob('*.png')))}")
    print()
    print("=== formulas that received a notation legend ===")
    for d in manifest["display"]:
        if d["notation"]:
            pairs = ", ".join(f"{c}->{a}" for c, a in d["notation"])
            print(f"  display [{d['index']:>2}] {pairs}")
    for d in manifest["inline"]:
        if d["notation"]:
            pairs = ", ".join(f"{c}->{a}" for c, a in d["notation"])
            print(f"  inline  [{d['index']:>3}] {pairs}")
    if fails:
        print()
        print(f"=== failures ({len(fails)}) ===")
        for n, err, e in fails:
            print(f"  {n}: {err}")
            print(f"      {e}")
    (OUT / "formula_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"manifest: {OUT / 'formula_manifest.json'}")
