"""
PACSP-ID build pipeline
From raw samples -> compute -> 5-layer protection -> single .pacsp

Execution order:
  Stage 1a: parallel L3a, L3b, L3c, L5
  Stage 1b: serial L1 (depends on L3)
  Stage 2:  serial L2, then L4 (depends on L1)
  Stage 3:  serial merge -> .pacsp
"""

import sys
import json
import hashlib
import platform
import numpy as np
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))
from pacsp_layer1 import layer_1_content_hash
from pacsp_merkle import (
    layer_3a_sample_merkle,
    layer_3b_compute_merkle,
    layer_3c_result_merkle,
    sha256_file,
)
from pacsp_sign import layer_2_sign
from pacsp_timestamp import layer_4_timestamp
from pacsp_layer6 import layer_6_innovation


ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
RECORDS_DIR = ROOT / "records"

# 是否产出 L6 创新动力学层（论文 §4.2）。默认关闭，保证既有五层记录不受影响。
ENABLE_INNOVATION = False


def load_samples(sample_dir):
    files = sorted(Path(sample_dir).glob("*.txt"))
    return [open(f, encoding="utf-8").read() for f in files], files


def compute_embeddings(texts, model_name="BAAI/bge-large-zh-v1.5"):
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name)
    return model.encode(texts, batch_size=8, normalize_embeddings=False)


def compute_deltas(embeddings):
    return [
        float(np.linalg.norm(embeddings[k+1] - embeddings[k]))
        for k in range(len(embeddings) - 1)
    ]


def compute_mus(embeddings, window=5):
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized = embeddings / (norms + 1e-8)
    cos_sim = normalized @ normalized.T

    mus = []
    for k in range(len(embeddings)):
        start = max(0, k - window)
        end = min(len(embeddings), k + window + 1)
        w = cos_sim[start:end, start:end]
        triu = np.triu_indices_from(w, k=1)
        mu = 1 - w[triu].mean() if len(triu[0]) > 0 else 0.0
        mus.append(float(mu))
    return mus


def compute_ct(deltas, mus):
    n = min(len(deltas), len(mus))
    return float(np.sum(np.array(mus[:n]) * np.array(deltas[:n])))


def detect_changepoints(signal, penalty, min_size=5):
    signal = np.asarray(signal, dtype=float)
    n = len(signal)

    if n < min_size * 2:
        return []

    F = np.zeros(n + 1)
    F[1:] = np.inf
    cp = np.zeros(n + 1, dtype=int)

    for t in range(min_size, n + 1):
        best = np.inf
        best_s = 0
        for s in range(0, t - min_size + 1):
            if s > 0 and s < min_size:
                continue
            seg = signal[s:t]
            sse = max(np.sum((seg - seg.mean()) ** 2), 1e-12)
            cost = len(seg) * np.log(sse / len(seg))
            total = F[s] + cost + penalty
            if total < best:
                best = total
                best_s = s
        F[t] = best
        cp[t] = best_s

    cps = []
    t = n
    while cp[t] > 0:
        cps.append(int(cp[t]))
        t = cp[t]
    return sorted(set(cps))


def solve_target_vector(embeddings, mode="none"):
    """按模式给出目标向量 target_vec，供 §8.2 的 A_goal(t)=cos(v_t, target) 使用。

    模式
    ----
    none     不定义目标 -> S_int / C_sel / DRI 记为未定义（默认）
    centroid 目标 = 该域嵌入的质心

    centroid 的语义：目标取该序列自身的语义重心，度量的是"每一步相对本域
    典型语义的对齐程度"。它**不引入任何外部偏好方向**，因此是唯一不偏袒
    某个结论的标定方式；但它衡量的是"本域一致性"，**不是**"朝某个意图推进"。
    要判定人脑式 vs LLM 式创新，仍需一个机器书写的对照组（见核查报告 §5.1）。
    """
    if mode == "none" or embeddings is None:
        return None
    if mode == "centroid":
        return np.mean(np.asarray(embeddings, dtype=float), axis=0)
    raise ValueError(f"未知的 target 模式: {mode}")


def layer_5_reproducibility(context):
    return {
        "layer_id": "L5",
        "status": "ok",
        "computed_at": datetime.now().isoformat(),
        "data": {
            "python_version": platform.python_version(),
            "platform": platform.system(),
            "embedding_model": context["metadata"]["parameters"]["embedding_model"],
            "window_size": context["metadata"]["parameters"]["window_size"],
            "pipeline_steps": [
                "load_samples",
                "compute_embeddings",
                "compute_deltas",
                "compute_mus",
                "compute_C_T",
                "detect_changepoints",
            ],
            "reproducible": True,
        },
        "error": None
    }


def build_figure_recipe():
    return {
        "figure_id": "main",
        "figsize": [14, 8],
        "dpi": 150,
        "layout": "2x1",
        "panels": [
            {
                "row": 0,
                "title": "Path Increments delta_k",
                "y_data": "compute.deltas",
                "y_label": "delta_k",
                "color": "#1f77b4",
                "marker": "o",
                "markersize": 5,
                "vlines": {
                    "source": "results.changepoints.delta_k",
                    "color": "red",
                    "linestyle": "--",
                    "linewidth": 2,
                }
            },
            {
                "row": 1,
                "title": "Cognitive Intensity mu_k",
                "y_data": "compute.mus",
                "y_label": "mu_k",
                "color": "#2ca02c",
                "marker": "o",
                "markersize": 5,
                "xlabel": "Snapshot",
                "vlines": {
                    "source": "results.changepoints.mu_k",
                    "color": "red",
                    "linestyle": "--",
                    "linewidth": 2,
                }
            }
        ],
        "font": {"family": "DejaVu Sans", "size": 12}
    }


def merge_fragments(fragments, context, artifacts=None):
    record = {
        "protocol": "PACSP-ID",
        "version": context.get("metadata", {}).get("protocol_version", "4.0.0-COMPACT"),
        "generated_at": datetime.now().isoformat(),
        "metadata": context["metadata"],
        "dataset": {
            "n_samples": int(fragments["L3a"]["data"]["n_samples"]),
            "sample_hashes": fragments["L3a"]["data"]["sample_hashes"],
        },
        "compute": {
            "deltas": context["deltas"],
            "mus": context["mus"],
        },
        "results": {
            "C_T_Se": float(context["C_T"]),
            "changepoints": context["changepoints"],
        },
        "stats": {
            "delta_mean": float(np.mean(context["deltas"])),
            "delta_std": float(np.std(context["deltas"])),
            "mu_mean": float(np.mean(context["mus"])),
            "mu_std": float(np.std(context["mus"])),
        },
        "figure_recipe": context["metadata"].get("figure_recipe"),
        "integrity": {
            "L1": fragments["L1"],
            "L2": fragments["L2"],
            "L3": {
                "sample": fragments["L3a"]["data"]["merkle_root"],
                "compute": fragments["L3b"]["data"]["merkle_root"],
                "result": fragments["L3c"]["data"]["merkle_root"],
            },
            "L4": fragments["L4"],
            "L5": fragments["L5"],
        }
    }

    # L6（论文 §4.2）：创新动力学标识存证。仅在启用时附加，
    # 使 v4.0.0 五层记录保持完全不变。
    if "L6" in fragments:
        record["integrity"]["L6"] = fragments["L6"]
    if artifacts:
        record["emotion_tree"] = artifacts.get("emotion_tree")
        record["innovation"] = artifacts.get("innovation")
        record["C_T_ext"] = artifacts.get("C_T_ext")

    return record


def build_pacsp(context, output_path, enable_innovation=False):
    fragments = {}

    # ============================================================
    # Stage 1a: Parallel L3a, L3b, L3c, L5
    # ============================================================
    print("\n[Stage 1a] Parallel: L3a, L3b, L3c, L5")
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {
            ex.submit(layer_3a_sample_merkle, context): "L3a",
            ex.submit(layer_3b_compute_merkle, context): "L3b",
            ex.submit(layer_3c_result_merkle, context): "L3c",
            ex.submit(layer_5_reproducibility, context): "L5",
        }
        for fut in as_completed(futures):
            lid = futures[fut]
            try:
                fragments[lid] = fut.result()
                print(f"  OK {lid}")
            except Exception as e:
                fragments[lid] = {
                    "layer_id": lid, "status": "failed",
                    "data": {}, "error": str(e)
                }
                print(f"  FAIL {lid}: {e}")

    # ============================================================
    # Stage 1b: L1 (depends on L3)
    # ============================================================
    print("[Stage 1b] L1 layered hash (depends on L3)")

    if (fragments.get("L3a", {}).get("status") != "ok" or
        fragments.get("L3b", {}).get("status") != "ok" or
        fragments.get("L3c", {}).get("status") != "ok"):
        print("  L3 incomplete, skip L1/L2/L4")
        return None, fragments

    l3_results = {
        "sample": fragments["L3a"]["data"]["merkle_root"],
        "compute": fragments["L3b"]["data"]["merkle_root"],
        "result": fragments["L3c"]["data"]["merkle_root"],
    }
    fragments["L1"] = layer_1_content_hash(context, l3_results)
    print(f"  OK L1")

    # ============================================================
    # Stage 2: Serial L2, then L4 (depends on L1)
    # ============================================================
    print("[Stage 2] Serial: L2 first, then L4 (depends on L1)")

    # L2 先做（快，本地签名）
    try:
        fragments["L2"] = layer_2_sign(context, fragments["L1"])
        print(f"  OK L2 ({fragments['L2']['status']})")
    except Exception as e:
        fragments["L2"] = {
            "layer_id": "L2", "status": "failed",
            "data": {}, "error": str(e)
        }
        print(f"  FAIL L2: {e}")

    # L4 后做（慢，需要网络，独占带宽）
    try:
        fragments["L4"] = layer_4_timestamp(context, fragments["L1"])
        print(f"  OK L4 ({fragments['L4']['status']})")
    except Exception as e:
        fragments["L4"] = {
            "layer_id": "L4", "status": "failed",
            "data": {}, "error": str(e)
        }
        print(f"  FAIL L4: {e}")

    # ============================================================
    # Stage 2b: L6 创新动力学标识存证（论文 §4.2 / 附录A）
    # 仅在 enable_innovation 为真时执行；v4.0.0 五层记录保持完全不变。
    # ============================================================
    produced_artifacts = None
    if enable_innovation:
        print("[Stage 2b] L6 innovation dynamics (emotion tree + 5-way decomposition)")
        try:
            l6_input = {
                "compute": context.get("compute", {}),
                "results": context.get("results", {}),
                "integrity": {"L1": fragments.get("L1", {})},
            }
            l6_kwargs = {}
            if context.get("embeddings") is not None:
                l6_kwargs["embeddings"] = context["embeddings"]
            if context.get("group_labels") is not None:
                l6_kwargs["group_labels"] = context["group_labels"]
            if context.get("target_vec") is not None:
                l6_kwargs["target_vec"] = context["target_vec"]

            l6_frag, produced_artifacts = layer_6_innovation(l6_input, **l6_kwargs)
            fragments["L6"] = l6_frag
            print(f"  OK L6 ({l6_frag['data']['verdict']})")
        except Exception as e:
            fragments["L6"] = {
                "layer_id": "L6", "status": "failed",
                "data": {}, "error": str(e)
            }
            produced_artifacts = None
            print(f"  FAIL L6: {e}")

    # ============================================================
    # Stage 3: Merge
    # ============================================================
    print("[Stage 3] Merge into single .pacsp")
    record = merge_fragments(fragments, context, produced_artifacts)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    print(f"  OK wrote: {output_path.name}")

    print("\n[Layer status]")
    for lid in ["L1", "L2", "L3a", "L3b", "L3c", "L4", "L5"]:
        frag = fragments.get(lid, {})
        status = frag.get("status", "missing")
        print(f"  {lid}: {status}")

    return record, fragments


def process_dataset(domain, epoch="epoch1", variant="base", window=5,
                    enable_innovation=ENABLE_INNOVATION, output_dir=None,
                    target_mode="none"):
    sample_dir = DATA_DIR / domain
    if not sample_dir.exists():
        print(f"Skip: {sample_dir} not found")
        return None

    print("\n" + "=" * 60)
    print(f"Process dataset: {domain}/{epoch}/{variant}")
    print("=" * 60)

    texts, files = load_samples(sample_dir)
    if len(texts) < 5:
        print(f"Not enough samples: {len(texts)}")
        return None
    print(f"[Load] {len(texts)} samples")

    print("[Compute] embeddings...")
    model_name = "BAAI/bge-large-zh-v1.5"
    embeddings = compute_embeddings(texts, model_name)

    print("[Compute] deltas, mus, C_T...")
    deltas = compute_deltas(embeddings)
    mus = compute_mus(embeddings, window=window)
    C_T = compute_ct(deltas, mus)

    print("[Compute] PELT changepoints...")
    cp_mu = detect_changepoints(mus, penalty=0.5)
    cp_delta = detect_changepoints(deltas, penalty=10.0)

    cp_mu_1based = [int(c + 1) for c in cp_mu]
    cp_delta_1based = [int(c + 1) for c in cp_delta]

    print(f"  C_T = {C_T:.4f} Se")
    print(f"  mu changepoints: {cp_mu_1based}")
    print(f"  delta changepoints: {cp_delta_1based}")

    sample_hashes = [sha256_file(f) for f in files]

    context = {
        "metadata": {
            "domain": domain,
            "epoch": epoch,
            "variant": variant,
            "CT_display": f"{C_T:.2f}Se",
            "protocol_version": ("7.0.0-COMPLETE" if enable_innovation
                                 else "4.0.0-COMPACT"),
            "parameters": {
                "embedding_model": model_name,
                "window_size": window,
                "n_samples": len(texts),
            },
            "figure_recipe": build_figure_recipe(),
        },
        "dataset": {
            "n_samples": len(texts),
            "sample_hashes": sample_hashes,
        },
        "compute": {
            "deltas": deltas,
            "mus": mus,
        },
        "results": {
            "C_T_Se": C_T,
            "changepoints": {
                "mu_k": cp_mu_1based,
                "delta_k": cp_delta_1based,
            },
        },
        "figure_recipe": build_figure_recipe(),
        "sample_hashes": sample_hashes,
        "deltas": deltas,
        "mus": mus,
        "C_T": C_T,
        "changepoints": {
            "mu_k": cp_mu_1based,
            "delta_k": cp_delta_1based,
        },
        # L6 所需输入（仅在 enable_innovation 时被消费）
        "embeddings": embeddings,
        "target_vec": solve_target_vector(embeddings, target_mode),
        "target_mode": target_mode,
    }

    date = datetime.now().strftime("%Y%m%d")
    filename = f"{domain}_{epoch}_{variant}_CT{C_T:.2f}Se_{date}.pacsp"
    output_path = (Path(output_dir) / filename) if output_dir else (RECORDS_DIR / filename)

    return build_pacsp(context, output_path, enable_innovation=enable_innovation)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PACSP-ID build pipeline")
    parser.add_argument("--innov", action="store_true",
                        help="产出 L6 创新动力学层（论文 §4.2），版本标记为 7.0.0-COMPLETE")
    parser.add_argument("--datasets", nargs="*", default=["lyrics", "techdoc"],
                        help="要处理的数据集目录名")
    parser.add_argument("--out", default=None,
                        help="输出目录（默认 records/）")
    parser.add_argument("--window", type=int, default=5, help="滑动窗口半径")
    parser.add_argument("--target", choices=["none", "centroid"], default="none",
                        help="A_goal 目标标定：none=不定义（S_int/DRI 记未定义），"
                             "centroid=以本域嵌入质心为目标")
    args = parser.parse_args()

    print("=" * 60)
    print("PACSP-ID build pipeline")
    print(f"  innovation layer (L6): {'ON' if args.innov else 'OFF'}")
    print(f"  target mode          : {args.target}")
    print(f"  datasets: {args.datasets}")
    print(f"  output  : {args.out or 'records/'}")
    print("=" * 60)

    for domain in args.datasets:
        try:
            result = process_dataset(domain, window=args.window,
                                     enable_innovation=args.innov,
                                     output_dir=args.out,
                                     target_mode=args.target)
            if result:
                print(f"\nDONE: {domain}")
        except Exception as e:
            print(f"\nFAIL: {domain}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("All done")
    print("=" * 60)