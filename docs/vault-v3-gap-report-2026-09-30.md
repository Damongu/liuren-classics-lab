# Vault v3 Frontmatter Gap 报告

- **快照时间**：2026-09-30
- **Vault 根**：`六壬vault`
- **检查器**：`tools/check_v3_frontmatter.py --vault 六壬vault --json`

## Executive Summary

当前 `10-底本/` 下共 **872** 个 md，v3 检查器报出 **1680 条 error / 802 条 warn / 0 条 info**；完全合规文件 **32** 个，v3 覆盖率 **3.67%**。

- 主要 error 集中在两个字段：`anchor_id`（缺失）与 `作者`（缺失），两者一一对应——即每个缺 anchor_id 的文件同时缺 作者。
- `与六壬关系` 大面积缺失（warn），需 Task 4 按规则表回填；**唯一例外**是《武经总要》——已由上游 `build_vault.py` 写入细粒度值（`本体规则 / 兵占背景` 等），Task 4 幂等跳过。
- 未见 `作者不在花名枚举` 或 `anchor_id 格式错误` 等其他类别 error；Task 1 检查器已能识别但当前 vault 未触发。

## 按书统计

| 书 (目录名) | 花名 (作者字段目标值) | 总 md | 有缺失的 md | 缺 anchor_id | 缺 作者 | 缺 与六壬关系 (warn) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 六壬大全 | 大全查手 | 257 | 257 | 257 | 257 | 257 |
| 六壬心镜 | 心镜 | 189 | 185 | 185 | 185 | 185 |
| 六壬断案 | 邵彦和/阿甲/林景行 | 226 | 222 | 222 | 222 | 222 |
| 卜筮书残卷 | 卜筮残 | 5 | 2 | 2 | 2 | 1 |
| 占事略决 | 略决 | 40 | 36 | 36 | 36 | 36 |
| 壬归 | 壬归 | 47 | 43 | 43 | 43 | 43 |
| 太白阴经 | 太白 | 23 | 19 | 19 | 19 | 19 |
| 景祐六壬神定经 | 景祐 | 43 | 39 | 39 | 39 | 39 |
| 武经总要 | 武经 | 42 | 37 | 37 | 37 | 0 |
| **合计** | — | **872** | **840** | **840** | **840** | **802** |

## 其他 error 类别

**无**。当前 error 全部由 `anchor_id` / `作者` 两个字段的缺失贡献；未检出格式违规或枚举违规。

## Task 消费提示

- Task 3a `generate_anchor_ids.py` 会消费本文件与 `.aime/vault-v3-gap.json`，为除《六壬断案》外的所有条目回填 `anchor_id` 与 `作者`。
- Task 3b `split_duanan_by_author.py` 处理《六壬断案》的段级拆分（邵彦和 / 阿甲 / 林景行）。
- Task 4 `backfill_liuren_relation.py` 消费 `与六壬关系` 的 warn 列表补齐字段。

## 附：完整 issue 明细

机器可读 JSON 位于 `.aime/vault-v3-gap.json`；字段名与结构：

```json
{"vault": "...", "summary": {"total": N, "error": N, "warn": N, "info": N,
 "error_by_field": {"anchor_id": N, "作者": N}},
 "issues": [{"path": "...", "field": "...", "severity": "error|warn|info", "message": "..."}]}
```

