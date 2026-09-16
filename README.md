[![DOI](https://zenodo.org/badge/1373521342.svg)](https://doi.org/10.5281/zenodo.22801604)

# PACSP-ID

Pan-Agent Cognitive Sediment Protocol — Identity

认知沉积量的严格量化框架。通过信息几何度量认知路径的不可压缩性，以五层密码学防护保证记录的不可篡改。

## 核心公式

C_T = ∫ μ(t) dΛ(t)

其中：
- μ(t) = Tr[I_F(θ_t)]：认知曲率（Fisher信息矩阵的迹）
- Λ(t)：路径全变差测度（含连续漂移与离散相变）
- 单位：瑟（Se）

## 五层防护

| 层 | 机制 | 作用 |
|----|------|------|
| L1 | 分层内容哈希 | 6 个语义块独立 Merkle 化 |
| L2 | Ed25519 签名 | 检测来源伪造 |
| L3 | 三级 Merkle | 样本级 + 计算级 + 结果级 |
| L4 | OpenTimestamps | 比特币区块锚定 |
| L5 | 可复现验证 | 完整 pipeline 重放 |

## 目录结构

    data/          原始样本（权威）
    records/       权威 .pacsp 文件（1 个数据集 1 个文件）
    cache/         派生缓存（可删除重建）
    scripts/       全部 Python 脚本

## 快速开始

    pip install -r requirements.txt

    # 1. 构建 .pacsp
    python scripts/pacsp_build.py

    # 2. 生成缓存
    python scripts/pacsp_cache.py

    # 3. 重建图片
    python scripts/pacsp_figure.py

    # 4. 五层验证
    python scripts/pacsp_verify.py records/lyrics_*.pacsp data/lyrics

    # 5. 篡改测试
    python scripts/pacsp_tamper_test.py

## 文件命名规范

    {domain}_{epoch}_{variant}_CT{value}Se_{date}.{ext}

示例：`lyrics_epoch1_base_CT2.13Se_20260917.pacsp`

## 验证状态

| 数据集 | C_T | L1 | L2 | L3 | L4 | L5 |
|--------|-----|----|----|----|----|----|
| lyrics | 2.13 Se | OK | OK | OK | PEND | OK |
| techdoc | 7.40 Se | OK | OK | OK | PEND | OK |

L4 pending = 本地证明已生成，等待远程日历确认（非致命）。

## 核心发现

人类歌词创作与技术文档的认知模式存在显著差异：

| 维度 | 歌词 | 技术文档 |
|------|------|---------|
| C_T | 2.13 Se | 7.40 Se |
| 认知模式 | 振荡型 | 建构型 |
| 变点间距 | 均匀（5,5,5,5） | 漏斗型（6,5,5,6） |
| delta_k/mu_k 同步性 | 异步 | 同步 |

## 作者

jefely  
ORCID: [0009-0005-9487-8555](https://orcid.org/0009-0005-9487-8555)

## 引用

    @misc{pacsp2026,
      title={PACSP-ID: Pan-Agent Cognitive Sediment Protocol for Identity},
      author={jefely},
      year={2026},
      doi={10.5281/zenodo.22801604},
      orcid={0009-0005-9487-8555},
      note={v4.0.0-COMPACT}
    }

## 许可证

MIT License