"""
实验1：验证相位耦合决定干涉强度
核心假设：振幅相同、相位不同的单元，干涉强度显著不同
"""


import sys
from pathlib import Path

# Make the sibling package `transient` importable without installing.
_EXP_ROOT = Path(__file__).resolve().parent.parent
if str(_EXP_ROOT) not in sys.path:
    sys.path.insert(0, str(_EXP_ROOT))

import torch
import numpy as np
from transient.transient_matrix import TransientMatrix


def run_experiment():
    print("=" * 60)
    print("实验1：相位耦合决定干涉强度")
    print("=" * 60)

    torch.manual_seed(42)
    transient = TransientMatrix(dt=0.01)

    # 构造三种相位关系的单元
    A = 0.8  # 固定振幅

    # 情况1：相位对齐（coherent）
    psi_coherent = torch.tensor([
        [A * np.exp(1j * 0.0), A * np.exp(1j * 0.0), A * np.exp(1j * 0.0)]
    ], dtype=torch.complex64)

    # 情况2：相位失配（incoherent）
    psi_incoherent = torch.tensor([
        [A * np.exp(1j * 0.0), A * np.exp(1j * np.pi), A * np.exp(1j * np.pi/2)]
    ], dtype=torch.complex64)

    # 情况3：完全反相
    psi_anti = torch.tensor([
        [A * np.exp(1j * 0.0), A * np.exp(1j * np.pi), A * np.exp(1j * np.pi)]
    ], dtype=torch.complex64)

    # 计算干涉强度
    I_coherent = transient.interference_strength(psi_coherent)
    I_incoherent = transient.interference_strength(psi_incoherent)
    I_anti = transient.interference_strength(psi_anti)

    # 计算相位耦合矩阵
    phase_coherent = transient.phase_coupling_matrix(psi_coherent)
    phase_incoherent = transient.phase_coupling_matrix(psi_incoherent)

    print("\n干涉强度：")
    print(f"  相位对齐:   {I_coherent.item():.4f}")
    print(f"  相位失配:   {I_incoherent.item():.4f}")
    print(f"  完全反相:   {I_anti.item():.4f}")

    print("\n相位耦合矩阵（相位对齐）：")
    print(phase_coherent[0].numpy())

    print("\n相位耦合矩阵（相位失配）：")
    print(phase_incoherent[0].numpy())

    # 验证结论
    print("\n验证结论：")
    if I_coherent > I_incoherent > I_anti:
        print("  ✓ 相位对齐干涉最强，失配次之，反相最弱")
        print("  ✓ 相位耦合确实决定干涉强度")
    else:
        print("  ✗ 结果不符合预期")

    return {
        "I_coherent": I_coherent.item(),
        "I_incoherent": I_incoherent.item(),
        "I_anti": I_anti.item(),
    }


if __name__ == "__main__":
    run_experiment()