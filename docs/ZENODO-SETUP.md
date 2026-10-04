# 建立 DOI：Zenodo 集成状态与指引

**状态更新（2026-10-04）**：Zenodo 集成**已开启并已生效**——发布 `v7.0.0` 时
Zenodo 自动归档并铸造了 DOI。本文档记录核实结果、一个必须知道的行为限制，
以及后续版本的操作方式。

---

## 一、已核实的 DOI（2026-10-04 实测）

经 `doi.org` 与 Zenodo API 双向核实：

| 项 | 值 |
|---|---|
| **概念 DOI**（始终指向最新版） | **`10.5281/zenodo.22801604`** |
| **版本 DOI**（v7.0.0 专用） | **`10.5281/zenodo.23138538`** |
| 记录页 | https://zenodo.org/records/23138538 |
| 概念记录 ID | 22801604 |
| 版本记录 ID | 23138538 |
| 创建时间 | 2026-10-04T14:49:37 UTC（GitHub Release 发布后 4 秒） |
| 标题 | `jefely/pacsp-id: PACSP-ID 7.0.0 — 公开预印本` |
| 版本 | `v7.0.0` |
| 资源类型 | `Software` |
| 许可 | MIT |
| 作者 | jefely（DOI 记录中 ORCID 为空） |

**核实方式**：`https://zenodo.org/api/records/23138538` 返回
`conceptdoi: 10.5281/zenodo.22801604`、`doi: 10.5281/zenodo.23138538`。
README 首行的徽章 `zenodo.org/badge/1373521342.svg` 中 `1373521342` 是
**Zenodo 的 GitHub 仓库 ID**，与 DOI 记录号无关，两者不应混淆。

---

## 二、必须知道的行为限制：Release 附件**不会**被归档

**Zenodo 的 GitHub 集成只归档仓库快照，不抓取 Release 附件。**

v7.0.0 记录中的文件清单（API 实测）：

```
jefely/pacsp-id-v7.0.0.zip    7,772,053 bytes    ← 仅此一项
```

**PDF 与 DOCX 不在 DOI 记录内。** 这是集成层的既有行为，两个官方 issue 记录了该问题：
[zenodo#1235](https://github.com/zenodo/zenodo/issues/1235)、
[zenodo#1728](https://github.com/zenodo/zenodo/issues/1728)。

〔整理者按〕**这对"预印本"是个真问题**：DOI 归档的是一份**软件**快照
（`resource_type: Software`），而非论文本身。目前论文的 PDF/DOCX 只在
GitHub Release 上，**不随 DOI 永久保存**。若 GitHub 不可用，DOI 指向的内容里没有论文。

### 三种补救方式

| 方式 | 做法 | 代价 |
|---|---|---|
| **A. 手工把 PDF/DOCX 传到 Zenodo 记录**（推荐） | 在该记录的 **Edit → Files → Upload** 补传两个文件，保存后 DOI 不变 | 每个版本手工一次 |
| **B. 在 Zenodo 上另建 Publication 记录** | 以 *Publication → Preprint* 类型新建，手工上传论文，获得独立论文 DOI | 与软件 DOI 分离，需两个 DOI |
| **C. 接受现状** | 论文仅存于 GitHub Release | 论文不随 DOI 长期保存 |

**A 是可自动化程度最高的**：Zenodo 提供 REST API，只要你有
[个人访问令牌](https://zenodo.org/account/settings/applications/)（勾选 `deposit:write`），
我可以写成脚本，每次发布后自动把 PDF/DOCX 补进对应记录。

---

## 三、后续版本的操作流程

Zenodo 集成已生效，因此**发新 Release 即自动铸造新 DOI**，无需任何手工步骤：

```powershell
cd D:\myproject\PACSP-ID

# 1. 重建交付物
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pacsp_release.ps1 -NoRelease

# 2. 打新标签并推送
git tag -a v7.1.0 -m "PACSP-ID 7.1.0"
git push origin v7.1.0

# 3. 在 GitHub 建 Release 并上传 dist/ 下的 PDF 与 DOCX
#    https://github.com/jefely/pacsp-id/releases/new?tag=v7.1.0

# 4. 几分钟后到「二、A」把两个文件补进 Zenodo 记录
```

**注意顺序**：先上传好 Release 附件、**再**触发归档并无帮助——
因为附件本来就不会被抓取。附件必须在 Zenodo 记录上单独补传。

---

## 四、下一版建议同时修正的三项

| 项 | 现状 | 建议 |
|---|---|---|
| 资源类型 | `Software` | 在 Zenodo 设置中把仓库类型改为 **Publication / Preprint** |
| 关键词 | 空 | Zenodo 从仓库读取；`CITATION.cff` 已加 12 个关键词，下版应能带入 |
| 作者 ORCID | 空 | 在 Zenodo 账号设置中绑定 ORCID `0009-0005-9487-8555` |

---

## 五、引用格式（已核实，可直接使用）

```
jefely. (2026). 从意义权到认知沉积：PACSP-ID 框架的理论建构、
创新动力学标识与验证工程 (7.0.0). Zenodo.
https://doi.org/10.5281/zenodo.22801604
```

**引用建议**：引用**概念 DOI** `10.5281/zenodo.22801604`（永远指向最新版）；
若要精确指向某一版，用该版的**版本 DOI**。

---

## 六、状态登记

| 项 | 状态 |
|---|---|
| GitHub Release v7.0.0 | ✅ 已发布（含 PDF/DOCX 附件） |
| tag v7.0.0 | ✅ 已推送 |
| Zenodo 自动归档 | ✅ **已生效** |
| 概念 DOI | ✅ `10.5281/zenodo.22801604`（已核实） |
| 版本 DOI | ✅ `10.5281/zenodo.23138538`（已核实） |
| `CITATION.cff` | ✅ 已加入仓库（校验通过） |
| **PDF/DOCX 进入 DOI 记录** | ⬜ **未完成**——需「二、A」步骤 |
| 资源类型改为 Preprint | ⬜ 待做 |
| DOI 记录中的 ORCID | ⬜ 待绑定 |
