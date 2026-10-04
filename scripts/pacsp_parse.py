"""Parse the paper Markdown into a structured document model.

Stage 1 of the publication build. The archive file is read only; nothing here
writes to it. Inline and display formulas become image references resolved
against cache/formulas/formula_manifest.json, and figure placeholders are
recognised so the DOCX stage can embed the PNGs.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(r"D:\myproject\PACSP-ID")
DOC = ROOT / "docs" / "PACSP-ID-7.0.0-COMPLETE.md"
FORMULA_DIR = ROOT / "cache" / "formulas"
MANIFEST = FORMULA_DIR / "formula_manifest.json"

DISPLAY_RE = re.compile(r"\\\[(.*?)\\\]", re.S)
INLINE_RE = re.compile(r"\\\((.*?)\\\)", re.S)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
TABLE_SEP_RE = re.compile(r"^\|[\s:\-|]+\|$")
IMG_RE = re.compile(r"^!\[(.*?)\]\((.*?)\)\s*(.*)$")


@dataclass
class Block:
    kind: str
    text: str = ""
    level: int = 0
    items: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    lines: list = field(default_factory=list)
    caption: str = ""
    image: str = ""


def load_manifest():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    disp = {d["index"]: d for d in data["display"]}
    inl = {d["index"]: d for d in data["inline"]}
    return disp, inl


def decorate_inline(text, inl):
    """Replace each \\(...\\) with a marker the DOCX stage turns into an image."""
    counter = {"n": 0}

    def sub(m):
        counter["n"] += 1
        idx = counter["n"]
        entry = inl.get(idx)
        if not entry:
            return m.group(0)
        return "⟦INLINE:%03d⟧" % idx

    return INLINE_RE.sub(sub, text)


def parse(md_text, inl):
    lines = md_text.splitlines()
    blocks = []
    i = 0
    disp_counter = {"n": 0}

    # strip the provenance HTML comment at the top
    if lines and lines[0].startswith("<!--"):
        while i < len(lines) and "-->" not in lines[i]:
            i += 1
        i += 1

    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped in ("---", "***", "___"):
            blocks.append(Block(kind="rule"))
            i += 1
            continue

        m = HEADING_RE.match(line)
        if m:
            blocks.append(Block(kind="heading", level=len(m.group(1)),
                                text=m.group(2).strip()))
            i += 1
            continue

        # fenced code
        if stripped.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            blocks.append(Block(kind="code", lines=buf))
            continue

        # image
        mi = IMG_RE.match(stripped)
        if mi:
            blocks.append(Block(kind="figure", caption=mi.group(1),
                                image=mi.group(2), text=mi.group(3)))
            i += 1
            continue

        # display formula: \[ ... \] possibly spanning lines
        if stripped.startswith("\\["):
            buf = [stripped]
            while "\\]" not in buf[-1] and i + 1 < len(lines):
                i += 1
                buf.append(lines[i].strip())
            joined = "\n".join(buf)
            mm = DISPLAY_RE.search(joined)
            if mm:
                disp_counter["n"] += 1
                idx = disp_counter["n"]
                entry = load_manifest()[0].get(idx)
                blocks.append(Block(kind="formula",
                                    text=" ".join(mm.group(1).split()),
                                    level=idx,
                                    caption=entry["file"] if entry else "",
                                    image=entry.get("legend") or "" if entry else ""))
            i += 1
            continue

        # table
        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cell_line = lines[i].strip()
                if not TABLE_SEP_RE.match(cell_line):
                    cells = [c.strip() for c in cell_line.strip("|").split("|")]
                    rows.append(cells)
                i += 1
            blocks.append(Block(kind="table", rows=rows))
            continue

        # lists
        if re.match(r"^\s*(?:[-*+]|\d+\.)\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*(?:[-*+]|\d+\.)\s+", lines[i]):
                m2 = re.match(r"^(\s*)(?:[-*+]|\d+\.)\s+(.*)$", lines[i])
                items.append((len(m2.group(1)), m2.group(2)))
                i += 1
            blocks.append(Block(kind="list", items=items))
            continue

        # blockquote
        if stripped.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append(Block(kind="quote", lines=buf))
            continue

        # paragraph
        buf = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", "|", ">", "```", "\\["))
                    or nxt in ("---", "***", "___")
                    or re.match(r"^\s*(?:[-*+]|\d+\.)\s+", lines[i])):
                break
            buf.append(nxt)
            i += 1
        text = " ".join(buf)
        blocks.append(Block(kind="paragraph", text=decorate_inline(text, inl)))

    return blocks


def main():
    disp, inl = load_manifest()
    md = DOC.read_text(encoding="utf-8")
    blocks = parse(md, inl)

    kinds = {}
    for b in blocks:
        kinds[b.kind] = kinds.get(b.kind, 0) + 1

    print("=== parsed block counts ===")
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        print(f"  {k:10} {v}")

    print()
    print(f"  headings : {kinds.get('heading', 0)}")
    print(f"  formulas : {kinds.get('formula', 0)}  (manifest display: {len(disp)})")
    print(f"  tables   : {kinds.get('table', 0)}")
    print(f"  figures  : {kinds.get('figure', 0)}  (archive has none; added later)")

    print()
    print("=== first 8 headings ===")
    n = 0
    for b in blocks:
        if b.kind == "heading":
            print(f"  {'  ' * (b.level - 1)}{'#' * b.level} {b.text[:70]}")
            n += 1
            if n >= 8:
                break

    print()
    print("=== formula blocks: manifest mapping ===")
    for b in blocks:
        if b.kind == "formula":
            leg = b.image or "-"
            print(f"  [{b.level:>2}] {b.caption:22} legend={leg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
