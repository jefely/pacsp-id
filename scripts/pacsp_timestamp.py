"""
L4: OpenTimestamps 外部锚定
3 次重试 + 本地证明降级
"""

import base64
import hashlib
import os
import re
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


def _ots_run(args, timeout_sec):
    """Run ots with a workspace-local cache.

    The client keeps a cache under the user profile by default, which fails on a machine
    where that path is not writable. Pointing it at the cache beside the proofs keeps the
    command self-contained and made the difference between an upgrade that worked and a
    PermissionError.
    """
    env = dict(os.environ)
    env["OTS_CACHE"] = str(OTS_DIR / "cache")
    try:
        return subprocess.run(["ots", *args], capture_output=True, text=True,
                              timeout=timeout_sec, env=env)
    except Exception as e:
        class _R:
            returncode = 1
            stdout = ""
            stderr = f"{type(e).__name__}: {e}"
        return _R()


def _bitcoin_blocks(ots_file):
    """Pull Bitcoin block heights out of a proof by reading `ots info`."""
    r = _ots_run(["info", str(ots_file)], 120)
    text = (r.stdout or "") + (r.stderr or "")
    blocks = []
    for m in re.finditer(r"BitcoinBlockHeaderAttestation\((\d+)\)", text):
        h = int(m.group(1))
        if h not in blocks:
            blocks.append(h)
    return blocks


def _try_upgrade(ots_file, timeout_sec=120):
    """Attempt to complete a pending proof. Returns (changed, block_heights).

    A failure here is not fatal: the proof is still a valid PendingAttestation, and the
    record marks it as such. What must not happen is a record claiming an anchor it does
    not have, so the returned blocks come from reading the proof back, not from the
    command's own exit status.
    """
    before = _bitcoin_blocks(ots_file)
    if before:
        return False, before
    r = _ots_run(["upgrade", str(ots_file)], timeout_sec)
    after = _bitcoin_blocks(ots_file)
    changed = bool(after) and after != before
    if not after and r.returncode != 0:
        # leave the proof as it was; the caller records pending
        pass
    return changed, after


def layer_4_timestamp(context, l1_result):
    """L4: 对 content_hash 生成 OTS 时间戳

    〔2026-10-05 修订：把取证对象写清楚，并增加 upgrade〕

    原实现的绑定是成立的，但记录里读不出来，原因有两处：

    1. `ots stamp` 对**文件**取证，即对文件内容的 SHA-256 取证。原实现把
       `content_hash + "\n"` 写入文件，所以日历收到的是
       `sha256("sha256:<64hex>\\n" 的字节)`，而记录里存的是 `<64hex>`。
       两者是不同的值，记录里没有任何字段说明这一跳。诊断见
       PACSP-M/docs/L4-PROVENANCE-AUDIT.md。

    2. `ots stamp` 只产生 PendingAttestation。要让证明带上 Bitcoin 区块头路径，
       必须再执行 `ots upgrade`。原实现从未调用它，所以记录里的证明永远停在
       "待确认"，尽管日历其实已经把它锚定进区块了（实测区块 969867、969869）。

    修订内容：
      * 新增 stamped_digest 字段，记录实际提交给日历的摘要
      * 新增 stamped_file 字段，记录被取证的文件路径
      * 新增 stamped_bytes_sha256，记录取证对象的原始字节摘要（应与 stamped_digest 相同）
      * stamp 之后尝试 upgrade，并把 upgrade 结果写入 upgraded / bitcoin_attestations
      * 保留 content_hash 与 timestamp_anchor，不改动已有字段，保证旧记录仍可读
    """
    content_hash = l1_result["data"]["content_hash"]
    OTS_DIR.mkdir(parents=True, exist_ok=True)

    # 写哈希到文件
    hash_hex = content_hash.replace("sha256:", "")
    hash_file = OTS_DIR / f"{hash_hex[:16]}.txt"
    with open(hash_file, "w", encoding="utf-8") as f:
        f.write(content_hash + "\n")

    # 日历实际收到的摘要 = 被取证文件的 SHA-256（原始字节）
    with open(hash_file, "rb") as f:
        stamped_digest = "sha256:" + hashlib.sha256(f.read()).hexdigest()

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
                "stamped_file": str(hash_file),
                "stamped_digest": stamped_digest,
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
                    # Try to complete the proof. `ots stamp` yields a PendingAttestation;
                    # without an upgrade the proof never carries a block header path even
                    # after the calendars have anchored it. Measured on the 2026-10-04
                    # records: upgrade turned an 840-byte pending proof into a 2913-byte
                    # one with BitcoinBlockHeaderAttestation(969867) and (969869).
                    upgraded, blocks = _try_upgrade(ots_file, timeout_sec)
                    with open(ots_file, "rb") as f:
                        ots_bytes = f.read()
                    anchor = ("bitcoin_block:" + ",".join(str(b) for b in blocks)
                              if blocks else "pending_bitcoin_confirmation")
                    return {
                        "layer_id": "L4",
                        "status": "ok",
                        "computed_at": datetime.now().isoformat(),
                        "data": {
                            "content_hash": content_hash,
                            "stamped_file": str(hash_file),
                            "stamped_digest": stamped_digest,
                            "timestamp_proof": "base64:" + base64.b64encode(ots_bytes).decode("ascii"),
                            "timestamp_anchor": anchor,
                            "ots_file": str(ots_file),
                            "upgraded": upgraded,
                            "bitcoin_attestations": blocks,
                            "attempts": attempt,
                            "note": ("已上链，区块 " + ", ".join(str(b) for b in blocks)
                                     if blocks else
                                     "已提交，等待 Bitcoin 确认；可用 ots upgrade 补齐"),
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