# Task 3b Implementer Report — 断案段级拆分与 anchor_id

**Date:** 2026-09-30
**Branch:** `pi`
**Commit:** `39362c8 feat(vault): split 断案 by author (邵彦和/阿甲/林景行) with segment-level anchors`

## Status
DONE. All 9 plan steps executed. TDD RED/GREEN confirmed. Selftest 11/11 pass. v3 checker: 0 error / 802 warn (与六壬关系 — Task 4 前置)。

## Deliverables

- `tools/split_duanan_by_author.py`（实现，复用 `generate_anchor_ids.slugify/compute_anchor_id/book_to_penname`）
- `tools/split_duanan_by_author_selftest.py`（11 条测试，5 条 plan 规定 + 3 条真实文件形态 + 3 条 backfill 集成）
- `六壬vault/10-底本/唐宋层/六壬断案/*.md` × 222 条 frontmatter 更新（正文未动）

## TDD 证据

### RED（Step 2）
```
$ python3 tools/split_duanan_by_author_selftest.py
ModuleNotFoundError: No module named 'split_duanan_by_author'
```

### GREEN（Step 4）
```
Ran 11 tests in 0.007s
OK
```

## 段边界规则实现细节

`detect_segments()` 使用正则 `(?:(?<=\n)|(?<=。)|(?<=\A))(爱函按|缘生谛)([：:])`。前置必须是：文首、行首、或中文句号 `。`。这与 plan 规定 body_1（`空。缘生谛：占于...`）在同一行也要切段的要求一致。同时 `false_match_not_at_line_start` 用例的 `此处提到缘生谛校本云云` 因无冒号不触发。所有 8 条边界测试通过。

## 真实文件 dry-run 输出片段（Step 5）

```
>>> 六壬断案-01 韩太守占祈雪（第一章 天时）.md
  main_anchor_id = 邵彦和-01-韩太守占祈雪-第一章-天时-001
  含内嵌注家 = ['林景行', '阿甲']
  段数 = 3
    - [邵彦和] 邵彦和-01-韩太守占祈雪-第一章-天时-001  lines 0..0
    - [林景行] 林景行-01-韩太守占祈雪-第一章-天时-001  lines 0..23
    - [阿甲]   阿甲-01-韩太守占祈雪-第一章-天时-001    lines 24..24

>>> 六壬断案-02 某占晴雨（第一章 天时）.md
  main_anchor_id = 邵彦和-02-某占晴雨-第一章-天时-001
  含内嵌注家 = []
  段数 = 1
    - [邵彦和] 邵彦和-02-某占晴雨-第一章-天时-001  lines 0..21

>>> 六壬断案-135 林子成丙辰生四十八岁占平生养息（第八章 财产）.md
  main_anchor_id = 邵彦和-135-林子成丙辰生四十八岁占平生养息-第八章-财产-001
  含内嵌注家 = ['林景行', '阿甲']
  段数 = 7 （5 段林景行 + 1 段阿甲）
```

## 段数统计（全量，Step 6）

| 作者 | 段数 |
|---|---|
| 邵彦和 | 222（每 md 主段 × 1，与 md 总数一致）|
| 阿甲 | 223 |
| 林景行 | 319 |
| **合计** | **764** |

含内嵌注家分布（209 条 md）：
- 林景行+阿甲: 158
- 林景行: 30
- 阿甲: 21
- 单段（仅邵彦和）: 13

## 幂等 & 影响范围

- `git -c core.quotepath=off diff --name-only HEAD~1` 全部落在 `六壬vault/10-底本/唐宋层/六壬断案/*.md`。
- 只加 5 类字段：`anchor_id / 作者 / 含内嵌注家 / 段索引:`（外加 4 子行 per segment）；上游既有字段完全保序。
- 正文 body（含 `> ⚠️ 机器切分的录文…` blockquote）字符级未改动。

## v3 Checker 结果（Step 8）

```
$ python3 tools/check_v3_frontmatter.py --vault 六壬vault --quiet
v3 frontmatter 检查：0 error / 802 warn / 0 info
```

- `anchor_id` 与 `作者` error 数 = 0（Task 3a + 3b 合力全绿）
- 802 warn 全部为 `与六壬关系` 缺失 → Task 4 处理
- 与 Plan Task 3b Step 8 预期一致。

## Concerns

1. **段边界"loose semantic"**：`缘生谛：` 的短行内 gloss（如"缘生谛：申，象鹅。"）会把后续 `邵先生曰：` / `林曰：` 等段落也吃进林景行段，直到下一个 marker 才收尾。这是 plan 规定的简化（每段直吃到下一个 marker），可能导致 `段索引` 里的 `end` 覆盖到不属于该注家的原辞。语义精确切分（`。` 结束短 gloss）留待后续扩展。
2. `六壬断案-135` 有 5 段林景行 vs 上游 grep 显示 `缘生谛：` 出现 5 次 → 一致，验证 mid-line 匹配（`。缘生谛：`）落地成功。
3. `_污染位置表.md` / `00-*.md` 通过前缀 skip 规则被自动排除，未被处理。
4. 未有任何 md 因"已有 anchor_id" 被跳过 → Task 3a 的 `--skip-book 六壬断案` 生效，无覆盖冲突。

## 报告文件路径

`/workspace/ws1/liuren-classics-lab/.aime/task3b-implementer-report.md`
