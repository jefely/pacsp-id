"""
实验6：高精度相位对齐检测
验证理论预测：实数模型 O(ε^{-1})，复数模型 O(1)
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
# 数据生成：高精度相位对齐
# ============================================================
def generate_high_precision_data(
    batch_size=64,
    seq_len=10,
    epsilon=1e-3,
    device="cpu",
):
    """
    生成高精度相位对齐数据

    - 正样本：|Δθ| < ε
    - 负样本：|Δθ| > 2ε
    - 中间区域不生成，避免边界模糊
    """
    # 基础序列：单位圆上的随机相位
    theta_X = torch.rand(batch_size, seq_len, device=device) * 2 * np.pi
    X_complex = torch.complex(torch.cos(theta_X), torch.sin(theta_X))

    # 标签
    labels = torch.randint(0, 2, (batch_size,), device=device).float()

    # 为每个样本生成一个相位偏移
    # 正样本：偏移 < ε
    # 负样本：偏移 ∈ (2ε, π]
    delta_positive = (torch.rand(batch_size, device=device) * 2 - 1) * epsilon
    delta_negative = (
        2 * epsilon
        + torch.rand(batch_size, device=device) * (np.pi - 2 * epsilon)
    )
    delta = torch.where(labels.bool(), delta_positive, delta_negative)

    # 应用到整个序列（每个样本一个统一的相位偏移）
    Y_complex = X_complex * torch.exp(1j * delta).unsqueeze(-1)

    # 转换为实部虚部
    X_real = torch.stack([X_complex.real, X_complex.imag], dim=-1)
    Y_real = torch.stack([Y_complex.real, Y_complex.imag], dim=-1)

    return X_real, Y_real, labels, delta


# ============================================================
# 实数模型
# ============================================================
class RealHighPrecisionClassifier(nn.Module):
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

        # 关键：分类器需要精细的决策边界
        self.classifier = nn.Sequential(
            nn.LayerNorm(d_model * 2),
            nn.Linear(d_model * 2, d_model),
            nn.GELU(),
            nn.Linear(d_model, d_model),
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
class ComplexHighPrecisionClassifier(nn.Module):
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
            nn.Linear(d_model, d_model),
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
def train_model(model, epsilon, n_steps=5000, batch_size=64, lr=1e-3, device="cuda"):
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=n_steps)
    model.train()

    losses = []
    accs = []

    for step in range(n_steps):
        X, Y, labels, _ = generate_high_precision_data(
            batch_size, epsilon=epsilon, device=device
        )

        logits = model(X, Y)
        loss = F.binary_cross_entropy_with_logits(logits, labels)

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        losses.append(loss.item())
        acc = ((logits > 0).float() == labels).float().mean().item()
        accs.append(acc)

        if step % 500 == 0:
            print(f"    step {step}: loss = {loss.item():.4f}, acc = {acc:.4f}")

    return losses, accs


@torch.no_grad()
def evaluate(model, epsilon, n_samples=2000, device="cuda"):
    model.eval()
    X, Y, labels, _ = generate_high_precision_data(
        n_samples, epsilon=epsilon, device=device
    )
    logits = model(X, Y)
    preds = (logits > 0).float()
    acc = (preds == labels).float().mean().item()
    return acc


# ============================================================
# 参数量匹配
# ============================================================
def count_params(model):
    return sum(p.numel() for p in model.parameters())


def find_matched_real_model(target_params, epsilon, device):
    """搜索能匹配目标参数量的实数模型配置"""
    for d_model in [8, 16, 32, 64, 128, 256]:
        for n_layers in [1, 2, 3, 4]:
            model = RealHighPrecisionClassifier(
                d_model=d_model, n_heads=min(4, d_model // 8), n_layers=n_layers
            ).to(device)
            n = count_params(model)
            if n >= target_params * 0.8 and n <= target_params * 1.5:
                return d_model, n_layers, n
            del model
    return None


# ============================================================
# 主流程
# ============================================================
def run_experiment_for_epsilon(epsilon, device):
    print(f"\n{'='*60}")
    print(f"ε = {epsilon:.1e}")
    print(f"{'='*60}")

    torch.manual_seed(42)

    # 复数模型（固定架构）
    complex_model = ComplexHighPrecisionClassifier(
        d_model=32, n_units=3, n_layers=2
    ).to(device)
    complex_params = count_params(complex_model)
    print(f"\n复数模型参数量: {complex_params}")

    # 训练复数模型
    print(f"\n训练复数模型 (ε={epsilon:.1e})...")
    complex_losses, complex_accs = train_model(
        complex_model, epsilon, n_steps=5000, device=device
    )
    complex_acc = evaluate(complex_model, epsilon, device=device)
    print(f"  复数模型准确率: {complex_acc:.4f}")

    # 实数模型：参数匹配
    print(f"\n搜索匹配的实数模型 (目标参数: {complex_params})...")
    matched = find_matched_real_model(complex_params, epsilon, device)

    if matched is None:
        # 用最接近的
        real_model = RealHighPrecisionClassifier(
            d_model=32, n_heads=4, n_layers=2
        ).to(device)
    else:
        d_model, n_layers, _ = matched
        real_model = RealHighPrecisionClassifier(
            d_model=d_model, n_heads=min(4, d_model // 8), n_layers=n_layers
        ).to(device)

    real_params = count_params(real_model)
    print(f"实数模型参数量: {real_params}")

    # 训练实数模型
    print(f"\n训练实数模型 (ε={epsilon:.1e})...")
    real_losses, real_accs = train_model(
        real_model, epsilon, n_steps=5000, device=device
    )
    real_acc = evaluate(real_model, epsilon, device=device)
    print(f"  实数模型准确率: {real_acc:.4f}")

    return {
        "epsilon": epsilon,
        "real_params": real_params,
        "complex_params": complex_params,
        "param_ratio": real_params / complex_params,
        "real_acc": real_acc,
        "complex_acc": complex_acc,
        "real_final_loss": real_losses[-1],
        "complex_final_loss": complex_losses[-1],
    }


def main():
    print("=" * 60)
    print("实验6：高精度相位对齐检测")
    print("=" * 60)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"设备: {device}")

    # 扫描多个 epsilon 值
    epsilons = [1e-1, 1e-2, 1e-3]

    all_results = []
    for eps in epsilons:
        result = run_experiment_for_epsilon(eps, device)
        all_results.append(result)

    # 汇总
    print("\n" + "=" * 60)
    print("汇总：量级对比")
    print("=" * 60)
    print(f"{'ε':<10}{'实数参数':<12}{'复数参数':<12}{'参数比':<10}"
          f"{'实数准确率':<12}{'复数准确率':<12}")
    print("-" * 70)

    for r in all_results:
        print(f"{r['epsilon']:<10.1e}{r['real_params']:<12}"
              f"{r['complex_params']:<12}{r['param_ratio']:<10.2f}"
              f"{r['real_acc']:<12.4f}{r['complex_acc']:<12.4f}")

    # 分析
    print("\n" + "=" * 60)
    print("理论预测验证")
    print("=" * 60)
    print("理论：实数参数量 ∝ 1/ε，复数参数量 ∝ 1")
    print()

    for r in all_results:
        theoretical_ratio = 1.0 / r["epsilon"]
        print(f"ε={r['epsilon']:.1e}: "
              f"理论参数比 ≈ {theoretical_ratio:.1f}, "
              f"实测参数比 = {r['param_ratio']:.2f}")


if __name__ == "__main__":
    main()