"""Add figure cross-references to the DOCX build, purely additively.

The archive stays untouched. Rather than editing the Markdown, this appends one
extra sentence at the end of each data-bearing subsection during assembly, so the
insertion lives in one place, affects only the preprint, and cannot alter any
original sentence.

Figure numbering follows the appendix order produced by pacsp_docx.build_appendix:
  poem F.1-F.4   lyrics F.5-F.8   techdoc F.9-F.12
  machine_poem F.13-F.16   machine_lyrics F.17-F.20   machine_techdoc F.21-F.24
  cross-domain F.25-F.26
within a domain the order is main, tree, innov, ctext.
"""

from dataclasses import dataclass

# An anchor is matched against a paragraph's text or, for table anchors, against
# the joined text of the table's rows. Numbering was derived from the appendix
# build order and verified against the rendered page (图 F.5 = lyrics main).
REFS = [
    # (anchor, kind, cross-reference sentence)
    ("`μ_k` 均值随认知负荷严格递增（0.1272 < 0.1677 < 0.3352），与 §5.3 的论断方向一致。",
     "paragraph",
     "各域的路径增量与认知强度曲线见图 F.1、F.5、F.9（人机交互三域）。"),

    ("结构决定而非序列长度，短文本的情绪表征更集中，反而形成更深的层级。",
     "paragraph",
     "三域的瑟-树耦合分解见图 F.4、F.8、F.12。"),

    ("7.7315", "table",
     "三域的五元分解构成与四个判定系数见图 F.3、F.7、F.11。"),

    ("（约 7%–21%），说明当前指标主要刻画**内容域特性**而非**书写主体特性**。",
     "paragraph",
     "六个域的完整对照见附录F：人机交互三域为图 F.1–F.12，自主生成三域为图 F.13–F.24，"
     "跨域汇总见图 F.25 与图 F.26。"),

    ("不足以支撑判定用途**，§8.4 需据此修订。",
     "paragraph",
     "本节的跨嵌入对比数据来源见 `docs/CONSISTENCY-REPORT.md`。"),

    ("需要强调三点事实：", "paragraph", None),   # marker only, no insertion
]


@dataclass
class Result:
    insertions: int
    unmatched: list


def apply_refs(blocks):
    """Append cross-reference paragraphs. Mutates and returns the block list.

    For a table anchor the reference becomes a new paragraph placed after the
    table rather than an extra table row: an 8-column table padded with a
    "【图】" cell reads badly.
    """
    used = set()
    n = 0
    out = []

    for b in blocks:
        out.append(b)
        for anchor, kind, ref in REFS:
            if anchor in used or ref is None:
                continue
            if kind == "paragraph" and b.kind == "paragraph":
                if b.text.strip().endswith(anchor):
                    b.text = b.text.rstrip() + " " + ref
                    used.add(anchor)
                    n += 1
                    break
            elif kind == "table" and b.kind == "table":
                flat = " ".join(" ".join(r) for r in b.rows)
                if anchor in flat:
                    from pacsp_parse import Block
                    out.append(Block(kind="paragraph", text=ref))
                    used.add(anchor)
                    n += 1
                    break

    blocks[:] = out
    unmatched = [a[:40] for a, k, r in REFS if r is not None and a not in used]
    return Result(n, unmatched)


def describe():
    for a, k, r in REFS:
        if r:
            print(f"  [{k:9}] {a[:52]}")
            print(f"              -> {r[:76]}")
