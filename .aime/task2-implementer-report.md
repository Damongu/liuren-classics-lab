# Task 2 Implementer Report — vault v3 gap 快照

**Task:** 生成 vault 现状 gap 报告（Plan Task 2）
**Branch:** `pi`
**Commit:** `379a31d24e4553c1e55368220de161dbd608d36f`
**Subject:** `docs(vault): snapshot v3 frontmatter gap report`
**Status:** DONE

## 执行摘要

按 Plan Task 2 三步执行完毕：

1. **Step 1 · 跑检查器 →** `python3 tools/check_v3_frontmatter.py --vault 六壬vault --json > .aime/vault-v3-gap.json`，退出码 **2**，stdout 是有效 JSON（`vault` / `summary` / `issues` 三键顶层结构）。summary 与 Task 1 report 一致：`total 2482 / error 1680 / warn 802 / info 0`。
2. **Step 2 · 生成人读报告 →** 因渲染逻辑超过 30 行，落到 `tools/render_gap_report.py`（约 150 行，含 argparse / find fallback / 按书聚合 / 输出模板），产物为 `docs/vault-v3-gap-report-2026-09-30.md`（约 1.7 KB）。
3. **Step 3 · Commit →** 单个 commit 收纳三份新增文件；未 push（等 controller 统一 push）。

## 关键发现

- **v3 覆盖率极低**：`10-底本/` 共 872 md，仅 **32 个**完全合规，覆盖率 **3.67%**。
- **error 结构**：1680 条 error 全部由 `anchor_id`（840）+ `作者`（840）两字段的缺失贡献，且这 840 个文件两个字段同时缺——即每缺 anchor_id 必缺 作者。**未检出任何格式违规或枚举违规**（no `anchor_id 格式错误`、no `作者不在花名枚举`）。
- **warn 结构**：802 条 warn 全部是 `与六壬关系` 缺失。分布如下：
  - 六壬大全 257 / 六壬心镜 185 / 六壬断案 222 / 卜筮书残卷 1 / 占事略决 36 / 壬归 43 / 太白阴经 19 / 景祐 39
  - **武经总要 0 条** → 上游 `build_vault.py` 已给武经写入细粒度 `与六壬关系` 值，Task 4 幂等回填只需跳过。这是本次快照对 Task 4 最有价值的信号。
- **按书 breakdown**（详见报告 markdown 表格）：

  | 书 | 总 md | 有缺失 | 缺 anchor_id | 缺 作者 | 缺 与六壬关系 |
  | --- | ---: | ---: | ---: | ---: | ---: |
  | 六壬大全 | 257 | 257 | 257 | 257 | 257 |
  | 六壬心镜 | 189 | 185 | 185 | 185 | 185 |
  | 六壬断案 | 226 | 222 | 222 | 222 | 222 |
  | 卜筮书残卷 | 5 | 2 | 2 | 2 | 1 |
  | 占事略决 | 40 | 36 | 36 | 36 | 36 |
  | 壬归 | 47 | 43 | 43 | 43 | 43 |
  | 太白阴经 | 23 | 19 | 19 | 19 | 19 |
  | 景祐六壬神定经 | 43 | 39 | 39 | 39 | 39 |
  | 武经总要 | 42 | 37 | 37 | 37 | 0 |
  | **合计** | **872** | **840** | **840** | **840** | **802** |

- **JSON 结构与 Plan 描述略有差异**：Plan Task 2 描述期望 `{"missing_anchor_id":[...], "missing_liuren_relation":[...], "other_errors":[...]}`，实际 Task 1 checker 输出的是 `{vault, summary, issues:[{path,field,severity,message}...]}`。这是**更通用、更结构化**的格式，Task 3a/3b/4 只需按 field 过滤即可等价拿到 Plan 描述的三张列表。不构成阻塞——已在报告"Task 消费提示"章节和 JSON schema 附录里明确指出。
- **32 clean 文件按书分布**（提示这些是已被上游 `build_vault.py` 或人工写好的 header/README/骨架）：太白/断案/壬归/心镜/景祐/略决 各 4，武经 5，卜筮残 3。Task 3a/3b 回填时应对齐现有 anchor_id 格式（若有）以确保幂等。

## 产物

- `.aime/vault-v3-gap.json` — 机器可读原始快照
- `docs/vault-v3-gap-report-2026-09-30.md` — 人读报告
- `tools/render_gap_report.py` — 渲染脚本；下次 vault 变更后可 `python3 tools/render_gap_report.py` 一键刷新，无需手写 markdown

## Concerns

- 无严重 concern。渲染脚本没有 selftest（Plan Task 2 未强制要求），因为逻辑相当于 Counter 聚合 + 模板拼串；下游 Task 3 若消费本快照，只依赖 Task 1 checker 的 JSON schema，不依赖 render 脚本。
- 报告的 `按书统计` 表格用了目录名（`六壬大全` / `武经总要` 等），并在同一行附花名列（`大全查手` / `武经` 等）方便和 Global Constraints 的花名映射表对照——这是我在 Plan 要求"按书（花名/上游书名任选）"的基础上二选合一。
