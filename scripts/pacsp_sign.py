"""
L2: Ed25519 数字签名
对 L1 的 content_hash 签名
"""

import hashlib
import base64
from pathlib import Path
from datetime import datetime
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


# 密钥存储位置
KEY_DIR = Path.home() / ".pacsp"
KEY_PATH = KEY_DIR / "signing_key.pem"


def get_or_create_key():
    """获取或创建 Ed25519 密钥"""
    KEY_DIR.mkdir(parents=True, exist_ok=True)

    if KEY_PATH.exists():
        with open(KEY_PATH, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)

    private_key = ed25519.Ed25519PrivateKey.generate()
    with open(KEY_PATH, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    print(f"✓ 密钥已生成: {KEY_PATH}")
    return private_key


def get_public_key_id(private_key):
    """从公钥派生短 ID（16 位十六进制）"""
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return hashlib.sha256(pub_bytes).hexdigest()[:16]


def layer_2_sign(context, l1_result):
    """L2: 对 L1 的 content_hash 签名"""
    content_hash = l1_result["data"]["content_hash"]

    private_key = get_or_create_key()
    signature = private_key.sign(content_hash.encode("utf-8"))

    return {
        "layer_id": "L2",
        "status": "ok",
        "computed_at": datetime.now().isoformat(),
        "data": {
            "signature": "base64:" + base64.b64encode(signature).decode("ascii"),
            "signature_algorithm": "ed25519",
            "public_key_id": get_public_key_id(private_key),
            "signed_content_hash": content_hash,   # 冗余存储，便于验证
        },
        "error": None
    }


def verify_l2(record):
    """验证 L2 签名"""
    l2 = record.get("integrity", {}).get("L2", {})
    if not l2:
        return False, "缺少 integrity.L2"

    if l2.get("status") != "ok":
        return False, f"L2 状态: {l2.get('status')}"

    data = l2["data"]
    signature_b64 = data["signature"]
    public_key_id = data["public_key_id"]
    signed_content_hash = data.get("signed_content_hash")

    # 获取当前密钥
    try:
        private_key = get_or_create_key()
    except Exception as e:
        return False, f"无法读取密钥: {e}"

    # 检查公钥 ID 是否匹配
    current_pub_id = get_public_key_id(private_key)
    if current_pub_id != public_key_id:
        return False, f"公钥 ID 不匹配: 当前 {current_pub_id} != 存储 {public_key_id}"

    # 检查签名的 content_hash 是否与 L1 一致
    l1_content_hash = record.get("integrity", {}).get("L1", {}).get("content_hash")
    if signed_content_hash != l1_content_hash:
        return False, f"签名的内容哈希与 L1 不一致"

    # 验证签名
    try:
        signature = base64.b64decode(signature_b64.replace("base64:", ""))
        private_key.public_key().verify(signature, signed_content_hash.encode("utf-8"))
        return True, f"签名有效 (公钥 {public_key_id})"
    except Exception as e:
        return False, f"签名无效: {e}"


def export_public_key():
    """导出公钥（用于分享给第三方验证者）"""
    private_key = get_or_create_key()
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pub_bytes.decode("ascii")


if __name__ == "__main__":
    print("=" * 60)
    print("L2: Ed25519 签名 自测")
    print("=" * 60)

    # 1. 生成/读取密钥
    print("\n[1/4] 获取或创建密钥")
    private_key = get_or_create_key()
    pub_id = get_public_key_id(private_key)
    print(f"  公钥 ID: {pub_id}")

    # 2. 模拟 L1 输出
    print("\n[2/4] 模拟 L1 输入")
    l1_result = {
        "data": {
            "content_hash": "sha256:4ddf6e39156a3f11a509206fecb8fe7e0dcd6e9be59d9d581b24687749e34799"
        }
    }
    print(f"  content_hash: {l1_result['data']['content_hash'][:50]}...")

    # 3. 签名
    print("\n[3/4] 生成签名")
    result = layer_2_sign({}, l1_result)
    print(f"  算法:   {result['data']['signature_algorithm']}")
    print(f"  公钥 ID: {result['data']['public_key_id']}")
    print(f"  签名:   {result['data']['signature'][:60]}...")

    # 4. 验证
    print("\n[4/4] 验证签名")
    fake_record = {
        "integrity": {
            "L1": {"content_hash": l1_result["data"]["content_hash"]},
            "L2": result,
        }
    }
    ok, msg = verify_l2(fake_record)
    icon = "✅" if ok else "❌"
    print(f"  {icon} {msg}")

    # 5. 篡改测试
    print("\n[5/5] 篡改测试")
    fake_record["integrity"]["L1"]["content_hash"] = "sha256:tampered"
    ok, msg = verify_l2(fake_record)
    icon = "✅ 正确检测" if not ok else "❌ 未检测到"
    print(f"  {icon}: {msg}")

    print("\n" + "=" * 60)
    print("自测完成")
    print("=" * 60)