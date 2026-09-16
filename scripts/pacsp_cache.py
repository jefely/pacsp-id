"""
从 .pacsp 生成人机双读 .txt 缓存 + 全局索引
"""

import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
RECORDS_DIR = ROOT / "records"
CACHE_DIR = ROOT / "cache"
CACHE_DIR.mkdir(exist_ok=True)


def format_txt_cache(record, ref_name):
    m = record["metadata"]
    d = record["dataset"]
    r = record["results"]
    s = record.get("stats", {})
    p = m["parameters"]
    integ = record["integrity"]

    W = 64
    lines = []
    lines.append("=" * W)
    lines.append("PACSP Cache")
    lines.append("=" * W)
    lines.append(f"dataset      : {m['domain']}_{m['epoch']}_{m['variant']}")
    lines.append(f"generated_at : {record['generated_at']}")
    lines.append(f"protocol     : {record['protocol']} {record['version']}")
    lines.append("=" * W)
    lines.append("")

    lines.append("[METADATA]")
    lines.append(f"domain       = {m['domain']}")
    lines.append(f"epoch        = {m['epoch']}")
    lines.append(f"variant      = {m['variant']}")
    lines.append(f"C_T          = {r['C_T_Se']:.4f} Se")
    lines.append(f"n_samples    = {d['n_samples']}")
    lines.append(f"model        = {p['embedding_model']}")
    lines.append(f"window       = {p['window_size']}")
    lines.append("")

    lines.append("[STATS]")
    lines.append(f"delta_mean   = {s.get('delta_mean', 0):.4f}")
    lines.append(f"delta_std    = {s.get('delta_std', 0):.4f}")
    lines.append(f"mu_mean      = {s.get('mu_mean', 0):.4f}")
    lines.append(f"mu_std       = {s.get('mu_std', 0):.4f}")
    lines.append("")

    lines.append("[CHANGEPOINTS]")
    cp = r.get("changepoints", {})
    lines.append(f"mu_k         = {cp.get('mu_k', [])}")
    lines.append(f"delta_k      = {cp.get('delta_k', [])}")
    lines.append("")

    lines.append("[INTEGRITY]")
    l1 = integ.get("L1", {})
    l1_data = l1.get("data", l1)
    lines.append(f"L1 content_hash   = {l1_data.get('content_hash', 'N/A')[:50]}...")

    l2 = integ.get("L2", {})
    l2_data = l2.get("data", l2)
    lines.append(f"L2 public_key_id  = {l2_data.get('public_key_id', 'N/A')}")
    lines.append(f"L2 status         = {l2.get('status', 'N/A')}")

    l3 = integ.get("L3", {})
    lines.append(f"L3 sample_merkle  = {str(l3.get('sample', 'N/A'))[:40]}...")
    lines.append(f"L3 compute_merkle = {str(l3.get('compute', 'N/A'))[:40]}...")
    lines.append(f"L3 result_merkle  = {str(l3.get('result', 'N/A'))[:40]}...")

    l4 = integ.get("L4", {})
    lines.append(f"L4 status         = {l4.get('status', 'N/A')}")

    l5 = integ.get("L5", {})
    lines.append(f"L5 status         = {l5.get('status', 'N/A')}")
    lines.append("")

    # 逐快照明细
    deltas = record.get("compute", {}).get("deltas", [])
    mus = record.get("compute", {}).get("mus", [])
    mu_cps = set(cp.get("mu_k", []))
    delta_cps = set(cp.get("delta_k", []))

    if deltas and mus:
        lines.append("[PER-SNAPSHOT]")
        lines.append(f"  #    delta_k    mu_k       tag")
        lines.append(" ---  ---------  ---------  ----------------")
        for k in range(len(mus)):
            d_val = deltas[k] if k < len(deltas) else 0.0
            m_val = mus[k]
            tag = ""
            if (k+1) in mu_cps:
                tag = "<- mu changepoint"
            elif (k+1) in delta_cps:
                tag = "<- delta changepoint"
            lines.append(f" {k+1:>3}   {d_val:>8.4f}  {m_val:>8.4f}  {tag}")
        lines.append("")

    lines.append("[FILES]")
    lines.append(f"pacsp  : records/{ref_name}")
    lines.append(f"txt    : cache/{m['domain']}_{m['epoch']}_{m['variant']}.txt")
    lines.append(f"png    : cache/{m['domain']}_{m['epoch']}_{m['variant']}_main.png")
    lines.append("")
    lines.append("=" * W)

    return "\n".join(lines)


def build_index(records_data):
    return {
        "protocol": "PACSP-ID",
        "version": "4.0.0-COMPACT",
        "generated_at": datetime.now().isoformat(),
        "total_records": len(records_data),
        "records": records_data,
    }


def main():
    pacsp_files = sorted(RECORDS_DIR.glob("*.pacsp"))
    print(f"Found {len(pacsp_files)} .pacsp files")

    index_records = []

    for pacsp_path in pacsp_files:
        with open(pacsp_path, encoding="utf-8") as f:
            record = json.load(f)

        m = record["metadata"]
        r = record["results"]

        # 生成 .txt
        txt_content = format_txt_cache(record, pacsp_path.name)
        txt_name = f"{m['domain']}_{m['epoch']}_{m['variant']}.txt"
        txt_path = CACHE_DIR / txt_name
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt_content)
        print(f"  OK {txt_name}")

        # 收集索引条目
        l1 = record["integrity"].get("L1", {})
        l1_data = l1.get("data", l1)

        index_records.append({
            "ref": pacsp_path.name,
            "domain": m["domain"],
            "epoch": m["epoch"],
            "variant": m["variant"],
            "C_T_Se": r["C_T_Se"],
            "n_samples": record["dataset"]["n_samples"],
            "content_hash": l1_data.get("content_hash"),
            "cache": {
                "txt": f"cache/{txt_name}",
                "png": f"cache/{m['domain']}_{m['epoch']}_{m['variant']}_main.png",
            }
        })

    # 全局索引
    index = build_index(index_records)
    index_path = CACHE_DIR / "_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"  OK _index.json")


if __name__ == "__main__":
    main()