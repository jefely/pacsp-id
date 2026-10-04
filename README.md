[![DOI](https://zenodo.org/badge/1373521342.svg)](https://doi.org/10.5281/zenodo.22801604)

# PACSP-ID

Pan-Agent Cognitive Sediment Protocol — Identity

认知沉积量的严格量化框架。通过信息几何度量认知路径的不可压缩性，以六层密码学防护保证记录的不可篡改。

## 核心公式

C_T = ∫ μ(t) dΛ(t)

其中：
- μ(t) = Tr[I_F(θ_t)]：认知曲率（Fisher信息矩阵的迹）
- Λ(t)：路径全变差测度（含连续漂移与离散相变）
- 单位：瑟（Se）

## 六层防护

| 层 | 机制 | 作用 |
|----|------|------|
| L1 | 分层内容哈希 | 6 个语义块独立 Merkle 化 |
| L2 | Ed25519 签名 | 检测来源伪造 |
| L3 | 三级 Merkle | 样本级 + 计算级 + 结果级 |
| L4 | OpenTimestamps | 比特币区块锚定 |
| L5 | 可复现验证 | 完整 pipeline 重放 |
| L6 | 创新动力学标识存证 | 情绪树 + 五元分解 + 四系数（§4.2 新增） |

## 论文版本

| 版本 | 标题 | 位置 |
|------|------|------|
| **7.0.0-COMPLETE** | 从意义权到认知沉积：PACSP-ID框架的理论建构、创新动力学标识与验证工程 | [`docs/PACSP-ID-7.0.0-COMPLETE.md`](docs/PACSP-ID-7.0.0-COMPLETE.md) |

7.0.0 在 6.0.0-FORMAL 的基础上新增两章：

- **§7 情绪树集成**：接入 ICML 2026「LLM 层级化情绪树」发现（Okawa et al.），提出瑟-树耦合方程
  `C_T^ext = C_路径 + C_跳跃 + C_深度 + C_偏见`（α = 0.1 Se/层，β = 0.05 Se/bit）
- **§8 创新动力学标识层（IDL）**：五元分解
  `C_T^innov = C_DMN + C_ECN + C_SN + C_mem + C_sel`
  与四个判定系数 `χ_innov`、`DRI`、`H_switch`、`S_int`，用于区分
  「人脑解耦—重组式创新」与「LLM 组合式重组」

## 数据集

| 域 | 目录 | 篇数 | 来源 | C_T |
|----|------|------|------|-----|
| 诗歌 | `data/poem` | 31 | 人机交互 | 1.90 Se |
| 歌词 | `data/lyrics` | 31 | 人机交互 | 2.13 Se |
| 技术文档 | `data/techdoc` | 31 | 人机交互 | 7.40 Se |

**语料来源更正**：`data/poem|lyrics|techdoc` 三域**全部是人机交互产物**（有人的引导与筛选），
并非纯人类书写，不能充当「人脑」对照组。`data/machine_*` 为单次独立生成、无人工筛选的 LLM 输出。
可观测的差异轴是**每篇是否经人筛选**。详见
[`docs/CORRECTION-CORPUS-PROVENANCE.md`](docs/CORRECTION-CORPUS-PROVENANCE.md)。
`μ_k` 均值随认知负荷严格递增（0.1272 → 0.1677 → 0.3352），与论文 §5.3 预测一致。
素材附带的第三方基线（`uacp_results.npz` / `uacp_result.png`）归档于 `materials/<域>/`。

## 目录结构

    data/          原始样本（权威）
    records/       权威 .pacsp 文件（1 个数据集 1 个文件）
    docs/          论文与核查报告
    materials/     素材附带的第三方基线
    cache/         派生缓存（可删除重建）
    scripts/       全部 Python 脚本

## 快速开始

    pip install -r requirements.txt

    # 1. 构建 .pacsp（默认五层，版本 4.0.0-COMPACT）
    python scripts/pacsp_build.py

    # 1b. 构建含 L6 创新动力学层的记录（版本 7.0.0-COMPLETE）
    python scripts/pacsp_build.py --innov --datasets lyrics techdoc poem

    # 1c. 带目标标定的 L6（A_goal = 本域嵌入质心）
    python scripts/pacsp_build.py --innov --target centroid --datasets lyrics techdoc poem

    # 2. 生成缓存
    python scripts/pacsp_cache.py

    # 3. 重建图片
    python scripts/pacsp_figure.py

    # 4. 六层验证
    python scripts/pacsp_verify.py records/lyrics_*.pacsp data/lyrics

    # 5. 篡改测试
    python scripts/pacsp_tamper_test.py

## A_goal 标定模式

§8.2 的 `S_int = Corr(ΔC_T, ΔA_goal)` 依赖明确的目标 `target`。归档记录只含文本嵌入，
不含意图信息，因此提供两种模式：

| `--target` | target | S_int / DRI / C_sel | 语义 |
|---|---|---|---|
| `none`（默认） | 无 | 记为 `null` | 不伪造目标，避免无意义相关性 |
| `centroid` | 本域嵌入质心 | 可计算 | 衡量本域一致性，**非**意图推进 |

`C_DMN / C_SN / C_mem / H_switch` 与目标无关，任何模式下均有效。

## 实验分支（含已终止的探索）

`experiments/` 下是实验树，其中 `transient/` 是**已终止**的"瞬在/干涉"分支：

> 作者判定：瞬在的探索是失败的，语言模型架构完全不支持瞬在，跑不通工程验证。

失败证据、**数学根源证明**（干涉强度 `Σ|I_ij|²` 中相位被模长平方消去，故相位无效）、
三个架构障碍与复现命令见
[`docs/NEGATIVE-RESULT-TRANSIENT.md`](docs/NEGATIVE-RESULT-TRANSIENT.md)。
回归防护见 `tests/test_transient.py`。

运行实验（模块方式，从仓库根目录）：

```bash
python -m experiments.transient_interference.exp1_phase_coupling
python -m experiments.transient_interference.exp6_high_precision
```

## 可构建项目结构

本仓库是可安装的 Python 项目：

```bash
pip install -e ".[dev]"    # 安装（含 pytest 等开发依赖）
pytest                     # 运行测试
python -m build            # 构建发行包
```

`pyproject.toml` 中把 `experiments/` 下的 `transient` 暴露为**顶层包**——
因为 `PACSP-ID` 含连字符，不能作为 Python 包名。

## 构建与发布预印本

一条命令重建并发布排版后的论文（34 页 PDF + DOCX）：

```bash
python scripts/pacsp_formula.py     # 90 张公式图（matplotlib，无需 LaTeX）
python scripts/pacsp_parse.py       # Markdown → 块模型（只读校验）
python scripts/pacsp_docx.py        # 块模型 → DOCX，含附录F 的 26 张图
```

或一条命令走完全部阶段：

```powershell
# 完整流程（含 PDF、GitHub Release、Zenodo）
$env:GIT_TOKEN    = "<github token, repo scope>"
$env:ZENODO_TOKEN = "<zenodo token, deposit:write>"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pacsp_release.ps1

# 常用变体
... -SkipPdf        # 只到 DOCX（无 LibreOffice 时）
... -NoRelease      # 不建 Release、不挂 DOI
... -SkipZenodo     # 跳过 DOI 附件
... -SkipChecks     # 跳过结构校验
```

**已知约束**：DOCX→PDF 需要 LibreOffice，它会**创建子进程**。
在受限沙箱中该操作会以 `spawn EPERM` 被拒，因此这一步需在普通终端运行，
或对该条命令单独放宽权限。其余全部阶段均可在沙箱内完成。

| 脚本 | 用途 |
|---|---|
| `pacsp_formula.py` | 渲染 90 个公式 + 6 张中文图例 + 可审计清单 |
| `pacsp_parse.py` | 解析论文 Markdown 为块模型 |
| `pacsp_inline.py` | 行内 **粗体** / *斜体* / `代码` / 公式标记 |
| `pacsp_refs.py` | 正文图交叉引用（纯追加，不改原文） |
| `pacsp_docx.py` | 装配 DOCX，含附录F |
| `pacsp_release.ps1` | 八阶段一键构建与发布 |
| `pacsp_github_release.py` | 建 tag 与 GitHub Release，上传附件 |
| `pacsp_check_release.py` | 校验已发布附件（DOCX 按内容、PDF 按字节） |
| `pacsp_zenodo.py` | 把 PDF/DOCX 补进 DOI 记录 |
| `pacsp_zenodo_info.py` | 显示 DOI 记录与文件清单 |

转换规则与全部变换登记见 [`docs/PUBLICATION-NOTES.md`](docs/PUBLICATION-NOTES.md)；
DOI 状态与 Zenodo 行为说明见 [`docs/ZENODO-SETUP.md`](docs/ZENODO-SETUP.md)。

## 脚本一览

| 脚本 | 职责 |
|------|------|
| `pacsp_build.py` | 构建流水线：计算 → 六层防护 → 合并 `.pacsp` |
| `pacsp_layer1.py` | L1 分层内容哈希 |
| `pacsp_sign.py` | L2 Ed25519 签名 |
| `pacsp_merkle.py` | L3 三级 Merkle 承诺 |
| `pacsp_timestamp.py` | L4 OpenTimestamps |
| `pacsp_emotion_tree.py` | §7 情绪树构建与瑟-树耦合 |
| `pacsp_innov.py` | §8 IDL 五元分解与四系数 |
| `pacsp_layer6.py` | L6 存证与验证 |
| `pacsp_verify.py` | 六层完整验证 |
| `pacsp_tamper_test.py` | 四类篡改攻击测试 |

## 文件命名规范

    {domain}_{epoch}_{variant}_CT{value}Se_{date}.{ext}

示例：`lyrics_epoch1_base_CT2.13Se_20260917.pacsp`

## 验证状态

| 数据集 | C_T | L1 | L2 | L3 | L4 | L5 | L6 |
|--------|-----|----|----|----|----|----|----|
| poem | 1.90 Se | OK | OK | OK | PEND | OK | OK |
| lyrics | 2.13 Se | OK | OK | OK | PEND | OK | OK |
| techdoc | 7.40 Se | OK | OK | OK | PEND | OK | OK |

L4 pending = 本地证明已生成，等待远程日历确认（非致命）。
L6 对 4.0.0-COMPACT 遗留记录显示 N/A（非致命，向后兼容）。

## 核心发现

人类诗歌、歌词与技术文档的认知模式存在显著差异：

| 维度 | 诗歌 | 歌词 | 技术文档 |
|------|------|------|---------|
| C_T | 1.90 Se | 2.13 Se | 7.40 Se |
| μ_k 均值 | 0.1272 | 0.1677 | 0.3352 |
| δ_k 均值 | 0.3973 | 0.4018 | 0.7266 |
| 情绪树深度 | 2 | 1 | 1 |
| C_DMN | 1.548 | 1.312 | 7.731 |
| C_SN | 2.50 | 3.50 | 2.50 |
| E_glob | 2.517 | 2.489 | 1.376 |
| 认知模式 | 短句凝缩 | 振荡型 | 建构型 |
| 变点间距 | 8,18 | 均匀（5,5,5,5） | 漏斗型（6,5,5,6） |

ICML 2026 情绪树扩展与 IDL 创新动力学层的完整实测指标、以及
**人/机对照组缺失**这一关键限制，见
[`docs/CONSISTENCY-REPORT.md`](docs/CONSISTENCY-REPORT.md)。

## 自主生成对照语料

为检验论文 §8.5 的判定表，`data/machine_*/` 提供**单次独立生成、无人工筛选**的平行语料：

| 域 | 目录 | 总字数 | 生成方式 |
|----|------|--------|---------|
| 诗歌 | `data/machine_poem` | 1,056 | qwen2.5:7b, 31 篇独立生成 |
| 歌词 | `data/machine_lyrics` | 1,077 | 同上 |
| 技术文档 | `data/machine_techdoc` | 32,877 | 同上 |

逐篇提示词、种子与哈希见 `data/machine_corpus_manifest.json`。

**实测结论（详见 [`docs/AXIS-COMPARISON-REPORT.md`](docs/AXIS-COMPARISON-REPORT.md)）**：
9 个 IDL 指标中**没有任何一个**在两条轴之间保持方向一致；域间差异大于轴间差异。
三组配对中仅机器歌词落入 §8.5 预期类别。

## 图表

`cache/figures/` 含 26 张图，覆盖 6 个域 × 4 类：

| 后缀 | 内容 |
|------|------|
| `_main.png` | 路径增量 δ_k 与认知强度 μ_k |
| `_L6_tree.png` | 情绪树拓扑（论文 §7） |
| `_L6_innov.png` | 五元分解 + 四系数（论文 §8） |
| `_L6_ctext.png` | 瑟-树耦合分解（论文 §7.4） |
| `_L6_comparison.png` | 跨域全景 |
| `_L6_human_vs_machine.png` | 人机对照 |

重建：`python scripts/pacsp_figure.py --out cache/figures`

## 报告

| 文档 | 内容 |
|------|------|
| [`docs/PACSP-ID-7.0.0-COMPLETE.md`](docs/PACSP-ID-7.0.0-COMPLETE.md) | 完整论文 |
| [`docs/CONSISTENCY-REPORT.md`](docs/CONSISTENCY-REPORT.md) | 三域一致性核查 |
| [`docs/AXIS-COMPARISON-REPORT.md`](docs/AXIS-COMPARISON-REPORT.md) | 两条对照轴与嵌入敏感性 |
| [`docs/SECTION-10-RESULTS.md`](docs/SECTION-10-RESULTS.md) | 论文 §10 结果章节 |
## 作者

jefely
ORCID: [0009-0005-9487-8555](https://orcid.org/0009-0005-9487-8555)

## 引用

概念 DOI（始终指向最新版）：`10.5281/zenodo.22801604`
v7.0.0 版本 DOI：`10.5281/zenodo.23138930`

```bibtex
@misc{pacspid2026,
  title        = {从意义权到认知沉积：PACSP-ID 框架的理论建构、创新动力学标识与验证工程},
  author       = {jefely},
  year         = {2026},
  version      = {7.0.0},
  doi          = {10.5281/zenodo.22801604},
  howpublished = {Zenodo (concept DOI, latest version)},
  orcid        = {0009-0005-9487-8555},
  url          = {https://github.com/jefely/pacsp-id}
}
```

排版后的预印本（34 页，PDF 与 DOCX）在各版本的 release 页面：
https://github.com/jefely/pacsp-id/releases

> **归档范围说明**：Zenodo 的 GitHub 集成**只归档仓库快照，不抓取 Release 附件**。
> 因此 DOI 记录中的文件为源码 zip，**PDF 与 DOCX 仅存于 release 页面**。
> 详见 [`docs/ZENODO-SETUP.md`](docs/ZENODO-SETUP.md)。

## 许可证

MIT License
