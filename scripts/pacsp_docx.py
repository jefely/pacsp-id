"""Assemble the publication DOCX from the parsed paper.

Stage 2 of the publication build. Reads the archive read-only; writes only into
build/. Formulas are embedded as images (mathtext cannot be inlined as OMML),
figures are appended in a dedicated appendix so the original chapter numbering is
undisturbed, and every Chinese term inside a formula is explained by an
auto-generated legend plus a global notation table.
"""

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(r"D:\myproject\PACSP-ID")
sys.path.insert(0, str(ROOT / "scripts"))

from pacsp_parse import (  # noqa: E402
    DOC, FORMULA_DIR, ROOT as _R, load_manifest, parse,
)

FIG_DIR = ROOT / "cache" / "figures"
BUILD = ROOT / "build"
OUT_DOCX = BUILD / "PACSP-ID-7.0.0-preprint.docx"

CJK = "SimSun"
CJK_HEAD = "SimHei"
LATIN = "Cambria"
MONO = "Consolas"

# figure stem -> (group label, kind label)
KINDS = [
    ("main", "主图", "路径增量 delta_k 与认知强度 mu_k（虚线为变点）"),
    ("L6_tree", "情绪树", "情绪树结构与深度 d_tree"),
    ("L6_innov", "创新五元分解", "创新动力学五元分解（论文 §8.2）与四个判定系数（§8.4）"),
    ("L6_ctext", "瑟-树耦合", "瑟-树耦合分解 C_path / C_jump / C_depth / C_bias（论文 §7.4）"),
]

DOMAIN_LABEL = {
    "poem": "诗歌（人机交互）",
    "lyrics": "歌词（人机交互）",
    "techdoc": "技术文档（人机交互）",
    "machine_poem": "诗歌（自主生成）",
    "machine_lyrics": "歌词（自主生成）",
    "machine_techdoc": "技术文档（自主生成）",
}

NOTATION_ORDER = [("本能", "instinct"), ("技术", "technique"), ("路径", "path"),
                  ("跳跃", "jump"), ("深度", "depth"), ("偏见", "bias"),
                  ("无外部奖励", "noReward")]


def set_run_font(run, name=LATIN, size=None, bold=None, color=None):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rf)
    rf.set(qn("w:ascii"), name)
    rf.set(qn("w:hAnsi"), name)
    rf.set(qn("w:eastAsia"), CJK_HEAD if name in (CJK_HEAD,) else CJK)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def add_para(doc, text="", size=10.5, bold=None, align=None, space_after=4,
             style=None, indent_first=False):
    p = doc.add_paragraph(style=style)
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.28
    if indent_first:
        p.paragraph_format.first_line_indent = Pt(21)
    if text:
        r = p.add_run(text)
        set_run_font(r, LATIN, size, bold)
    return p


def add_heading(doc, text, level):
    import pacsp_inline
    text = pacsp_inline.strip_markup(text)
    sizes = {1: 17, 2: 13, 3: 11.5, 4: 11, 5: 10.5, 6: 10.5}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12 if level <= 2 else 8)
    p.paragraph_format.space_after = Pt(5)
    r = p.add_run(text)
    set_run_font(r, CJK_HEAD, sizes.get(level, 10.5), bold=True,
                 color=RGBColor(0x1A, 0x1A, 0x1A))
    return p


def add_mixed_text(p, text, size=10.5):
    """Write text honouring **bold**, *italic*, `code` and formula markers."""
    import pacsp_inline

    inl = load_manifest()[1]
    for kind, payload in pacsp_inline.split_inline(text):
        if kind == "formula":
            entry = inl.get(int(payload))
            if entry:
                png = FORMULA_DIR / entry["file"]
                if png.exists():
                    p.add_run().add_picture(str(png), height=Pt(size * 1.30))
                    continue
            r = p.add_run("(公式)")
            set_run_font(r, LATIN, size)
        elif kind == "code":
            r = p.add_run(payload)
            set_run_font(r, MONO, size - 0.5)
        elif kind == "bold":
            r = p.add_run(payload)
            set_run_font(r, CJK_HEAD, size, bold=True)
        elif kind == "italic":
            r = p.add_run(payload)
            set_run_font(r, LATIN, size)
            r.font.italic = True
        else:
            r = p.add_run(payload)
            set_run_font(r, LATIN, size)


def add_display_formula(doc, block):
    png = FORMULA_DIR / block.caption
    if png.exists():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(3)
        width = Cm(13.2)
        p.add_run().add_picture(str(png), width=width)
    if block.image:
        leg = FORMULA_DIR / block.image
        if leg.exists():
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(8)
            p.add_run().add_picture(str(leg), width=Cm(9.5))
    else:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(8)


def add_table(doc, block):
    rows = block.rows
    if not rows:
        return
    ncol = max(len(r) for r in rows)
    t = doc.add_table(rows=0, cols=ncol)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for ci in range(ncol):
            txt = row[ci] if ci < len(row) else ""
            cell = cells[ci]
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            r = p.add_run(txt)
            set_run_font(r, LATIN, 9, bold=(ri == 0))
    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(6)


def add_figure(doc, path, caption, width_cm=14.0):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(str(path), width=Cm(width_cm))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.space_after = Pt(10)
    r = c.add_run(caption)
    set_run_font(r, CJK, 9, color=RGBColor(0x33, 0x33, 0x33))


def build_appendix(doc):
    doc.add_page_break()
    add_heading(doc, "附录F：图表", 1)
    add_para(doc, "本附录收载全部 26 张由流水线生成的图。这些图在原始存档 "
                  "PACSP-ID-7.0.0-COMPLETE.md 中未被引用；此处补入，"
                  "并在正文相应小节标注交叉引用。全部图可由 "
                  "scripts/pacsp_figure.py 复现。", size=10)

    fig_no = 0
    groups = ["poem", "lyrics", "techdoc", "machine_poem", "machine_lyrics",
              "machine_techdoc"]
    for g in groups:
        add_heading(doc, f"F.{groups.index(g)+1} {DOMAIN_LABEL[g]}", 2)
        for stem, kind_label, kind_desc in KINDS:
            png = FIG_DIR / f"{g}_epoch1_base_{stem}.png"
            if not png.exists():
                continue
            fig_no += 1
            add_figure(doc, png, f"图 F.{fig_no}　{DOMAIN_LABEL[g]}·{kind_label}：{kind_desc}")

    add_heading(doc, "F.7 跨域对比", 2)
    for png, cap in (
        (FIG_DIR / "_L6_comparison.png", "跨域：认知沉积量与情绪树深度、创新动力学五元分解"),
        (FIG_DIR / "_L6_human_vs_machine.png", "跨域：人机交互与自主生成两组对照"),
    ):
        if png.exists():
            fig_no += 1
            add_figure(doc, png, f"图 F.{fig_no}　{cap}")
    return fig_no


def build(doc):
    disp, inl = load_manifest()
    blocks = parse(DOC.read_text(encoding="utf-8"), inl)

    import pacsp_refs
    refs = pacsp_refs.apply_refs(blocks)
    print(f"  figure cross-references inserted: {refs.insertions}")
    for u in refs.unmatched:
        print(f"  [!] anchor unmatched: {u}")

    # title page
    add_heading(doc, "从意义权到认知沉积", 1)
    add_para(doc, "PACSP-ID 框架的理论建构、创新动力学标识与验证工程",
             size=12.5, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=14)
    add_para(doc, "版本 7.0.0-COMPLETE · 公开预印本", size=10.5,
             align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    add_para(doc, "作者：jefely　ORCID 0009-0005-9487-8555", size=10.5,
             align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    add_para(doc, "仓库：https://github.com/jefely/pacsp-id", size=10,
             align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    add_para(doc, "本预印本由 docs/PACSP-ID-7.0.0-COMPLETE.md 机械转换而来，"
                  "转换规则见 docs/PUBLICATION-NOTES.md。原始存档未作改动。",
             size=9, align=WD_ALIGN_PARAGRAPH.CENTER)

    # notation table
    doc.add_page_break()
    add_heading(doc, "公式符号记法", 1)
    add_para(doc, "原始存档的公式使用中文下标（如 μ_本能）。为符合排版规范并保证"
                  "正确渲染，预印本改用 ASCII 记法，对应关系如下（含义完全不变）：",
             size=10)
    t = doc.add_table(rows=1, cols=2)
    t.style = "Table Grid"
    hdr = t.rows[0].cells
    for i, h in enumerate(("原中文记法", "预印本记法")):
        hdr[i].text = ""
        r = hdr[i].paragraphs[0].add_run(h)
        set_run_font(r, CJK_HEAD, 9.5, bold=True)
    for cn, asc in NOTATION_ORDER:
        cells = t.add_row().cells
        for i, v in enumerate((cn, asc)):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(v)
            set_run_font(r, LATIN, 9.5)

    for b in blocks:
        if b.kind == "heading":
            if b.level == 1:
                doc.add_page_break()
                add_heading(doc, b.text, 1)
            else:
                add_heading(doc, b.text, min(b.level, 4))
        elif b.kind == "paragraph":
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 1.28
            if not b.text.startswith(("本文", "**")):
                p.paragraph_format.first_line_indent = Pt(21)
            add_mixed_text(p, b.text, 10.5)
        elif b.kind == "formula":
            add_display_formula(doc, b)
        elif b.kind == "list":
            for depth, item in b.items:
                p = doc.add_paragraph(style="List Bullet" if depth == 0 else "List Bullet 2")
                p.paragraph_format.space_after = Pt(2)
                add_mixed_text(p, item, 10.5)
        elif b.kind == "table":
            add_table(doc, b)
        elif b.kind == "quote":
            for line in b.lines:
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Pt(18)
                p.paragraph_format.space_after = Pt(3)
                add_mixed_text(p, line, 10)
        elif b.kind == "code":
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            r = p.add_run("\n".join(b.lines))
            set_run_font(r, MONO, 8.5)
        elif b.kind == "rule":
            pass

    nfig = build_appendix(doc)
    return len(blocks), nfig


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    doc = Document()
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Cm(2.4)
    sec.top_margin = sec.bottom_margin = Cm(2.2)

    style = doc.styles["Normal"]
    style.font.name = LATIN
    style.font.size = Pt(10.5)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), CJK)

    nblocks, nfig = build(doc)
    doc.save(str(OUT_DOCX))
    print(f"  blocks: {nblocks}")
    print(f"  figures embedded: {nfig}")
    print(f"  written: {OUT_DOCX}")
    print(f"  size: {OUT_DOCX.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
