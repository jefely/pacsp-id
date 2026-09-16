"""
PACSP-ID 五层完整验证
用法: python pacsp_verify.py <pacsp_path> [data_dir]
"""

import sys
import json
import base64
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def _unwrap(fragment):
    """兼容两种格式：完整 fragment 或 data-only"""
    if isinstance(fragment, dict) and "data" in fragment and "status" in fragment:
        return fragment["data"]
    return fragment


# ============================================================
# L1: 分层内容哈希
# ============================================================
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
            hashlib.sha256((level[i] + level[i+1]).encode()).hexdigest()
            for i in range(0, len(level), 2)
        ]
    return "sha256:" + level[0]


def recompute_l1(record):
    """从 record 重建 L1 分层哈希"""
    l3 = record.get("integrity", {}).get("L3", {})

    l1a = _sha256_canonical(record.get("metadata", {}))
    l1b = _sha256_canonical(record.get("dataset", {}))
    l1c = _sha256_canonical(record.get("compute", {}))
    l1d = _sha256_canonical(record.get("results", {}))
    l1e = _sha256_canonical(record.get("figure_recipe") or {})

    l1f = _sha256_canonical({
        "sample": l3.get("sample"),
        "compute": l3.get("compute"),
        "result": l3.get("result"),
    })

    root = _merkle_root([l1a, l1b, l1c, l1d, l1e, l1f])

    return {
        "content_hash": root,
        "sub_hashes": {
            "metadata": l1a,
            "dataset": l1b,
            "compute": l1c,
            "results": l1d,
            "figure_recipe": l1e,
            "l3_reference": l1f,
        }
    }


def verify_l1(record):
    """验证 L1 分层哈希"""
    l1_full = record.get("integrity", {}).get("L1", {})
    if not l1_full:
        return False, "缺少 integrity.L1"

    l1 = _unwrap(l1_full)

    stored_root = l1.get("content_hash")
    stored_subs = l1.get("sub_hashes", {})

    if not stored_root:
        return False, "缺少 L1.content_hash"

    recomputed = recompute_l1(record)

    if stored_root != recomputed["content_hash"]:
        return False, f"根哈希不匹配: {stored_root[:24]}... != {recomputed['content_hash'][:24]}..."

    mismatches = []
    for key in stored_subs:
        if stored_subs[key] != recomputed["sub_hashes"].get(key):
            mismatches.append(key)

    if mismatches:
        return False, f"子哈希不匹配: {mismatches}"

    return True, "L1 分层哈希验证通过"


# ============================================================
# L2: Ed25519 签名
# ============================================================
def verify_l2(record):
    """验证 L2 签名"""
    l2_full = record.get("integrity", {}).get("L2", {})
    if not l2_full:
        return False, "缺少 integrity.L2"

    # status
    status = l2_full.get("status")
    if status and status != "ok":
        return False, f"L2 状态: {status}"

    data = _unwrap(l2_full)
    signature_b64 = data.get("signature")
    public_key_id = data.get("public_key_id")
    signed_content_hash = data.get("signed_content_hash")

    if not signature_b64 or not public_key_id:
        return False, "缺少签名字段"

    try:
        from pacsp_sign import get_or_create_key, get_public_key_id
        private_key = get_or_create_key()
    except Exception as e:
        return False, f"无法读取密钥: {e}"

    current_pub_id = get_public_key_id(private_key)
    if current_pub_id != public_key_id:
        return False, f"公钥 ID 不匹配: 当前 {current_pub_id} != 存储 {public_key_id}"

    # 读取 L1 的 content_hash
    l1_full = record.get("integrity", {}).get("L1", {})
    l1_data = _unwrap(l1_full)
    l1_content_hash = l1_data.get("content_hash")

    if signed_content_hash != l1_content_hash:
        return False, f"签名的内容哈希与 L1 不一致"

    try:
        signature = base64.b64decode(signature_b64.replace("base64:", ""))
        private_key.public_key().verify(signature, signed_content_hash.encode("utf-8"))
        return True, f"签名有效 (公钥 {public_key_id})"
    except Exception as e:
        return False, f"签名无效: {e}"


# ============================================================
# L3: 三级 Merkle
# ============================================================
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_l3(record, data_dir=None):
    """验证 L3 三级 Merkle"""
    l3 = record.get("integrity", {}).get("L3", {})
    if not l3:
        return False, "缺少 integrity.L3"

    results = []

    # L3a
    if data_dir and Path(data_dir).exists():
        sample_hashes = [sha256_file(f) for f in sorted(Path(data_dir).glob("*.txt"))]
        actual = _merkle_root(sample_hashes)
        if actual == l3.get("sample"):
            results.append("L3a OK")
        else:
            results.append(f"L3a FAIL")
    else:
        results.append("L3a SKIP")

    # L3b
    deltas = record.get("compute", {}).get("deltas", [])
    mus = record.get("compute", {}).get("mus", [])
    deltas_hash = hashlib.sha256(
        json.dumps(deltas, sort_keys=True).encode()
    ).hexdigest()
    mus_hash = hashlib.sha256(
        json.dumps(mus, sort_keys=True).encode()
    ).hexdigest()
    actual = _merkle_root([deltas_hash, mus_hash])
    if actual == l3.get("compute"):
        results.append("L3b OK")
    else:
        results.append("L3b FAIL")

    # L3c
    c_t = record.get("results", {}).get("C_T_Se")
    cps = record.get("results", {}).get("changepoints", {})
    cps_clean = {k: [int(x) for x in v] for k, v in cps.items()}

    c_t_hash = hashlib.sha256(str(c_t).encode()).hexdigest()
    cp_hash = hashlib.sha256(
        json.dumps(cps_clean, sort_keys=True).encode()
    ).hexdigest()
    actual = _merkle_root([c_t_hash, cp_hash])
    if actual == l3.get("result"):
        results.append("L3c OK")
    else:
        results.append("L3c FAIL")

    all_ok = all("OK" in r for r in results)
    return all_ok, " | ".join(results)


# ============================================================
# L4: 时间戳
# ============================================================
def verify_l4(record):
    """验证 L4 时间戳（非致命层）"""
    l4_full = record.get("integrity", {}).get("L4", {})
    if not l4_full:
        return None, "缺少 integrity.L4"

    status = l4_full.get("status")
    data = _unwrap(l4_full)

    if status == "ok":
        proof = data.get("timestamp_proof", "")
        anchor = data.get("timestamp_anchor", "unknown")
        if proof:
            return True, f"时间戳存在 (锚点: {anchor})"
        return False, "缺少 timestamp_proof"
    elif status == "pending":
        return None, "时间戳待确认（非致命）"
    else:
        err = l4_full.get("error", "")
        return False, f"L4 状态: {status} {('- ' + err[:60]) if err else ''}"


# ============================================================
# L5: 可复现元数据
# ============================================================
def verify_l5(record):
    """验证 L5 可复现元数据"""
    l5_full = record.get("integrity", {}).get("L5", {})
    if not l5_full:
        return False, "缺少 integrity.L5"

    status = l5_full.get("status")
    if status and status != "ok":
        return False, f"L5 状态: {status}"

    data = _unwrap(l5_full)
    steps = data.get("pipeline_steps", [])
    if len(steps) > 0:
        return True, f"Pipeline 步骤: {len(steps)}"
    return False, "缺少 pipeline_steps"


# ============================================================
# 主流程
# ============================================================
def full_verify(pacsp_path, data_dir=None):
    with open(pacsp_path, encoding="utf-8") as f:
        record = json.load(f)

    print(f"\n{'='*60}")
    print(f"验证: {Path(pacsp_path).name}")
    print(f"{'='*60}")

    results = {}

    ok, msg = verify_l1(record)
    results["L1"] = ok
    print(f"  {'OK  ' if ok else 'FAIL'} L1: {msg}")

    ok, msg = verify_l2(record)
    results["L2"] = ok
    print(f"  {'OK  ' if ok else 'FAIL'} L2: {msg}")

    ok, msg = verify_l3(record, data_dir)
    results["L3"] = ok
    print(f"  {'OK  ' if ok else 'FAIL'} L3: {msg}")

    ok, msg = verify_l4(record)
    results["L4"] = ok
    icon = "OK  " if ok is True else ("PEND" if ok is None else "FAIL")
    print(f"  {icon} L4: {msg}")

    ok, msg = verify_l5(record)
    results["L5"] = ok
    print(f"  {'OK  ' if ok else 'FAIL'} L5: {msg}")

    critical = ["L1", "L2", "L3", "L5"]
    all_ok = all(results.get(l) is True for l in critical)

    print(f"\n{'='*60}")
    print(f"结果: {'VERIFIED' if all_ok else 'FAILED'}")
    print(f"{'='*60}")

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python pacsp_verify.py <path_to.pacsp> [data_dir]")
        sys.exit(1)

    pacsp_path = sys.argv[1]
    data_dir = sys.argv[2] if len(sys.argv) > 2 else None
    full_verify(pacsp_path, data_dir)