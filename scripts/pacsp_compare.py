"""
对比图：lyrics vs techdoc 并排展示
论文配图
"""

import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(__file__).parent.parent
RECORDS_DIR = ROOT / "records"
CACHE_DIR = ROOT / "cache"
CACHE_DIR.mkdir(exist_ok=True)


def load_record(pacsp_path):
    with open(pacsp_path, encoding="utf-8") as f:
        return json.load(f)


def main():
    pacsp_files = sorted(RECORDS_DIR.glob("*.pacsp"))
    if len(pacsp_files) < 2:
        print("Need at least 2 .pacsp files")
        return

    records = [(load_record(p), p.stem) for p in pacsp_files]

    plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(2, 2, figsize=(16, 9))

    colors = ["#1f77b4", "#d62728"]

    for i, (record, name) in enumerate(records):
        m = record["metadata"]
        deltas = np.array(record["compute"]["deltas"])
        mus = np.array(record["compute"]["mus"])
        cp = record["results"]["changepoints"]

        x_delta = np.arange(1, len(deltas) + 1)
        x_mu = np.arange(1, len(mus) + 1)

        # 左列：delta_k
        ax = axes[0][i]
        ax.plot(x_delta, deltas, marker="o", color=colors[0], markersize=4)
        for c in cp.get("delta_k", []):
            ax.axvline(c, color="red", linestyle="--", alpha=0.7)
        ax.set_ylabel("delta_k", fontsize=11)
        ax.set_title(
            f"{m['domain']} - Path Increments\nC_T = {record['results']['C_T_Se']:.2f} Se",
            fontsize=12
        )
        ax.grid(alpha=0.3)

        # 右列：mu_k
        ax = axes[1][i]
        ax.plot(x_mu, mus, marker="o", color=colors[1], markersize=4)
        for c in cp.get("mu_k", []):
            ax.axvline(c, color="red", linestyle="--", alpha=0.7)
        ax.set_xlabel("Snapshot", fontsize=11)
        ax.set_ylabel("mu_k", fontsize=11)
        ax.set_title(f"{m['domain']} - Cognitive Intensity", fontsize=12)
        ax.grid(alpha=0.3)

    plt.tight_layout()
    out_path = CACHE_DIR / "_comparison.png"
    plt.savefig(str(out_path), dpi=150, bbox_inches="tight")
    print(f"OK wrote: {out_path.name}")


if __name__ == "__main__":
    main()