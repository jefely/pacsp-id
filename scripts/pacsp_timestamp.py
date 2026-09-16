"""
L4: OpenTimestamps 外部锚定
3 次重试 + 本地证明降级
"""

import base64
import subprocess
import shutil
import time
from pathlib import Path
from datetime import datetime


ROOT_DIR = Path(__file__).parent.parent
OTS_DIR = ROOT_DIR / "cache" / "ots"


def _ots_available():
    """检查 ots 命令是否可用"""
    return shutil.which("ots") is not None


def layer_4_timestamp(context, l1_result):
    """L4: 对 content_hash 生成 OTS 时间戳"""
    content_hash = l1_result["data"]["content_hash"]
    OTS_DIR.mkdir(parents=True, exist_ok=True)

    # 写哈希到文件
    hash_hex = content_hash.replace("sha256:", "")
    hash_file = OTS_DIR / f"{hash_hex[:16]}.txt"
    with open(hash_file, "w", encoding="utf-8") as f:
        f.write(content_hash + "\n")

    # ots 不可用 -> pending
    if not _ots_available():
        return {
            "layer_id": "L4",
            "status": "pending",
            "computed_at": datetime.now().isoformat(),
            "data": {
                "content_hash": content_hash,
                "timestamp_proof": None,
                "timestamp_anchor": None,
                "hash_file": str(hash_file),
                "note": "ots 命令不可用，安装：pip install opentimestamps-client",
            },
            "error": None
        }

    # 3 次重试 + 120 秒超时
    max_retries = 3
    timeout_sec = 120
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            result = subprocess.run(
                ["ots", "stamp", str(hash_file)],
                capture_output=True,
                text=True,
                timeout=timeout_sec
            )

            if result.returncode == 0:
                ots_file = hash_file.with_suffix(".txt.ots")
                if ots_file.exists():
                    with open(ots_file, "rb") as f:
                        ots_bytes = f.read()
                    return {
                        "layer_id": "L4",
                        "status": "ok",
                        "computed_at": datetime.now().isoformat(),
                        "data": {
                            "content_hash": content_hash,
                            "timestamp_proof": "base64:" + base64.b64encode(ots_bytes).decode("ascii"),
                            "timestamp_anchor": "pending_bitcoin_confirmation",
                            "ots_file": str(ots_file),
                            "attempts": attempt,
                            "note": "等待 Bitcoin 区块确认（通常 1-6 小时）",
                        },
                        "error": None
                    }
            else:
                # 远程失败，尝试读本地 .ots
                last_error = result.stderr[:200]
                ots_file = hash_file.with_suffix(".txt.ots")
                if ots_file.exists():
                    with open(ots_file, "rb") as f:
                        ots_bytes = f.read()
                    return {
                        "layer_id": "L4",
                        "status": "pending",
                        "computed_at": datetime.now().isoformat(),
                        "data": {
                            "content_hash": content_hash,
                            "timestamp_proof": "base64:" + base64.b64encode(ots_bytes).decode("ascii"),
                            "timestamp_anchor": "local_only_pending_remote",
                            "ots_file": str(ots_file),
                            "attempts": attempt,
                            "note": "本地证明已生成，远程提交部分失败",
                        },
                        "error": None
                    }

        except subprocess.TimeoutExpired:
            last_error = f"超时（第 {attempt} 次，{timeout_sec}s）"
        except Exception as e:
            last_error = str(e)

        if attempt < max_retries:
            print(f"    L4 retry {attempt}/{max_retries - 1}... ({last_error})")
            time.sleep(5)

    # 全部失败
    return {
        "layer_id": "L4",
        "status": "failed",
        "computed_at": datetime.now().isoformat(),
        "data": {"content_hash": content_hash},
        "error": f"3 次重试均失败: {last_error}"
    }


def verify_l4(record):
    """验证 L4 时间戳（非致命层）"""
    l4 = record.get("integrity", {}).get("L4", {})
    if not l4:
        return None, "缺少 integrity.L4"

    status = l4.get("status")
    if status == "ok":
        data = l4.get("data", {})
        proof = data.get("timestamp_proof", "")
        anchor = data.get("timestamp_anchor", "unknown")
        if proof:
            return True, f"时间戳存在 (锚点: {anchor})"
        return False, "缺少 timestamp_proof"
    elif status == "pending":
        return None, "时间戳待确认（非致命）"
    else:
        err = l4.get("error", "")
        return False, f"L4 状态: {status} {('- ' + err[:60]) if err else ''}"


if __name__ == "__main__":
    print("=" * 60)
    print("L4: OpenTimestamps self-test")
    print("=" * 60)

    print("\n[1/3] Check ots command")
    if _ots_available():
        print("  OK ots available")
    else:
        print("  PEND ots not available")

    print("\n[2/3] Mock L1 input")
    l1_result = {
        "data": {
            "content_hash": "sha256:4ddf6e39156a3f11a509206fecb8fe7e0dcd6e9be59d9d581b24687749e34799"
        }
    }
    print(f"  content_hash: {l1_result['data']['content_hash'][:50]}...")

    print("\n[3/3] Generate timestamp")
    result = layer_4_timestamp({}, l1_result)
    print(f"  status: {result['status']}")
    if result["data"].get("timestamp_proof"):
        print(f"  proof: {result['data']['timestamp_proof'][:60]}...")
        print(f"  anchor: {result['data']['timestamp_anchor']}")
    elif result["data"].get("note"):
        print(f"  note: {result['data']['note']}")

    print("\n" + "=" * 60)
    print("Self-test complete")
    print("=" * 60)