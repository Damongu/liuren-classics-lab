# Task 1 Implementer Report — v3 frontmatter 规约与检查器

- **Status:** DONE_WITH_CONCERNS
- **Commit:** `5de1a9ca40b7e2d2ee6b81998473f8f390d3cdac` — `feat(vault): add v3 frontmatter schema and checker`
- **Branch:** `pi`（未 push，等待 controller review）

## 交付物

- `docs/vault-frontmatter-schema.md` — v3 schema 文档（上游沿用字段、v3 新增字段、断案专用字段、三层语料差异、stub 状态、检查器速查表）
- `tools/check_v3_frontmatter.py` — 检查器实现
- `tools/check_v3_frontmatter_selftest.py` — unittest selftest，7 条

## TDD 证据

### RED（Step 3）

```
$ python3 tools/check_v3_frontmatter_selftest.py
Traceback (most recent call last):
  File "/workspace/ws1/liuren-classics-lab/tools/check_v3_frontmatter_selftest.py", line 18, in <module>
    from check_v3_frontmatter import check_file  # noqa: E402
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ModuleNotFoundError: No module named 'check_v3_frontmatter'
```

### GREEN（Step 5）

```
$ python3 tools/check_v3_frontmatter_selftest.py
test_anchor_id_format_regex ... ok
test_invalid_author_is_error ... ok
test_missing_anchor_id_is_error ... ok
test_missing_author_is_error ... ok
test_missing_liuren_relation_is_warn ... ok
test_stub_file_is_info_not_error ... ok
test_valid_frontmatter_zero_errors ... ok

----------------------------------------------------------------------
Ran 7 tests in 0.003s

OK
```

7/7 通过（plan 里预计 4 条，实际按 spec 里第 2 步复制的 7 条全绿）。

## 实盘 CLI 冒烟

`python3 tools/check_v3_frontmatter.py --vault 六壬vault --quiet` →
`1680 error / 802 warn / 0 info`；`error 分布：anchor_id=840, 作者=840`；退出码 2。
这就是 gap 报告 Task 2 要吃的输入。JSON 模式：`--json` 打出合法 JSON，
`summary + issues[]` 结构，第一条 issue 采样如下：

```
{'path': '六壬vault/10-底本/六壬大全/01-第一册 起例/002-十干寄宫.md',
 'field': 'anchor_id', 'severity': 'error', 'message': '缺 anchor_id'}
```

## 实现要点

- `Issue = namedtuple("Issue", "path field severity message")`，`severity ∈ {error, warn, info}`。
- `check_file(path)`：读 md → 用 `split_fm` 拆 frontmatter → `yaml.safe_load` 解析 → 逐字段校验；
  `状态: stub` 命中时，`_is_stub` 使全部 v3 检查 `sev()` 降为 info。
- `check_vault(root)`：遍历 `10-底本/**/*.md` 与 `90-禄命辅助/**/*.md`，
  跳过 `00-`/`_` 前缀的目录卡与辅助文件（与 `tools/selfcheck.py` 惯例一致）。
- anchor_id 正则：`^[^-]+-[^-]+-\d{3}$`（要求两个分隔 `-` + 末尾三位数字；花名与卷篇可含中文）。
- `作者` 严格枚举校验；`与六壬关系` 目前仅判缺失 warn，**不做值域校验**（见 Concerns）。
- CLI：`python3 tools/check_v3_frontmatter.py [--vault PATH] [--json] [--quiet]`；无 error → 0，有 error → 2。
- PyYAML 已可用（`yaml.__version__ == 6.0.3`），不引新依赖。

## Concerns（DONE_WITH_CONCERNS 原因）

1. **上游 `build_vault.py` 已写入 `与六壬关系` 字段，但取值域与 v3 spec 不一致。**
   - `六壬vault/10-底本/唐宋层/武经总要/武经总要-后集卷二十 占候五 入式课加临永用例.md`
     的 frontmatter 有 `与六壬关系: 本体规则`；而 v3 spec 规定枚举是
     `主体 / 旁证 / 遁甲 / 太乙 / 占候旁证 / N/A / 字典`。
   - 也就是说：**upstream 已经在写 v3 命名字段但值不符 v3 spec**。
   - 本 task 只让 checker 在 `与六壬关系` 缺失时判 warn，**没有对既有值做枚举校验**，
     避免与 Task 4（`backfill_liuren_relation.py`）撞车。schema 文档里明确了 v3 枚举，
     Task 4 会用规则表把武经/太白等既有值收敛到 v3 枚举后，再考虑给 checker 加严格
     枚举校验（可在 Task 4 步骤里以一行 `if relation not in VALID_RELATIONS` 补上）。
   - Checker 代码里已经列了 `VALID_RELATIONS`，注释解释了为何暂不启用。
2. **anchor_id 正则容忍中文：** 采用 `^[^-]+-[^-]+-\d{3}$`（依 task prompt 明写），
   花名段和卷篇段允许任何非 `-` 字符（含中文与空格）。对 `太白-玄女式-001`、
   `邵彦和-01-韩太守占祈雪-001` 等示例都可通过；对含 `-` 的卷篇名可能过严
   （例如 `推-五-帝-法` slugify 后会形成多段），Task 3a 的 slugify 需要在
   实现时约定「把内部空格换成 `-` 但不制造总段数 > 3」的形式，或 Task 3a 完成
   后再回来放宽本正则。**已在 schema 文档中把正则明写出来**，Task 3a 需就此对齐。
3. **测试条数：** plan Step 5 预期 `Ran 4 tests ... OK`，但 plan Step 2 里的测试
   源码有 7 条 test case。我按 prompt「Copy verbatim」，全部收录，实际 7 tests。
   与 plan step 5 的文字预期不一致，但与 plan step 2 的源码一致；未视为阻塞。

## 未做（依据 task prompt 明令）

- 未修改任何 vault 文件、上游脚本或 `一键部署.sh`。
- 未 `git push`。
- 未 dispatch 子 agent。
