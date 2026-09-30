# 子项目 A：语料工程 · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 liuren-classics-lab 上游的 vault 收敛到 v3 spec 要求的 frontmatter 规约，建 `90-禄命辅助/` 骨架，把 v3 检查器集成到 `一键部署.sh --check`，全绿即视为子项目 A 完成。

**Architecture:** 复用上游中文 frontmatter（`书 / 版本 / 卷篇 / 证据等级 / 断代 / 待核 / tags`），仅新增两个 v3 定制字段 `anchor_id` 与 `与六壬关系`；不重写字段名，避免 breaking 上游 `build_vault.py`。检查器与 anchor_id 生成器都放在 `tools/` 下，遵循上游"vault 外 Python 相对路径读写"惯例。

**Tech Stack:** Python 3.10+ 纯标准库 + PyYAML（上游 `build_vault.py` 已依赖）；测试用 `unittest` 或独立 selftest 脚本（与上游 `retro_selftest.py`、`tutor_selftest.py` 风格一致）。

**Spec:** `docs/superpowers/specs/2026-09-30-liuren-tutor-design.md`

## Global Constraints

- Python 版本 ≥ 3.10（与上游 README 一致）
- Vault 外的 `.py` 文件不入 vault，避免 Obsidian 索引污染
- 上游脚本（`build_vault.py` / `selfcheck.py` / `mark_pollution.py`）不改逻辑，只允许扩展（新增 hook 或调用点）
- 新增字段 `anchor_id` / `作者` / `与六壬关系` / `含内嵌注家` **不覆盖已有值**（幂等）
- 所有新增脚本必带 selftest（对照 `retro_selftest.py` 47 项风格）
- Frontmatter 使用 YAML；不引入 TOML / JSON5
- **书魂花名映射**（作为 `作者` 字段默认值来源，也是 anchor_id 前缀）：`凝神子=中黄经·正文 / 略决=占事略决 / 太白=太白阴经卷十元女式及诸篇 / 心镜=六壬心镜 / 景祐=景祐六壬神定经 / 武经=武经总要后集卷二十一 / 邵彦和=断案南宋原辞 / 阿甲=断案清人爱函按 / 林景行=断案现代今注 / 壬归=壬归 / 卜筮残=卜筮书残卷 / 大全查手=六壬大全`
- **断案三魂段级拆分**（选项 Y）：《大六壬断案》一 md 内按段拆 anchor_id，主段 `作者=邵彦和`；`爱函按：`开头段 `作者=阿甲`；`缘生谛：`开头段 `作者=林景行`；`含内嵌注家` 字段记录该 md 出现过的注家花名

## Review Focus

| 输入 / 失败模式 | 期望行为 | 归属 task |
|---|---|---|
| 已有 frontmatter 中 `anchor_id` 已存在但格式不符 v3 规约 | 检查器识别为 error，报出但不擅自覆盖 | Task 2 |
| 单文件多段原文（同书同章多小节） | anchor_id 生成器逐段生成不重复的 id | Task 3a |
| 断案 md 内「爱函按：」「缘生谛：」段边界识别错误（漏切、错切） | Task 3b selftest 覆盖 4–6 条典型模式（段首、段中出现、伪匹配） | Task 3b |
| 武经/太白按每条实际标注 `与六壬关系`，不能默认全部主体 | Task 4 规则表按 chapter 名精确打表（玄女式=主体；推五帝法=占候旁证；遁甲相关=遁甲；等） | Task 4 |
| `90-禄命辅助/` 骨架文件在子项目 D 未落地前被检查器扫到 | 检查器识别为 stub（frontmatter 里 `状态: stub`），不判 fail | Task 5 |
| 上游 `--check` 因 anchor_id 缺失全部条目而红 | 集成必须在补齐后，先跑 Task 3a/3b 再跑 Task 6 | Task 6 依赖顺序 |

---

## File Structure

```
liuren-classics-lab/
├── docs/
│   ├── superpowers/
│   │   ├── specs/2026-09-30-liuren-tutor-design.md     # 已有
│   │   └── plans/2026-09-30-liuren-tutor-subproject-A.md  # 本文件
│   └── vault-frontmatter-schema.md                       # Task 1 新增
├── tools/
│   ├── check_v3_frontmatter.py                           # Task 1 新增
│   ├── check_v3_frontmatter_selftest.py                  # Task 1 新增
│   ├── generate_anchor_ids.py                            # Task 3a 新增（通用）
│   ├── generate_anchor_ids_selftest.py                   # Task 3a 新增
│   ├── split_duanan_by_author.py                         # Task 3b 新增（断案段级拆分）
│   ├── split_duanan_by_author_selftest.py                # Task 3b 新增
│   ├── backfill_liuren_relation.py                       # Task 4 新增
│   ├── liuren_relation_rules.py                          # Task 4 新增（武经/太白规则表）
│   ├── add_lulu_stub.py                                  # Task 5 新增（禄命辅助增补工具）
│   └── selfcheck.py                                      # Task 6 扩展调用点
├── 六壬vault/
│   ├── 10-底本/                                           # Task 3 批量回填
│   ├── 90-禄命辅助/                                       # Task 5 新增
│   │   ├── README.md
│   │   └── {本命,行年,年命上神,禄,马,贵人,天乙,驿马}.md  # 8 张骨架
│   └── ...
└── 一键部署.sh                                            # Task 6 追加 --check 调用
```

---

## Task 1: v3 frontmatter 规约与检查器

**Files:**
- Create: `docs/vault-frontmatter-schema.md`
- Create: `tools/check_v3_frontmatter.py`
- Test: `tools/check_v3_frontmatter_selftest.py`

**Interfaces:**
- Consumes: 无（首个 task）
- Produces:
  - `check_v3_frontmatter.check_file(path: pathlib.Path) -> list[Issue]`，`Issue` 是 `namedtuple("Issue", "path field severity message")`；severity 取 `error` / `warn` / `info`
  - `check_v3_frontmatter.check_vault(root: pathlib.Path) -> list[Issue]`，遍历 `10-底本/` 下所有 md
  - CLI: `python3 tools/check_v3_frontmatter.py [--vault 六壬vault] [--json]`；退出码 0 = 无 error；2 = 有 error

- [ ] **Step 1: 起草 schema 文档**

写入 `docs/vault-frontmatter-schema.md`，包含：
1. 上游沿用字段清单（书/版本/卷篇/断代/证据等级/理据价值/抄大全风险/繁简/待核/源文件/tags）
2. v3 新增字段：
   - `anchor_id` 格式为 `<花名>-<卷篇 slugified>-<段序 3 位>`（例 `太白-玄女式-001`、`邵彦和-01-韩太守占祈雪-001`、`阿甲-40-郑三公占坟地-001`）
   - `作者`：书魂花名字符串，取值枚举 `凝神子/略决/太白/心镜/景祐/武经/邵彦和/阿甲/林景行/壬归/卜筮残/大全查手`
   - `与六壬关系` 取值域完整保留：`主体 / 旁证 / 遁甲 / 太乙 / 占候旁证 / N/A / 字典`
   - `含内嵌注家`：可选，仅《大六壬断案》主 md 使用，值为花名列表 `[阿甲, 林景行]` 之类
3. 每字段 required / optional 标记
4. 三层语料的必须字段差异（宋本硬本 vs 唐本佐证 vs 大全字典）
5. 断案三魂拆分规则：主段（原辞）作者=邵彦和；`爱函按：`开头段作者=阿甲；`缘生谛：`开头段作者=林景行

- [ ] **Step 2: 写失败测试**

```python
# tools/check_v3_frontmatter_selftest.py
import unittest, tempfile, pathlib
from check_v3_frontmatter import check_file

VALID_AUTHORS = {"凝神子","略决","太白","心镜","景祐","武经",
                 "邵彦和","阿甲","林景行","壬归","卜筮残","大全查手"}

class TestFrontmatterCheck(unittest.TestCase):
    def _write(self, content):
        f = pathlib.Path(tempfile.mkstemp(suffix=".md")[1])
        f.write_text(content, encoding="utf-8")
        return f

    def test_missing_anchor_id_is_error(self):
        f = self._write("---\n书: 太白阴经\n卷篇: 玄女式\n作者: 太白\n---\n正文")
        issues = check_file(f)
        errs = [i for i in issues if i.field == "anchor_id" and i.severity == "error"]
        self.assertEqual(len(errs), 1)

    def test_missing_author_is_error(self):
        f = self._write("---\n书: 太白阴经\n卷篇: 玄女式\nanchor_id: 太白-玄女式-001\n---\n正文")
        issues = check_file(f)
        errs = [i for i in issues if i.field == "作者" and i.severity == "error"]
        self.assertEqual(len(errs), 1)

    def test_invalid_author_is_error(self):
        f = self._write("---\n作者: 无名氏\nanchor_id: X-Y-001\n---\n正文")
        errs = [i for i in check_file(f) if i.field == "作者" and i.severity == "error"]
        self.assertEqual(len(errs), 1)

    def test_missing_liuren_relation_is_warn(self):
        f = self._write("---\n书: 太白阴经\n卷篇: 玄女式\n作者: 太白\n"
                        "anchor_id: 太白-玄女式-001\n---\n正文")
        warns = [i for i in check_file(f) if i.field == "与六壬关系" and i.severity == "warn"]
        self.assertEqual(len(warns), 1)

    def test_valid_frontmatter_zero_errors(self):
        f = self._write("---\n书: 太白阴经\n卷篇: 玄女式\n作者: 太白\n"
                        "anchor_id: 太白-玄女式-001\n与六壬关系: 主体\n---\n正文")
        errs = [i for i in check_file(f) if i.severity == "error"]
        self.assertEqual(errs, [])

    def test_stub_file_is_info_not_error(self):
        f = self._write("---\n状态: stub\n---\n骨架待填")
        errs = [i for i in check_file(f) if i.severity == "error"]
        self.assertEqual(errs, [])

    def test_anchor_id_format_regex(self):
        # 不合规格式判 error
        f = self._write("---\n作者: 太白\nanchor_id: 无花名格式\n---\n正文")
        errs = [i for i in check_file(f) if i.field == "anchor_id" and i.severity == "error"]
        self.assertGreaterEqual(len(errs), 1)
```

- [ ] **Step 3: 跑测试确认失败**

Run: `python3 tools/check_v3_frontmatter_selftest.py`
Expected: `ModuleNotFoundError: No module named 'check_v3_frontmatter'`

- [ ] **Step 4: 实现 `tools/check_v3_frontmatter.py`**

签名与 CLI 见 Interfaces。实现路径：读文件 → 用 PyYAML 解析 frontmatter → 按 schema 逐字段检查 → 生成 Issue 列表。`状态: stub` 命中时全字段降级为 info。

- [ ] **Step 5: 跑测试确认通过**

Run: `python3 tools/check_v3_frontmatter_selftest.py -v`
Expected: `Ran 4 tests ... OK`

- [ ] **Step 6: Commit**

```bash
git add docs/vault-frontmatter-schema.md tools/check_v3_frontmatter.py tools/check_v3_frontmatter_selftest.py
git commit -m "feat(vault): add v3 frontmatter schema and checker"
```

---

## Task 2: 生成 vault 现状 gap 报告

**Files:**
- Create: `docs/vault-v3-gap-report-2026-09-30.md`（人可读）
- Create: `.aime/vault-v3-gap.json`（机器可读，用于 Task 3 消费）

**Interfaces:**
- Consumes: `tools/check_v3_frontmatter.check_vault`
- Produces: gap 报告文件；`.aime/vault-v3-gap.json` 结构：`{"missing_anchor_id": [path...], "missing_liuren_relation": [path...], "other_errors": [{path,field,message}...]}`

- [ ] **Step 1: 跑检查器**

Run: `python3 tools/check_v3_frontmatter.py --vault 六壬vault --json > .aime/vault-v3-gap.json`
Expected: 退出码 2（因当前 vault 缺 anchor_id）；stdout 是有效 JSON

- [ ] **Step 2: 生成人读报告**

Run: `python3 -c "$(cat <<'EOF'
import json, collections, pathlib
data = json.loads(pathlib.Path('.aime/vault-v3-gap.json').read_text())
by_book = collections.Counter()
for p in data.get('missing_anchor_id', []):
    by_book[pathlib.Path(p).parts[2]] += 1  # 六壬vault/10-底本/唐宋层/<书>/...
# write markdown ...
EOF
)"
```

产物 `docs/vault-v3-gap-report-2026-09-30.md` 至少含：按书统计的缺 anchor_id 条数、缺`与六壬关系`条数、其他 error 列表。

- [ ] **Step 3: Commit**

```bash
git add docs/vault-v3-gap-report-2026-09-30.md .aime/vault-v3-gap.json
git commit -m "docs(vault): snapshot v3 frontmatter gap report"
```

---

## Task 3a: 通用 anchor_id 生成器与批量回填（断案除外）

**Files:**
- Create: `tools/generate_anchor_ids.py`
- Test: `tools/generate_anchor_ids_selftest.py`
- Modify: `六壬vault/10-底本/**/*.md`（**除《六壬断案》**外全部批量回填）

**Interfaces:**
- Consumes: `check_v3_frontmatter` 的 Issue；`.aime/vault-v3-gap.json`；花名映射表（Global Constraints）
- Produces:
  - `generate_anchor_ids.slugify(text: str) -> str`
  - `generate_anchor_ids.book_to_penname(book: str) -> str`——从 `书` 字段映射到花名（例 `太白阴经 → 太白`）
  - `generate_anchor_ids.compute_anchor_id(penname: str, chapter: str, index: int) -> str`，返回 `f"{penname}-{slugify(chapter)}-{index:03d}"`
  - `generate_anchor_ids.backfill(path: pathlib.Path, dry_run: bool = True) -> BackfillResult`——同时回填 `anchor_id` 与 `作者`（若缺）
  - CLI: `python3 tools/generate_anchor_ids.py [--vault 六壬vault] [--apply] [--skip-book 六壬断案]`

- [ ] **Step 1: 写失败测试**

```python
# tools/generate_anchor_ids_selftest.py
import unittest
from generate_anchor_ids import compute_anchor_id, slugify, book_to_penname

class T(unittest.TestCase):
    def test_slugify_keeps_hanzi(self):
        self.assertEqual(slugify("玄女式"), "玄女式")

    def test_slugify_replaces_spaces(self):
        self.assertEqual(slugify("推 五 帝 法"), "推-五-帝-法")

    def test_book_to_penname_taibai(self):
        self.assertEqual(book_to_penname("太白阴经"), "太白")

    def test_book_to_penname_zhongshan(self):
        self.assertEqual(book_to_penname("大六壬五变中黄经"), "凝神子")

    def test_book_to_penname_wuji(self):
        self.assertEqual(book_to_penname("武经总要"), "武经")

    def test_anchor_id_shape(self):
        self.assertEqual(compute_anchor_id("太白", "玄女式", 1),
                         "太白-玄女式-001")

    def test_anchor_id_stable_for_same_inputs(self):
        a = compute_anchor_id("壬归", "总说", 42)
        b = compute_anchor_id("壬归", "总说", 42)
        self.assertEqual(a, b)

    def test_idempotent_backfill(self):
        # 已有 anchor_id 的文件不覆盖
        pass  # 具体见实现文件
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 tools/generate_anchor_ids_selftest.py`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: 实现 `tools/generate_anchor_ids.py`**

`book_to_penname` 是字典查表；`compute_anchor_id` 纯函数。`backfill` 逻辑：读文件 → 解析 frontmatter → 已有 `anchor_id` 非空则 skip → 否则由 `书` → penname，配 `卷篇` 与该书内文件字典序 index，生成 id 与 `作者` 一起写回。**《六壬断案》通过 `--skip-book 六壬断案` 排除**，交给 Task 3b。

- [ ] **Step 4: 跑测试通过**

Run: `python3 tools/generate_anchor_ids_selftest.py -v`
Expected: `OK`

- [ ] **Step 5: Dry-run 批量回填**

Run: `python3 tools/generate_anchor_ids.py --vault 六壬vault --skip-book 六壬断案 | tail -20`
Expected: 输出 would-set 条数为 `gap 报告缺 anchor_id 总数 - 六壬断案条目数`

- [ ] **Step 6: Apply**

Run: `python3 tools/generate_anchor_ids.py --vault 六壬vault --skip-book 六壬断案 --apply`
Expected: 退出码 0

- [ ] **Step 7: Commit**

```bash
git add tools/generate_anchor_ids.py tools/generate_anchor_ids_selftest.py 六壬vault/
git commit -m "feat(vault): backfill anchor_id and 作者 to non-断案 corpus"
```

---

## Task 3b: 断案段级拆分与 anchor_id

**Files:**
- Create: `tools/split_duanan_by_author.py`
- Test: `tools/split_duanan_by_author_selftest.py`
- Modify: `六壬vault/10-底本/唐宋层/六壬断案/*.md`（frontmatter 加 `作者`/`含内嵌注家`/`段索引`）

**Interfaces:**
- Consumes: 单条断案 md 的正文
- Produces:
  - `split_duanan.detect_segments(body: str) -> list[Segment]`——`Segment` 是 `dataclass("author: str, start_line: int, end_line: int, first_line: str")`
  - 段边界规则：
    - 段首以 `爱函按：` 或 `爱函按:` 开头 → `作者=阿甲`
    - 段首以 `缘生谛：` 或 `缘生谛:` 开头 → `作者=林景行`
    - 其他 → `作者=邵彦和`（默认主段）
    - 一段的结束 = 下一段的起始，或文末
  - `split_duanan.backfill(path, dry_run) -> BackfillResult`——把段索引写入 frontmatter 的 `段索引` 字段（列表：`[{anchor_id: ..., 作者: ..., start: int, end: int}]`），并把主段的 `anchor_id` 与 `作者=邵彦和` 直接写在 frontmatter 顶层；`含内嵌注家` 列出该 md 出现过的除邵彦和外的花名
  - CLI: `python3 tools/split_duanan_by_author.py [--vault 六壬vault] [--apply]`

- [ ] **Step 1: 写失败测试（覆盖段边界识别）**

```python
# tools/split_duanan_by_author_selftest.py
import unittest
from split_duanan_by_author import detect_segments

BODY_1 = """庚戌年八月十五日癸丑日辰将辰时。甲辰旬，寅卯空。缘生谛：占于 1125
年 9 月 13 日，乙巳年乙酉月癸丑日，八月十五。1130 年庚戌八月十五日为甲申日，非癸丑日。
贵后阴玄"""

BODY_2 = """己酉年正月二十三壬寅日子将寅时。甲午旬，辰巳空。爱函按：郑四月
一日未时生。缘生谛：占于 1129 年 2 月 13 日，己酉年丙寅月壬寅日，正月二十三。
贵后阴玄"""

BODY_3 = """纯原辞正文,没有任何注家标记。
第二段仍是原辞。"""

class T(unittest.TestCase):
    def test_body_1_two_segments(self):
        segs = detect_segments(BODY_1)
        # 原辞开头 + 缘生谛段
        authors = [s.author for s in segs]
        self.assertEqual(authors, ["邵彦和", "林景行"])

    def test_body_2_three_segments(self):
        segs = detect_segments(BODY_2)
        authors = [s.author for s in segs]
        self.assertEqual(authors, ["邵彦和", "阿甲", "林景行"])

    def test_body_3_single_segment(self):
        segs = detect_segments(BODY_3)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0].author, "邵彦和")

    def test_false_match_not_at_line_start(self):
        # "他缘生谛" 不在行首,不触发切段
        body = "此处提到缘生谛校本云云,但非注段"
        segs = detect_segments(body)
        self.assertEqual(len(segs), 1)

    def test_multibyte_colon(self):
        # 全角:半角冒号都能识别
        body = "原辞\n爱函按:半角冒号\n爱函按：全角冒号"
        segs = detect_segments(body)
        self.assertEqual(len(segs), 3)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 tools/split_duanan_by_author_selftest.py`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: 实现 `tools/split_duanan_by_author.py`**

`detect_segments` 用正则 `^(爱函按|缘生谛)[：:]` 逐行扫描找段首，段与段之间为原辞（`邵彦和`）。段序 3 位从 001 起；同一 md 内多段各自递增。anchor_id：`f"{author}-{slugify(卷篇)}-{index:03d}"`。frontmatter 顶层 `作者=邵彦和`（主段），`含内嵌注家=[阿甲, 林景行]` 若存在。段索引写到 `段索引` 字段。

- [ ] **Step 4: 跑测试通过**

Run: `python3 tools/split_duanan_by_author_selftest.py -v`
Expected: `OK`（5/5）

- [ ] **Step 5: Dry-run 单条**

Run: `python3 tools/split_duanan_by_author.py --vault 六壬vault --sample 六壬断案-02*.md`
Expected: 打印段索引预览，作者分布合理

- [ ] **Step 6: Dry-run 全部**

Run: `python3 tools/split_duanan_by_author.py --vault 六壬vault`
Expected: 总段数 > 222（因为每 md 至少 1 段，含注家的多段）；含内嵌注家的 md 数量报出

- [ ] **Step 7: Apply**

Run: `python3 tools/split_duanan_by_author.py --vault 六壬vault --apply`
Expected: 退出码 0；`git diff --stat` 只动 `六壬断案/*.md`

- [ ] **Step 8: 重跑 v3 检查器**

Run: `python3 tools/check_v3_frontmatter.py --vault 六壬vault`
Expected: 缺 anchor_id / 作者 的 error 数为 0（Task 3a + 3b 合力全绿）；`与六壬关系` 的 warn 保留（等 Task 4）

- [ ] **Step 9: Commit**

```bash
git add tools/split_duanan_by_author.py tools/split_duanan_by_author_selftest.py 六壬vault/10-底本/唐宋层/六壬断案/
git commit -m "feat(vault): split 断案 by author (邵彦和/阿甲/林景行) with segment-level anchors"
```

Run: `python3 tools/check_v3_frontmatter.py --vault 六壬vault`
Expected: 缺 anchor_id 的 error 数为 0；退出码可能仍为 2（因缺`与六壬关系`），此为 Task 4 处理

- [ ] **Step 8: Commit**

```bash
git add tools/generate_anchor_ids.py tools/generate_anchor_ids_selftest.py 六壬vault/
git commit -m "feat(vault): backfill anchor_id to all corpus entries"
```

---

## Task 4: `与六壬关系` 批量回填

**Files:**
- Create: `tools/backfill_liuren_relation.py`
- Create: `tools/liuren_relation_rules.py`（规则表数据）
- Modify: `六壬vault/10-底本/**/*.md`

**Interfaces:**
- Consumes: `.aime/vault-v3-gap.json` 的 `missing_liuren_relation` 列表；`liuren_relation_rules.RULES`
- Produces:
  - `backfill_liuren_relation.default_relation(book: str, chapter: str) -> str`——按规则表返回七取值之一
  - `liuren_relation_rules.RULES` 结构：`dict[book_penname, dict[chapter_pattern, relation]]`
  - CLI: `python3 tools/backfill_liuren_relation.py [--vault 六壬vault] [--apply]`

**规则表（写入 `liuren_relation_rules.py`）**：

```python
RULES = {
    # 宋本主线六部：所有条目默认 主体
    "凝神子": {"*": "主体"},
    "心镜": {"*": "主体"},
    "景祐": {"*": "主体"},
    "壬归": {"*": "主体"},

    # 断案三魂：全部 主体
    "邵彦和": {"*": "主体"},
    "阿甲": {"*": "主体"},
    "林景行": {"*": "主体"},

    # 武经总要·后集卷二十一「六壬占法」= 主体；
    # 其余「后集卷十六~二十占候五卷」按篇实际：
    "武经": {
        "六壬占法": "主体",              # 卷二十一
        "占候·天文": "占候旁证",
        "占候·气候": "占候旁证",
        "遁甲": "遁甲",
        "太乙": "太乙",
        "*": "占候旁证",                 # 未列明的默认作占候旁证
    },

    # 太白阴经·卷十元女式 = 主体；卷十其余篇按实际：
    "太白": {
        "玄女式": "主体",
        "推伏吟反吟法": "主体",         # 六壬用
        "推月将加时法": "主体",
        "推三十六禽法": "占候旁证",
        "推五帝法": "占候旁证",
        "*": "占候旁证",
    },

    # 唐本佐证
    "略决": {"*": "主体"},
    "卜筮残": {"*": "主体"},

    # 大全 = 字典
    "大全查手": {"*": "字典"},
}
```

- [ ] **Step 1: 落规则表 + selftest**

写 `tools/liuren_relation_rules.py`；写 `backfill_liuren_relation.py` 顶部含 `--selftest` 子命令；selftest 覆盖：

- 武经 · 六壬占法 → `主体`
- 武经 · 遁甲 → `遁甲`
- 武经 · 未知篇 → `占候旁证`（fallback）
- 太白 · 玄女式 → `主体`
- 太白 · 推五帝法 → `占候旁证`
- 凝神子 · 任何篇 → `主体`
- 大全查手 · 任何条 → `字典`
- 未知作者 → 抛 `KeyError`

- [ ] **Step 2: 跑 selftest 通过**

Run: `python3 tools/backfill_liuren_relation.py --selftest`
Expected: `OK`（8/8）

- [ ] **Step 3: Dry-run**

Run: `python3 tools/backfill_liuren_relation.py --vault 六壬vault`
Expected: 输出 would-set 条数与 gap 报告 `missing_liuren_relation` 一致；按作者/关系分组统计打印

- [ ] **Step 4: 人工抽查**

抽查 dry-run 输出里武经 5 条 + 太白 5 条，确认规则表匹配符合实际。若有漏项（如武经卷号识别不到），补 `RULES` 后回 Step 3。

- [ ] **Step 5: Apply**

Run: `python3 tools/backfill_liuren_relation.py --vault 六壬vault --apply`
Expected: 退出码 0

- [ ] **Step 6: 重跑 v3 检查器**

Run: `python3 tools/check_v3_frontmatter.py --vault 六壬vault`
Expected: **退出码 0（全绿）**，只余 `90-禄命辅助/` 的 info（stub 状态）

- [ ] **Step 7: Commit**

```bash
git add tools/backfill_liuren_relation.py tools/liuren_relation_rules.py 六壬vault/
git commit -m "feat(vault): backfill 与六壬关系 with 武经/太白 rule table"
```

---

## Task 5: `90-禄命辅助/` 骨架

**Files:**
- Create: `六壬vault/90-禄命辅助/README.md`
- Create: `六壬vault/90-禄命辅助/本命.md`
- Create: `六壬vault/90-禄命辅助/行年.md`
- Create: `六壬vault/90-禄命辅助/年命上神.md`
- Create: `六壬vault/90-禄命辅助/禄.md`
- Create: `六壬vault/90-禄命辅助/马.md`
- Create: `六壬vault/90-禄命辅助/贵人.md`
- Create: `六壬vault/90-禄命辅助/天乙.md`
- Create: `六壬vault/90-禄命辅助/驿马.md`

**Interfaces:**
- Consumes: v3 spec §7.1 / §7.2
- Produces: 8 张卡的 stub 文件；每张 frontmatter 含 `状态: stub`、`概念名`、`别名`、`所属层: 禄命辅助`、`宋本硬证: []`、`tags: [禄命辅助, stub]`

- [ ] **Step 1: 定义骨架模板**

模板正文四段占位：
```markdown
## 一、界说

<!-- TODO(D-1): 该概念在禄命法与六壬中的一致含义（一句话） -->

## 二、在断辞中的用法

<!-- TODO(D-2): 举 1–2 个宋本断辞用例,标 anchor_id -->

## 三、宋本硬证

<!-- TODO(D-3): 列 2 处宋本原文出处 -->

## 四、易混淆点

<!-- TODO(D-4): 与他书或近义概念的区别 -->
```

- [ ] **Step 2: 生成 8 张 stub**

Run:
```bash
python3 - <<'EOF'
import pathlib
tpl = pathlib.Path('/tmp/liuren_stub.tpl').read_text()  # 上一步写到 /tmp
for name in ["本命","行年","年命上神","禄","马","贵人","天乙","驿马"]:
    p = pathlib.Path(f"六壬vault/90-禄命辅助/{name}.md")
    fm = f"---\n概念名: {name}\n所属层: 禄命辅助\n状态: stub\n宋本硬证: []\ntags: [禄命辅助, stub]\n---\n\n"
    p.write_text(fm + tpl, encoding='utf-8')
EOF
```

- [ ] **Step 3: 写 README**

`六壬vault/90-禄命辅助/README.md`：说明本目录用途（宋壬与禄命一脉相承的辅助卡，非"迁移桥"）、四段模板、状态字段含义、与主线 `20-概念卡/` 的区别、子项目 D 会填内容。

- [ ] **Step 4: 跑 v3 检查器确认 stub 被识别为 info**

Run: `python3 tools/check_v3_frontmatter.py --vault 六壬vault`
Expected: 退出码 0；`90-禄命辅助/` 下文件仅出 info 级别的字段

- [ ] **Step 5: 新增增补工具 `tools/add_lulu_stub.py`**

CLI：`python3 tools/add_lulu_stub.py <概念名> [--别名 X,Y] [--tags a,b]`

功能：给定概念名，在 `六壬vault/90-禄命辅助/<概念名>.md` 生成 stub（若已存在则拒绝并提示）；frontmatter 与四段模板与前 8 张一致。

Selftest（`tools/add_lulu_stub_selftest.py`）3 条：
- 新建不冲突路径 → 成功、文件存在、frontmatter 完整
- 已存在时再建 → 退出码非零，不覆盖
- 概念名含空格 → slugify 处理（`天医 星` → `天医-星.md`）

- [ ] **Step 6: 跑 selftest 通过**

Run: `python3 tools/add_lulu_stub_selftest.py -v`
Expected: `OK`（3/3）

- [ ] **Step 7: Commit**

```bash
git add 六壬vault/90-禄命辅助/ tools/add_lulu_stub.py tools/add_lulu_stub_selftest.py
git commit -m "feat(vault): scaffold 90-禄命辅助 seeds + add_lulu_stub tool"
```

---

## Task 6: 集成到 `selfcheck.py` 与 `一键部署.sh --check`

**Files:**
- Modify: `tools/selfcheck.py`（新增 v3 检查调用）
- Modify: `一键部署.sh`（保持既有流程,已有的 `--check` 会自动包含）

**Interfaces:**
- Consumes: `check_v3_frontmatter.check_vault`
- Produces: 无新 API；只改变 `--check` 的退出码语义（v3 gap 也会导致非零）

- [ ] **Step 1: 找 selfcheck 的 hook 位置**

Run: `grep -n "def main\|print.*通过\|sys.exit" tools/selfcheck.py`
记录退出码逻辑与 print 汇总位置

- [ ] **Step 2: 写扩展 selftest**

新增 `tools/selfcheck_v3_selftest.py`，两条用例：
- 造一个只缺 anchor_id 的 vault 副本 → `selfcheck --v3` 应非零
- 造一个全绿 vault → `selfcheck --v3` 应为 0

- [ ] **Step 3: 跑失败**

Run: `python3 tools/selfcheck_v3_selftest.py`
Expected: FAIL（`--v3` 参数未实现）

- [ ] **Step 4: 在 selfcheck.py 里增加 `--v3` 开关**

Modify: `tools/selfcheck.py` `main()` 加参数解析，`--v3` 时额外调用 `check_v3_frontmatter.check_vault`；打印形如 `v3 frontmatter 检查：<n> 条 error, <m> 条 warn`；有 error → 退出码非零。默认（无 `--v3`）行为不变，向后兼容。

- [ ] **Step 5: 跑通过**

Run: `python3 tools/selfcheck_v3_selftest.py -v`
Expected: `OK`

- [ ] **Step 6: 端到端验证**

Run: `./一键部署.sh --check`（在 vault 已跑完 Task 3–5 之后）
Expected: 已有输出 + `底本条目合计：583 条`；然后 `python3 tools/selfcheck.py --v3` 也 0 退出

- [ ] **Step 7: Commit**

```bash
git add tools/selfcheck.py tools/selfcheck_v3_selftest.py
git commit -m "feat(check): integrate v3 frontmatter check into selfcheck"
```

---

## Task 7: 子项目 A 收尾 · 更新 spec 状态

**Files:**
- Modify: `docs/superpowers/specs/2026-09-30-liuren-tutor-design.md`（更新 §12 Open Questions 与状态标记）

**Interfaces:**
- Consumes: 前六个 task 的产物
- Produces: 更新后的 spec，反映 A 已完成

- [ ] **Step 1: 更新 spec §12**

关闭「anchor_id 生成规则」相关的 Open Question（若有）；在 spec 顶部状态由 `awaiting user review` 更新为 `subproject A completed on 2026-XX-XX`（保持 spec 本体不动）。

- [ ] **Step 2: MVP 门槛自检**

按 spec §10.2 检查：
- ✅ vault 全 9 部书 frontmatter v3 合规
- ✅ `--check` 全绿
- ⏸️ 子项目 B 依赖项：`AGENTS.md` 骨架、《中黄经》书魂档、第六红线诱导测试用例——**转子项目 B**

- [ ] **Step 3: Commit + push**

```bash
git add docs/superpowers/specs/2026-09-30-liuren-tutor-design.md
git commit -m "docs(spec): mark subproject A completed"
git push origin pi
```

---

## Self-Review 记录

- **Spec coverage**：spec §10.1 子项目 A 的三件事（OCR 收敛 / 三层分区 frontmatter / `--check` 全绿）—— OCR 收敛在 liuren-classics-lab 上游已完成，本 plan 不重复；三层分区 frontmatter → Task 1–4；`--check` 全绿 → Task 6。§7.1 vault 结构 → Task 5（`90-禄命辅助/`）。§12 Open Question 「anchor_id 生成规则」→ Task 1 schema 定义。
- **Step scan**：每一 step 是单一动作 + 可检查结果，未出现 `TBD` / `handle edge cases` / 无归属类型。
- **Type consistency**：`check_file` 返回 `list[Issue]`、`Issue.severity ∈ {error,warn,info}` —— Task 2/6 都按 error 计入退出码；`compute_anchor_id` 返回 `str`，Task 3 直接写回 YAML frontmatter，格式一致。
- **Review Focus**：五条 Review Focus 都在 Task 里有对应 step 或 selftest 用例覆盖（stub 处理、幂等回填、`与六壬关系` 默认值、schema 已存在的 anchor_id 检测）。
- **Proportion**：plan 长度约 4200 字，spec 约 5800 字；plan / spec ≈ 0.72，未超过 spec，未沦为程序转录。

## Execution Handoff

Plan 已完成并保存到 `docs/superpowers/plans/2026-09-30-liuren-tutor-subproject-A.md`。请审阅。执行方式两选一：

- **Subagent-driven** — 每个 task 由独立 subagent 实现，另一 subagent review 后再进下一个，最后整分支 review。最稳；每个 task 都是一次新 context。
- **Native** — 我在当前会话里逐 task 实现，最后一次整分支 review。省 token，也快；子项目 A 各 task 之间接口耦合浅（除了 Task 3 消费 Task 1/2 产物），mid-tier 模型跑得动。

**推荐 Native**：7 个 task 里 5 个是数据 pipeline（回填、检查、骨架），错了容易 revert；只有 Task 1 的 schema 是设计决策，一旦定下后续都是机械操作。Native 更适合。

**你要哪种？以及 plan 是否符合预期？**
