"""Inline Markdown handling for the DOCX stage.

The archive mixes several inline conventions that must survive the conversion:
  **bold**   `code`   *italic*   \\x00INLINE:nnn\\x00 formula markers
An earlier version passed the paragraph text through verbatim, so the rendered
PDF showed literal "**定义 1.2.1**" and "`S_int`".
"""

import re

# Order matters: bold before italic, so ** is not eaten by a single *.
# Note the leading | on the italic branch -- without it the bold and italic
# patterns are concatenated instead of being alternatives, and nothing matches.
TOKEN_RE = re.compile(
    r"(⟦INLINE:\d+⟧"                # formula marker
    r"|\*\*.+?\*\*"                         # bold
    r"|(?<!\*)\*(?!\*).+?(?<!\*)\*(?!\*)"   # italic
    r"|`[^`]+`"                             # inline code
    r")",
    re.S,
)


def split_inline(text):
    """Yield (kind, payload) tuples.

    kind is one of: text, bold, italic, code, formula
    """
    out = []
    pos = 0
    for m in TOKEN_RE.finditer(text):
        if m.start() > pos:
            out.append(("text", text[pos:m.start()]))
        tok = m.group(0)
        if tok.startswith("⟦INLINE:"):
            out.append(("formula", tok[len("⟦INLINE:"):-1]))
        elif tok.startswith("**"):
            out.append(("bold", tok[2:-2]))
        elif tok.startswith("`"):
            out.append(("code", tok[1:-1]))
        elif tok.startswith("*"):
            out.append(("italic", tok[1:-1]))
        else:
            out.append(("text", tok))
        pos = m.end()
    if pos < len(text):
        out.append(("text", text[pos:]))
    return out


def strip_markup(text):
    """Plain text with all inline markup removed (for captions and headings)."""
    return "".join(p if k == "text" else (p if k == "text" else p)
                   for k, p in split_inline(text))


if __name__ == "__main__":
    samples = [
        "**定义 1.2.1（意义权）**：意义权是个体对认知生成的分层所有权。",
        "`S_int` 对嵌入空间不稳健，符号可翻转，§8.4 需修订",
        "本文以**意义权**替代“意义主权”。",
        "C_T 与 μ_k 均更高（见 x\\x00INLINE:018\\x00 与 y）",
        "混合：**粗体**、*斜体*、`代码`与公式\\x00INLINE:003\\x00。",
    ]
    for s in samples:
        print("IN :", s[:70])
        for k, p in split_inline(s):
            print(f"     {k:8} {p[:60]}")
        print()
