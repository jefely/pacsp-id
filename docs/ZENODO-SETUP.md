# 建立 DOI：Zenodo 集成状态与操作指引

**状态**：Zenodo 集成**已生效**——发布 `v7.0.0` 时自动归档并铸造了 DOI。
本文档记录核实结果、一个必须知道的行为限制，以及如何把**论文本身**挂进 DOI 记录。

---

## 一、已核实的 DOI（2026-10-04 实测）

经 `doi.org` 与 Zenodo API 双向核实：

| 项 | 值 |
|---|---|
| **概念 DOI**（始终指向最新版） | **`10.5281/zenodo.22801604`** |
| **版本 DOI**（v7.0.0 专用） | **`10.5281/zenodo.23138538`** |
| 记录页 | https://zenodo.org/records/23138538 |
| 创建时间 | 2026-10-04T14:49:37 UTC（GitHub Release 发布后 4 秒） |
| 资源类型 | `Software` |
| 许可 | MIT |
| 作者 | jefely（DOI 记录中 ORCID 为空） |

**核实方式**：`https://zenodo.org/api/records/23138538` 返回
`conceptdoi: 10.5281/zenodo.22801604`、`doi: 10.5281/zenodo.23138538`。

> README 首行的徽章 `zenodo.org/badge/1373521342.svg` 中 `1373521342` 是
> **Zenodo 的 GitHub 仓库 ID**，与 DOI 记录号无关，两者不应混淆。

---

## 二、行为限制：Release 附件**不会**被归档

**Zenodo 的 GitHub 集成只归档仓库快照，不抓取 Release 附件。**

v7.0.0 记录中的文件清单（API 实测）：

```
jefely/pacsp-id-v7.0.0.zip    7,772,053 bytes    ← 仅此一项
```

**PDF 与 DOCX 不在 DOI 记录内。** 这是集成层的既有行为，官方 issue 有记录：
[zenodo#1235](https://github.com/zenodo/zenodo/issues/1235)、
[zenodo#1728](https://github.com/zenodo/zenodo/issues/1728)。

〔整理者按〕**这对"预印本"是个真问题**：DOI 归档的是一份**软件**快照
（`resource_type: Software`），而非论文本身。论文的 PDF/DOCX 只在 GitHub Release 上，
**不随 DOI 永久保存**。

---

## 三、把论文挂进 DOI 记录

### 方式 A：脚本（推荐，可重复）

需要 Zenodo 个人访问令牌。**两个 scope 都必须勾**：

| Scope | 官方说明 | 为何需要 |
|---|---|---|
| `deposit:write` | 授予 depositions 的写权限，**但不允许发布**上传 | 上传文件 |
| `deposit:actions` | 授予**发布**、编辑、丢弃编辑的权限 | 提交上传使其生效 |

> **只勾 `deposit:write` 不够**——上传会成功但**无法发布**，记录不会更新。
> 依据：[Zenodo API 官方文档](https://developers.zenodo.org/) 的 Scopes 一节。

创建令牌：https://zenodo.org/account/settings/applications/tokens/new/

```powershell
$env:ZENODO_TOKEN = "<令牌>"
cd D:\myproject\PACSP-ID
python scripts\pacsp_zenodo.py
```

脚本会：发现最新记录 → 列出当前文件 → **依次探测两代 API**
（`/api/deposit/depositions/{id}` 与 `/api/records/{id}/draft`）→
上传 PDF 与 DOCX → 打印记录最终文件清单。

也可由发布脚本一并完成（stage 8）：

```powershell
$env:GIT_TOKEN    = "<github token>"
$env:ZENODO_TOKEN = "<zenodo token>"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pacsp_release.ps1
```

### 方式 B：网页手工（4 步）

1. 打开 https://zenodo.org/records/23138538
2. 点 **Edit**
3. **Files → Upload**，传 `dist/` 下的两个文件
4. **Save**（DOI 不变）

网页方式**不需要令牌**——若不想创建令牌，用这个。

---

## 四、后续版本

集成已生效，**发新 Release 即自动铸造新版本 DOI**：

```powershell
# 1. 重建交付物
powershell -File scripts\pacsp_release.ps1 -SkipPdf -NoRelease

# 2. 打标签并推送
git tag -a v7.1.0 -m "PACSP-ID 7.1.0"
git push origin v7.1.0

# 3. 在 GitHub 建 Release 并上传 dist/ 下两个文件
#    https://github.com/jefely/pacsp-id/releases/new?tag=v7.1.0

# 4. 等几分钟，确认新 DOI，再把论文挂进新记录
python scripts\pacsp_zenodo.py
```

**注意顺序无效**：先传好 Release 附件再触发归档**没有帮助**——附件本来就不会被抓取。
附件必须在 Zenodo 记录上单独补传。

---

## 五、下一版建议同时修正

| 项 | 现状 | 建议 |
|---|---|---|
| 资源类型 | `Software` | 在 Zenodo 仓库设置中改为 **Publication / Preprint** |
| 关键词 | 空 | 仓库根已有 `CITATION.cff`（12 个关键词），下版应能带入 |
| 作者 ORCID | 空 | 在 Zenodo 账号设置中绑定 ORCID `0009-0005-9487-8555` |

---

## 六、引用格式（已核实）

```
jefely. (2026). 从意义权到认知沉积：PACSP-ID 框架的理论建构、
创新动力学标识与验证工程 (7.0.0). Zenodo.
https://doi.org/10.5281/zenodo.22801604
```

**引用概念 DOI**（永远指向最新版）；若要精确指向某一版，用该版的**版本 DOI**。

---

## 七、状态登记

| 项 | 状态 |
|---|---|
| GitHub Release v7.0.0 | ✅ 已发布（含 PDF/DOCX 附件） |
| Zenodo 自动归档 | ✅ 已生效 |
| 概念 DOI | ✅ `10.5281/zenodo.22801604`（已核实） |
| 版本 DOI | ✅ `10.5281/zenodo.23138538`（已核实） |
| `CITATION.cff` | ✅ 已加入仓库（校验通过） |
| Scope 要求已查证 | ✅ `deposit:write` + `deposit:actions` |
| **PDF/DOCX 进入 DOI 记录** | ⬜ **待执行**（方式 A 或 B） |
| 资源类型改为 Preprint | ⬜ 待做 |
| ORCID 绑定 | ⬜ 待做 |
