# 投稿版转换说明

本文件记录从 `PACSP-ID-7.0.0-COMPLETE.md`（原始存档）到投稿版所做的**全部变换**。
原则：**原始存档永不修改**；投稿版另存，且每一处改动都在此登记。

生成脚本：`scripts/pacsp_formula.py`（公式）、`scripts/pacsp_publish.py`（文档装配）。

---

## 1. 公式：中文下标改为 ASCII 记法

### 为什么必须改

公式中的中文下标（如 `\mu_{\text{本能}}`）在目标排版工具下无法正确输出：

| 方案 | 结果 |
|---|---|
| LaTeX 编译 | 环境无 LaTeX（`pandoc`/`xelatex`/`tectonic` 均不存在） |
| matplotlib mathtext | **能解析但画不出来**——`\mathrm{本能}` 渲染为空心方框 |
| HPacker 拼接 mathtext + 中文字体 | **失败**：在任意位置切分 LaTeX（如 `\left[` 与 `\mu_` 之间）产生非法片段，静默退化为**输出原始源码文本** |

因此改用 ASCII 记法，并在**每个受影响公式下方自动生成中文对照图例**。

### 1:1 映射表

| 中文 | ASCII 记法 | 出现次数 |
|---|---|---|
| 本能 | `instinct` | 3 |
| 技术 | `technique` | 3 |
| 路径 | `path` | 3 |
| 跳跃 | `jump` | 3 |
| 深度 | `depth` | 4 |
| 偏见 | `bias` | 5 |
| 无外部奖励 | `noReward` | 1 |

### 举例

原文：

```
\Pi(T) = \int_0^T \left[ \mu_{\text{本能}}(t) - \mu_{\text{技术}}(t) \right]^+ dt
```

投稿版：

```
\Pi(T) = \int_0^T \left[ \mu_{\mathrm{instinct}}(t) - \mu_{\mathrm{technique}}(t) \right]^+ dt
```

**图例**：`本能 = instinct　技术 = technique`

### 其他机械修正（不改变数学含义）

| 原写法 | 改为 | 原因 |
|---|---|---|
| `\le` | `\leq` | mathtext 不认 `\le` |
| `\big(` `\big|` `\Big|` | 删除 | mathtext 不支持尺寸修饰符 |
| `\;` | `\,` | mathtext 不支持 `\;` |
| `\text{X}` | `\mathrm{X}` | mathtext 能解析 `\text{}` 但**无法渲染**（报 `NoneType has no bbox`） |

### 渲染结果

| 项 | 数量 |
|---|---|
| 显示公式（`\[...\]`） | 17 |
| 行内公式（`\(...\)`） | 73 |
| **合计** | **90，全部渲染成功** |
| 生成的公式图 | 90 |
| 生成的中文图例图 | 6 |
| 产物目录 | `cache/formulas/` |
| 清单 | `cache/formulas/formula_manifest.json` |

清单中每个公式都记录了 `source`（原文）、`rendered`（实际渲染串）、`notation`（用到的记法）与 `legend`（图例文件），可逐条核对。

---

## 2. 图：26 张已存在的图尚未被论文引用

论文原文**图片引用数为 0**，而 `cache/figures/` 下有 26 张由流水线生成的 PNG：

| 分组 | 张数 | 内容 |
|---|---|---|
| `poem_epoch1` | 4 | 人机交互诗歌：主图 + L6 情绪树/五元分解/瑟-树耦合 |
| `lyrics_epoch1` | 4 | 人机交互歌词：同上 |
| `techdoc_epoch1` | 4 | 人机交互技术文档：同上 |
| `machine_poem` | 4 | 自主生成诗歌：同上 |
| `machine_lyrics` | 4 | 自主生成歌词：同上 |
| `machine_techdoc` | 4 | 自主生成技术文档：同上 |
| 跨域 | 2 | `_L6_comparison`、`_L6_human_vs_machine` |

**计划**：新增「图表」附录（不改动原章节编号），按域分组插入并配中英图题；
在 §10 各小节加入交叉引用（如「见图 A.1–A.4」）。

〔状态〕**待办**——本轮只完成公式管线，插图尚未实施。

---

## 3. 未做的事（明确登记）

1. **未修改原始存档** `PACSP-ID-7.0.0-COMPLETE.md`，一字未动。
2. **未改动论文正文文字**——投稿版仅做上述公式记法替换与（计划的）插图。
3. **未解决证据缺口**：纯人类对照组缺失、Keci 模型无出处、素材 07 数值自相矛盾、
   α_i 两版数值冲突、瞬在 AI 路径验证失败。投稿版应保留这些为显式的「局限」章节，
   不得因排版需要而淡化。
4. **未确定目标平台**：作者为个人研究者，暂不投期刊；按公开预印本（GitHub Release
   ＋ Zenodo DOI）推进。

---

## 4. 复现

```bash
cd PACSP-ID
python scripts/pacsp_formula.py        # 生成 90 张公式图 + 6 张图例 + 清单
python scripts/pacsp_publish.py        # 装配投稿版 Markdown → DOCX → PDF
```

环境：matplotlib + numpy（系统 Python 3.10 已具备）；
文档装配另需 `python-docx`（DSH 捆绑 Python 3.12 已具备）。
