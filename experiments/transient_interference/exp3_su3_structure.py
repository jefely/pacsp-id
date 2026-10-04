"""
实验3：验证 3×3 矩阵的 SU(3) 结构
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
from transient.dynamics import su3_generators, decompose_into_su3


def run_experiment():
    print("=" * 60)
    print("实验3：SU(3) 结构验证")
    print("=" * 60)

    torch.manual_seed(42)

    # 检查 SU(3) 生成元的正交性
    print("\n[1] SU(3) 生成元的正交性")
    generators = su3_generators()
    for i in range(8):
        for j in range(i+1, 8):
            inner = torch.trace(generators[i] @ generators[j]).real
            if abs(inner) > 1e-5:
                print(f"  ✗ λ{i+1} 和 λ{j+1} 不正交: {inner:.6f}")
                return False
    print("  ✓ 所有生成元正交")

    # 检查厄米性
    print("\n[2] 生成元的厄米性")
    for i in range(8):
        is_hermitian = torch.allclose(generators[i], generators[i].conj().T)
        if not is_hermitian:
            print(f"  ✗ λ{i+1} 不是厄米矩阵")
            return False
    print("  ✓ 所有生成元厄米")

    # 验证任意厄米矩阵可被 SU(3) 生成元分解
    print("\n[3] 任意厄米矩阵的 SU(3) 分解")
    transient = TransientMatrix(dt=0.01)
    H = transient.get_hamiltonian()

    # 分解
    coeffs = decompose_into_su3(H)

    # 重构
    generators = su3_generators()
    H_reconstructed = sum(c * g for c, g in zip(coeffs, generators))

    error = torch.norm(H - H_reconstructed).item()
    print(f"  分解误差: {error:.6e}")
    if error < 1e-5:
        print("  ✓ 厄米矩阵可被 SU(3) 生成元完备分解")
    else:
        print("  ✗ 分解误差过大")
        return False

    # 验证特征值结构
    print("\n[4] 集体模式特征值")
    eigenvalues = transient.eigenvalues().numpy()
    print(f"  特征值: {eigenvalues}")
    if len(eigenvalues) == 3 and len(set(np.round(eigenvalues, 4))) == 3:
        print("  ✓ 三个非简并集体模式")
    else:
        print("  ⚠ 存在简并，可能需要微调哈密顿量")

    return True


if __name__ == "__main__":
    run_experiment()