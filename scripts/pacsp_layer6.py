"""
L6: 创新动力学标识存证（论文 §4.2 / 附录 A）

论文 §4.2 将五层防护扩展为六层：

    L1 六语义块分层哈希   L2 Ed25519 签名      L3 三级 Merkle 承诺
    L4 OpenTimestamps     L5 完整可复现验证    L6 创新动力学标识存证（新增）

L6 不改变 L1–L5 的任何既有语义：它把情绪树与创新动力学五元分解的结果
独立哈希后存证，因此对已归档的 v4.0.0 记录完全向后兼容 —— 缺少 L6 的
旧记录判定为 "absent"（非致命），而非失败。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from pacsp_emotion_tree import (          # noqa: E402
    EmotionTree, build_emotion_tree, compute_emotion_distribution,
    compute_ct_extended,
)
from pacsp_innov import (                 # noqa: E402
    compute_innovation, compute_innovation_from_record,
    goal_alignment_from_record, infer_explore_labels_from_changepoints,
)


def _sha256_canonical(obj):
    canonical = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _merkle_root(hashes):
    if not hashes:
        return None
    level = list(hashes)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [
            hashlib.sha256((level[i] + level[i + 1]).encode()).hexdigest()
            for i in range(0, len(level), 2)
        ]
    return "sha256:" + level[0]


def layer_6_innovation(record, embeddings=None, group_labels=None,
                       alpha=0.1, beta=0.05, target_vec=None):
    """L6: 计算情绪树 + 创新动力学五元分解，并生成存证 fragment。

    参数
    ----
    record       : 已构建的 .pacsp 记录（需含 compute.deltas/mus 与 results.changepoints）
    embeddings   : 可选。给出则计算真实情绪分布与目标对齐；否则用记录的 deltas 离线重建
    group_labels : 可选。身份群体标签，用于计算偏见熵 B_tree
    target_vec   : 可选。目标向量，仅在 embeddings 给出时使用

    返回
    ----
    (fragment, artifacts)，artifacts 含 emotion_tree / innovation / C_T_ext 三段，供合并进记录
    """
    deltas = record.get("compute", {}).get("deltas") or []
    mus = record.get("compute", {}).get("mus") or []
    cps = (record.get("results", {}).get("changepoints") or {}).get("delta_k") or []

    # ---- 情绪树 ----
    if embeddings is not None:
        P = compute_emotion_distribution(embeddings)
        tree = build_emotion_tree(P, group_labels=group_labels)
    else:
        # 离线：用 deltas 的滑动窗口构造一个确定性分布，保证可复现
        P = _proxy_distribution_from_deltas(deltas)
        tree = build_emotion_tree(P, group_labels=group_labels)

    # ---- 创新动力学 ----
    # A_goal 只有在给出真实目标向量时才有意义；否则 S_int/C_sel/DRI 记为未定义。
    if embeddings is not None and target_vec is not None:
        from pacsp_innov import goal_alignment_from_embeddings
        labels = infer_explore_labels_from_changepoints(deltas, cps)
        A_goal = goal_alignment_from_embeddings(embeddings, target_vec)
        innov = compute_innovation(deltas, mus, A_goal, labels)
    else:
        innov = compute_innovation_from_record(record)

    # ---- 瑟-树耦合 ----
    c_ext = compute_ct_extended(deltas, mus, {"delta_k": cps}, tree, alpha, beta)

    innov_dict = innov.to_dict()
    tree_dict = tree.to_dict()

    # ---- 三层子哈希 -> L6 根 ----
    h_innov = _sha256_canonical(innov_dict)
    h_tree = _sha256_canonical(tree_dict)
    h_ct = _sha256_canonical(c_ext)
    root = _merkle_root([h_innov, h_tree, h_ct])

    l1_hash = (record.get("integrity", {}).get("L1", {}) or {})
    if isinstance(l1_hash, dict) and "data" in l1_hash:
        l1_hash = l1_hash["data"]
    l1_content_hash = (l1_hash or {}).get("content_hash")

    artifacts = {
        "emotion_tree": tree_dict,
        "innovation": innov_dict,
        "C_T_ext": c_ext,
    }

    fragment = {
        "layer_id": "L6",
        "status": "ok",
        "computed_at": datetime.now().isoformat(),
        "data": {
            "innovation_hash": root,
            "hash_algorithm": "sha256",
            "hash_scope": "innovation_dynamics",
            "l1_content_hash": l1_content_hash,
            "sub_hashes": {
                "innovation": h_innov,
                "emotion_tree": h_tree,
                "ct_extended": h_ct,
            },
            "verdict": innov_dict.get("verdict"),
        },
        "error": None,
    }
    return fragment, artifacts


def _proxy_distribution_from_deltas(deltas, n_channels=8, window=3):
    """离线模式下由 deltas 构造确定性情绪分布代理。

    不依赖嵌入模型，仅用路径增量的滑动窗口统计，保证同一记录必得同一分布。
    """
    import numpy as np

    d = np.asarray(deltas, dtype=float)
    T = len(d)
    if T == 0:
        return np.zeros((0, n_channels))

    lo, hi = d.min(), d.max()
    norm = (d - lo) / (hi - lo + 1e-12)

    P = np.zeros((T, n_channels))
    for t in range(T):
        lo_w = max(0, t - window)
        hi_w = min(T, t + window + 1)
        local = norm[lo_w:hi_w]
        # 用一个确定性散列把局部统计映射到通道
        seed = int(round(float(local.mean()) * 1e6)) + t
        ch = seed % n_channels
        P[t, ch] = 1.0

    P = 0.9 * P + 0.1 * (np.ones((T, n_channels)) / n_channels)
    P /= P.sum(axis=1, keepdims=True)
    return P


def verify_l6(record):
    """验证 L6：重算五元分解与情绪树哈希，与存证比对。

    返回 (ok, message)。ok 为 None 表示该记录不含 L6（非致命）。
    """
    l6 = record.get("integrity", {}).get("L6")
    if not l6:
        return None, "该记录不含 L6（v4.0.0 遗留格式，非致命）"

    status = l6.get("status")
    if status and status != "ok":
        return False, f"L6 状态: {status}"

    data = l6.get("data", {})
    stored_root = data.get("innovation_hash")
    stored_subs = data.get("sub_hashes", {})
    if not stored_root:
        return False, "缺少 L6.innovation_hash"

    # 记录中是否带有 L6 的三个产物
    innov = record.get("innovation")
    tree = record.get("emotion_tree")
    cext = record.get("C_T_ext")
    if not (innov and tree and cext):
        return False, "记录缺少 innovation / emotion_tree / C_T_ext 产物，无法重算"

    h_innov = _sha256_canonical(innov)
    h_tree = _sha256_canonical(tree)
    h_ct = _sha256_canonical(cext)
    recomputed = _merkle_root([h_innov, h_tree, h_ct])

    if recomputed != stored_root:
        return False, (f"L6 根哈希不匹配: {stored_root[:24]}... != {recomputed[:24]}...")

    for key, val in (("innovation", h_innov), ("emotion_tree", h_tree),
                     ("ct_extended", h_ct)):
        if stored_subs.get(key) != val:
            return False, f"L6 子哈希不匹配: {key}"

    # 交叉引用：L6 记录的 L1 哈希须与当前 L1 一致
    l1 = record.get("integrity", {}).get("L1", {})
    if isinstance(l1, dict) and "data" in l1:
        l1 = l1["data"]
    l1_hash = (l1 or {}).get("content_hash")
    if data.get("l1_content_hash") and l1_hash and data["l1_content_hash"] != l1_hash:
        return False, "L6 引用的 L1 哈希与当前 L1 不一致"

    verdict = data.get("verdict", "")
    return True, f"L6 创新动力学存证通过（判定: {verdict}）"


if __name__ == "__main__":
    print("=" * 60)
    print("L6: 创新动力学标识存证 self-test")
    print("=" * 60)

    rec = {
        "compute": {"deltas": [0.2, 0.4, 0.9, 0.3, 0.5, 1.1, 0.25, 0.6],
                    "mus": [0.1, 0.2, 0.45, 0.15, 0.25, 0.5, 0.12, 0.3]},
        "results": {"C_T_Se": 1.23, "changepoints": {"delta_k": [3, 6]}},
        "integrity": {"L1": {"data": {"content_hash": "sha256:" + "ab" * 32}}},
    }
    frag, arts = layer_6_innovation(rec)
    print(f"\nstatus        : {frag['status']}")
    print(f"innovation_hash: {frag['data']['innovation_hash'][:46]}...")
    print(f"verdict       : {frag['data']['verdict']}")
    print(f"tree          : {arts['emotion_tree']}")
    print(f"C_T_ext       : {arts['C_T_ext']['C_T_ext']} Se "
          f"(path {arts['C_T_ext']['C_path']:.4f} + jump {arts['C_T_ext']['C_jump']:.4f} "
          f"+ depth {arts['C_T_ext']['C_depth']:.4f} + bias {arts['C_T_ext']['C_bias']:.4f})")

    rec["integrity"]["L6"] = frag
    rec.update(arts)
    ok, msg = verify_l6(rec)
    print(f"\nverify        : {ok} - {msg}")
