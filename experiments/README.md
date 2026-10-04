# experiments/

本目录含两类内容，性质完全不同，请先读本节再读代码。

## `transient/` —— 已终止的探索（**不要期待它能工作**）

`transient` 是"瞬在/干涉"分支的实现包，作者已判定：

> 瞬在的探索是失败的，语言模型架构完全不支持瞬在，跑不通工程验证。

包内 `transient_unit.py` / `transient_matrix.py` / `complex_layer.py` / `dynamics.py`
构成"瞬在最小单元 → 3×3 瞬在矩阵 → 可插入 Transformer 的复数瓶颈层 → 动力学分析"的链条。
**它能构造、能被 import，但验证不通过。**

失败证据、架构层面的三个障碍、以及从失败中提炼的唯一正面线索，全部记录在
[`../docs/NEGATIVE-RESULT-TRANSIENT.md`](../docs/NEGATIVE-RESULT-TRANSIENT.md)。

## `transient_interference/` —— 六个实验

| 实验 | 检验内容 | 结果 |
|---|---|---|
| `exp1_phase_coupling.py` | 相位耦合决定干涉强度 | ✗ 三种相位条件结果完全相同 |
| `exp2_amplitude_control.py` | 区分相位贡献与振幅贡献 | 未跑完 |
| `exp3_su3_structure.py` | 3×3 矩阵的 SU(3) 结构 | ✗ 分解误差 1.87e-02 |
| `exp4_integration.py` | 相位对齐检测：实数 vs 复数 | 未跑完 |
| `exp5_param_matched.py` | 参数匹配下的相位对齐 | 未跑完 |
| `exp6_high_precision.py` | 验证 O(ε⁻¹) vs O(1) | ✗ 与预测差三个数量级 |

运行方式（模块方式，从仓库根目录）：

```bash
python -m experiments.transient_interference.exp1_phase_coupling
```

## 为什么保留这个目录

**否定结果与正面结果同等重要。** 保留它的目的是防止后续研究者（包括作者本人）
重复投入同一路径，并提供具体的故障表现作为参照。相关测试见 `../tests/test_transient.py`。

## 如何进入包搜索路径

`pip install -e .` 之后可直接 `import transient`。
未安装时，在仓库根目录运行会通过 `conftest.py`（测试）或
`PYTHONPATH=experiments python -m ...`（脚本）解析。
