"""
从 .pacsp 重建 PNG
只依赖 .pacsp 内的 figure_recipe + compute.deltas/mus + results.changepoints
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


def main():
    pacsp_files = sorted(RECORDS_DIR.glob("*.pacsp"))
    print(f"Found {len(pacsp_files)} .pacsp files\n")

    for pacsp_path in pacsp_files:
        print(f"Processing: {pacsp_path.name}")
        with open(pacsp_path, encoding="utf-8") as f:
            record = json.load(f)

        png_path, err = render_figure(record, CACHE_DIR)
        if err:
            print(f"  SKIP: {err}")
            continue

        png_hash = sha256_file(png_path)
        print(f"  OK wrote: {png_path.name}")
        print(f"     hash = {png_hash[:60]}...")
        print()


if __name__ == "__main__":
    main()