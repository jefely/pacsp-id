"""
3×3 瞬在矩阵
三个瞬在单元的完整代数封装
"""

import torch
import torch.nn as nn
import numpy as np


class TransientMatrix(nn.Module):
    """
    3×3 瞬在矩阵

    核心结构：
    - psi: (batch, 3) 复数向量，三个单元
    - H: (3, 3) 厄米矩阵，哈密顿量
    - I: (batch, 3, 3) 干涉矩阵 = psi * psi†
    """

    def __init__(self, dt: float = 0.01):
        super().__init__()
        self.dt = dt

        # 哈密顿量参数（厄米分解）
        self.H_real = nn.Parameter(torch.randn(3, 3) * 0.1)
        self.H_imag = nn.Parameter(torch.randn(3, 3) * 0.1)

    def get_hamiltonian(self) -> torch.Tensor:
        """构造厄米哈密顿量"""
        H_real = 0.5 * (self.H_real + self.H_real.T)
        H_imag = 0.5 * (self.H_imag - self.H_imag.T)
        return torch.complex(H_real, H_imag)

    def interference_matrix(self, psi: torch.Tensor) -> torch.Tensor:
        """
        计算干涉矩阵
        I_ij = psi_i * conj(psi_j)
        """
        return torch.einsum('bi,bj->bij', psi, psi.conj())

    def evolve(self, psi: torch.Tensor) -> torch.Tensor:
        """
        通过酉演化更新单元
        psi(t+dt) = exp(-i H dt) psi(t)
        """
        H = self.get_hamiltonian()
        U = torch.matrix_exp(-1j * H * self.dt)
        return torch.einsum('ij,bj->bi', U, psi)

    def forward(self, psi: torch.Tensor) -> torch.Tensor:
        """前向：一次演化"""
        return self.evolve(psi)

    def eigenvalues(self) -> torch.Tensor:
        """集体模式特征值"""
        H = self.get_hamiltonian()
        return torch.linalg.eigvalsh(H)

    def phase_coupling_matrix(self, psi: torch.Tensor) -> torch.Tensor:
        """相位耦合矩阵"""
        I = self.interference_matrix(psi)
        return torch.angle(I)

    def interference_strength(self, psi: torch.Tensor) -> torch.Tensor:
        """干涉强度（非对角元模长的平方和）"""
        I = self.interference_matrix(psi)
        # 取出非对角元
        mask = ~torch.eye(3, dtype=torch.bool, device=psi.device)
        return (I.abs() ** 2 * mask).sum(dim=(-2, -1))