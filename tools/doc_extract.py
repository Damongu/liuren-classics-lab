#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Word 97-2003 (.doc) 正文抽取器
==============================

环境里没有 antiword / catdoc / libreoffice，所以按 [MS-DOC] 规范
自己走一遍 piece table：FIB → Clx → PlcPcd → 逐 piece 解码。

比「整个文件按 UTF-16LE 硬解」可靠得多：后者会把格式表、样式名、
修订记录一起当正文抽出来，混进大量乱码，且丢失段落边界。

用法：
    python3 tools/doc_extract.py 某文件.doc            # 打印到 stdout
    python3 tools/doc_extract.py 某文件.doc out.txt    # 写文件
"""

import struct
import sys

import olefile


def extract(path: str) -> str:
    ole = olefile.OleFileIO(path)
    wd = ole.openstream("WordDocument").read()

    # --- FIB base：判断 piece table 在 0Table 还是 1Table
    # FibBase.flags1 位于偏移 0x000A，bit 9 (0x0200) = fWhichTblStm
    (flags1,) = struct.unpack_from("<H", wd, 0x000A)
    table_name = "1Table" if (flags1 & 0x0200) else "0Table"
    if not ole.exists(table_name):  # 少数文件标志位与实际不符
        table_name = "0Table" if table_name == "1Table" else "1Table"
    tbl = ole.openstream(table_name).read()

    # --- FibRgFcLcb97 中 fcClx / lcbClx 的绝对偏移
    fc_clx, lcb_clx = struct.unpack_from("<II", wd, 0x01A2)
    clx = tbl[fc_clx : fc_clx + lcb_clx]

    # --- 跳过 Clx 前部的 Prc 块（0x01 开头），定位 Pcdt（0x02 开头）
    i = 0
    while i < len(clx) and clx[i] == 0x01:
        (cb_grpprl,) = struct.unpack_from("<H", clx, i + 1)
        i += 3 + cb_grpprl
    if i >= len(clx) or clx[i] != 0x02:
        raise ValueError("Clx 中找不到 Pcdt（0x02）")

    (lcb_pcdt,) = struct.unpack_from("<I", clx, i + 1)
    plc = clx[i + 5 : i + 5 + lcb_pcdt]

    # --- PlcPcd = (n+1) 个 4 字节 CP + n 个 8 字节 Pcd
    n = (len(plc) - 4) // 12
    cps = list(struct.unpack_from("<%dI" % (n + 1), plc, 0))
    pcd_off = 4 * (n + 1)

    out = []
    for k in range(n):
        # Pcd: 2字节 flags, 4字节 fc, 2字节 prm
        fc = struct.unpack_from("<I", plc, pcd_off + k * 8 + 2)[0]
        n_chars = cps[k + 1] - cps[k]
        compressed = bool(fc & 0x40000000)  # bit 30
        real_fc = fc & 0x3FFFFFFF
        if compressed:
            # 单字节，cp1252 映射；中文文档正文一般不走这条
            raw = wd[real_fc // 2 : real_fc // 2 + n_chars]
            out.append(raw.decode("cp1252", errors="replace"))
        else:
            raw = wd[real_fc : real_fc + n_chars * 2]
            out.append(raw.decode("utf-16-le", errors="replace"))

    text = "".join(out)

    # --- 清理 Word 控制字符，段落边界统一成 \n
    repl = {
        "\r": "\n",  # 段落结束
        "\x07": "\n",  # 单元格/行结束
        "\x0b": "\n",  # 手动换行
        "\x0c": "\n",  # 分页
        "\x1e": "-",  # 不换行连字符
        "\x1f": "",  # 可选连字符
        "\x13": "",
        "\x14": "",
        "\x15": "",  # 域字符
        "\x01": "",
        "\x02": "",
        "\x05": "",
        "\x08": "",
        "\xa0": " ",
    }
    for a, b in repl.items():
        text = text.replace(a, b)

    lines, seen_blank = [], False
    for ln in text.split("\n"):
        ln = ln.strip()
        if ln:
            lines.append(ln)
            seen_blank = False
        elif not seen_blank:
            lines.append("")
            seen_blank = True
    return "\n".join(lines).strip() + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    result = extract(sys.argv[1])
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as f:
            f.write(result)
        cjk = sum(1 for c in result if "\u4e00" <= c <= "\u9fff")
        print(f"{sys.argv[2]}：{len(result)} 字符，其中汉字 {cjk}")
    else:
        sys.stdout.write(result)
