"""
瞬在单元：单个复数单元
对应一个瞬在的最小表示
"""

import torch
import torch.nn as nn
import numpy as np
from dataclasses import dataclass


@dataclass
class TransientUnit:
    """单瞬在单元（三环节封装）"""
    F: complex  # 前向展开态
    B: complex  # 反向接缝态
    U: complex  # 更新沉淀态

    @property
    def amplitude(self) -> float:
        """整体振幅"""
        return abs(self.F + self.B + self.U) / 3.0

    @property
    def theta(self) -> float:
        """整体相位"""
        return np.angle(self.F + self.B + self.U)

    @property
    def delta_FB(self) -> float:
        """相对相位 1"""
        return np.angle(self.F) - np.angle(self.B)

    @property
    def delta_BU(self) -> float:
        """相对相位 2"""
        return np.angle(self.B) - np.angle(self.U)

    def rotate(self, phi: float):
        """相位旋转"""
        self.F *= np.exp(1j * phi)
        self.B *= np.exp(1j * phi)
        self.U *= np.exp(1j * phi)

    def to_complex(self) -> complex:
        """压缩为单个复数（用于矩阵运算）"""
        return (self.F + self.B + self.U) / 3.0

    @classmethod
    def from_complex(cls, z: complex, delta_FB: float, delta_BU: float):
        """从复数 + 相对相位重建三环节"""
        theta = np.angle(z)
        A = abs(z)
        theta_F = theta + (2 * delta_FB + delta_BU) / 3
        theta_B = theta - (delta_FB - delta_BU) / 3
        theta_U = theta - (delta_FB + 2 * delta_BU) / 3
        return cls(
            F=A * np.exp(1j * theta_F),
            B=A * np.exp(1j * theta_B),
            U=A * np.exp(1j * theta_U),
        )