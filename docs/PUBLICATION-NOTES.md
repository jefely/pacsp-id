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

## 2. 图：26 张图已补入附录F

论文原文**图片引用数为 0**，而 `cache/figures/` 下有 26 张由流水线生成的 PNG。
预印本新增**附录F「图表」**收载全部 26 张（不改动原有章节编号），逐图配中文图题。

| 分组 | 张数 | 内容 |
|---|---|---|
| `poem_epoch1` | 4 | 人机交互诗歌：主图 + L6 情绪树/五元分解/瑟-树耦合 |
| `lyrics_epoch1` | 4 | 人机交互歌词：同上 |
| `techdoc_epoch1` | 4 | 人机交互技术文档：同上 |
| `machine_poem` | 4 | 自主生成诗歌：同上 |
| `machine_lyrics` | 4 | 自主生成歌词：同上 |
| `machine_techdoc` | 4 | 自主生成技术文档：同上 |
| 跨域 | 2 | `_L6_comparison`、`_L6_human_vs_machine` |

**图 F.1–F.24** 按六个域各四类排列；**图 F.25–F.26** 为跨域对比。

〔状态〕**已完成**。

---

## 3. 排版转换中修正的三处缺陷

全部由**渲染页面并目视检查**发现，而非结构校验发现：

| # | 缺陷 | 根因 | 若不检查的后果 |
|---|---|---|---|
| 1 | `**定义 1.2.1**` 与 `` `S_int` `` 原样显示 | `pacsp_inline.TOKEN_RE` 在斜体分支前**漏了 `\|`**，导致粗体与斜体正则被**拼接**而非互为备选，全都匹配不上 | 直接带病发布 |
| 2 | DOXC 生成崩溃：`no NULL bytes or control characters` | 公式哨兵用了 `\x00`，lxml 拒绝 | 构建失败 |
| 3 | 图题/标题含 Markdown 标记 | 未过 `strip_markup` | 图题显示 `**` |

结构校验（`check_office.py`）只报 **verdict: pass**，三处缺陷它都发现不了——
**结构正确不等于排版正确**。

---

## 4. 构建管道与约束

```bash
cd PACSP-ID
python scripts/pacsp_formula.py     # 90 张公式图 + 6 张图例 + 清单
python scripts/pacsp_parse.py       # 解析校验（只读）
python scripts/pacsp_docx.py        # 生成 DOCX（捆绑 Python 3.12）
node <libreoffice-kit cli> convert --input build/...docx --output dist/...pdf
```

**已知约束**：DOCX→PDF 需 LibreOffice，它要**创建子进程**，而沙箱以
`spawn EPERM` 拒绝。因此这一步需要**一次性放宽权限**；其余全部步骤均在沙箱内可完成。

| 步骤 | 是否可在沙箱内完成 |
|---|---|
| 公式渲染 | ✅ |
| Markdown 解析 | ✅ |
| DOCX 生成 | ✅ |
| 结构校验 | ✅ |
| **DOCX→PDF** | ❌ 需放宽（LibreOffice 子进程） |
| 页面渲染复核 | ❌ 同上 |

产物：`dist/PACSP-ID-7.0.0-preprint.docx`（2.28 MB）、
`dist/PACSP-ID-7.0.0-preprint.pdf`（1.45 MB，34 页）。

---

## 5. 未做的事（明确登记）

1. **未修改原始存档** `PACSP-ID-7.0.0-COMPLETE.md`，逐字节未动。
2. **未改动论文正文文字**——仅公式记法替换、行内标记转格式、插图。
3. **未在正文加入图交叉引用**——图集中在附录F，正文未插入「见图 F.x」指向。
4. **未解决证据缺口**：纯人类对照组缺失、Keci 模型无出处、素材 07 数值自相矛盾、
   α_i 两版数值冲突、瞬在 AI 路径验证失败。预印本保留这些为显式「局限」，未因排版淡化。
5. **未确定目标平台**：作者为个人研究者，暂不投期刊；按公开预印本（GitHub Release
   ＋ Zenodo DOI）推进。
6. **尚未建立版本化发布**：tag / GitHub Release / Zenodo DOI 准备尚未完成。
