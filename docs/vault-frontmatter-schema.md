# 六壬 vault v3 Frontmatter 规约

本规约面向 `六壬vault/10-底本/**/*.md` 与 `六壬vault/90-禄命辅助/**/*.md` 两组语料，
在上游 `build_vault.py` 已写入的字段基础上，追加 v3 spec 所需的三个定制字段
（`anchor_id` / `作者` / `与六壬关系`），并新增一个断案专用的可选字段
`含内嵌注家`。字段名沿用中文，避免破坏上游脚本对 YAML 的读写。

字段用 YAML 表达；schema 描述采用「上游沿用 / v3 新增 / 断案专用 / stub 状态」
四层结构，检查器 `tools/check_v3_frontmatter.py` 与本文档一一对应。

---

## 一、上游沿用字段（`build_vault.py` 已写入）

| 字段 | 类型 | required | 说明 |
|---|---|---|---|
| `类型` | str | required（底本条目） | 一律 `底本条目`；非 stub 语料必填 |
| `书` | str | required（底本条目） | 例 `太白阴经`、`大六壬五变中黄经` |
| `版本` | str | required | 例 `卷十`、`南宋原辞` |
| `卷篇` | str | required | 每条一段；断案的段级 `anchor_id` 复用本字段 slugify |
| `断代` | str | required | 例 `唐·约759（乾元二年进献）` |
| `证据等级` | str | required | 例 `一手·基准层`、`二手·佐证层` |
| `理据价值` | str | optional | `★`~`★★★★★` |
| `抄大全风险` | str | optional | `无`/`轻`/`重` |
| `繁简` | str | optional | 例 `已转（opencc t2s，保护 乾/徵）` |
| `待核` | bool | optional | 布尔，标 OCR 待复核 |
| `源文件` | str | optional | 原始 PDF/txt 文件名 |
| `tags` | list[str] | required | Obsidian tag 数组 |
| `部` | str | optional | 武经总要专用（六壬/占候/太乙/遁甲/风角） |
| `污染` | bool | optional | 由 `mark_pollution.py` 写入 |
| `今注` | bool | optional | 由 `mark_pollution.py` 写入 |

## 二、v3 新增字段

| 字段 | 类型 | required | 说明 |
|---|---|---|---|
| `anchor_id` | str | required（底本条目） | 格式 `<花名>-<卷篇 slugified>-<段序 3 位>`；正则 `^[^-]+-[^-]+-\d{3}$` |
| `作者` | str | required（底本条目） | 书魂花名，取自下方枚举 |
| `与六壬关系` | str | required（底本条目） | 取值 `主体 / 旁证 / 遁甲 / 太乙 / 占候旁证 / N/A / 字典`；缺失时 checker 判 warn |

`作者` 枚举（12 位书魂花名）：

```
凝神子   ← 中黄经·正文
略决     ← 占事略决
太白     ← 太白阴经卷十元女式及诸篇
心镜     ← 六壬心镜
景祐     ← 景祐六壬神定经
武经     ← 武经总要后集卷十六~二十一
邵彦和   ← 大六壬断案·南宋原辞
阿甲     ← 大六壬断案·清人爱函按
林景行   ← 大六壬断案·现代今注（缘生谛）
壬归     ← 壬归
卜筮残   ← 卜筮书残卷
大全查手 ← 六壬大全
```

`anchor_id` 示例：

- `太白-玄女式-001` — 太白阴经·玄女式篇的第 1 段
- `邵彦和-01-韩太守占祈雪-001` — 大六壬断案第 01 案·主段（原辞）
- `阿甲-40-郑三公占坟地-001` — 大六壬断案第 40 案内爱函按段
- `凝神子-总说-003` — 中黄经·总说篇第 3 段

## 三、断案专用字段

| 字段 | 类型 | required | 说明 |
|---|---|---|---|
| `含内嵌注家` | list[str] | optional | 仅《大六壬断案》主 md 使用，列出该 md 中除主段外出现的注家花名，例 `[阿甲, 林景行]` |
| `段索引` | list[dict] | optional | 段级拆分表，元素 `{anchor_id, 作者, start, end}`；由 Task 3b `split_duanan_by_author.py` 写入 |

断案三魂段边界规则（Task 3b 落地）：

- 主段（原辞） → `作者=邵彦和`
- 段首以 `爱函按：` 或 `爱函按:` 开头 → `作者=阿甲`
- 段首以 `缘生谛：` 或 `缘生谛:` 开头 → `作者=林景行`
- 段与段之间的边界 = 下一段起始行 或 文末
- 段序 3 位从 001 起，同一 md 内独立递增

## 四、三层语料的必须字段差异

| 层次 | 典型书 | 必填 v3 字段 | 备注 |
|---|---|---|---|
| 宋本硬本 | 中黄经 / 心镜 / 景祐 / 壬归 / 断案 | `anchor_id` `作者` `与六壬关系=主体` | 主体层，`与六壬关系` 默认 `主体` |
| 唐本佐证 | 太白 / 略决 / 武经 / 卜筮残 | `anchor_id` `作者` `与六壬关系`（按篇打表） | 太白玄女式、武经六壬占法两篇是主体，其余占候旁证 |
| 大全字典 | 六壬大全 | `anchor_id` `作者=大全查手` `与六壬关系=字典` | 只做词条查手册用，不引作硬证 |

## 五、stub 状态

`状态: stub` 命中的文件（典型如 `六壬vault/90-禄命辅助/` 骨架卡）：

- 所有 v3 字段的检查都从 `error` / `warn` 降级为 `info`
- 允许缺 `anchor_id` / `作者` / `与六壬关系`
- 用于占位骨架，等子项目 D 补齐后升级到正式条目

## 六、检查器行为速查

`tools/check_v3_frontmatter.py`：

| 情形 | severity | 字段 |
|---|---|---|
| 无 YAML frontmatter | error | `frontmatter` |
| YAML 解析失败 | error | `frontmatter` |
| 缺 `anchor_id` | error（stub→info） | `anchor_id` |
| `anchor_id` 不匹配 `^[^-]+-[^-]+-\d{3}$` | error（stub→info） | `anchor_id` |
| 缺 `作者` | error（stub→info） | `作者` |
| `作者` 不在花名枚举 | error（stub→info） | `作者` |
| 缺 `与六壬关系` | warn（stub→info） | `与六壬关系` |

退出码：0 = 无 error；2 = 有 error。
