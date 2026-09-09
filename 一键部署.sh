#!/usr/bin/env bash
#
# 六壬知识库 · 一键部署
#
# 做四件事：
#   1. 装依赖（opencc / python-docx / olefile / PyMuPDF）
#   2. 从 sources/ 七部原书重建 vault
#   3. 扫清校污染
#   4. 自检 + 跑排盘器测试
#
# 用法：
#   ./一键部署.sh              重建全部
#   ./一键部署.sh --check      只自检，不动 vault
#   ./一键部署.sh --book 壬归   只重建一部书
#
# 注意：vault 已经是构建好的。这个脚本是给你**重建**用的，
#      日常读书不需要跑它 —— 直接用 Obsidian 打开 六壬vault/ 就行。

set -uo pipefail
cd "$(dirname "$0")"
export PYTHONUTF8=1

BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'
GRN=$'\033[32m'; YEL=$'\033[33m'; RST=$'\033[0m'

say()  { printf '%s\n' "$*"; }
step() { printf '\n%s▸ %s%s\n' "$BOLD" "$*" "$RST"; }
ok()   { printf '  %s✓%s %s\n' "$GRN" "$RST" "$*"; }
warn() { printf '  %s!%s %s\n' "$YEL" "$RST" "$*"; }
die()  { printf '\n%s✗ %s%s\n' "$RED" "$*" "$RST"; exit 1; }

ONLY_CHECK=0
BOOK_ARG=()
while [ $# -gt 0 ]; do
  case "$1" in
    --check) ONLY_CHECK=1; shift ;;
    --book)  BOOK_ARG=(--book "$2"); shift 2 ;;
    -h|--help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "不认识的参数：$1（试 --help）" ;;
  esac
done

cat <<'BANNER'

  六壬知识库 · 一键部署
  ─────────────────────────────────────────
  唐宋层七部书 → Obsidian 可互校条目

BANNER

# ---------------------------------------------------------------- 0. Python
step "检查 Python"
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then
    v=$("$c" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null) || continue
    maj=${v%%.*}; min=${v##*.}
    if [ "$maj" -eq 3 ] && [ "$min" -ge 8 ]; then PY="$c"; break; fi
  fi
done
[ -n "$PY" ] || die "需要 Python 3.8+。macOS 装法：brew install python3"
ok "$PY ($($PY -V 2>&1))"

# ---------------------------------------------------------------- 1. 自检模式
if [ "$ONLY_CHECK" -eq 1 ]; then
  step "自检"
  $PY tools/selfcheck.py
  exit $?
fi

# ---------------------------------------------------------------- 2. 依赖
step "检查依赖"
need_install=()
$PY -c 'import opencc' 2>/dev/null && ok "opencc 已装" || need_install+=(opencc)
$PY -c 'import docx'   2>/dev/null && ok "python-docx 已装" || need_install+=(python-docx)
$PY -c 'import olefile' 2>/dev/null && ok "olefile 已装" || need_install+=(olefile)
$PY -c 'import pymupdf' 2>/dev/null && ok "PyMuPDF 已装" || need_install+=(PyMuPDF)

if [ ${#need_install[@]} -gt 0 ]; then
  warn "缺 ${need_install[*]}，正在装…"
  if ! $PY -m pip install --quiet "${need_install[@]}" 2>/dev/null; then
    $PY -m pip install --quiet --user "${need_install[@]}" 2>/dev/null \
      || $PY -m pip install --quiet --break-system-packages "${need_install[@]}" 2>/dev/null \
      || warn "自动安装失败。手动跑：$PY -m pip install ${need_install[*]}"
  fi
  $PY -c 'import opencc' 2>/dev/null && ok "opencc" \
    || warn "opencc 仍缺失 —— 繁简转换会跳过，条目保留繁体（可用，但检索不便）"
  $PY -c 'import docx' 2>/dev/null && ok "python-docx" \
    || warn "python-docx 仍缺失 —— 《景祐六壬神定经》(.docx) 无法导入"
  $PY -c 'import olefile' 2>/dev/null && ok "olefile" \
    || warn "olefile 仍缺失 —— 《壬归》(.doc) 无法导入"
  $PY -c 'import pymupdf' 2>/dev/null && ok "PyMuPDF" \
    || warn "PyMuPDF 仍缺失 —— 部分中文 PDF 无法回退抽取"
fi

# ---------------------------------------------------------------- 3. 源文件
step "检查源文件"
[ -d sources ] || die "找不到 sources/ 目录"
missing=0
while IFS= read -r f; do
  if [ -f "sources/$f" ]; then
    ok "$f"
  else
    warn "缺 $f"
    missing=$((missing+1))
  fi
done <<'FILES'
神机制敌太白阴经.pdf
占事略決_中文正文_精校排版.pdf
景祐六壬神定經_繁體整理稿.docx
武經總要_四十卷_繁體易讀版.txt
大六壬心镜_完整整理文字版.txt
大六壬断案（缘生谛校注版）.pdf
宋-壬归-打印整理版.doc
FILES
[ "$missing" -eq 0 ] || warn "$missing 个源文件缺失，对应的书会跳过"

# ---------------------------------------------------------------- 4. 构建
step "构建 vault"
$PY tools/build_vault.py --force "${BOOK_ARG[@]+"${BOOK_ARG[@]}"}" \
  || die "构建失败。单独跑 $PY tools/build_vault.py --dry-run 看详情"

# ---------------------------------------------------------------- 5. 污染标记
step "扫清校污染"
$PY tools/mark_pollution.py --all --clear >/dev/null 2>&1
$PY tools/mark_pollution.py --all || warn "污染标记异常，vault 仍可用"

# ---------------------------------------------------------------- 6. 排盘器
step "排盘器自测"
if [ -d liuren-paipan ]; then
  if (cd liuren-paipan && $PY -m pytest -q tests/ 2>/dev/null); then
    ok "排盘器测试通过"
  elif (cd liuren-paipan && $PY tests/test_book_cases.py 2>/dev/null); then
    ok "排盘器测试通过"
  else
    warn "排盘器测试没跑起来（不影响读书）。装 pytest：$PY -m pip install pytest"
  fi
else
  warn "没有 liuren-paipan 目录，跳过"
fi

# ---------------------------------------------------------------- 6b. 训练器
step "训练器自测（9 关出题与判分）"
if $PY tools/tutor_selftest.py; then
  ok "训练器 9 关出题正常"
else
  warn "训练器自测未通过（不影响读书，但 tutor.py 可能出不了题）"
fi

# ---------------------------------------------------------------- 6c. 复盘引擎
step "复盘引擎自测（十条规则的边界用例）"
if $PY tools/retro_selftest.py >/dev/null 2>&1; then
  ok "复盘规则边界正常（signal_log.py / retro.py 可用）"
else
  warn "复盘引擎自测未通过：自我迭代会退回「靠 agent 自觉」，请跑 $PY tools/retro_selftest.py 看详情"
fi

# ---------------------------------------------------------------- 7. 自检
step "自检"
$PY tools/selfcheck.py --quiet
rc=$?

# ---------------------------------------------------------------- 完成
cat <<EOF

${BOLD}部署完成。${RST}

下一步：
  ${BOLD}1.${RST} 打开 Obsidian → 「Open folder as vault」→ 选 ${BOLD}$(pwd)/六壬vault${RST}
  ${BOLD}2.${RST} 装两个插件（社区插件市场）：${BOLD}Dataview${RST}、${BOLD}Templater${RST}
     Dataview 必装 —— 「00-索引/证据面板」靠它出表
  ${BOLD}3.${RST} 从 ${BOLD}六壬vault/README.md${RST} 开始读

主工作面：${BOLD}50-校读笔记/对校矩阵-五个判别点.md${RST}
${DIM}读书时随手记问题 → 70-待查/待查清单.md${RST}

${BOLD}每节课两道闸门${RST}（agent 自己会跑，你只需知道它该跑）：
  开场 ${BOLD}$PY tools/retro.py --brief${RST}　收尾 ${BOLD}$PY tools/retro.py --close${RST}
${DIM}它凭什么会自己改进：README「二·五、它怎么自己发现问题」${RST}

EOF
exit $rc
