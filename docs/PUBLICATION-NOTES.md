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

---

## 6. 正文图交叉引用（纯追加）

在 scripts/pacsp_refs.py 中登记 5 处交叉引用，**在装配阶段追加**，
不改动任何原句，也不触碰原始存档：

| 位置 | 追加的引用 |
|---|---|
| §10.2 结尾 | 见图 F.1、F.5、F.9（人机交互三域主图） |
| §10.3 结尾 | 见图 F.4、F.8、F.12（瑟-树耦合分解） |
| §10.4 表格后 | 见图 F.3、F.7、F.11（五元分解与判定系数） |
| §10.5 结尾 | 附录F 全图指引（F.1–F.12 / F.13–F.24 / F.25–F.26） |
| §10.6 结尾 | 指向 docs/CONSISTENCY-REPORT.md |

**图号已程序化核对**（erify_fig_numbers.py）：诗歌 F.1–F.4、歌词 F.5–F.8、
技术文档 F.9–F.12、自主生成 F.13–F.24、跨域 F.25–F.26，与附录实际生成顺序一致，
并与渲染后的页面吻合（第 24 页显示图 F.5 为歌词主图）。

〔整理者按〕这 5 处是**本次整理新增的文字**，不是原文。原文一字未改；
若需纯原文版本，直接取 docs/PACSP-ID-7.0.0-COMPLETE.md。

---

## 7. 发布过程中踩到的一个坑（供复用者参考）

GitHub Release 的附件上传端点返回的是 **uploads.github.com**，
而非 API 所在的 pi.github.com。把两者拼接会得到不存在的主机，
上传静默失败（urlopen error [Errno 2]）——**而删除旧附件的请求已经成功**，
于是 Release 一度处于**无附件状态**。必须使用 upload_url 的绝对值。
chrome-debug/update_release_assets.py 已修正并注释。

---

## 8. 可复现性验证（2026-10-04 实测）

在**仓库之外的全新克隆**中执行完整重建，以验证预印本的可复现性主张。

### 验证方法

`powershell
git -c http.sslBackend=openssl -c http.proxy=http://127.0.0.1:7897 `
    clone --depth 1 https://github.com/jefely/pacsp-id.git D:\tmp\clone
cd D:\tmp\clone
python scripts\pacsp_formula.py     # 重建 90 张公式图
python scripts\pacsp_docx.py        # 重建 DOCX
`

### 结果

| 检查项 | 结果 |
|---|---|
| 六层校验（8 份记录） | **8/8 VERIFIED** |
| 公式图逐字节比对 | **90/90 完全相同** |
| 重建 DOCX 正文文本 | **与已发布版本完全一致**（19,642 字符） |
| 重建 DOCX 嵌入媒体 | **50/50 条目字节全同** |
| 输出写向克隆而非原树 | **是**（隔离性已验证） |

DOCX 的**文件级** SHA256 与已发布版本不同，原因是 DOCX 为 ZIP 容器、
其条目携带生成时间戳。**内容级比对为完全一致**，故视为可复现。

### 本次验证发现并修复的一个真实缺陷

首次在别处克隆后重建时，输出被写到了 D:\myproject\PACSP-ID\，
**而不是克隆目录**——因为 pacsp_docx.py、pacsp_formula.py、pacsp_parse.py
中硬编码了绝对路径。这使「可复现」主张在他人机器上不成立。

已全部改为相对脚本位置解析：

`python
ROOT = Path(__file__).resolve().parent.parent   # 无论克隆到何处
`

pacsp_keci_adapter.py 另改用环境变量 PACSP_KECI_ROOT 作为可覆盖前缀。

〔整理者按〕这个缺陷**只有真正在别处克隆并重建才能发现**——
在主仓库内运行一切正常。这正是"可复现"必须实测而非声称的理由。

---

## 9. 发布脚本自包含化（2026-10-04）

在验证可复现性时发现第二类缺陷：**发布流程依赖仓库外的文件**。

| 问题 | 修正 |
|---|---|
| pacsp_release.ps1 引用 ..\chrome-debug\make_release.py（仓库外） | 移入 scripts/pacsp_github_release.py |
| 附件更新与校验脚本同样在仓库外 | 移入 scripts/pacsp_github_assets.py、scripts/pacsp_check_release.py |
| 这些脚本内硬编码 D:\myproject\PACSP-ID | 改为 Path(__file__).resolve().parent.parent |
| Zenodo 步骤未纳入发布流程 | 新增 **stage 8**，由 scripts/pacsp_zenodo.py 执行 |
| stage 8 错误地与 -NoRelease 耦合 | 解耦为独立开关 -SkipZenodo |

**克隆者现在无需仓库外的任何文件即可完整发版。**

### 第三个缺陷：校验脚本对 DOCX 过于严格

pacsp_check_release.py 原先只做字节比对，于是**健康的发布被报告为损坏**：

`
PACSP-ID-7.0.0-preprint.docx: HASH MISMATCH
RESULT: MISMATCH FOUND
`

原因是 **DOCX 是 ZIP 容器、其条目携带生成时间戳**，同内容重建必然哈希不同。
已改为分层判定：

| 文件类型 | 判定方式 |
|---|---|
| **DOCX** | 先比字节；不同则比**正文文本 + 全部嵌入媒体条目** |
| **PDF** | 比字节（并报告大小以供对照） |
| 其他 | 比字节 |

修正后结果：

`
PACSP-ID-7.0.0-preprint.docx: IDENTICAL (content: 19,642 chars, 50 media entries; ZIP timestamps differ)
PACSP-ID-7.0.0-preprint.pdf : IDENTICAL (bytes)
RESULT: all assets match
`

〔整理者按〕此处三次缺陷有共同模式——**"看起来通过"与"真的正确"之间的差距**：
主仓库内重建正常（实为路径写死）、字节比对失败（实为容器格式）、
stage 8 未触发（实为我传错开关）。三次都靠**换一个角度实测**才发现。