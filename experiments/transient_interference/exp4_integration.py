"""
experiments/exp4_integration.py
相位对齐检测：实数 vs 复数
"""


import sys
from pathlib import Path

# Make the sibling package `transient` importable without installing.
_EXP_ROOT = Path(__file__).resolve().parent.parent
if str(_EXP_ROOT) not in sys.path:
    sys.path.insert(0, str(_EXP_ROOT))

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from transient.complex_layer import ComplexMatrixBottleneck


# ============================================================
# 数据生成
# ============================================================
def generate_phase_data(batch_size=32, seq_len=20, vocab_size=16, device="cpu"):
    """
    生成相位敏感数据

    每个样本：两个序列 X, Y
    - 标签 1：Y = X 相移 φ（φ ~ Uniform(-π, π)）
    - 标签 0：Y = X 随机置换
    """
    # 基础序列：在复平面单位圆上均匀采样
    angles = torch.rand(batch_size, seq_len, device=device) * 2 * np.pi
    X_complex = torch.complex(torch.cos(angles), torch.sin(angles))

    # 标签
    labels = torch.randint(0, 2, (batch_size,), device=device).float()

    # 相移版本
    phi = (torch.rand(batch_size, 1, device=device) - 0.5) * 2 * np.pi
    Y_shifted = X_complex * torch.exp(1j * phi)

    # 随机置换版本
    perm = torch.argsort(torch.rand(batch_size, seq_len, device=device), dim=-1)
    Y_permuted = torch.gather(X_complex, 1, perm)

    # 根据标签选择
    Y_complex = torch.where(labels.unsqueeze(-1).bool(), Y_shifted, Y_permuted)

    # 返回实部和虚部（实数模型用）
    X_real = torch.stack([X_complex.real, X_complex.imag], dim=-1)  # (B, T, 2)
    Y_real = torch.stack([Y_complex.real, Y_complex.imag], dim=-1)

    return X_real, Y_real, labels


# ============================================================
# 实数模型
# ============================================================
class RealPhaseClassifier(nn.Module):
    """纯实数模型：拼接 X, Y 的实部虚部"""

    def __init__(self, d_model=32, n_heads=4, n_layers=2):
        super().__init__()
        # 输入：X, Y 各 2 维（实部、虚部）
        self.proj_x = nn.Linear(2, d_model)
        self.proj_y = nn.Linear(2, d_model)

        self.layers = nn.ModuleList([
            nn.TransformerEncoderLayer(
                d_model=d_model, nhead=n_heads,
                dim_feedforward=4 * d_model,
                batch_first=True,
            )
            for _ in range(n_layers)
        ])

        self.classifier = nn.Sequential(
            nn.LayerNorm(d_model * 2),
            nn.Linear(d_model * 2, d_model),
            nn.GELU(),
            nn.Linear(d_model, 1),
        )

    def forward(self, X, Y):
        # X, Y: (B, T, 2)
        x = self.proj_x(X)
        y = self.proj_y(Y)

        # 交错序列：X 和 Y 交替
        combined = torch.cat([x, y], dim=1)  # (B, 2T, d)

        for layer in self.layers:
            combined = layer(combined)

        # 全局池化
        pooled = combined.mean(dim=1)  # (B, d)

        # 同时用 X 和 Y 的摘要
        x_summary = x.mean(dim=1)
        y_summary = y.mean(dim=1)
        features = torch.cat([x_summary, y_summary], dim=-1)

        return self.classifier(features).squeeze(-1)


# ============================================================
# 复数模型
# ============================================================
class ComplexPhaseClassifier(nn.Module):
    """复数模型：使用 ComplexMatrixBottleneck"""

    def __init__(self, d_model=32, n_units=3, n_layers=2):
        super().__init__()
        # 输入：X, Y 各 2 维
        self.proj_x = nn.Linear(2, d_model)
        self.proj_y = nn.Linear(2, d_model)

        self.layers = nn.ModuleList([
            ComplexMatrixBottleneck(d_model, n_units=n_units, n_steps=2)
            for _ in range(n_layers)
        ])

        self.classifier = nn.Sequential(
            nn.LayerNorm(d_model * 2),
            nn.Linear(d_model * 2, d_model),
            nn.GELU(),
            nn.Linear(d_model, 1),
        )

    def forward(self, X, Y):
        x = self.proj_x(X)
        y = self.proj_y(Y)

        combined = torch.cat([x, y], dim=1)

        for layer in self.layers:
            combined = layer(combined)

        x_summary = combined[:, :x.shape[1]].mean(dim=1)
        y_summary = combined[:, x.shape[1]:].mean(dim=1)

        features = torch.cat([x_summary, y_summary], dim=-1)
        return self.classifier(features).squeeze(-1)


# ============================================================
# 训练与评估
# ============================================================
def train_model(model, n_steps=2000, batch_size=32, lr=1e-3, device="cuda"):
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    model.train()

    losses = []
    for step in range(n_steps):
        X, Y, labels = generate_phase_data(batch_size, device=device)

        logits = model(X, Y)
        loss = F.binary_cross_entropy_with_logits(logits, labels)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        losses.append(loss.item())

        if step % 200 == 0:
            print(f"    step {step}: loss = {loss.item():.4f}")

    return losses


@torch.no_grad()
def evaluate(model, n_samples=500, device="cuda"):
    model.eval()
    X, Y, labels = generate_phase_data(n_samples, device=device)
    logits = model(X, Y)
    preds = (logits > 0).float()
    acc = (preds == labels).float().mean().item()
    return acc


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 60)
    print("实验4：相位对齐检测")
    print("=" * 60)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"设备: {device}")

    torch.manual_seed(42)

    results = {}

    for name, model_cls in [
        ("实数", RealPhaseClassifier),
        ("复数", ComplexPhaseClassifier),
    ]:
        print(f"\n训练 {name} 模型...")
        model = model_cls().to(device)

        n_params = sum(p.numel() for p in model.parameters())
        print(f"  参数量: {n_params}")

        losses = train_model(model, n_steps=2000, device=device)
        acc = evaluate(model, device=device)

        results[name] = {
            "params": n_params,
            "final_loss": losses[-1],
            "accuracy": acc,
        }
        print(f"  最终 loss: {losses[-1]:.4f}, 准确率: {acc:.4f}")

    # 对比
    print("\n" + "=" * 60)
    print("对比结果")
    print("=" * 60)
    for name, r in results.items():
        print(f"{name}模型:")
        print(f"  参数量:  {r['params']}")
        print(f"  最终loss: {r['final_loss']:.4f}")
        print(f"  准确率:   {r['accuracy']:.4f}")

    # 判断
    print("\n" + "=" * 60)
    print("结论")
    print("=" * 60)
    real_acc = results["实数"]["accuracy"]
    complex_acc = results["复数"]["accuracy"]

    if abs(real_acc - complex_acc) < 0.02:
        print("  两种模型性能接近")
        print("  任务设计可能需要调整")
    elif complex_acc > real_acc:
        print(f"  复数模型优于实数模型: +{complex_acc - real_acc:.4f}")
        print("  相位信息确实有用")
    else:
        print(f"  实数模型优于复数模型: +{real_acc - complex_acc:.4f}")
        print("  当前任务中相位不是关键")


if __name__ == "__main__":
    main()