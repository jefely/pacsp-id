"""
篡改测试：证明五层防护有效
"""

import json
import shutil
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from pacsp_verify import (
    verify_l1, verify_l2, verify_l3, verify_l4, verify_l5
)

ROOT = Path(__file__).parent.parent
RECORDS_DIR = ROOT / "records"
TEST_DIR = ROOT / "cache" / "tamper_test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = ROOT / "data"


def run_verify(pacsp_path, data_dir=None):
    """跑五层验证并返回结果字典"""
    with open(pacsp_path, encoding="utf-8") as f:
        record = json.load(f)

    results = {}
    ok, _ = verify_l1(record); results["L1"] = ok
    ok, _ = verify_l2(record); results["L2"] = ok
    ok, _ = verify_l3(record, data_dir); results["L3"] = ok
    ok, _ = verify_l4(record); results["L4"] = ok
    ok, _ = verify_l5(record); results["L5"] = ok
    return results


def tamper_test(original_path, data_dir):
    """执行篡改测试"""
    original = Path(original_path)
    print(f"\n{'='*60}")
    print(f"Tamper Test: {original.name}")
    print(f"{'='*60}")

    # 基线
    print("\n[Baseline - 原始文件]")
    base = run_verify(original, data_dir)
    print(f"  L1={base['L1']} L2={base['L2']} L3={base['L3']} L4={base['L4']} L5={base['L5']}")

    # 读取原始
    with open(original, encoding="utf-8") as f:
        record = json.load(f)

    # ============ 篡改1: 改 C_T ============
    print("\n[Tamper 1: 修改 C_T_Se 从 2.13 -> 999.99]")
    tampered = json.loads(json.dumps(record))
    tampered["results"]["C_T_Se"] = 999.99
    test1_path = TEST_DIR / "tamper1.pacsp"
    with open(test1_path, "w", encoding="utf-8") as f:
        json.dump(tampered, f, ensure_ascii=False, indent=2)
    r = run_verify(test1_path, data_dir)
    print(f"  L1={r['L1']} L2={r['L2']} L3={r['L3']} L4={r['L4']} L5={r['L5']}")
    print(f"  → 检测: {'✅ 已捕获' if not r['L1'] or not r['L3'] else '❌ 未捕获'}")

    # ============ 篡改2: 改 deltas ============
    print("\n[Tamper 2: 修改 compute.deltas[0]]")
    tampered = json.loads(json.dumps(record))
    tampered["compute"]["deltas"][0] = 999.99
    test2_path = TEST_DIR / "tamper2.pacsp"
    with open(test2_path, "w", encoding="utf-8") as f:
        json.dump(tampered, f, ensure_ascii=False, indent=2)
    r = run_verify(test2_path, data_dir)
    print(f"  L1={r['L1']} L2={r['L2']} L3={r['L3']} L4={r['L4']} L5={r['L5']}")
    print(f"  → 检测: {'✅ 已捕获' if not r['L1'] or not r['L3'] else '❌ 未捕获'}")

    # ============ 篡改3: 改签名 ============
    print("\n[Tamper 3: 伪造 signature]")
    tampered = json.loads(json.dumps(record))
    tampered["integrity"]["L2"]["data"]["signature"] = "base64:FAKE_SIGNATURE_XXXX"
    test3_path = TEST_DIR / "tamper3.pacsp"
    with open(test3_path, "w", encoding="utf-8") as f:
        json.dump(tampered, f, ensure_ascii=False, indent=2)
    r = run_verify(test3_path, data_dir)
    print(f"  L1={r['L1']} L2={r['L2']} L3={r['L3']} L4={r['L4']} L5={r['L5']}")
    print(f"  → 检测: {'✅ 已捕获' if not r['L2'] else '❌ 未捕获'}")

    # ============ 篡改4: 改 metadata ============
    print("\n[Tamper 4: 修改 metadata.domain]")
    tampered = json.loads(json.dumps(record))
    tampered["metadata"]["domain"] = "FAKE_DOMAIN"
    test4_path = TEST_DIR / "tamper4.pacsp"
    with open(test4_path, "w", encoding="utf-8") as f:
        json.dump(tampered, f, ensure_ascii=False, indent=2)
    r = run_verify(test4_path, data_dir)
    print(f"  L1={r['L1']} L2={r['L2']} L3={r['L3']} L4={r['L4']} L5={r['L5']}")
    print(f"  → 检测: {'✅ 已捕获' if not r['L1'] else '❌ 未捕获'}")


if __name__ == "__main__":
    print("=" * 60)
    print("PACSP-ID Tamper Test")
    print("=" * 60)

    for pacsp in sorted(RECORDS_DIR.glob("*.pacsp")):
        domain = pacsp.stem.split("_")[0]
        data_dir = DATA_DIR / domain
        tamper_test(pacsp, data_dir)

    print("\n" + "=" * 60)
    print("Tamper Test Complete")
    print("=" * 60)