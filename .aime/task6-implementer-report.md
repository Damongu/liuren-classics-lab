# Task 6 Implementer Report

## Status
GREEN. Task 6 完成，local commit 已落地，未 push。

## Commit
- SHA: `4738268`
- Subject: `feat(check): integrate v3 frontmatter check into selfcheck`

## Selftest
- `python3 tools/selfcheck_v3_selftest.py -v` → **2/2 OK**
- 上游 `tools/check_v3_frontmatter_selftest.py -v` → **7/7 OK**（无回归）

## TDD 记录
- **RED**：先写 `tools/selfcheck_v3_selftest.py`（两条用例，subprocess 跑 `selfcheck.py --v3 --vault <tmp>`），跑得 FAIL（`--v3` 未被 argparse 识别）。
- **GREEN**：在 `tools/selfcheck.py` 里加 `--v3` 开关 + `check_v3()` 函数（延迟 `from check_v3_frontmatter import check_vault as v3_check_vault`）；无 `--v3` 时行为完全不变。跑 `python3 tools/selfcheck_v3_selftest.py -v` 通过 2/2。

## `一键部署.sh --check` 处理
走**方案 (b)**：在 `--check` 分支追加一步 `$PY tools/selfcheck.py --v3 --quiet`，用 `rc_base` / `rc_v3` 合并退出码（任一非零则非零，优先 base）。改动局部在原 `--check` 分支内，未动其他逻辑。E2E `./一键部署.sh --check` 输出保留原自检段，追加 `v3 frontmatter 检查：0 条 error, 0 条 warn, 27 条 info`，`底本条目合计：583 条` 仍打印。

## 端到端验证
- `./一键部署.sh --check` → exit 2（因原有 1 条断链 warn，属基线行为），v3 全绿 0/0/27。
- `python3 tools/selfcheck.py --v3 --quiet` → v3 汇总 0/0/27，exit 2（同因原 1 条断链 warn）。
- `python3 tools/selfcheck.py --quiet`（无 `--v3`）→ 与集成前完全一致：exit 2，1 条 warn，无 v3 段。

## Concerns
- Plan Step 6 期望 "退出 0"，但上游 vault 有一处**先存在**的双链断链 warn，导致 selfcheck 走 warn 分支返回 2。这是**基线**行为、与 v3 集成无关；v3 本身 0/0/27 全绿。若要整体绿，需修断链，属另外的任务范围。
- `--v3` 的汇总行 `v3 frontmatter 检查：N 条 error, M 条 warn, K 条 info` **强制打到 stdout**（不受 `--quiet` 抑制），方便外部脚本 grep；未打进 `Report.ok` 是刻意的（否则 `--quiet` 会吞掉）。

## 报告文件
`/workspace/ws1/liuren-classics-lab/.aime/task6-implementer-report.md`
