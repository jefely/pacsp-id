"""
从 .pacsp 重建 PNG

两层图：
  A. main  —— 由 figure_recipe 驱动的路径增量 / 认知强度面板（v4.0.0 起）
  B. L6    —— 创新动力学可视化（论文 §7 §8）：情绪树、五元分解、四系数

只依赖 .pacsp 内的 figure_recipe + compute.deltas/mus + results.changepoints
以及 L6 产出的 emotion_tree / innovation / C_T_ext。
"""

import sys
import json
import hashlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(__file__).parent.parent
RECORDS_DIR = ROOT / "records"
CACHE_DIR = ROOT / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# 中文字体回退链（按可用性取第一个）
CJK_FONTS = ["Microsoft YaHei", "SimHei", "Source Han Serif SC",
             "DengXian", "SimSun", "DejaVu Sans"]

# 五元分解配色（论文 §8.2）
CHANNEL_COLORS = {
    "C_DMN": "#d62728",   # 生成
    "C_ECN": "#1f77b4",   # 筛选
    "C_SN": "#2ca02c",    # 切换
    "C_mem": "#ff7f0e",   # 语义记忆
    "C_sel": "#9467bd",   # 内生选择
}
CHANNEL_LABELS = {
    "C_DMN": "C_DMN 生成",
    "C_ECN": "C_ECN 筛选",
    "C_SN": "C_SN 切换",
    "C_mem": "C_mem 语义记忆",
    "C_sel": "C_sel 内生选择",
}


def _use_cjk_font():
    plt.rcParams["font.sans-serif"] = CJK_FONTS
    plt.rcParams["axes.unicode_minus"] = False


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def resolve_path(data, path_str):
    """点分路径解析，如 'compute.deltas'"""
    parts = path_str.split(".")
    cur = data
    for p in parts:
        if isinstance(cur, dict):
            cur = cur[p]
        else:
            return None
    return cur


def render_figure(record, output_dir):
    """根据 figure_recipe 重建图片"""
    recipe = record.get("figure_recipe")
    if not recipe:
        return None, "no figure_recipe"

    figsize = recipe.get("figsize", [14, 8])
    dpi = recipe.get("dpi", 150)
    panels = recipe.get("panels", [])

    if not panels:
        return None, "no panels"

    # 中文字体
    font = recipe.get("font", {})
    plt.rcParams["font.sans-serif"] = [font.get("family", "DejaVu Sans")]
    plt.rcParams["axes.unicode_minus"] = False
    font_size = font.get("size", 12)

    fig, axes = plt.subplots(len(panels), 1, figsize=figsize)
    if len(panels) == 1:
        axes = [axes]

    for panel in panels:
        ax = axes[panel["row"]]

        # 取 y 数据
        y = resolve_path(record, panel["y_data"])
        if y is None:
            continue
        y = np.array(y, dtype=float)
        x = np.arange(1, len(y) + 1)

        # 主曲线
        ax.plot(
            x, y,
            color=panel.get("color", "#1f77b4"),
            marker=panel.get("marker", "o"),
            markersize=panel.get("markersize", 5),
            linewidth=1.5,
        )

        # 竖直变点线
        vlines = panel.get("vlines")
        if vlines:
            positions = resolve_path(record, vlines["source"]) or []
            for pos in positions:
                ax.axvline(
                    int(pos),
                    color=vlines.get("color", "red"),
                    linestyle=vlines.get("linestyle", "--"),
                    linewidth=vlines.get("linewidth", 2),
                    alpha=0.8,
                )

        # 标签
        ax.set_ylabel(panel.get("y_label", ""), fontsize=font_size)
        ax.set_title(panel.get("title", ""), fontsize=font_size + 1)
        if "xlabel" in panel:
            ax.set_xlabel(panel["xlabel"], fontsize=font_size)
        ax.grid(alpha=0.3)

    plt.tight_layout()

    # 文件名
    m = record["metadata"]
    figure_id = recipe.get("figure_id", "main")
    png_name = f"{m['domain']}_{m['epoch']}_{m['variant']}_{figure_id}.png"
    png_path = output_dir / png_name

    plt.savefig(str(png_path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    return png_path, None


def render_l6_emotion_tree(record, output_dir, tree_edges=None):
    """L6-A：情绪树结构图（论文 §7）。

    节点按层级（到根的距离）分层排布，边为父子关系。
    未提供真实情绪词表时使用 emo_0..emo_{n-1} 作为通道名。
    """
    tree = record.get("emotion_tree")
    if not tree:
        return None, "no emotion_tree"

    n_nodes = max(tree.get("n_roots", 0) + tree.get("path_length", 0), 2)
    # 拓扑明细：parents 以字符串为键存储，edges_flat 为 [parent, child] 列表
    parents = {int(k): int(v) for k, v in (tree.get("parents") or {}).items()}
    edges = [tuple(e) for e in (tree.get("edges_flat") or [])]
    roots = [int(r) for r in (tree.get("roots") or [])]

    fig, ax = plt.subplots(figsize=(11, 7))
    _use_cjk_font()

    if not edges:
        # 仅有汇总指标时，退化为指标条形图，避免画出错误拓扑
        ax.axis("off")
        info = [
            ("情绪树深度 d_tree", tree.get("depth")),
            ("树边数", tree.get("path_length")),
            ("根节点数", tree.get("n_roots")),
            ("偏见熵 B_tree (bit)", tree.get("bias_entropy")),
        ]
        ax.text(0.05, 0.85, "情绪树（无拓扑明细，仅汇总指标）",
                fontsize=15, fontweight="bold", transform=ax.transAxes)
        for i, (k, v) in enumerate(info):
            ax.text(0.08, 0.72 - i * 0.09, f"{k}：{v}",
                    fontsize=13, transform=ax.transAxes)
        ax.text(0.05, 0.20,
                "说明：.pacsp 记录当前只存情绪树的汇总指标。\n"
                "要绘制完整拓扑，需在 L6 阶段一并存下 parents / edges。",
                fontsize=10, color="#555555", transform=ax.transAxes)
    else:
        _draw_tree(ax, parents, edges, roots)
        ax.set_title(f"情绪树结构（{record['metadata']['domain']}）  "
                     f"depth={tree.get('depth')}  edges={tree.get('path_length')}  "
                     f"roots={tree.get('n_roots')}", fontsize=13)

    if ax.get_title() == "":
        ax.set_title(f"情绪树（{record['metadata']['domain']}）", fontsize=14)
    plt.tight_layout()
    p = output_dir / f"{_stem(record)}_L6_tree.png"
    plt.savefig(str(p), dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p, None


def _draw_tree(ax, parents, edges, roots=None):
    """把父子关系画成分层图，叶节点标出通道编号。"""
    import collections
    children = collections.defaultdict(list)
    nodes = set(parents.keys())
    for a, b in edges:
        children[a].append(b)
        nodes.add(a)
        nodes.add(b)
    if not roots:
        roots = sorted(n for n in nodes if n not in parents)

    depth = {}

    def walk(n, d, seen=frozenset()):
        if n in seen:
            return
        depth[n] = max(depth.get(n, 0), d)
        for c in children.get(n, []):
            walk(c, d + 1, seen | {n})

    for r in roots:
        walk(r, 0)

    by_level = collections.defaultdict(list)
    for n in sorted(nodes):
        by_level[depth.get(n, 0)].append(n)

    pos = {}
    max_d = max(by_level) if by_level else 0
    for d, lvl_nodes in sorted(by_level.items()):
        for i, n in enumerate(lvl_nodes):
            x = (i + 1) / (len(lvl_nodes) + 1)
            y = 1.0 - d / (max_d + 1) if max_d > 0 else 0.5
            pos[n] = (x, y)

    for a, b in edges:
        if a in pos and b in pos:
            ax.annotate("", xy=pos[b], xytext=pos[a],
                        arrowprops=dict(arrowstyle="->", color="#555555",
                                        lw=1.2, shrinkA=9, shrinkB=9))
    for n, (x, y) in pos.items():
        is_root = n in roots
        ax.scatter([x], [y], s=340 if is_root else 260,
                   color="#d62728" if is_root else "#1f77b4", zorder=3)
        ax.text(x, y, str(n), ha="center", va="center",
                fontsize=8, color="white", zorder=4)
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.06, 1.06)
    ax.axis("off")
    ax.text(0.01, 0.02,
            f"红=根({len(roots)})  蓝=内部/叶节点  层数={max_d + 1}",
            fontsize=9, color="#555555", transform=ax.transAxes)


def render_l6_decomposition(record, output_dir):
    """L6-B：五元分解 + 四系数（论文 §8.2 / §8.4）。"""
    innov = record.get("innovation")
    if not innov:
        return None, "no innovation"

    keys = ["C_DMN", "C_ECN", "C_SN", "C_mem", "C_sel"]
    vals = [float(innov.get(k) or 0.0) for k in keys]

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5),
                             gridspec_kw={"width_ratios": [1.15, 1]})
    _use_cjk_font()

    # --- 左：五元分解（水平堆叠条 + 分量条形） ---
    ax = axes[0]
    total = sum(vals)
    left = 0.0
    for k, v in zip(keys, vals):
        ax.barh([1], [v], left=left, color=CHANNEL_COLORS[k],
                edgecolor="white", height=0.5)
        if v > 0:
            ax.text(left + v / 2, 1, f"{v:.2f}", ha="center", va="center",
                    fontsize=9, color="white", fontweight="bold")
        left += v
    ax.barh([0], [total], color="#bbbbbb", height=0.5)
    ax.text(total / 2 if total else 0, 0, f"C_T_innov = {total:.3f}",
            ha="center", va="center", fontsize=10, fontweight="bold")
    ax.set_yticks([1, 0])
    ax.set_yticklabels(["五元分解", "合计"])
    ax.set_xlabel("瑟值分量", fontsize=11)
    ax.set_title(f"创新动力学五元分解（{record['metadata']['domain']}）", fontsize=13)
    ax.grid(axis="x", alpha=0.3)
    handles = [plt.Rectangle((0, 0), 1, 1, color=CHANNEL_COLORS[k])
               for k in keys]
    ax.legend(handles, [CHANNEL_LABELS[k] for k in keys],
              loc="lower right", fontsize=9, framealpha=0.9)

    # --- 右：四系数（量纲差异大，分开归一化展示） ---
    ax2 = axes[1]
    coef = [("chi_innov", innov.get("chi_innov")),
            ("H_switch", innov.get("H_switch")),
            ("S_int", innov.get("S_int")),
            ("DRI", innov.get("DRI"))]
    labels, values, colors, annot = [], [], [], []
    finite = [abs(float(v)) for _, v in coef if v is not None and abs(float(v)) > 1e-9]
    scale = max(finite) if finite else 1.0
    for name, v in coef:
        labels.append(name)
        if v is None:
            values.append(0.0)
            colors.append("#cccccc")
            annot.append("未定义")
        else:
            fv = float(v)
            values.append(fv / scale)          # 归一到同一尺度
            colors.append("#1f77b4" if fv >= 0 else "#d62728")
            annot.append(f"{fv:.3f}")
    bars = ax2.bar(labels, values, color=colors, edgecolor="white")
    for b, txt in zip(bars, annot):
        h = b.get_height()
        ax2.text(b.get_x() + b.get_width() / 2,
                 h + (0.03 if h >= 0 else -0.09),
                 txt, ha="center", fontsize=10)
    ax2.axhline(0, color="#333333", lw=1)
    ax2.set_ylim(-0.45, 1.15)
    ax2.set_ylabel(f"归一化系数（缩放因子 {scale:.2f}）", fontsize=10)
    ax2.set_title("四个判定系数（论文 §8.4，各自归一化）", fontsize=13)
    ax2.grid(axis="y", alpha=0.3)
    verdict = innov.get("verdict", "")
    ax2.text(0.5, 0.02, f"判定：{verdict}", ha="center", transform=ax2.transAxes,
             fontsize=10, color="#333333",
             bbox=dict(boxstyle="round", fc="#f5f5f5", ec="#cccccc"))

    plt.tight_layout()
    p = output_dir / f"{_stem(record)}_L6_innov.png"
    plt.savefig(str(p), dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p, None


def render_l6_series(record, output_dir):
    """L6-C：C_T 的四项分解时序（论文 §7.4 瑟-树耦合）。"""
    ce = record.get("C_T_ext")
    if not ce:
        return None, "no C_T_ext"

    parts = [("C_path", ce.get("C_path"), "#1f77b4"),
             ("C_jump", ce.get("C_jump"), "#d62728"),
             ("C_depth", ce.get("C_depth"), "#2ca02c"),
             ("C_bias", ce.get("C_bias"), "#ff7f0e")]
    labels = [p[0] for p in parts]
    vals = [float(p[1] or 0.0) for p in parts]

    fig, ax = plt.subplots(figsize=(10, 6))
    _use_cjk_font()
    bottom = 0.0
    for (name, v, color), val in zip(parts, vals):
        ax.bar([0], [val], bottom=bottom, color=color, width=0.5,
               edgecolor="white", label=name)
        if val > 1e-6:
            ax.text(0.32, bottom + val / 2, f"{name} = {val:.4f}",
                    va="center", fontsize=10)
        bottom += val
    ax.text(0, bottom, f"C_T_ext = {ce.get('C_T_ext'):.4f} Se",
            ha="center", va="bottom", fontsize=12, fontweight="bold")
    ax.set_xlim(-0.6, 1.6)
    ax.set_xticks([])
    ax.set_ylabel("瑟值（Se）", fontsize=11)
    ax.set_title(f"瑟-树耦合分解（{record['metadata']['domain']}）\n"
                 f"α={ce.get('alpha')} Se/层, β={ce.get('beta')} Se/bit", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    p = output_dir / f"{_stem(record)}_L6_ctext.png"
    plt.savefig(str(p), dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p, None


def render_l6_comparison(records, output_dir):
    """L6-D：跨域对照（六层记录全景）。人机成对时同时画对照。"""
    rows = []
    for rec in records:
        if "innovation" not in rec or "emotion_tree" not in rec:
            continue
        m = rec["metadata"]
        rows.append({
            "name": m["domain"],
            "C_T": rec["results"]["C_T_Se"],
            "depth": rec["emotion_tree"]["depth"],
            "C_DMN": float(rec["innovation"].get("C_DMN") or 0),
            "C_ECN": float(rec["innovation"].get("C_ECN") or 0),
            "C_SN": float(rec["innovation"].get("C_SN") or 0),
            "C_mem": float(rec["innovation"].get("C_mem") or 0),
            "chi": rec["innovation"].get("chi_innov"),
            "H": rec["innovation"].get("H_switch"),
            "verdict": rec["innovation"].get("verdict", ""),
        })
    if not rows:
        return None, "no L6 records"

    rows.sort(key=lambda r: r["C_T"])
    names = [r["name"] for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(16, 6.5))
    _use_cjk_font()

    # 左：C_T 与情绪树深度
    ax = axes[0]
    x = np.arange(len(rows))
    ax.bar(x - 0.2, [r["C_T"] for r in rows], width=0.4,
           color="#1f77b4", label="C_T (Se)")
    ax2 = ax.twinx()
    ax2.plot(x, [r["depth"] for r in rows], "o--", color="#d62728",
             markersize=9, label="情绪树深度")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=20, ha="right")
    ax.set_ylabel("C_T (Se)", fontsize=11)
    ax2.set_ylabel("情绪树深度 d_tree", fontsize=11, color="#d62728")
    ax.set_title("跨域：认知沉积量与情绪树深度", fontsize=13)
    ax.grid(axis="y", alpha=0.3)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=9)

    # 右：五元分解堆叠
    ax = axes[1]
    bottom = np.zeros(len(rows))
    for k in ["C_DMN", "C_ECN", "C_SN", "C_mem", "C_sel"]:
        vals = np.array([r.get(k, 0.0) if k != "C_sel" else 0.0 for r in rows])
        if k == "C_sel":
            vals = np.zeros(len(rows))
        ax.bar(x, vals, bottom=bottom, color=CHANNEL_COLORS[k],
               label=CHANNEL_LABELS[k], edgecolor="white")
        bottom += vals
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=20, ha="right")
    ax.set_ylabel("瑟值分量", fontsize=11)
    ax.set_title("跨域：创新动力学五元分解", fontsize=13)
    ax.legend(fontsize=8, ncol=2)
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    p = output_dir / "_L6_comparison.png"
    plt.savefig(str(p), dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p, None


def render_l6_human_vs_machine(records, output_dir):
    """L6-E：人 / 机对照（把 machine_* 域与同名人类域配对）。"""
    human = {}
    machine = {}
    for rec in records:
        dom = rec["metadata"]["domain"]
        if "innovation" not in rec:
            continue
        (machine if dom.startswith("machine_") else human)[
            dom.replace("machine_", "")] = rec
    pairs = sorted(set(human) & set(machine))
    if not pairs:
        return None, "no human/machine pairs"

    fig, axes = plt.subplots(1, 3, figsize=(17, 6))
    _use_cjk_font()
    metrics = [("C_T", "C_T (Se)"), ("C_DMN", "C_DMN"), ("E_glob", "E_glob")]

    for ax, (key, label) in zip(axes, metrics):
        hv, mv = [], []
        for d in pairs:
            if key == "E_glob":
                hv.append(float(human[d]["innovation"].get("E_glob") or 0))
                mv.append(float(machine[d]["innovation"].get("E_glob") or 0))
            elif key == "C_T":
                hv.append(human[d]["results"]["C_T_Se"])
                mv.append(machine[d]["results"]["C_T_Se"])
            else:
                hv.append(float(human[d]["innovation"].get(key) or 0))
                mv.append(float(machine[d]["innovation"].get(key) or 0))
        x = np.arange(len(pairs))
        ax.bar(x - 0.2, hv, width=0.4, color="#1f77b4", label="人类")
        ax.bar(x + 0.2, mv, width=0.4, color="#d62728", label="机器")
        ax.set_xticks(x)
        ax.set_xticklabels(pairs, rotation=15)
        ax.set_ylabel(label, fontsize=11)
        ax.set_title(f"{label}：人 / 机", fontsize=12)
        ax.legend(fontsize=9)
        ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    p = output_dir / "_L6_human_vs_machine.png"
    plt.savefig(str(p), dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p, None


def _stem(record):
    m = record["metadata"]
    return f"{m['domain']}_{m['epoch']}_{m['variant']}"


def main():
    import argparse

    ap = argparse.ArgumentParser(description="从 .pacsp 重建 PNG（main + L6）")
    ap.add_argument("--records", default=str(RECORDS_DIR), help="记录目录")
    ap.add_argument("--out", default=str(CACHE_DIR), help="输出目录")
    ap.add_argument("--only", default=None, help="只处理该前缀的记录（如 machine_）")
    ap.add_argument("--no-l6", action="store_true", help="只画 main 图")
    args = ap.parse_args()

    rec_dir = Path(args.records)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    pacsp_files = sorted(rec_dir.glob("*.pacsp"))
    if args.only:
        pacsp_files = [p for p in pacsp_files if p.name.startswith(args.only)]
    print(f"Found {len(pacsp_files)} .pacsp files\n")

    loaded = []
    for pacsp_path in pacsp_files:
        print(f"Processing: {pacsp_path.name}")
        with open(pacsp_path, encoding="utf-8") as f:
            record = json.load(f)

        png_path, err = render_figure(record, out_dir)
        if err:
            print(f"  main SKIP: {err}")
        else:
            png_hash = sha256_file(png_path)
            print(f"  OK main: {png_path.name}  {png_hash[:34]}...")

        if not args.no_l6 and (
                record.get("metadata", {}).get("protocol_version") == "7.0.0-COMPLETE"
                or "innovation" in record):
            for label, fn in (("tree", render_l6_emotion_tree),
                              ("innov", render_l6_decomposition),
                              ("ctext", render_l6_series)):
                try:
                    p, e = fn(record, out_dir)
                    if e:
                        print(f"  L6-{label} SKIP: {e}")
                    else:
                        print(f"  OK L6-{label}: {p.name}")
                except Exception as ex:
                    print(f"  L6-{label} FAIL: {type(ex).__name__}: {ex}")
            loaded.append(record)

        print()

    if not args.no_l6 and loaded:
        print("=== 跨域 L6 对照 ===")
        try:
            p, e = render_l6_comparison(loaded, out_dir)
            print(f"  {'OK ' + p.name if p else 'SKIP: ' + str(e)}")
        except Exception as ex:
            print(f"  FAIL: {type(ex).__name__}: {ex}")

        print("=== 人 / 机 对照 ===")
        try:
            p, e = render_l6_human_vs_machine(loaded, out_dir)
            print(f"  {'OK ' + p.name if p else 'SKIP: ' + str(e)}")
        except Exception as ex:
            print(f"  FAIL: {type(ex).__name__}: {ex}")

    print(f"\n输出目录: {out_dir}")


if __name__ == "__main__":
    main()