"""
PACSP-ID 创新动力学标识层 IDL（论文 §8）

五元分解（论文 §8.2）：

    C_T^innov = C_DMN + C_ECN + C_SN + C_mem + C_sel

四个核心判定系数（论文 §8.4）：

    chi_innov = Corr(C_DMN(t), C_ECN(t+tau), C_SN(t+tau/2))   创新耦合系数
    DRI       = dC_DMN(before Aha) / dC_ECN(after Aha)        解耦—重组指数
    H_switch  = -sum p(s_i) log p(s_i)                        自主切换熵
    S_int     = Corr(dC_T, dA_goal) | 无外部奖励               内生选择压力

判定规则（论文 §8.5）：人脑式解耦—重组 vs 当前 LLM 组合式重组。

设计说明
--------
本模块刻意与嵌入模型解耦：既接受嵌入矩阵（完整模式下自行计算目标对齐度），
也接受已归档记录中的 deltas/mus（离线模式下用变点位置重建目标对齐轨迹）。
后者保证对 PCM 归档记录的确定性重算，无需下载模型即可复现五元分解。
"""

from __future__ import annotations

import numpy as np

# 探索态阈值：d_sem 超过该值视为"远距离共激活"（论文 §8.2 的 d_sem^+）
D_SEM_THRESHOLD = 0.5

# 其余固定权重（与论文附录 E 参考实现一致）
C_SN_SWITCH_WEIGHT = 0.5
C_MEM_BASE_WEIGHT = 0.1
C_SEL_WEIGHT = 0.5

# Aha 判定：跳跃幅度超过均值 + AHA_SIGMA * 标准差
AHA_SIGMA = 1.0


# ------------------------------------------------------------------
# 探索/利用标签
# ------------------------------------------------------------------
def infer_explore_labels(deltas, threshold: float = D_SEM_THRESHOLD):
    """由路径增量推断探索态标签（确定性）。

    论文 §8.2 将"远距离概念共激活"记为探索态；在没有语义距离标注时，
    用超出阈值的路径增量作为远距离的代理。返回长度与 deltas 一致的布尔列表。
    """
    d = np.asarray(deltas, dtype=float)
    return [bool(x > threshold) for x in d]


def infer_explore_labels_from_changepoints(deltas, changepoints,
                                           threshold: float = D_SEM_THRESHOLD):
    """变点感知的探索态标签。

    变点及其前半段视为探索（DMN / 毛刺产生），变点后半段视为利用
    （ECN / 协调精加工）。这对应论文 §8.3 的"毛刺 -> 协调"时序。
    """
    d = np.asarray(deltas, dtype=float)
    n = len(d)
    labels = [bool(x > threshold) for x in d]
    cps = sorted({int(c) - 1 for c in (changepoints or [])})
    for c in cps:
        if 0 <= c < n:
            # 变点处及其邻近的 2 步标为探索
            for k in range(max(0, c - 1), min(n, c + 2)):
                labels[k] = True
    return labels


# ------------------------------------------------------------------
# 目标对齐轨迹
# ------------------------------------------------------------------
def goal_alignment_from_embeddings(embeddings, target_vec) -> np.ndarray:
    """A_goal(t) = cos(v_t, target)，论文 §8.2 的目标对齐度。"""
    E = np.asarray(embeddings, dtype=float)
    t = np.asarray(target_vec, dtype=float)
    tn = np.linalg.norm(t) + 1e-12
    return np.array([float(np.dot(v, t) / ((np.linalg.norm(v) + 1e-12) * tn)) for v in E])


def goal_alignment_from_record(deltas, changepoints=None):
    """离线模式下重建 A_goal 轨迹。

    思路：目标对齐度为累积量，跳跃（变点）代表目标流形上的重整，
    因此以"累积路径增量、在变点处折返"构造单调逼近目标的轨迹。
    这是确定性的，仅依赖归档记录中的 deltas 与变点。
    """
    d = np.asarray(deltas, dtype=float)
    n = len(d)
    if n == 0:
        return np.array([0.0])

    cps = {int(c) - 1 for c in (changepoints or [])}
    a = np.zeros(n + 1)
    acc = 0.0
    for i in range(n):
        if i in cps:
            acc *= 0.5          # 跳跃：目标重整，对齐度回落
        acc += float(d[i])
        a[i + 1] = acc
    # 归一化到 [0, 1]
    rng = a.max() - a.min()
    if rng > 1e-12:
        a = (a - a.min()) / rng
    return a


# 说明：目标对齐轨迹 A_goal 是 S_int / C_sel / DRI 的语义前提。
# 若调用方无法给出真实目标（目标向量或标注），则不应伪造 A_goal —— 
# 重建的"伪目标"与 ΔC_T 的相关性没有物理意义，会产出误导性结论。
# 因此这些指标一律标记为未定义，仅 C_DMN / C_SN / C_mem / H_switch 仍可用。
TARGET_REQUIRED_METRICS = ("S_int", "C_sel", "DRI")


# ------------------------------------------------------------------
# 五元分解
# ------------------------------------------------------------------
class InnovationMetrics:
    """五元分解与四个判定系数（论文 §8.2 / §8.4）。"""

    def __init__(self, C_DMN, C_ECN, C_SN, C_mem, C_sel,
                 chi_innov, DRI, H_switch, S_int,
                 E_glob, switch_count, aha_indices, labels,
                 A_goal_defined=True):
        self.C_DMN = C_DMN
        self.C_ECN = C_ECN
        self.C_SN = C_SN
        self.C_mem = C_mem
        self.C_sel = C_sel
        self.chi_innov = chi_innov
        self.DRI = DRI
        self.H_switch = H_switch
        self.S_int = S_int
        self.E_glob = E_glob
        self.switch_count = switch_count
        self.aha_indices = aha_indices
        self.labels = labels
        self.A_goal_defined = A_goal_defined

    @property
    def C_T_innov(self):
        return self.C_DMN + self.C_ECN + self.C_SN + self.C_mem + self.C_sel

    def verdict(self) -> str:
        """论文 §8.5 判定规则。

        注意：S_int / DRI / chi_innov 的判读依赖**明确的目标定义** A_goal。
        未提供真实目标对齐轨迹时，S_int 无物理意义，此处返回"未定义"
        而不是给出一个可能误导的结论。
        """
        if self.A_goal_defined is False:
            return "未定义（缺少目标对齐轨迹 A_goal）"
        if self.S_int is None:
            return "未定义（S_int 无法计算）"
        if self.S_int > 0.3 and self.DRI > 1.0 and self.chi_innov > 0.3:
            return "人脑式解耦—重组"
        if self.S_int <= 0.1 and self.DRI <= 0.5 and self.chi_innov <= 0.3:
            return "当前LLM组合式重组"
        if self.C_SN > 0 and self.DRI <= 0.5:
            return "LLM+响应余量（外部连续性增强）"
        return "介于两者之间"

    def to_dict(self):
        def r(x):
            return None if x is None else round(x, 6)
        return {
            "C_DMN": r(self.C_DMN),
            "C_ECN": r(self.C_ECN),
            "C_SN": r(self.C_SN),
            "C_mem": r(self.C_mem),
            "C_sel": r(self.C_sel),
            "C_T_innov": r(self.C_T_innov),
            "chi_innov": r(self.chi_innov),
            "DRI": r(self.DRI),
            "H_switch": r(self.H_switch),
            "S_int": r(self.S_int),
            "E_glob": r(self.E_glob),
            "switch_count": self.switch_count,
            "aha_indices": self.aha_indices,
            "A_goal_defined": self.A_goal_defined,
            "verdict": self.verdict(),
        }

    def __repr__(self):
        dri = "None" if self.DRI is None else f"{self.DRI:.4f}"
        sint = "None" if self.S_int is None else f"{self.S_int:.4f}"
        return (f"InnovationMetrics(C_T_innov={self.C_T_innov:.4f}, "
                f"DRI={dri}, S_int={sint}, "
                f"chi={self.chi_innov:.4f}, verdict={self.verdict()})")


def _safe_corr(a, b) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = min(len(a), len(b))
    if n < 2 or np.std(a[:n]) < 1e-9 or np.std(b[:n]) < 1e-9:
        return 0.0
    c = np.corrcoef(a[:n], b[:n])[0, 1]
    return 0.0 if not np.isfinite(c) else float(c)


def compute_innovation(deltas, mus, A_goal, labels,
                       pair_distances=None) -> InnovationMetrics:
    """五元分解 + 四系数（论文 §8.2 / §8.4）。

    参数
    ----
    deltas        : 路径增量序列，长度 n
    mus           : 认知强度序列，长度 >= n
    A_goal        : 目标对齐轨迹（长度 n+1）。传 None 表示目标未定义，
                    此时 S_int / C_sel / DRI 记为未定义，判定结果为"未定义"。
    labels        : 探索态布尔标签，长度 n
    pair_distances: 可选，嵌入两两距离（用于 E_glob 全局效率）
    """
    d = np.asarray(deltas, dtype=float)
    m = np.asarray(mus, dtype=float)[:len(d)]
    lab = list(labels)[:len(d)]
    n = len(d)

    a_defined = A_goal is not None
    if a_defined:
        a = np.asarray(A_goal, dtype=float)
    else:
        a = None
    dA = (np.diff(a) if (a_defined and len(a) > 1) else np.zeros(max(n, 1)))

    if n == 0:
        return InnovationMetrics(0, 0, 0, 0, 0, 0, 0, 0, None, 0, 0, [], [],
                                 A_goal_defined=a_defined)

    # --- C_DMN：远距离共激活的探索性沉积（论文 §8.2） ---
    C_DMN = float(sum(max(0.0, d[i] - D_SEM_THRESHOLD)
                      for i in range(n) if lab[i]))

    # --- C_ECN：目标对齐增益的利用性沉积 ---
    C_ECN = float(sum(max(0.0, dA[i])
                      for i in range(min(n, len(dA))) if not lab[i]))

    # --- C_SN：模式切换的沉积 ---
    switch_count = sum(1 for i in range(1, n) if lab[i] != lab[i - 1])
    C_SN = switch_count * C_SN_SWITCH_WEIGHT

    # --- C_mem：语义记忆分量，E_glob 为全局效率 ---
    if pair_distances is not None and len(pair_distances):
        E_glob = float(1.0 / (np.mean(pair_distances) + 1e-12))
    else:
        # 离线模式：用路径增量的均值倒数作为可达性代理
        E_glob = float(1.0 / (np.mean(d) + 1e-12))
    C_T_base = float(np.sum(m * d))
    C_mem = E_glob * C_MEM_BASE_WEIGHT * C_T_base / (1.0 + E_glob * C_MEM_BASE_WEIGHT)

    # --- S_int：内生选择压力（无外部奖励） ---
    dC = np.diff(d) if n > 1 else np.array([0.0])
    S_int = _safe_corr(dC, dA) if a_defined else None
    C_sel = (max(0.0, S_int) * C_SEL_WEIGHT) if a_defined else 0.0

    # --- chi_innov：创新耦合系数 ---
    dmn_series = np.cumsum([max(0.0, d[i] - D_SEM_THRESHOLD) if lab[i] else 0.0
                            for i in range(n)])
    ecn_series = np.cumsum([max(0.0, dA[i]) if not lab[i] else 0.0
                            for i in range(min(n, len(dA)))])
    sn_series = np.cumsum([1.0 if (i > 0 and lab[i] != lab[i - 1]) else 0.0
                           for i in range(n)])
    c1 = _safe_corr(dmn_series, ecn_series)
    c2 = _safe_corr(dmn_series, sn_series)
    c3 = _safe_corr(ecn_series, sn_series)
    chi_innov = float(np.mean([c1, c2, c3]))

    # --- DRI 与 Aha 位置 ---
    thr = float(np.mean(d) + AHA_SIGMA * np.std(d))
    aha = [i for i in range(n) if d[i] > thr]
    if not a_defined:
        DRI = None
    elif aha:
        first_aha = aha[0]
        dmn_before = float(sum(max(0.0, d[i] - D_SEM_THRESHOLD)
                               for i in range(first_aha) if lab[i]))
        ecn_after = float(sum(max(0.0, dA[i])
                              for i in range(first_aha, min(n, len(dA)))
                              if not lab[i]))
        DRI = dmn_before / (ecn_after + 1e-6)
    else:
        dmn_before = C_DMN
        ecn_after = C_ECN
        DRI = dmn_before / (ecn_after + 1e-6)

    # --- H_switch：自主切换熵（bit） ---
    p = switch_count / max(1, n - 1)
    H_switch = float(-p * np.log2(p + 1e-12) - (1 - p) * np.log2(1 - p + 1e-12))

    return InnovationMetrics(
        C_DMN=C_DMN, C_ECN=C_ECN, C_SN=C_SN, C_mem=C_mem, C_sel=C_sel,
        chi_innov=chi_innov, DRI=DRI, H_switch=H_switch, S_int=S_int,
        E_glob=E_glob, switch_count=switch_count, aha_indices=aha,
        labels=[bool(x) for x in lab], A_goal_defined=a_defined,
    )


# ------------------------------------------------------------------
# 便捷入口：从归档记录离线计算
# ------------------------------------------------------------------
def compute_innovation_from_record(record, threshold: float = D_SEM_THRESHOLD,
                                   use_changepoints: bool = True,
                                   A_goal=None) -> InnovationMetrics:
    """对已归档 .pacsp 记录做确定性五元分解（无需嵌入模型）。

    使用 record["compute"]["deltas"|"mus"] 与 record["results"]["changepoints"]。

    重要：A_goal（目标对齐轨迹）默认**不提供**。归档记录中并不含真实目标，
    而 S_int / C_sel / DRI 只有在目标明确时才有物理意义，因此默认为未定义。
    C_DMN / C_ECN / C_SN / C_mem / H_switch 不受影响，仍然有效。
    需要这些指标时，请由上游显式传入 A_goal。
    """
    deltas = record.get("compute", {}).get("deltas") or []
    mus = record.get("compute", {}).get("mus") or []
    cps = (record.get("results", {}).get("changepoints") or {}).get("delta_k") or []

    if use_changepoints:
        labels = infer_explore_labels_from_changepoints(deltas, cps, threshold)
    else:
        labels = infer_explore_labels(deltas, threshold)

    return compute_innovation(deltas, mus, A_goal, labels)


__all__ = [
    "D_SEM_THRESHOLD", "AHA_SIGMA",
    "InnovationMetrics",
    "infer_explore_labels", "infer_explore_labels_from_changepoints",
    "goal_alignment_from_embeddings", "goal_alignment_from_record",
    "compute_innovation", "compute_innovation_from_record",
]
