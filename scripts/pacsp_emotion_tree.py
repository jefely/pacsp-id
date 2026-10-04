"""
PACSP-ID 情绪树集成（论文 §7：瑟-树耦合方程）

实现论文 §7.4 的四项分解：

    C_T^ext = C_path + C_jump + C_depth + C_bias

    C_depth = alpha * d_tree(T)                     (alpha = 0.1 Se/层)
    C_bias  = beta  * B_tree(T)                     (beta  = 0.05 Se/bit)

其中 d_tree 为情绪树层级深度，B_tree 为身份群体误标记熵。

依据论文 §7.1（ICML 2026, Okawa et al.）的四项发现：
  1. 层级化组织  2. 规模效应  3. 性能预测  4. 系统性偏见

设计说明
--------
本模块不依赖任何外部情感分类器。compute_emotion_distribution() 用嵌入的
局部邻域密度给出一个确定性的"情绪样"分布代理，可直接作用于 31 个文本快照
的嵌入；若上游能提供真实情感概率矩阵，build_emotion_tree() 也一并接受。
所有指标均为确定性计算，同一输入必得同一输出，满足 L5 可复现要求。
"""

from __future__ import annotations

import numpy as np

# 论文 §7.4 初始标定
ALPHA_DEPTH = 0.1    # Se / 层
BETA_BIAS = 0.05     # Se / bit

# 建树默认阈值（论文附录 E 参考实现使用 0.1）
EDGE_THRESHOLD = 0.1


# ------------------------------------------------------------------
# 1. 情绪分布代理
# ------------------------------------------------------------------
def compute_emotion_distribution(embeddings: np.ndarray, k: int = 5,
                                 n_channels: int = 8,
                                 temperature: float = 1.0) -> np.ndarray:
    """由嵌入的局部密度给出确定性"情绪样"分布。

    返回形状 (T, n_channels)，每行归一化和为 1。

    构造方式：
      1. 对每个快照 t 取 k 个最近邻的平均距离作为"激活强度" act(t)；
      2. 为每个通道 c 设一个确定性原型 p_c = c/(n_channels-1)；
      3. 用 softmax(-|act(t) - p_c| / temperature) 做**软分配**。

    软分配是必要的：硬分配（one-hot）会让通道间共现恒为零，条件概率
    永远低于建树阈值，情绪树深度恒为 0，从而失去区分能力。
    """
    E = np.asarray(embeddings, dtype=float)
    T = len(E)
    if T == 0:
        return np.zeros((0, n_channels))

    # 成对距离
    diff = E[:, None, :] - E[None, :, :]
    dist = np.linalg.norm(diff, axis=2)

    kk = max(1, min(k, T - 1)) if T > 1 else 1
    density = np.zeros(T)
    for i in range(T):
        d = np.sort(dist[i])
        nbr = d[1:kk + 1] if T > 1 else d[:1]
        density[i] = float(np.mean(nbr)) if len(nbr) else 0.0

    # 归一化到 [0, 1] 作为激活强度
    lo, hi = density.min(), density.max()
    act = (density - lo) / (hi - lo + 1e-12)

    # 通道原型
    protos = np.linspace(0.0, 1.0, n_channels)

    # softmax 软分配
    logits = -np.abs(act[:, None] - protos[None, :]) / max(temperature, 1e-6)
    logits -= logits.max(axis=1, keepdims=True)
    P = np.exp(logits)
    P /= P.sum(axis=1, keepdims=True)
    return P


# ------------------------------------------------------------------
# 2. 建树
# ------------------------------------------------------------------
class EmotionTree:
    """情绪树（论文 §7.2 / §7.4）。

    属性
    ----
    depth        : 层级深度 d_tree
    edges        : 有向边列表 [(parent_idx, child_idx), ...]
    path_length  : 边的数量
    parents      : 子节点 -> 父节点 映射
    roots        : 无父节点的节点
    bias_entropy : 身份群体误标记熵 B_tree（bit），未提供群体标签时为 0
    """

    def __init__(self, depth, edges, parents, roots, bias_entropy=0.0):
        self.depth = int(depth)
        self.edges = list(edges)
        self.path_length = len(self.edges)
        self.parents = dict(parents)
        self.roots = list(roots)
        self.bias_entropy = float(bias_entropy)

    def to_dict(self):
        return {
            "depth": self.depth,
            "path_length": self.path_length,
            "n_edges": len(self.edges),
            "n_roots": len(self.roots),
            "bias_entropy": round(self.bias_entropy, 6),
        }

    def __repr__(self):
        return (f"EmotionTree(depth={self.depth}, edges={self.path_length}, "
                f"roots={len(self.roots)}, bias_entropy={self.bias_entropy:.4f})")


def build_emotion_tree(prob_matrix, emotion_words=None,
                       threshold: float = EDGE_THRESHOLD,
                       group_labels=None) -> EmotionTree:
    """由概率矩阵构建情绪树（论文附录 E 参考实现的一致算法）。

    父节点选择：对每个节点 j，在所有 i 中选满足
        P(i|j) > threshold 且 P(i|j) > P(j|i)
    且 P(i|j) - P(j|i) 最大者作为父节点。条件概率由列归一化的
    共现矩阵 C = P^T P 给出。

    group_labels 若给出（长度 T），则额外计算身份群体误标记熵 B_tree。
    """
    P = np.asarray(prob_matrix, dtype=float)
    if P.ndim != 2:
        raise ValueError("prob_matrix 必须是二维 (T, n_channels)")

    n = P.shape[1]
    if emotion_words is None:
        emotion_words = [f"emo_{i}" for i in range(n)]

    C = P.T @ P
    col_sum = C.sum(axis=0, keepdims=True) + 1e-12
    P_cond = C / col_sum

    parents = {}
    edges = []
    for j in range(n):
        best_parent, best_score = None, -1.0
        for i in range(n):
            if i == j:
                continue
            p_ij = P_cond[i, j]
            p_ji = P_cond[j, i]
            if p_ij > threshold and p_ij > p_ji:
                score = p_ij - p_ji
                if score > best_score:
                    best_score, best_parent = score, i
        if best_parent is not None:
            parents[j] = best_parent
            edges.append((best_parent, j))

    # 深度：沿父链上溯，带环路保护
    depth = 0
    for j in range(n):
        d, cur, seen = 0, j, set()
        while cur in parents and cur not in seen:
            seen.add(cur)
            cur = parents[cur]
            d += 1
        depth = max(depth, d)

    roots = [j for j in range(n) if j not in parents]

    bias = 0.0
    if group_labels is not None:
        bias = compute_bias_entropy(P, group_labels)

    return EmotionTree(depth=depth, edges=edges, parents=parents,
                       roots=roots, bias_entropy=bias)


# ------------------------------------------------------------------
# 3. 偏见熵
# ------------------------------------------------------------------
def compute_bias_entropy(prob_matrix, group_labels) -> float:
    """身份群体误标记熵 B_tree（论文 §7.3 / §7.4，单位 bit）。

    对每个身份群体 g，取其成员在各情绪通道上的平均分布 q_g，与该群体
    应得的均匀分布 u 做 KL 散度；再对群体做熵加权平均。

    B_tree 越大，说明该群体的情绪被越系统性地压缩到少数通道上
    —— 即论文所说的"意义技术层对匿名基底的不当标记"。
    """
    P = np.asarray(prob_matrix, dtype=float)
    g = np.asarray(group_labels)
    if P.ndim != 2 or len(P) != len(g):
        raise ValueError("group_labels 长度必须与 prob_matrix 行数一致")

    n_ch = P.shape[1]
    u = np.ones(n_ch) / n_ch

    per_group = []
    for gid in sorted(set(g.tolist())):
        mask = (g == gid)
        if not mask.any():
            continue
        q = P[mask].mean(axis=0)
        q = q / (q.sum() + 1e-12)
        # KL(q || u)，单位 nat -> bit
        kl = float(np.sum(q * np.log((q + 1e-12) / u)))
        per_group.append(kl / np.log(2))

    if not per_group:
        return 0.0
    return float(np.mean(per_group))


# ------------------------------------------------------------------
# 4. 瑟-树耦合
# ------------------------------------------------------------------
def compute_ct_extended(deltas, mus, changepoints, tree: EmotionTree,
                        alpha: float = ALPHA_DEPTH,
                        beta: float = BETA_BIAS) -> dict:
    """论文 §7.4：C_T^ext = C_path + C_jump + C_depth + C_bias

    C_path 与 C_jump 复用主流水线的计算结果；jump 的具体认定沿用
    pacsp_build 的 PELT 变点结果，幅度取对应位置的 delta 值。
    为保持与已归档记录一致，这里对连续/跳跃采用与主流水线相同的
    合成方式：C_path + C_jump 即原 C_T，故 C_path 取 C_T 减去跳跃贡献。
    """
    deltas = np.asarray(deltas, dtype=float)
    mus = np.asarray(mus, dtype=float)
    n = min(len(deltas), len(mus))

    c_total_base = float(np.sum(mus[:n] * deltas[:n]))

    # 跳跃贡献：变点处（1-based 记录，转为 0-based 索引）
    cps = [int(c) - 1 for c in (changepoints.get("delta_k") or [])]
    cps = [c for c in cps if 0 <= c < n]
    jump_mags = [float(deltas[c]) for c in cps]
    c_jump = float(sum(mus[c] * deltas[c] for c in cps))

    c_path = c_total_base - c_jump
    c_depth = alpha * tree.depth
    c_bias = beta * tree.bias_entropy

    c_ext = c_path + c_jump + c_depth + c_bias

    return {
        "C_path": round(c_path, 6),
        "C_jump": round(c_jump, 6),
        "C_depth": round(c_depth, 6),
        "C_bias": round(c_bias, 6),
        "C_T_base": round(c_total_base, 6),
        "C_T_ext": round(c_ext, 6),
        "alpha": alpha,
        "beta": beta,
        "tree": tree.to_dict(),
        "changepoints_used": [c + 1 for c in cps],
        "jump_magnitudes": [round(m, 6) for m in jump_mags],
    }


__all__ = [
    "ALPHA_DEPTH", "BETA_BIAS", "EDGE_THRESHOLD",
    "EmotionTree", "build_emotion_tree", "compute_emotion_distribution",
    "compute_bias_entropy", "compute_ct_extended",
]
