# 建立 DOI：Zenodo 归档状态与操作指引

**状态（2026-10-04 实测）**：Zenodo 集成已生效，`v7.0.0` 已自动归档并铸造 DOI。
预印本 PDF 与 DOCX **已进入 DOI 记录**并逐字节验证。

> **归档图谱、一处由整理造成的损坏、以及引用时应使用哪个 DOI，
> 全部登记在 [`DOI-ARCHIVE-STATUS.md`](DOI-ARCHIVE-STATUS.md)。**
> 本文只讲操作。

---

## 一、你要用的 DOI

| 用途 | DOI |
|---|---|
| **引用（推荐）** | **`10.5281/zenodo.22801604`** ← 概念 DOI，始终指向最新版 |
| 精确指向 7.0.0 | `10.5281/zenodo.23138930` ← 正确版本，含 PDF 与 DOCX |
| ~~不要使用~~ | ~~`10.5281/zenodo.23138538`~~ ← 该版 DOCX 内容错误 |

**概念 DOI 会随新版本自动前移**，所以引用它最稳妥。

---

## 二、行为限制：Release 附件不会被自动归档

Zenodo 的 GitHub 集成**只归档仓库快照，不抓取 Release 附件**。

v7.0.0 记录初始只有一个 `jefely/pacsp-id-v7.0.0.zip`，**PDF 与 DOCX 不在其中**。
官方 issue 记录此行为：[zenodo#1235](https://github.com/zenodo/zenodo/issues/1235)、
[zenodo#1728](https://github.com/zenodo/zenodo/issues/1728)。

因此论文必须在 Zenodo 记录上**单独补传**。

---

## 三、用令牌补传（已实现）

### 令牌 scope（两个都要）

依据 [Zenodo API 官方文档](https://developers.zenodo.org/)：

| Scope | 官方说明 | 用途 |
|---|---|---|
| `deposit:write` | 授予 depositions 的写权限，**但不允许发布** | 上传文件 |
| `deposit:actions` | 授予**发布**、编辑、丢弃编辑的权限 | 提交生效 |

> **只勾 `deposit:write` 不够**——上传会成功但无法发布，记录不会更新。

创建令牌：https://zenodo.org/account/settings/applications/tokens/new/

### 命令

```powershell
$env:ZENODO_TOKEN = "<令牌>"
cd D:\myproject\PACSP-ID

python scripts\pacsp_zenodo.py --status      # 盘点账号下的记录
python scripts\pacsp_zenodo.py --verify      # 下载回验已发布文件（最重要）
python scripts\pacsp_zenodo.py --add-new-version --yes   # 新建版本并上传
```

### 已发布记录不能再改文件

```
POST /api/records/{id}/file-modification   → 曾返回 200，发布后即不可再获取
POST /api/records/{id}/draft               → 201，但
DELETE/POST .../draft/files                → 403 "Bucket is locked for modifications."
```

**修改资源似为一次性**。已发布版本的文件无法就地更正，只能新建版本。
新版本会铸造新的版本 DOI；概念 DOI 不变。

### ⚠️ 上传后必须回验

**HTTP 200/201 只说明请求被接受，不说明字节正确。**

本仓库曾因此损坏过一条已发布记录（详见 `DOI-ARCHIVE-STATUS.md`）。
所以：

```powershell
python scripts\pacsp_zenodo.py --verify
```

会下载每个已发布文件并与本地原件比对 SHA-256。**这是强制步骤，不是可选检查。**

---

## 四、网页端替代方案（不需要令牌）

1. 打开 https://zenodo.org/records/23138930
2. **Edit**
3. **Basic information**：标题、版本、资源类型改为 Publication → Preprint、
   关键词、ORCID `0009-0005-9487-8555`
4. **Files**：可补传仓库 zip
5. **Publish**

REST API 对已发布记录的元数据返回 404，**元数据只能在网页端改**。

---

## 五、后续版本的流程

```powershell
# 1. 重建交付物（公式 → DOCX → PDF）
powershell -File scripts\pacsp_release.ps1 -SkipPdf -NoRelease
#    （PDF 步骤需在普通终端运行，LibreOffice 需创建子进程）

# 2. 打标签并推送
git tag -a v7.1.0 -m "PACSP-ID 7.1.0"
git push origin v7.1.0

# 3. 在 GitHub 建 Release 并上传 dist/ 下两个文件
#    https://github.com/jefely/pacsp-id/releases/new?tag=v7.1.0

# 4. 等 Zenodo 自动归档后，把论文补进新记录
python scripts\pacsp_zenodo.py --status
python scripts\pacsp_zenodo.py --add-new-version --yes
python scripts\pacsp_zenodo.py --verify
```

**注意**：先传好 Release 附件再触发归档**没有帮助**——附件本来就不会被抓取。

---

## 六、下一版建议同时修正

| 项 | 现状 | 建议 |
|---|---|---|
| 资源类型 | `Software` | 网页端改为 **Publication → Preprint** |
| 版本字段 | 空 | 填 `7.0.0`（或新版本号） |
| 标题 | `jefely/pacsp-id: ...` | 改为论文正式标题 |
| 关键词 | 空 | 从 `CITATION.cff` 的 12 个关键词填入 |
| ORCID | 空 | 绑定 `0009-0005-9487-8555` |
| 仓库 zip | 不在 23138930 | 网页端补传，或接受源码仅在 GitHub |

---

## 七、状态登记

| 项 | 状态 |
|---|---|
| Zenodo 自动归档 | ✅ 已生效 |
| 概念 DOI | ✅ `10.5281/zenodo.22801604`（已核实） |
| 正确版本 DOI | ✅ `10.5281/zenodo.23138930` |
| PDF/DOCX 进入 DOI 记录 | ✅ **已完成并逐字节验证** |
| `scripts/pacsp_zenodo.py --verify` | ✅ 已实现并实测通过 |
| 损坏版本 `23138538` | ⚠️ 永久保留，已非最新，**不可删除** |
| 元数据（标题/版本/类型/关键词/ORCID） | ⬜ 需网页端修改 |
| 仓库 zip 进入正确版本 | ⬜ 需网页端补传 |
