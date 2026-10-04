"""
L6 适配器：把旧 schema 的 Keci 记录接入创新动力学层（论文 §5.2 模型对比）

背景
----
`PACSP/records_keci/*.pacsp` 由早期流水线产出，schema 与本仓库不同：

    旧（Keci）：   {C_T, avg_delta, avg_mu, measurement:{deltas, mus, cumulative}, ...}
    新（PACSP-ID）：{metadata, compute:{deltas,mus}, results:{C_T_Se, changepoints}, ...}

本模块做 schema 规范化，使 Keci 测量可以直接进入 L6 的情绪树与五元分解，
从而在**同一算法**下比较两种底层空间：

    sentence-transformers (bge-large-zh-v1.5, 1024 维)
    Keci (Clifford 代数嵌入, 64 维, ConceptNet 中文子集)

这对应论文 §5.2「Keci 版与 s-t 版给出相同的区分排序，量级偏差约 30–50%」。
"""
import os

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pacsp_innov import (compute_innovation, infer_explore_labels_from_changepoints,
                         goal_alignment_from_record)
from pacsp_emotion_tree import build_emotion_tree, compute_ct_extended


def normalize_legacy(record):
    """把旧 schema 记录规范化为 L6 可消费的中间结构。"""
    m = record.get("measurement") or {}
    deltas = m.get("deltas") or []
    mus = m.get("mus") or []

    if not deltas or not mus:
        raise ValueError("记录缺少 measurement.deltas / mus")

    params = record.get("parameters") or {}
    return {
        "metadata": {
            "domain": record.get("domain"),
            "epoch": record.get("experiment", "epoch1"),
            "variant": record.get("variant", "v1"),
            "protocol_version": "legacy-keci",
            "parameters": params,
        },
        "compute": {"deltas": list(deltas), "mus": list(mus)},
        "results": {
            "C_T_Se": float(record.get("C_T") or m.get("C_T") or 0.0),
            # 旧记录不含变点结果：由 deltas 的阈值法给出确定性替代
            "changepoints": {"mu_k": [], "delta_k": _simple_changepoints(deltas)},
        },
        "dataset": {"n_samples": record.get("snapshot_count"),
                    "valid": record.get("valid_snapshot_count")},
        "model_tag": record.get("model_tag"),
        "cumulative": m.get("cumulative"),
    }


def _simple_changepoints(deltas, sigma=1.0):
    """阈值法变点（与附录 E 参考实现一致），1-based。"""
    import numpy as np
    d = np.asarray(deltas, dtype=float)
    if len(d) < 3:
        return []
    thr = d.mean() + sigma * d.std()
    return [int(i + 1) for i in range(1, len(d)) if d[i] > thr]


def proxy_distribution(deltas, n_channels=8, window=3):
    """由 deltas 构造确定性情绪分布代理（离线，无需嵌入模型）。"""
    import numpy as np
    d = np.asarray(deltas, dtype=float)
    T = len(d)
    if T == 0:
        return np.zeros((0, n_channels))
    lo, hi = d.min(), d.max()
    norm = (d - lo) / (hi - lo + 1e-12)
    protos = np.linspace(0.0, 1.0, n_channels)
    logits = -np.abs(norm[:, None] - protos[None, :])
    logits -= logits.max(axis=1, keepdims=True)
    P = np.exp(logits)
    return P / P.sum(axis=1, keepdims=True)


def compute_l6_legacy(record, threshold=0.5):
    """对旧 schema 记录计算 L6 指标，返回 (核心指标 dict, 瑟-树耦合 dict)。"""
    norm = normalize_legacy(record)
    deltas = norm["compute"]["deltas"]
    mus = norm["compute"]["mus"]
    cps = norm["results"]["changepoints"]["delta_k"]

    labels = infer_explore_labels_from_changepoints(deltas, cps, threshold)
    A = goal_alignment_from_record(deltas, cps)
    innov = compute_innovation(deltas, mus, A, labels)

    P = proxy_distribution(deltas)
    tree = build_emotion_tree(P)
    cext = compute_ct_extended(deltas, mus, {"delta_k": cps}, tree)

    return norm, innov.to_dict(), tree.to_dict(), cext


def load_keci_records(root):
    """读取目录下全部 Keci 记录（按 domain 索引）。"""
    out = {}
    for f in sorted(Path(root).glob("*.pacsp")):
        try:
            r = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if "measurement" not in r:
            continue
        out.setdefault(r.get("domain"), []).append((f.name, r))
    return out


if __name__ == "__main__":
    root = os.environ.get("PACSP_KECI_ROOT") or str(
    Path(__file__).resolve().parent.parent.parent / "PACSP" / "records_keci")
    recs = load_keci_records(root)
    print(f"Keci 记录: { {k: len(v) for k, v in recs.items()} }\n")
    for dom, items in recs.items():
        for name, r in items:
            norm, innov, tree, cext = compute_l6_legacy(r)
            print(f"--- {dom}  ({name})")
            print(f"    model_tag : {norm['model_tag']}")
            print(f"    C_T       : {norm['results']['C_T_Se']:.4f} Se")
            print(f"    树深度    : {tree['depth']}  边数 {tree['path_length']}")
            print(f"    C_DMN={innov['C_DMN']:.4f} C_SN={innov['C_SN']:.2f} "
                  f"E_glob={innov['E_glob']:.4f}")
            print(f"    S_int={innov['S_int']} chi={innov['chi_innov']:.4f} "
                  f"DRI={innov['DRI']}")
            print(f"    判定      : {innov['verdict']}")
            print(f"    C_T_ext   : {cext['C_T_ext']:.4f} "
                  f"(path {cext['C_path']:.4f} + jump {cext['C_jump']:.4f} "
                  f"+ depth {cext['C_depth']:.4f})")
            print()
