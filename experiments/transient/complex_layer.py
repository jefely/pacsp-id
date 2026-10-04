"""
复数瓶颈层
可插入到标准 Transformer 中
"""

import torch
import torch.nn as nn
from .transient_matrix import TransientMatrix


class ComplexMatrixBottleneck(nn.Module):
    """
    3×3 复矩阵瓶颈层

    流程：
    实数向量 → 3个复单元 → 矩阵演化 → 提取输出 → 实数向量
    """

    def __init__(self, d_model: int, n_units: int = 3, n_steps: int = 3):
        super().__init__()
        self.d_model = d_model
        self.n_units = n_units
        self.n_steps = n_steps

        # 实数 → 复数
        self.to_complex = nn.Linear(d_model, n_units * 2)

        # 瞬在矩阵
        self.transient = TransientMatrix(dt=0.01)

        # 复数 → 实数
        self.to_real = nn.Linear(n_units * 2, d_model)

        # 层归一化
        self.norm_in = nn.LayerNorm(d_model)
        self.norm_out = nn.LayerNorm(d_model)

        self._reset_parameters()

    def _reset_parameters(self):
        nn.init.xavier_uniform_(self.to_complex.weight)
        nn.init.zeros_(self.to_complex.bias)
        nn.init.xavier_uniform_(self.to_real.weight)
        nn.init.zeros_(self.to_real.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, seq, d_model) 实数向量
        Returns:
            (batch, seq, d_model) 实数向量
        """
        residual = x
        x = self.norm_in(x)

        batch, seq, _ = x.shape

        # 投影到复单元
        params = self.to_complex(x)  # (batch, seq, 2*n_units)
        params = params.reshape(batch, seq, self.n_units, 2)
        psi = torch.complex(params[..., 0], params[..., 1])  # (batch, seq, n_units)

        # 归一化（防止数值爆炸）
        norm = psi.abs().sum(dim=-1, keepdim=True) + 1e-8
        psi = psi / norm

        # 多次演化
        psi_flat = psi.reshape(-1, self.n_units)  # (batch*seq, n_units)
        for _ in range(self.n_steps):
            psi_flat = self.transient(psi_flat)
        psi = psi_flat.reshape(batch, seq, self.n_units)

        # 提取输出
        psi_out = torch.cat([psi.real, psi.imag], dim=-1)  # (batch, seq, 2*n_units)
        out = self.to_real(psi_out)

        return self.norm_out(out) + residual