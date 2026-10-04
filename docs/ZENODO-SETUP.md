# 建立 DOI：Zenodo 集成指引

预印本已经发布在 GitHub（[v7.0.0](https://github.com/jefely/pacsp-id/releases/tag/v7.0.0)），
但**尚无独立 DOI**。本文说明如何取得可引用的 DOI。

**需要你本人操作**——Zenodo 的授权只能在网页上完成，无法自动化。

---

## 一、为什么需要 DOI

| 无 DOI | 有 DOI |
|---|---|
| 引用需写 GitHub 链接，可能变动 | 永久标识，不会失效 |
| 无法被 DataCite / OpenAlex 索引 | 进入学术索引体系 |
| 版本管理靠 git tag | 每个版本自动获得独立 DOI |

Zenodo 与 GitHub 联动后，**每次发布 Release 都会自动归档并铸造 DOI**，无需手工上传。

---

## 二、操作步骤（约 3 分钟）

### 1. 用 GitHub 账号登录 Zenodo

打开 https://zenodo.org ，点 **Sign up** → **Sign up with GitHub**，授权。

> 若你已有 Zenodo 账号，用同一邮箱登录即可，然后在 Settings → Linked accounts 关联 GitHub。

### 2. 开启仓库同步

打开 **https://zenodo.org/account/settings/github/**

页面会列出你的 GitHub 仓库。找到 **`jefely/pacsp-id`**，把右侧开关拨到 **ON**。

> 若列表为空，点右上角 **Sync now** 刷新。

### 3. 发布新版本以触发归档

**已发布的 v7.0.0 不会被追溯归档**——Zenodo 只处理开启之后的 Release。
所以需要发一个新版本：

```powershell
cd D:\myproject\PACSP-ID

# 打个新标签并推送
git tag -a v7.0.1 -m "PACSP-ID 7.0.1 -- public preprint"
git push origin v7.0.1
```

然后在 GitHub 上建对应 Release：

https://github.com/jefely/pacsp-id/releases/new?tag=v7.0.1

标题与说明可复制 `docs/RELEASE-7.0.0.md`，**附件上传 `dist/` 下的 DOCX 与 PDF**。

### 4. 查看 DOI

发布后几分钟内，回到 https://zenodo.org/account/settings/github/ ，
`jefely/pacsp-id` 那一行会显示 **DOI 徽章**，形如 `10.5281/zenodo.XXXXXXXX`。

同时 Zenodo 会为该版本创建一个条目页，永久保存 DOCX 与 PDF 的副本。

---

## 三、仓库中已有的 DOI 说明

`docs/PACSP-ID-7.0.0-COMPLETE.md` 与 `README` 中已出现一条 DOI：

```
https://doi.org/10.5281/zenodo.22801604
```

**这条 DOI 在本次整理中未能核实**——本环境网络受限，且它超出整理者知识范围。
请你在步骤 4 拿到真实 DOI 后：

1. 核对 `10.5281/zenodo.22801604` 是否确实指向本项目；
2. 若不符，把仓库中所有出现该 DOI 的位置替换为真实 DOI：

```powershell
cd D:\myproject\PACSP-ID
# 找出所有出现位置
git grep -n "22801604"
```

〔整理者按〕**在 DOI 未经核实前，不应把它写进正式引用**。
一个错误的 DOI 会使引用失效，且比没有 DOI 更糟——读者会以为链接坏了。

---

## 四、Zenodo 与 GitHub Release 的分工

| 内容 | 由谁保存 |
|---|---|
| 源代码（各版本快照） | GitHub + Zenodo 各存一份 |
| 论文 DOCX / PDF | GitHub Release 附件 + Zenodo 归档 |
| 公式图 / 图表（可重建） | 仅 GitHub（可由脚本重建，无需归档） |
| 原始对话素材 | 仅 GitHub `pacsp-collection` 仓库 |
| **DOI** | **Zenodo 铸造** |

---

## 五、DOI 状态登记

| 项 | 状态 |
|---|---|
| GitHub Release v7.0.0 | ✅ 已发布 |
| tag v7.0.0 | ✅ 已推送 |
| Zenodo 集成 | ⬜ **待你开启** |
| 新版本触发归档 | ⬜ 待做（开启集成后） |
| 真实 DOI | ⬜ 待获取 |
| 仓库内 DOI 核对与替换 | ⬜ 待做 |

---

## 六、可选：手动上传（不想开集成时）

若不愿让 Zenodo 访问 GitHub，可手工上传：

1. https://zenodo.org/uploads/new
2. **Upload type** 选 *Publication* → *Preprint*
3. 上传 `dist/PACSP-ID-7.0.0-preprint.pdf` 与 `.docx`
4. 填写标题、作者（jefely，ORCID `0009-0005-9487-8555`）、版本 `7.0.0`
5. **Related identifiers** 填 GitHub 链接
6. **Publish** → 获得 DOI

此法的代价：后续每个版本都要手工重做。
