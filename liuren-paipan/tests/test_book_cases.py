"""底本课例回归测试：每条都能指回《六壬大全》原文。

跑法：python3 -m pytest tests -q      或      python3 tests/test_book_cases.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from liuren import Options, from_ganzhi, from_jia, from_time  # noqa: E402
from liuren.search import enumerate720, filter_courses  # noqa: E402

# (日干支, 时, 将, 期望初传, 期望课式关键字或None, 底本出处)
CASES_SHI_JIANG = [
    ("甲子", "卯", "子", "午", "元首", "第六册 元首课：甲子日卯时子将占，午加酉为用"),
    ("丁卯", "丑", "亥", "亥", "涉害", "第六册 涉害课：丁卯日丑时亥将占"),
    ("庚戌", "辰", "申", "辰", "涉害", "第六册 涉害课·察微：庚戌日辰时申将占"),
    ("甲午", "辰", "午", "辰", "涉害", "第六册 涉害课·缀瑕：甲午日辰时午将占"),
    ("丙辰", "卯", "辰", "亥", "别责", "第六册 别责课：丙辰日卯时辰将占，戌上亥发用"),
    ("甲寅", "辰", "丑", "丑", "八专", "第六册 八专课：甲寅日辰时丑将占，顺数三至丑"),
    ("丁未", "丑", "辰", None, "八专", "第六册 八专课：丁未日丑时辰将占，帷薄不修"),
    ("己未", "未", "酉", None, "八专", "第六册 八专课：己未日未时酉将占，独足格"),
    ("甲寅", "亥", "未", "戌", None, "第七册 斩关课：甲寅日亥时未将占，戌加寅为用"),
    ("壬午", "巳", "丑", "戌", None, "第七册 和美课：壬午日巳时丑将占，戌加寅为用"),
]

# (日干支, 天盘加地盘, 期望初传, 底本出处)
CASES_JIA = [
    ("甲辰", "戌", "寅", "子", "第十一册 第九十三法：乃择比为用，非涉害也，子申辰作三传"),
    ("甲戌", "子", "戌", "子", "第十一册 第九十三法：甲戌日干上辰，乃子加戌为用"),
    ("丁卯", "亥", "丑", "亥", "第六册 涉害课订讹：丁卯日丑加卯、亥加丑…取亥发用"),
]

# 底本只给三传不给时将者：该三传必须出现在该日十二局之中
# (日干支, 三传, 底本出处)
CASES_CHUAN = [
    ("戊子", "午卯子", "第六册 涉害课·比用格：戊子日午卯子，皆用比不用涉害"),
    ("壬戌", "申丑午", "第六册 涉害课·比用格：壬戌日申丑午"),
    ("庚子", "戌申午", "第六册 涉害课·比用格：庚子日戌申午"),
    ("乙卯", "亥酉未", "第六册 涉害课：乙卯日亥酉未／乙卯日寅时子将，亥加丑为用"),
    ("甲辰", "子申辰", "第十一册 第九十三法：三传子申辰生日"),
    ("甲戌", "子寅辰", "第六册 涉害课·比用格：甲戌日取子加戌，子生甲木比者为用"),
    ("甲午", "辰午申", "第六册 涉害课·缀瑕：六月甲午日辰时午将，辰加寅…缀瑕"),
]


def test_shi_jiang():
    for gz, shi, jiang, chu, keshi, src in CASES_SHI_JIANG:
        p = from_ganzhi(gz, shi, jiang)
        if chu:
            assert p.chuan[0] == chu, f"{gz}日{shi}时{jiang}将 初传应{chu}，得{p.chuan[0]}｜{src}"
        if keshi:
            assert keshi in p.keshi, f"{gz}日{shi}时{jiang}将 课式应含{keshi}，得{p.keshi}｜{src}"


def test_jia():
    for gz, t, d, chu, src in CASES_JIA:
        p = from_jia(gz, t, d)
        assert p.chuan[0] == chu, f"{gz}日{t}加{d} 初传应{chu}，得{p.chuan[0]}｜{src}"


# 底本明写"几重"的涉害算例：(日, 上神, 所临宫, 重数, 层, 出处)
SHEHAI_DEPTHS = [
    ("庚子", "午", "庚", 2, "kejing", "第六册涉害课订讹：午加庚金，前行历酉、辛金二重"),
    ("庚子", "戌", "子", 1, "kejing", "同上：戌加子水，前行历癸水一重"),
    ("丁卯", "丑", "卯", 1, "kejing", "同上：丑加卯木，前行历辰中乙木一重"),
    ("丁卯", "亥", "丑", 5, "kejing", "同上：亥加丑土，前行历辰、戊、未、己、戌土五重"),
    ("甲午", "申", "午", 1, "kejing", "第六册涉害课：申加午，丁火一重"),
    ("甲午", "辰", "寅", 1, "kejing", "第六册涉害课：辰加寅，卯木一重"),
    ("甲辰", "戌", "寅", 2, "kejing", "观月经：路涉前头一重卯木、二重乙木"),
    ("甲辰", "子", "辰", 4, "guanyue", "观月经：巳上戊土、未上未土、己土，前又戌土，共四重"),
]


def test_shehai_depths():
    """涉害重数必须和底本写的数字一样，不许只对结论不对过程。"""
    for gz, up, gong, want, table, src in SHEHAI_DEPTHS:
        p = from_jia(gz, up, gong, opts=Options(shehai_table=table))
        got = p.shehai_depth(up)
        assert got == want, f"{gz}日{up}加{gong}（{table}层）应{want}重，得{got}｜{src}"


def test_shehai_table_layers_differ():
    """巳是否兼计戊土 —— 课经层与观月经层的分歧，两层都要能算。"""
    a = from_jia("甲辰", "子", "辰", opts=Options(shehai_table="kejing"))
    b = from_jia("甲辰", "子", "辰", opts=Options(shehai_table="guanyue"))
    assert (a.shehai_depth("子"), b.shehai_depth("子")) == (3, 4)


def test_gengzi_shehai_divergence():
    """第六册涉害课订讹：庚子日午加庚，前行历酉辛二重为深，取午发用（纯涉害）。
    同册比用格却把庚子归入"皆用比，不用涉害"。底本自相矛盾，两说都要能算。"""
    pure = from_jia("庚子", "午", "庚", opts=Options(shehai_bihe=False))
    assert pure.chuan[0] == "午", pure.chuan
    biyong = from_jia("庚子", "午", "庚", opts=Options(shehai_bihe=True))
    assert biyong.chuan[0] == "戌" and biyong.divergences


def test_chuan_in_twelve_ju():
    for gz, chuan, src in CASES_CHUAN:
        hits = [r for r in filter_courses(enumerate720(), day_gz=gz)
                if "".join(r.chuan) == chuan]
        assert hits, f"{gz}日十二局中应有三传{chuan}｜{src}"


def test_yuanshou_dunkan():
    """第六册元首课：午上遁得庚金为官星 —— 验旬遁。"""
    p = from_ganzhi("甲子", "卯", "子")
    assert p.dun("午") == "庚"


def test_tianjiang_from_book():
    """第六册元首课明言午乘青龙、卯乘朱雀、酉乘太常、子乘天后 —— 验贵人默认表。"""
    p = from_ganzhi("甲子", "卯", "子")
    for zhi, jiang in [("午", "青龙"), ("卯", "朱雀"), ("酉", "太常"), ("子", "天后")]:
        assert p.jiang_on(zhi) == jiang, f"{zhi}应乘{jiang}，得{p.jiang_on(zhi)}"


# 第十册第三十八法「闭口卦」：地盘旬首上神乘玄武者，逐日枚举。
# 这批数据只涉天将，不涉三传，正好独立校验贵人表 + 顺逆 + 昼夜三件事。
XUANWU_38 = [
    ("甲子", "戌", "子", "both"), ("戊辰", "戌", "子", "both"),
    ("乙丑", "卯", "子", "昼"), ("乙丑", "亥", "子", "夜"),
    ("庚午", "戌", "子", "both"), ("庚午", "辰", "子", "both"),
    ("己巳", "卯", "子", "昼"), ("己巳", "亥", "子", "夜"),
    ("甲申", "戌", "申", "both"), ("戊子", "辰", "申", "both"),
    ("庚寅", "辰", "申", "both"), ("乙酉", "亥", "申", "夜"),
    ("乙酉", "卯", "申", "昼"), ("丙戌", "子", "申", "夜"),
    ("丙戌", "午", "申", "夜"), ("乙亥", "巳", "戌", "夜"),
    ("己卯", "卯", "戌", "昼"),
]


def test_xuanwu_38fa():
    for gz, t, d, dn in XUANWU_38:
        for x in (["昼", "夜"] if dn == "both" else [dn]):
            p = from_jia(gz, t, d, daynight=x)
            assert p.jiang_on(t) == "玄武", \
                f"第三十八法：{gz}日{t}加{d}{x}应乘玄武，得{p.jiang_on(t)}"


def test_book_counts():
    """底本可数自述：720 总数、别责 9 课、八专日五除癸丑、独足格唯一。"""
    rows = enumerate720()
    assert len(rows) == 720
    assert len(filter_courses(rows, keshi="别责")) == 9
    assert sorted({r.day_gz for r in filter_courses(rows, keshi="八专")}) == \
        sorted(["丁未", "己未", "庚申", "甲寅"])
    dz = [r for r in rows if r.day_gz == "己未" and r.keshi == "八专"
          and len(set(r.chuan)) == 1]
    assert len(dz) == 1


def test_fu_fan_yin():
    """伏吟 60、返吟 60：将加时同位／冲位。"""
    rows = enumerate720()
    assert len(filter_courses(rows, keshi="伏吟")) == 60
    assert len(filter_courses(rows, keshi="返吟")) == 60
    assert all(r.k == 0 for r in filter_courses(rows, keshi="伏吟"))
    assert all(r.k == 6 for r in filter_courses(rows, keshi="返吟"))


def test_jigong():
    """第一册十干寄宫：甲寅乙辰丙戊巳丁己未庚申辛戌壬亥癸丑。"""
    from liuren.ganzhi import JIGONG
    assert JIGONG == {"甲": "寅", "乙": "辰", "丙": "巳", "丁": "未", "戊": "巳",
                      "己": "未", "庚": "申", "辛": "戌", "壬": "亥", "癸": "丑"}


def test_real_time_lmt():
    """地方平太阳时：成都比东八区钟表时慢约 64 分钟，跨时辰边界要体现。"""
    p = from_time(datetime(2026, 9, 7, 14, 30), "成都")
    assert p.place.lmt_offset_minutes < -60
    assert p.shi == "未"          # 钟表 14:30，LMT 13:26 → 未时
    p2 = from_time(datetime(2026, 9, 7, 14, 30), "上海")
    assert p2.shi == "未"
    p3 = from_time(datetime(2026, 9, 7, 15, 10), "上海")
    assert p3.shi == "申"          # 上海 LMT ≈ 15:06 → 申时；成都同刻仍是未
    assert from_time(datetime(2026, 9, 7, 15, 10), "成都").shi == "未"


def test_zhongqi_huanjiang():
    """中气换将：处暑（约 8/23）后用巳将，处暑前用午将。"""
    a = from_time(datetime(2026, 8, 20, 12, 0), "开封")
    b = from_time(datetime(2026, 8, 26, 12, 0), "开封")
    assert a.jiang == "午" and b.jiang == "巳", (a.jiang, b.jiang)


def test_options_divergence_recorded():
    """涉害比用格：两说都要留痕，不许静默。"""
    on = from_ganzhi("庚子", "戌", "申", opts=Options(shehai_bihe=True))
    off = from_ganzhi("庚子", "戌", "申", opts=Options(shehai_bihe=False))
    assert on.chuan[0] != off.chuan[0]
    assert on.divergences and off.divergences
    assert on.divergences[0]["另一说"] == off.chuan[0]


def test_guiren_tables_differ():
    book = from_ganzhi("甲子", "卯", "子", opts=Options(guiren="book"))
    common = from_ganzhi("甲子", "卯", "子", opts=Options(guiren="common"))
    assert book.guiren != common.guiren
    assert common.guiren == "丑"


# 伏吟有克：《景祐六壬神定经·释用式第三十一》
#   「伏吟，六癸日有克者，当以克处为课首，尽刑为三传。」
#   「六乙日有克自刑者，当以克处为课首，次传其辰，冲动所刑为中、末传。」
# 伏吟天盘即地盘，中末若取天盘上神会得出三传全同，必须走刑链。
# 六十日中第一课有克者恰只有六乙、六癸两组，与《景祐》所举日数吻合。
CASES_FUYIN_KE = [
    ("乙丑", ("辰", "丑", "戌"), "乙寄辰受克为用，次传其辰丑，丑刑戌为末"),
    ("乙卯", ("辰", "卯", "子"), "次传卯，卯刑子"),
    ("乙巳", ("辰", "巳", "申"), "次传巳，巳刑申"),
    ("乙未", ("辰", "未", "丑"), "次传未，未刑丑"),
    ("乙酉", ("辰", "酉", "卯"), "次传酉复自刑，冲取卯为末"),
    ("乙亥", ("辰", "亥", "巳"), "次传亥复自刑，冲取巳为末"),
    ("癸酉", ("丑", "戌", "未"), "癸寄丑受克为用，丑刑戌、戌刑未，尽刑为三传"),
    ("癸卯", ("丑", "戌", "未"), "六癸日伏吟三传恒为丑戌未"),
]


def test_fuyin_youke_jingyou():
    """伏吟有克须迤逦刑之，不得三传全同"""
    for gz, want, why in CASES_FUYIN_KE:
        p = from_ganzhi(gz, "子", "子")
        assert p.keshi == "伏吟", f"{gz} 课式应为伏吟，实为 {p.keshi}"
        assert p.chuan == want, f"{gz} 三传应 {want}，实为 {p.chuan}（{why}）"
        assert len(set(p.chuan)) > 1, f"{gz} 三传全同 {p.chuan}，退回了取天盘的旧错"


def test_fuyin_wuke_unchanged():
    """伏吟无克的刚柔自任自信不受上项修正影响"""
    for gz, want, sub in [
        ("甲子", ("寅", "巳", "申"), "自任"),
        ("丁未", ("未", "丑", "戌"), "自信"),
        ("庚辰", ("申", "寅", "巳"), "自任"),
    ]:
        p = from_ganzhi(gz, "子", "子")
        assert p.chuan == want, f"{gz} 三传应 {want}，实为 {p.chuan}"
        assert sub in p.keshi_sub, f"{gz} 应为{sub}，实为 {p.keshi_sub}"


def main() -> int:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    bad = 0
    for f in fns:
        try:
            f()
            print(f"✅ {f.__name__}")
        except AssertionError as e:
            bad += 1
            print(f"❌ {f.__name__}\n   {e}")
    print(f"\n通过 {len(fns) - bad}/{len(fns)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
