"""
L3: 三级 Merkle 承诺
- L3a: 样本级（samples 的哈希集）
- L3b: 计算级（deltas + mus）
- L3c: 结果级（C_T + changepoints）
"""

import json
import hashlib
from datetime import datetime


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


def sha256_file(path):
    """计算文件 SHA256"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ============================================================
# L3a: 样本级 Merkle
# ============================================================
def layer_3a_sample_merkle(context):
    hashes = context["sample_hashes"]
    return {
        "layer_id": "L3a",
        "status": "ok",
        "computed_at": datetime.now().isoformat(),
        "data": {
            "merkle_root": _merkle_root(hashes),
            "n_samples": len(hashes),
            "sample_hashes": hashes,
        },
        "error": None
    }


# ============================================================
# L3b: 计算级 Merkle
# ============================================================
def layer_3b_compute_merkle(context):
    deltas = context["deltas"]
    mus = context["mus"]

    deltas_canonical = json.dumps(deltas, sort_keys=True, ensure_ascii=False)
    mus_canonical = json.dumps(mus, sort_keys=True, ensure_ascii=False)

    deltas_hash = hashlib.sha256(deltas_canonical.encode()).hexdigest()
    mus_hash = hashlib.sha256(mus_canonical.encode()).hexdigest()

    return {
        "layer_id": "L3b",
        "status": "ok",
        "computed_at": datetime.now().isoformat(),
        "data": {
            "merkle_root": _merkle_root([deltas_hash, mus_hash]),
            "deltas_hash": "sha256:" + deltas_hash,
            "mus_hash": "sha256:" + mus_hash,
        },
        "error": None
    }


# ============================================================
# L3c: 结果级 Merkle
# ============================================================
def layer_3c_result_merkle(context):
    c_t_hash = hashlib.sha256(str(context["C_T"]).encode()).hexdigest()

    # 关键修复：把 numpy 整数转为 Python 原生 int
    cps = context["changepoints"]
    cps_clean = {k: [int(x) for x in v] for k, v in cps.items()}

    cp_canonical = json.dumps(cps_clean, sort_keys=True, ensure_ascii=False)
    cp_hash = hashlib.sha256(cp_canonical.encode()).hexdigest()

    return {
        "layer_id": "L3c",
        "status": "ok",
        "computed_at": datetime.now().isoformat(),
        "data": {
            "merkle_root": _merkle_root([c_t_hash, cp_hash]),
            "C_T_hash": "sha256:" + c_t_hash,
            "changepoints_hash": "sha256:" + cp_hash,
        },
        "error": None
    }


# ============================================================
# 验证
# ============================================================
def verify_l3(record, data_dir=None):
    """验证 L3 三级 Merkle"""
    from pathlib import Path

    l3 = record.get("integrity", {}).get("L3", {})
    if not l3:
        return False, "缺少 integrity.L3"

    results = []

    # L3a: 样本级
    if data_dir and Path(data_dir).exists():
        sample_hashes = [sha256_file(f) for f in sorted(Path(data_dir).glob("*.txt"))]
        actual = _merkle_root(sample_hashes)
        if actual == l3.get("sample"):
            results.append("L3a ✓")
        else:
            results.append(f"L3a ✗ ({actual[:20]}...)")
    else:
        results.append("L3a ⏭")

    # L3b: 计算级
    deltas = record["compute"]["deltas"]
    mus = record["compute"]["mus"]
    deltas_hash = hashlib.sha256(
        json.dumps(deltas, sort_keys=True).encode()
    ).hexdigest()
    mus_hash = hashlib.sha256(
        json.dumps(mus, sort_keys=True).encode()
    ).hexdigest()
    actual = _merkle_root([deltas_hash, mus_hash])
    if actual == l3.get("compute"):
        results.append("L3b ✓")
    else:
        results.append(f"L3b ✗")

    # L3c: 结果级
    c_t = record["results"]["C_T_Se"]
    cps = record["results"]["changepoints"]
    c_t_hash = hashlib.sha256(str(c_t).encode()).hexdigest()
    cp_hash = hashlib.sha256(
        json.dumps(cps, sort_keys=True).encode()
    ).hexdigest()
    actual = _merkle_root([c_t_hash, cp_hash])
    if actual == l3.get("result"):
        results.append("L3c ✓")
    else:
        results.append(f"L3c ✗")

    all_ok = all("✓" in r for r in results)
    return all_ok, " | ".join(results)


if __name__ == "__main__":
    # 自测：模拟 context
    ctx = {
        "sample_hashes": [hashlib.sha256(f"s{i}".encode()).hexdigest() for i in range(5)],
        "deltas": [0.5, 0.3, 0.7, 0.4],
        "mus": [0.13, 0.20, 0.25, 0.18, 0.15],
        "C_T": 1.8950,
        "changepoints": {"mu_k": [2, 4], "delta_k": [3]},
    }

    r3a = layer_3a_sample_merkle(ctx)
    r3b = layer_3b_compute_merkle(ctx)
    r3c = layer_3c_result_merkle(ctx)

    print("L3a 样本级:", r3a["data"]["merkle_root"])
    print("            n_samples:", r3a["data"]["n_samples"])
    print()
    print("L3b 计算级:", r3b["data"]["merkle_root"])
    print("            deltas_hash:", r3b["data"]["deltas_hash"][:40], "...")
    print("            mus_hash:   ", r3b["data"]["mus_hash"][:40], "...")
    print()
    print("L3c 结果级:", r3c["data"]["merkle_root"])
    print("            C_T_hash:", r3c["data"]["C_T_hash"][:40], "...")