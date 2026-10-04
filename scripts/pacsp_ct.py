"""Compute C_T for a corpus directory, as a small standalone tool.

C_T = sum_k mu_k * delta_k over consecutive snapshots, where
    delta_k = ||emb[k+1] - emb[k]||      (unnormalised Euclidean distance)
    mu_k    = 1 - mean cosine similarity inside a window  (semantic roughness)
with embeddings from BAAI/bge-large-zh-v1.5.

This is a thin front end over the functions in pacsp_build, imported rather than
reimplemented, so the numbers here match the pipeline byte for byte. It exists
because measuring a directory otherwise means running the whole six-layer build and
reading a record file.

Usage
    python scripts/pacsp_ct.py data/poem
    python scripts/pacsp_ct.py data/poem data/machine_poem --json out.json
    python scripts/pacsp_ct.py data/poem --explain
    python scripts/pacsp_ct.py data/poem --bootstrap 2000

Read the caveats printed under --explain before comparing corpora of different
lengths or registers: C_T sums unnormalised distances, so it rises with text length
and with semantic distance from the embedding space's centre. Both have already
produced misleading comparisons in this project.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pacsp_build import (  # noqa: E402
    compute_ct, compute_deltas, compute_embeddings, compute_mus, load_samples,
)

DEFAULT_MODEL = "BAAI/bge-large-zh-v1.5"
DEFAULT_WINDOW = 5

EXPLAIN = """
C_T 是什么
----------
    delta_k = ||emb[k+1] - emb[k]||         相邻快照嵌入的欧氏距离（未归一化）
    mu_k    = 1 - 窗口内余弦相似度均值        局部语义"粗糙度"
    C_T     = sum_k mu_k * delta_k

一次"快照"是目录里的一个 .txt 文件，按文件名排序。所以 C_T 度量的是
**相邻文本之间的语义位移，乘以该处的语义粗糙度**。

读数时必须知道的四件事
----------------------
1. **长度效应**：delta_k 未归一化，文本越长，可累积的位移越多，C_T 通常越大。
   跨语料比较前请先看表里报出的 bytes 均值；长度差超过约 10% 工具会自动提示。

2. **语域/离群效应**：mu_k 含 (1 - cos_sim)，文本若整体远离嵌入空间中心
   （例如文言、方言、专业术语密集），mu_k 会系统性偏高。
   本项目实测：唐代绝句（每首 72 字节，最短）C_T 反而最高（11.54 Se），
   高于篇均 19,545 字节的技术文档（7.40 Se）。

3. **结构效应**：相同字符数下，句子更短更密会产生更多语义跳变。
   本项目实测：HC3 数据中 AI 答案句数是人类的 1.19-1.35 倍、句均长 0.60-0.64 倍。

4. **模型效应**：同一题、同一提示，仅换生成模型，C_T 相差可达 31%
   （qwen2.5:7b 9.5902 vs deepseek-r1:14b 6.6421）。

**结论**：C_T 在**同一语料、同一嵌入空间、同一采集方式**内部比较是有意义的；
跨语料比较必须控制长度、语域与结构，否则测到的是这些表层特征，而不是认知负荷。
"""


def warm_encoder(model_name):
    """Load the encoder once before the loop; loading dominates short runs."""
    t0 = time.time()
    compute_embeddings(["warmup"], model_name=model_name)
    print(f"  [encoder {model_name} loaded in {time.time()-t0:.1f}s]",
          file=sys.stderr)


def analyse(directory, model_name, window, bootstrap=0, seed=0):
    t0 = time.time()
    texts, files = load_samples(directory)
    if len(texts) < 2:
        return {"dir": str(directory), "error": "need at least 2 .txt files",
                "files": len(texts)}
    if not texts:
        return {"dir": str(directory), "error": "no .txt files found", "files": 0}

    emb = compute_embeddings(texts, model_name=model_name)
    deltas = compute_deltas(emb)
    mus = compute_mus(emb, window=window)
    ct = compute_ct(deltas, mus)

    sizes = [len(t.encode("utf-8")) for t in texts]
    chars = [len(t) for t in texts]
    d = np.asarray(deltas, dtype=float)
    m = np.asarray(mus, dtype=float)

    out = {
        "dir": str(directory),
        "files": len(texts),
        "bytes_total": int(sum(sizes)),
        "bytes_mean": int(sum(sizes) / len(sizes)),
        "bytes_min": int(min(sizes)),
        "bytes_max": int(max(sizes)),
        "chars_mean": int(sum(chars) / len(chars)),
        "C_T_Se": round(ct, 6),
        "delta_mean": round(float(d.mean()), 6),
        "delta_std": round(float(d.std()), 6),
        "mu_mean": round(float(m.mean()), 6),
        "mu_std": round(float(m.std()), 6),
        "window": window,
        "model": model_name,
        "seconds": round(time.time() - t0, 1),
    }

    if bootstrap:
        # moving-block bootstrap over the (mu, delta) pairs. Consecutive snapshots are
        # autocorrelated, so resampling single pairs would understate the spread.
        rng = np.random.default_rng(seed)
        n = len(d)
        block = max(2, window)
        nblocks = int(np.ceil(n / block))
        vals = []
        for _ in range(bootstrap):
            starts = rng.integers(0, max(1, n - block + 1), size=nblocks)
            idx = np.concatenate([np.arange(s, s + block) for s in starts])[:n]
            idx = idx[idx < n]
            vals.append(float(np.sum(m[idx] * d[idx])))
        vals = np.asarray(vals)
        out["C_T_ci95"] = [round(float(np.percentile(vals, 2.5)), 6),
                           round(float(np.percentile(vals, 97.5)), 6)]
        out["C_T_std_boot"] = round(float(vals.std()), 6)
        out["bootstrap"] = bootstrap
    return out


def print_row(r):
    if r.get("error"):
        print(f"  {Path(r['dir']).name:<26} ERROR: {r['error']}")
        return
    print(f"  {Path(r['dir']).name:<26} C_T = {r['C_T_Se']:>10.4f} Se   "
          f"n={r['files']:<3} bytes={r['bytes_mean']:>6} "
          f"mu={r['mu_mean']:.4f} delta={r['delta_mean']:.4f}")
    if "C_T_ci95" in r:
        lo, hi = r["C_T_ci95"]
        print(f"  {'':<26} 95% CI [{lo:.4f}, {hi:.4f}]  "
              f"(block bootstrap, {r['bootstrap']} resamples)")


def compare(results):
    ok = [r for r in results if not r.get("error")]
    if len(ok) < 2:
        return
    print()
    print("  pairwise ratios (row / column)")
    names = [Path(r["dir"]).name for r in ok]
    print(f"  {'':<26}" + "".join(f"{n[:11]:>13}" for n in names))
    for a in ok:
        cells = []
        for b in ok:
            cells.append(f"{a['C_T_Se']/b['C_T_Se']:>13.3f}")
        print(f"  {Path(a['dir']).name:<26}" + "".join(cells))

    print()
    lens = [r["bytes_mean"] for r in ok]
    if max(lens) / max(1, min(lens)) > 1.1:
        print(f"  [!] mean byte length varies {(max(lens)/min(lens)-1)*100:.0f}%; "
              f"C_T rises with length, so this comparison is confounded")
    else:
        print(f"  length is reasonably matched "
              f"(max/min = {max(lens)/max(1,min(lens)):.2f})")


def main():
    ap = argparse.ArgumentParser(
        description="Compute C_T for one or more corpus directories.")
    ap.add_argument("dirs", nargs="+", help="directories of .txt snapshots")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW,
                    help="window radius for mu (default 5)")
    ap.add_argument("--json", help="write results to this file")
    ap.add_argument("--bootstrap", type=int, default=0,
                    help="block-bootstrap resamples for a 95%% interval")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--quiet", action="store_true",
                    help="only print the C_T lines")
    ap.add_argument("--explain", action="store_true",
                    help="print what C_T measures and how to read it")
    args = ap.parse_args()

    if args.explain:
        print(EXPLAIN)
        return 0

    warm_encoder(args.model)

    results = []
    for d in args.dirs:
        p = Path(d)
        if not p.is_dir():
            results.append({"dir": str(p), "error": "not a directory"})
            continue
        results.append(analyse(p, args.model, args.window,
                               bootstrap=args.bootstrap, seed=args.seed))

    if not args.quiet:
        print()
        print("  corpus                     C_T (Se)")
        print("  " + "-" * 68)
    for r in results:
        print_row(r)

    if len(results) > 1:
        compare(results)

    if args.json:
        Path(args.json).write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  written {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
