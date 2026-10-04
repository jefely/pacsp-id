"""
实验5：参数匹配下的相位对齐检测
控制实数/复数模型参数量相同，比较性能
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
# 数据生成（同实验4）
# ============================================================
def generate_phase_data(batch_size=32, seq_len=20, device="cpu"):
    angles = torch.rand(batch_size, seq_len, device=device) * 2 * np.pi
    X_complex = torch.complex(torch.cos(angles), torch.sin(angles))

    labels = torch.randint(0, 2, (batch_size,), device=device).float()

    phi = (torch.rand(batch_size, 1, device=device) - 0.5) * 2 * np.pi
    Y_shifted = X_complex * torch.exp(1j * phi)

    perm = torch.argsort(torch.rand(batch_size, seq_len, device=device), dim=-1)
    Y_permuted = torch.gather(X_complex, 1, perm)

    Y_complex = torch.where(labels.unsqueeze(-1).bool(), Y_shifted, Y_permuted)

    X_real = torch.stack([X_complex.real, X_complex.imag], dim=-1)
    Y_real = torch.stack([Y_complex.real, Y_complex.imag], dim=-1)

    return X_real, Y_real, labels


# ============================================================
# 实数模型（可调 d_model 控制参数量）
# ============================================================
class RealPhaseClassifier(nn.Module):
    def __init__(self, d_model=32, n_heads=4, n_layers=2):
        super().__init__()
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
        x = self.proj_x(X)
        y = self.proj_y(Y)
        combined = torch.cat([x, y], dim=1)

        for layer in self.layers:
            combined = layer(combined)

        x_summary = x.mean(dim=1)
        y_summary = y.mean(dim=1)
        features = torch.cat([x_summary, y_summary], dim=-1)
        return self.classifier(features).squeeze(-1)


# ============================================================
# 复数模型
# ============================================================
class ComplexPhaseClassifier(nn.Module):
    def __init__(self, d_model=32, n_units=3, n_layers=2):
        super().__init__()
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
# 训练
# ============================================================
def train_model(model, n_steps=3000, batch_size=32, lr=1e-3, device="cuda"):
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=n_steps)
    model.train()

    losses = []
    for step in range(n_steps):
        X, Y, labels = generate_phase_data(batch_size, device=device)
        logits = model(X, Y)
        loss = F.binary_cross_entropy_with_logits(logits, labels)

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        losses.append(loss.item())

        if step % 300 == 0:
            print(f"    step {step}: loss = {loss.item():.4f}")

    return losses


@torch.no_grad()
def evaluate(model, n_samples=1000, device="cuda"):
    model.eval()
    X, Y, labels = generate_phase_data(n_samples, device=device)
    logits = model(X, Y)
    preds = (logits > 0).float()
    acc = (preds == labels).float().mean().item()
    return acc


# ============================================================
# 主流程
# ============================================================
def count_params(model):
    return sum(p.numel() for p in model.parameters())


def main():
    print("=" * 60)
    print("实验5：参数匹配下的相位对齐检测")
    print("=" * 60)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"设备: {device}\n")

    torch.manual_seed(42)

    # 目标参数量：约 3500（与实验4的复数模型相近）
    # 调整 d_model 让实数模型参数量接近复数模型
    configs = [
        ("实数-matched", RealPhaseClassifier, {"d_model": 24, "n_heads": 4, "n_layers": 2}),
        ("复数-matched", ComplexPhaseClassifier, {"d_model": 32, "n_units": 3, "n_layers": 2}),
    ]

    results = {}

    for name, model_cls, kwargs in configs:
        print(f"\n{'='*60}")
        print(f"训练 {name} 模型")
        print(f"{'='*60}")

        model = model_cls(**kwargs).to(device)
        n_params = count_params(model)
        print(f"  参数量: {n_params}")

        # 复数模型用更小的学习率
        lr = 3e-4 if "复数" in name else 1e-3
        print(f"  学习率: {lr}")

        losses = train_model(model, n_steps=3000, lr=lr, device=device)
        acc = evaluate(model, device=device)

        results[name] = {
            "params": n_params,
            "final_loss": losses[-1],
            "min_loss": min(losses),
            "accuracy": acc,
            "losses": losses,
        }
        print(f"  最终 loss: {losses[-1]:.4f}")
        print(f"  最小 loss: {min(losses):.4f}")
        print(f"  准确率: {acc:.4f}")

    # 对比
    print("\n" + "=" * 60)
    print("对比结果")
    print("=" * 60)
    print(f"{'模型':<15}{'参数量':<10}{'最终loss':<12}{'最小loss':<12}{'准确率':<10}")
    print("-" * 60)
    for name, r in results.items():
        print(f"{name:<15}{r['params']:<10}{r['final_loss']:<12.4f}"
              f"{r['min_loss']:<12.4f}{r['accuracy']:<10.4f}")

    # 判断
    print("\n" + "=" * 60)
    print("结论")
    print("=" * 60)

    real_r = results["实数-matched"]
    complex_r = results["复数-matched"]

    # 参数效率比
    param_ratio = real_r["params"] / complex_r["params"]
    print(f"参数量比（实/复）: {param_ratio:.2f}")

    if complex_r["accuracy"] > real_r["accuracy"] + 0.02:
        print(f"✓ 相同参数量下，复数模型准确率更高")
        print(f"  优势: +{complex_r['accuracy'] - real_r['accuracy']:.4f}")
    elif abs(complex_r["accuracy"] - real_r["accuracy"]) < 0.02:
        print(f"≈ 相同参数量下，两模型性能接近")
    else:
        print(f"✗ 实数模型仍占优")

    # 训练稳定性
    real_std = np.std(real_r["losses"][-500:])
    complex_std = np.std(complex_r["losses"][-500:])
    print(f"\n训练稳定性（最后500步 loss 标准差）:")
    print(f"  实数: {real_std:.4f}")
    print(f"  复数: {complex_std:.4f}")


if __name__ == "__main__":
    main()