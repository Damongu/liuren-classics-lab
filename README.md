# 六壬伴读工作区

> **最快上手**：不用跑任何命令。
> Obsidian → `Open folder as vault` → 选 **`六壬vault/`** → 装 Dataview 插件 → 开读。
> vault 里已经有 **8 部书、838 条**切好的原文，唐宋层七部全部入库完毕。

---

## 零、一键部署

### 你其实不需要部署

`六壬vault/` 是**构建好的成品**。解压完直接用 Obsidian 打开就行，
零依赖、零命令、零配置。下面这些只在你想**重建**时才用。

### 想重建 / 验证包完整

```bash
cd 六壬agent工作区
./一键部署.sh            # 装依赖 → 七部书重建 → 扫污染 → 自检 → 跑排盘器测试
./一键部署.sh --check     # 只自检，不动 vault（推荐解压后先跑一次）
./一键部署.sh --book 壬归  # 只重建一部书
```

Windows（PowerShell）没有 bash 的话，按顺序手动跑这四条即事等价：

```powershell
py -3 -m pip install opencc python-docx
py -3 tools\build_vault.py --force
py -3 tools\mark_pollution.py --all
py -3 tools\selfcheck.py
```

`--check` 全通过的样子：

```
底本条目合计：581 条
✅ 全部通过。vault 完整可用。
```

### 目录

```
六壬agent工作区/                ← Trae 打开这一层
├── AGENTS.md                   ← ★ Agent 指令（Trae 自动读；换别的工具就粘进自定义指令）
├── .trae/rules/                ← Trae 项目规则，内容指向 AGENTS.md
├── 一键部署.sh                 ← 重建入口
├── tools/tutor.py              ← ★ 交互式训练器（9 关，程序判分）
├── sources/                    ← 七部原书（PDF/DOC/DOCX/TXT），构建器的输入
├── 六壬vault/                  ← Obsidian 打开这一层（不是上一层！）
│   ├── 00-索引/                阅读路线图、证据面板、书目分级、排盘器用法
│   ├── 10-底本/
│   │   ├── 六壬大全/            257 条明本正文（十二册）
│   │   └── 唐宋层/              ★ 七部佐证书，581 条
│   │       ├── 太白阴经/            18 条（唐·759，卷十玄女式）
│   │       ├── 占事略决/            36 条（10c 末，课用九法）
│   │       ├── 景祐六壬神定经/       39 条（宋·1034，官修专书）
│   │       ├── 武经总要/            37 条（宋·1044，后集卷十六—二十占候五卷）
│   │       ├── 六壬心镜/           185 条（唐撰清校，20 条须设防）
│   │       ├── 六壬断案/           222 条（南宋占例）
│   │       └── 壬归/               43 条（题宋，存疑）
│   ├── 20-概念卡/ 30-课例/ 40-考据卡/ 50-校读笔记/
│   ├── 60-掌握度/ 70-待查/ 90-禄命对照/ 99-今注剥离/
│   └── README.md
├── liuren-paipan/              ← 排盘器（纯标准库 Python，不占 vault）
│   ├── liuren/                 引擎
│   ├── tests/                  底本课例回归 18 项 + duanan_cases.json（164 则南宋课例）
│   └── README.md               口径、依据、已知分歧
├── tools/
│   ├── build_vault.py          七部书 → vault 一键构建器
│   ├── mark_pollution.py       清校污染 / 今注标记器
│   ├── doc_extract.py          Word97 .doc 正文抽取（环境无 antiword 时用）
│   ├── import_tangsong.py      通用文献导入器（导新书用）
│   └── selfcheck.py            vault 完整性自检
└── README.md                   本文件
```

为什么排盘器和 tools 放在 vault **外面**：`.py`、`__pycache__` 进 vault 会污染搜索、
拖慢索引、还会被 Obsidian 当附件管；而它们读写 vault 只走相对路径，不影响协作。

### 进门先看几个地方

| 看什么 | 在哪 | 为什么 |
| :--- | :--- | :--- |
| **主工作面** | `50-校读笔记/对校矩阵-五个判别点.md` | 七部书在同一问题上的答案并置。**唐宋四硬本已填**，附 5 条已成立结论 |
| **今天能用的结论** | 同上「派生结论区」 | 涉害两层结构、贵人表唐宋迁移、九宗门之九的成因 |
| **哪些句子不可信** | `10-底本/唐宋层/六壬心镜/_污染位置表.md` | 《心镜》185 条里 20 条字句被清人改过，逐条列了位置 |
| **同一部书里也分层** | `10-底本/唐宋层/武经总要/00-分层索引-占候五卷.md` | 37 条里只有 15 条能当硬证，其余是遁甲／太乙／占候旁证。用 frontmatter 的 `与六壬关系` 过滤，别拿书名当证据等级 |
| **要练不要只读** | `00-索引/交互训练-关卡表.md` | 9 个关卡对齐阅读路线图的通关里程碑；`python3 tools/tutor.py` 直接开练，程序判分 |

---


## 一、Trae + Obsidian 怎么配

**一句话：Trae 管"改"，Obsidian 管"读"。同一份文件，两个视角。**

### 第一步：落地

1. 把整个 `六壬agent工作区/` 解压到一个**你自己能记住、不带同步冲突**的路径。
   建议：
   - Windows：`D:\六壬agent工作区`（别放 `C:\Users\…\OneDrive\` 下面，会和后面的
     同步方案打架）
   - macOS：`~/Documents/六壬agent工作区`
2. **Trae**：`File → Open Folder` 选 `六壬agent工作区`（**顶层**，这样 AI 能同时看到
   笔记和代码）。
3. **Obsidian**：`Open folder as vault` 选 `六壬agent工作区/六壬vault`（**只选 vault 那层**）。
   首次打开会提示信任作者，允许即可。
4. **让 agent 知道规矩**：顶层 `AGENTS.md` 是这个伴读 agent 的行为指令（角色设定、四拍循环、
   取证分层、污染判定、收尾更新哪些目录）。Trae 打开顶层后会自动读取 `.trae/rules/`，
   它指向 `AGENTS.md`，**不需要你手动做什么**。
   换成别的工具（Cursor / Claude Code / 网页版对话）就把 `AGENTS.md` 全文粘进
   「自定义指令 / System Prompt」，否则 AI 只会当成普通问答，不会走四拍循环，
   也不会自动更新掌握度。**这一步不做，这套东西就只是一堆 Markdown。**

### 第二步：验证跑得起来

Trae 底部终端里：

```bash
cd liuren-paipan
python3 -m liuren pan --day 甲子 --shi 卯 --jiang 子     # Windows 用 py -3 -m liuren …
python3 tests/test_book_cases.py                        # 应显示 通过 18/18
```

再试一次落卡，回 Obsidian 应该立刻看到新文件（Obsidian 会自动热加载）：

```bash
python3 -m liuren pan --day 甲午 --shi 辰 --jiang 午 --card
```

Python 版本要求 ≥ 3.10。Windows 下若 `python3` 不识别，用 `py -3`；
终端中文乱码执行一次 `chcp 65001`。

### 第三步：Obsidian 插件（够用就好，别装成插件收藏家）

vault 里每条笔记的 frontmatter 已经写好了 `册/篇/页/类型/阶段/前置/mastery/状态`
这些字段，装下面几个就能自动跑起来：

| 插件 | 干什么 | 必要性 |
| :--- | :--- | :---: |
| **Dataview** | 掌握度看板、待查清单、错题队列自动汇总（字段已埋好） | 必装 |
| **Obsidian Git** | 免费多端同步的主力，见第三节 | 必装 |
| **Spaced Repetition** | 间隔重复，把 1／3／7／21 天复现自动排期 | 强烈建议 |
| **Templater** | 概念卡／课例卡／考据卡模板自动填日期与出处 | 建议 |
| **Advanced Tables** | 手改表格不用数竖线 | 建议 |
| Excalidraw／Canvas | 画天地盘、画九宗门判定流程 | 想画再装 |

设置里建议开：`设置 → 编辑器 → 严格换行` 关掉；`设置 → 文件与链接 → 新链接格式`
选"相对路径"；`附件默认位置`设为指定文件夹，别散落。

### 第四步：日常动线（每次学习 60–90 分钟）

**开工第一句，直接复制粘给 Trae 里的 agent：**

```
按 AGENTS.md 的四拍循环带我学。先读 六壬vault/00-索引/阅读路线图.md，
告诉我我现在该学哪一节、为什么是这一节，然后开始第一拍。
```

后面每轮就这么说：`继续下一节` / `这条我没懂，重讲第一拍` / `这条你给我唐宋硬证`
/ `排一个能看出涉害的盘`。

1. Obsidian 打开 `00-索引/阅读路线图.md`，按阶段读底本笔记，读到卡壳就在 Trae 里问。
2. 要看盘 → Trae 终端 `python3 -m liuren pan …`；要留痕 → 加 `--card`。
3. **读完一节就练**：`python3 tools/tutor.py`（见下节）。只读不练，六壬前三关必塌。
4. 把错题贴给 agent，它按四拍循环讲；每轮收尾让它更新 `60-掌握度/`、`70-待查/`。
5. 关机前：Obsidian 左侧 Git 图标 → `Commit-and-sync`（或让它自动，见下）。

**分工铁律**：要改 vault 的事（切条、建卡、批改、更新掌握度）交给 Trae 里的 agent；
只要一个答案的事（这个术语什么意思、这句在哪一册）直接在 Obsidian 里搜或问轻问答。

---

## 二、交互训练（程序判分，agent 讲解）

```bash
python3 tools/tutor.py              # 自动选当前该练的关，10 题
python3 tools/tutor.py -l 5 --n 20  # 指定关卡与题量
python3 tools/tutor.py --review     # 错题复现：跨关卡，重问原题
python3 tools/tutor.py --status     # 进度条
python3 tools/tutor.py --list       # 列 9 个关卡
```

**为什么它的判分可信**：六壬的抽象盘一共只有 **720 课**（60 日干支 × 12 局），
排盘器 40 毫秒全枚举。所以题目从全集里采样，标准答案由排盘器现算，
**完全不经过语言模型**——模型会把三传算错，程序不会。答完直接给出盘面、
四课、三传，外加排盘器的推导链（「上克下凡 3 处 → 俱不比入涉害 → 深浅相等取临四孟
→ 比用格改取比和之寅」）。

**分工**：程序判分与排期，agent 讲解与佐证，你负责读和想。别让 agent 判分。

九个关卡与通关标准见 `六壬vault/00-索引/交互训练-关卡表.md`。要点：

- **关卡 4 按课体等概率抽题**，不按自然频率。因为别责只占 720 课的 9 例（1.25%），
  纯随机抽 100 题大概率一次都碰不到——而它恰恰最容易忘。
- **通关线**：近 12 题正确率 ≥ 85%，不达标卡住不放行。这是故意的。
- **「半对」**：底本自相矛盾处（如涉害比用格），你答另一说不判错，判 ◐ 半对，
  并把两说依据同时摊开。分歧要看见，不要被抹平。
- 进度写入 `六壬vault/60-掌握度/训练记录.md`，错题进 `错题队列.md`
  的 `<!-- tutor:begin -->` 区。两个文件由脚本维护，不要手改。

---

## 三、不花钱的随时随地同步

Obsidian Sync 是官方付费服务，**同步能力本身不是必须买的** —— vault 就是一堆
Markdown 文本文件，任何文件同步方案都能带得动。按你的设备情况挑一条主线，
**只挑一条**，多条并行必然打架。

### 方案 A（推荐给你）：Git 私有仓库 + Obsidian Git 插件

**为什么最适合你**：你这个工作区天生就是「笔记 + 代码」混装，Git 一条线把两样
都同步了；而且笔记有完整版本history，改错能回滚，考据结论的演变过程本身就是资产。

**包里已经初始化好了**：`.gitignore` 写好了，而且已有一个基线提交
（`git log` 能看到 `六壬伴读工作区 v1`）。所以你**不用 `git init`**，直接接远端：

1. 在 GitHub（或 Gitee，国内快）建一个 **private** 仓库，比如 `liuren-study`。
2. 顶层执行：

   ```bash
   cd 六壬agent工作区
   git remote add origin git@github.com:<你的账号>/liuren-study.git
   git push -u origin master        # 想叫 main：git branch -M main 后再 push
   ```

   `.gitignore` 的两处口径，用之前先知道：
   - **`sources/` 的原书不入库**（体积大）。所以换台机器 clone 下来 `sources/` 是空的，
     `./一键部署.sh` 会跳过所有书 —— 但 `六壬vault/` 里已构建好的 838 条条目照常同步，
     **读书和训练完全不受影响**。要在新机器上重建才需要手工拷 `sources/`。
   - **`.trae/rules/` 入库**（agent 规则必须跟着走），`.trae/` 下其他本地状态不入库。

3. **电脑端**：Trae 自带 Git，直接用；Obsidian 装 `Obsidian Git` 插件，设置里开
   `Auto commit-and-sync every 10 minutes` + `Pull on startup`，基本无感。
4. **手机／平板**：Obsidian 移动版同样装 `Obsidian Git`（现在支持移动端），
   填 GitHub 用户名 + **Personal Access Token**（不是密码）即可 clone。
   - iOS 另有 `Working Copy` 可做 clone/pull，但推送要付费，能用 Obsidian Git 就别绕。
   - 首次 clone 会慢（几百个文件），之后是增量。

**注意**：
- 移动端只装 vault 那层（`六壬vault` 作为 sparse 目录不好搞，简单做法是手机上
  clone 整个仓库，Obsidian 选其中的 `六壬vault` 作为 vault）。
- 换设备前先 `pull`，走之前先 `push`；别两端同时改同一个文件。
- 冲突了不要慌：Markdown 冲突就是文件里多出 `<<<<<<<` 几行，删掉不要的一段即可。

### 方案 B：Syncthing —— 纯 P2P，不经云，量大也不心疼

开源免费、无容量限制、局域网内极快。适合 Windows/macOS/Linux/Android 之间。
两端都装 Syncthing，互相添加设备 ID，共享 `六壬agent工作区` 文件夹即可。

- 缺点 1：**iOS 没有免费客户端**（Möbius Sync 收费）。
- 缺点 2：要两端**同时在线**才同步（或有一台常开的机器／NAS 做中继）。
- 缺点 3：无版本history，误删就是误删（可开 File Versioning 缓解）。

### 方案 C：Apple 全家桶就用 iCloud Drive

Mac + iPhone + iPad，直接把 vault 放 `iCloud Drive/Obsidian/` 下，
iOS 版 Obsidian 原生识别，5GB 免费空间对纯文本绰绰有余。
缺点：偶发同步延迟与 `.icloud` 占位文件；Windows 端体验差。

### 方案 D：国内云盘 WebDAV + Remotely Save 插件

坚果云（免费额度：每月 1GB 上传／3GB 下载）+ Obsidian 社区插件 `Remotely Save`，
安卓/iOS 都能用，也支持 OneDrive／Dropbox／S3。
缺点：有流量额度、同步是"插件级"而非文件级，冲突处理不如 Git 直观。

### 一句话选择

| 你的设备 | 选 |
| :--- | :--- |
| Windows/Mac + 安卓，想要版本history（**你这种笔记+代码**） | **A：Git** |
| 电脑之间为主，讨厌云、文件多 | B：Syncthing |
| 全 Apple | C：iCloud（+ A 做备份也行） |
| 主力手机是 iPhone 且不想碰 Git | D：坚果云 WebDAV |

**千万别做的事**：把同一个 vault 同时交给两套同步（比如 iCloud + Git 都盯着），
`.obsidian/workspace.json` 这类高频变动文件会反复冲突。`.gitignore` 里已经帮你
排除了它。

---

## 四、两份 README 分别看什么

- **排盘器怎么用、口径依据、已知分歧** → `liuren-paipan/README.md`
- **读书路线、笔记体例、每条笔记字段** → `六壬vault/README.md` 与 `00-索引/阅读路线图.md`
- **排盘器在读书时的随手用法** → `六壬vault/00-索引/排盘器用法.md`
