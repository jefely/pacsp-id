# PACSP-ID 7.0.0 — 公开预印本

**从意义权到认知沉积：PACSP-ID 框架的理论建构、创新动力学标识与验证工程**

首个可引用版本。论文以 Markdown 存档形式存在于仓库，并首次以排版后的
DOCX / PDF 形式发布。

## 本次发布的内容

| 文件 | 说明 |
|---|---|
| `PACSP-ID-7.0.0-preprint.pdf` | 34 页预印本（中文） |
| `PACSP-ID-7.0.0-preprint.docx` | 可编辑源文档 |

论文正文：`docs/PACSP-ID-7.0.0-COMPLETE.md`（**逐字节未改动**）。

## 本版做了什么

**公式渲染（90/90）** — 17 个显示公式与 73 个行内公式全部渲染为矢量图。
原始公式使用中文下标（如 `μ_本能`），预印本改用 ASCII 记法并在每个公式下方
自动生成中文对照：

| 原中文 | 预印本记法 | 原中文 | 预印本记法 |
|---|---|---|---|
| 本能 | `instinct` | 深度 | `depth` |
| 技术 | `technique` | 偏见 | `bias` |
| 路径 | `path` | 无外部奖励 | `noReward` |
| 跳跃 | `jump` | | |

**图表（26 张）** — 论文原稿图片引用数为 0。本版新增**附录F**收载全部 26 张
流水线生成的图（六个域 × 四类：主图、情绪树、创新五元分解、瑟-树耦合，
外加两张跨域对比），逐图配中文图题。

## 核心结果

| 域 | 篇数 | C_T (Se) | μ_k 均值 | 情绪树深度 |
|---|---|---|---|---|
| 诗歌 | 31 | 1.8950 | 0.1272 | 2 |
| 歌词 | 31 | 2.1261 | 0.1677 | 1 |
| 技术文档 | 31 | 7.3982 | 0.3352 | 1 |

C_T 精确可复现（偏差 < 1e-9）；六层防护在 8 份记录上全部通过；
四类篡改攻击全部被捕获。

## 必须报告的三项负面结果

1. **`S_int` 对嵌入空间不稳健** — 同一语料仅换嵌入空间即符号翻转
   （−0.15 → +0.41），§8.4 需修订。
2. **九个 IDL 指标无一致方向** — 在「经人筛选」与「自主生成」两条轴之间，
   域间差异大于轴间差异，§8.5 判定表的判别力尚未确立。
3. **缺少纯人类对照组** — 三个语料全部为人机交互产物，因此 §8.5 设想的
   「人脑 vs LLM」判定在本版**无法完成**。

此外实测**否定**了「AI 生成的情绪强度低于人类」这一直觉假设：
诗歌与歌词上自主生成组的 C_T 与 μ_k 均更高。

## 复现

```bash
git clone https://github.com/jefely/pacsp-id
cd pacsp-id
pip install -e ".[dev]"
pytest                                      # 冒烟测试
python scripts/pacsp_formula.py             # 90 张公式图
python scripts/pacsp_docx.py                # 重建 DOCX
python scripts/pacsp_verify.py <record> <data-dir>   # 六层校验
```

完整构建说明见 `docs/PUBLICATION-NOTES.md`。

## 相关记录

- `docs/NEGATIVE-RESULT-TRANSIENT.md` — 已终止的「瞬在」AI 实现路径，
  含失败的数学根源证明
- `docs/CONSISTENCY-REPORT.md` — 嵌入空间敏感性独立复核
- `docs/AXIS-COMPARISON-REPORT.md` — 两条对照轴的比较
- `docs/PUBLICATION-NOTES.md` — 从存档到预印本的全部变换登记

## 引用

```
jefely. (2026). 从意义权到认知沉积：PACSP-ID 框架的理论建构、
创新动力学标识与验证工程 (7.0.0). Zenodo.
https://doi.org/10.5281/zenodo.22801604
```

**ORCID**：0009-0005-9487-8555
