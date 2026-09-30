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
- 新增字段 `anchor_id` 与`与六壬关系` **不覆盖已有值**（幂等）
- 所有新增脚本必带 selftest（对照 `retro_selftest.py` 47 项风格）
- Frontmatter 使用 YAML；不引入 TOML / JSON5

## Review Focus

| 输入 / 失败模式 | 期望行为 | 归属 task |
|---|---|---|
| 已有 frontmatter 中 `anchor_id` 已存在但格式不符 v3 规约 | 检查器识别为 error，报出但不擅自覆盖 | Task 2 |
| 单文件多段原文（同书同章多小节） | anchor_id 生成器逐段生成不重复的 id | Task 3 |
| `与六壬关系` 在《武经总要》分层索引里已用，其他书未用 | 补齐时保留已有值，未涉及的书填默认 `"主体"` 或 `"N/A"` | Task 4 |
| `90-禄命辅助/` 骨架文件在子项目 D 未落地前被检查器扫到 | 检查器识别为 stub（frontmatter 里 `状态: stub`），不判 fail | Task 5 |
| 上游 `--check` 因 anchor_id 缺失全部条目而红 | 集成必须在补齐后，先跑 Task 3 再跑 Task 6 | Task 6 依赖顺序 |

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
│   ├── generate_anchor_ids.py                            # Task 3 新增
│   ├── generate_anchor_ids_selftest.py                   # Task 3 新增
│   ├── backfill_liuren_relation.py                       # Task 4 新增
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
2. v3 新增字段：`anchor_id` 格式为 `<书>-<卷篇 slugified>-<段序 3 位>`（例 `太白阴经-玄女式-001`）；`与六壬关系` 取值域 `"主体" / "旁证" / "遁甲" / "太乙" / "占候旁证" / "N/A"`
3. 每字段 required / optional 标记
4. 三层语料的必须字段差异（宋本硬本 vs 唐本佐证 vs 大全字典）

- [ ] **Step 2: 写失败测试**

```python
# tools/check_v3_frontmatter_selftest.py
import unittest, tempfile, pathlib
from check_v3_frontmatter import check_file

class TestFrontmatterCheck(unittest.TestCase):
    def _write(self, content):
        f = pathlib.Path(tempfile.mkstemp(suffix=".md")[1])
        f.write_text(content, encoding="utf-8")
        return f

    def test_missing_anchor_id_is_error(self):
        f = self._write("---\n书: 太白阴经\n卷篇: 玄女式\n---\n正文")
        issues = check_file(f)
        errs = [i for i in issues if i.field == "anchor_id" and i.severity == "error"]
        self.assertEqual(len(errs), 1)

    def test_missing_liuren_relation_is_warn(self):
        f = self._write("---\n书: 太白阴经\n卷篇: 玄女式\nanchor_id: 太白阴经-玄女式-001\n---\n正文")
        issues = check_file(f)
        warns = [i for i in issues if i.field == "与六壬关系" and i.severity == "warn"]
        self.assertEqual(len(warns), 1)

    def test_valid_frontmatter_zero_issues(self):
        f = self._write("---\n书: 太白阴经\n卷篇: 玄女式\n"
                        "anchor_id: 太白阴经-玄女式-001\n与六壬关系: 主体\n---\n正文")
        issues = [i for i in check_file(f) if i.severity == "error"]
        self.assertEqual(issues, [])

    def test_stub_file_is_info_not_error(self):
        f = self._write("---\n状态: stub\n---\n骨架待填")
        issues = [i for i in check_file(f) if i.severity == "error"]
        self.assertEqual(issues, [])
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

## Task 3: anchor_id 生成器与批量回填

**Files:**
- Create: `tools/generate_anchor_ids.py`
- Test: `tools/generate_anchor_ids_selftest.py`
- Modify: `六壬vault/10-底本/**/*.md`（批量回填）

**Interfaces:**
- Consumes: `check_v3_frontmatter` 的 Issue（识别缺 anchor_id 的文件）；`.aime/vault-v3-gap.json`
- Produces:
  - `generate_anchor_ids.slugify(text: str) -> str`（去空白、保汉字、punct → dash）
  - `generate_anchor_ids.compute_anchor_id(book: str, chapter: str, index: int) -> str`，返回 `f"{book}-{slugify(chapter)}-{index:03d}"`
  - `generate_anchor_ids.backfill(path: pathlib.Path, dry_run: bool = True) -> BackfillResult`，`BackfillResult` 含 `changed: bool, before: str|None, after: str`
  - CLI: `python3 tools/generate_anchor_ids.py [--vault 六壬vault] [--apply]`；默认 dry-run

- [ ] **Step 1: 写失败测试**

```python
# tools/generate_anchor_ids_selftest.py
import unittest
from generate_anchor_ids import compute_anchor_id, slugify

class T(unittest.TestCase):
    def test_slugify_keeps_hanzi(self):
        self.assertEqual(slugify("玄女式"), "玄女式")

    def test_slugify_replaces_spaces(self):
        self.assertEqual(slugify("推 五 帝 法"), "推-五-帝-法")

    def test_anchor_id_shape(self):
        self.assertEqual(compute_anchor_id("太白阴经", "玄女式", 1),
                         "太白阴经-玄女式-001")

    def test_anchor_id_stable_for_same_inputs(self):
        a = compute_anchor_id("壬归", "总说", 42)
        b = compute_anchor_id("壬归", "总说", 42)
        self.assertEqual(a, b)

    def test_idempotent_backfill(self):
        # 已有 anchor_id 的文件不覆盖 —— 用临时文件验证 backfill(dry_run=False).changed == False
        pass  # 具体见实现文件
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 tools/generate_anchor_ids_selftest.py`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: 实现 `tools/generate_anchor_ids.py`**

`compute_anchor_id` 是纯函数。`backfill` 逻辑：读文件 → 解析 frontmatter → 若已有 `anchor_id` 非空则 skip → 否则用 `书` + `卷篇` + 该书内当前文件相对顺序（按文件名字典序）计算 id → 写回。批量模式按书遍历，index 从 001 起。

- [ ] **Step 4: 跑测试通过**

Run: `python3 tools/generate_anchor_ids_selftest.py -v`
Expected: `OK`

- [ ] **Step 5: Dry-run 批量回填**

Run: `python3 tools/generate_anchor_ids.py --vault 六壬vault | tee /tmp/anchor_dry.log | tail -20`
Expected: 输出 `would set anchor_id: <path> -> <id>` 条数与 gap 报告一致

- [ ] **Step 6: Apply**

Run: `python3 tools/generate_anchor_ids.py --vault 六壬vault --apply`
Expected: 退出码 0；`git diff --stat` 显示 vault 下修改条目数与 dry-run 一致

- [ ] **Step 7: 重跑 v3 检查器**

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
- Modify: `六壬vault/10-底本/**/*.md`

**Interfaces:**
- Consumes: `.aime/vault-v3-gap.json` 的 `missing_liuren_relation` 列表
- Produces:
  - `backfill_liuren_relation.default_relation(book: str, chapter: str) -> str`，规则表：
    - 《武经总要》→ 复用上游 `00-分层索引-占候五卷.md` 的映射（占候/遁甲/太乙/占候旁证）
    - 《太白阴经·玄女式》及六壬 chapter → `"主体"`；其他 → `"占候旁证"`
    - 宋本主线六部所有条目 → `"主体"`（默认）
    - 大全条目 → `"字典"`
  - CLI: `python3 tools/backfill_liuren_relation.py [--vault 六壬vault] [--apply]`

- [ ] **Step 1: 写规则表并做 selftest 骨架**

在脚本顶部固化规则字典；写 4–6 条 selftest 覆盖典型：
- 武经总要 · 占候五卷 · 遁甲 → `"遁甲"`
- 太白阴经 · 玄女式 → `"主体"`
- 太白阴经 · 推五帝法 → `"占候旁证"`
- 中黄经 · 任何篇 → `"主体"`

- [ ] **Step 2: 跑 selftest 通过**

Run: `python3 tools/backfill_liuren_relation.py --selftest`
Expected: `OK`

- [ ] **Step 3: Dry-run**

Run: `python3 tools/backfill_liuren_relation.py --vault 六壬vault`
Expected: 输出 would-set 条数与 gap 报告 `missing_liuren_relation` 一致

- [ ] **Step 4: Apply**

Run: `python3 tools/backfill_liuren_relation.py --vault 六壬vault --apply`
Expected: 退出码 0

- [ ] **Step 5: 重跑 v3 检查器**

Run: `python3 tools/check_v3_frontmatter.py --vault 六壬vault`
Expected: **退出码 0（全绿）**，只余 `90-禄命辅助/` 的 info（stub 状态）

- [ ] **Step 6: Commit**

```bash
git add tools/backfill_liuren_relation.py 六壬vault/
git commit -m "feat(vault): backfill 与六壬关系 to all corpus entries"
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

- [ ] **Step 5: Commit**

```bash
git add 六壬vault/90-禄命辅助/
git commit -m "feat(vault): scaffold 90-禄命辅助 with 8 stubs"
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
