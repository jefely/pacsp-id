"""
动力学分析工具
"""

import torch
import numpy as np


def su3_generators() -> torch.Tensor:
    """
    SU(3) 的 8 个盖尔曼矩阵
    返回: (8, 3, 3) 张量
    """
    # 泡利矩阵
    sigma1 = torch.tensor([[0, 1], [1, 0]], dtype=torch.complex64)
    sigma2 = torch.tensor([[0, -1j], [1j, 0]], dtype=torch.complex64)
    sigma3 = torch.tensor([[1, 0], [0, -1]], dtype=torch.complex64)

    I2 = torch.eye(2, dtype=torch.complex64)
    zero = torch.zeros_like(I2)

    generators = torch.zeros(8, 3, 3, dtype=torch.complex64)

    # λ1, λ2, λ3
    generators[0, :2, :2] = sigma1
    generators[1, :2, :2] = sigma2
    generators[2, :2, :2] = sigma3

    # λ4, λ5
    generators[3, 0, 2] = 1
    generators[3, 2, 0] = 1
    generators[4, 0, 2] = -1j
    generators[4, 2, 0] = 1j

    # λ6, λ7
    generators[5, 1, 2] = 1
    generators[5, 2, 1] = 1
    generators[6, 1, 2] = -1j
    generators[6, 2, 1] = 1j

    # λ8
    generators[7] = torch.tensor([
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, -2]
    ], dtype=torch.complex64) / np.sqrt(3)

    return generators


def decompose_into_su3(H: torch.Tensor) -> torch.Tensor:
    """
    将 3×3 厄米矩阵分解为 SU(3) 生成元的线性组合
    返回: (8,) 系数
    """
    generators = su3_generators().to(H.device)
    # 系数 c_i = Tr(H @ λ_i) / 2
    coeffs = torch.einsum('ij,kji->k', H, generators) / 2
    return coeffs.real


def phase_order_parameter(psi: torch.Tensor) -> float:
    """
    计算相位序参量
    0 = 完全无序
    1 = 完全同步
    """
    psi = psi / (psi.abs() + 1e-8)
    mean_phase = psi.mean(dim=-1)
    return float(mean_phase.abs().mean())