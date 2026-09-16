"""
L1: 分层内容哈希
root = Merkle(metadata, dataset, compute, results, figure_recipe, l3_reference)
"""

import json
import hashlib
from datetime import datetime


def _sha256_canonical(obj):
    """规范化 JSON 哈希"""
    canonical = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _merkle_root(hashes):
    """标准 Merkle 根"""
    if not hashes:
        return None
    level = list(hashes)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [
            hashlib.sha256((level[i] + level[i+1]).encode()).hexdigest()
            for i in range(0, len(level), 2)
        ]
    return "sha256:" + level[0]


def layer_1_content_hash(context, l3_results=None):
    """
    L1: 分层内容哈希

    参数:
      context: 含 metadata, dataset, compute, results, figure_recipe
      l3_results: L3 三级 merkle root (sample, compute, result)

    返回:
      标准 fragment: {layer_id, status, computed_at, data, error}
    """
    l1a = _sha256_canonical(context.get("metadata", {}))
    l1b = _sha256_canonical(context.get("dataset", {}))
    l1c = _sha256_canonical(context.get("compute", {}))
    l1d = _sha256_canonical(context.get("results", {}))
    l1e = _sha256_canonical(context.get("figure_recipe") or {})

    if l3_results:
        l1f = _sha256_canonical({
            "sample": l3_results.get("sample"),
            "compute": l3_results.get("compute"),
            "result": l3_results.get("result"),
        })
    else:
        l1f = "sha256:" + "0" * 64

    root = _merkle_root([l1a, l1b, l1c, l1d, l1e, l1f])

    return {
        "layer_id": "L1",
        "status": "ok",
        "computed_at": datetime.now().isoformat(),
        "data": {
            "content_hash": root,
            "hash_algorithm": "sha256",
            "hash_scope": "layered",
            "sub_hashes": {
                "metadata": l1a,
                "dataset": l1b,
                "compute": l1c,
                "results": l1d,
                "figure_recipe": l1e,
                "l3_reference": l1f,
            }
        },
        "error": None
    }


if __name__ == "__main__":
    ctx = {
        "metadata": {"domain": "test"},
        "dataset": {"n": 2},
        "compute": {"deltas": [0.1], "mus": [0.5]},
        "results": {"C_T_Se": 1.0},
        "figure_recipe": {},
    }
    l3 = {"sample": "sha256:a", "compute": "sha256:b", "result": "sha256:c"}
    r = layer_1_content_hash(ctx, l3)
    print("L1 root:", r["data"]["content_hash"][:40], "...")
    print("sub_hashes count:", len(r["data"]["sub_hashes"]))
    print("status:", r["status"])