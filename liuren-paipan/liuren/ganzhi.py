"""干支、五行、寄宫、刑冲合害、旬遁等基础常量与函数。

口径来源：《六壬大全》怀庆杨衙藏版（下称"底本"）第一册起例。
凡与通行说法不同处，代码里以 [底本] / [通行] 标注。
"""
from __future__ import annotations

# ---------- 干支 ----------
GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

GAN_YINYANG = {g: ("阳" if i % 2 == 0 else "阴") for i, g in enumerate(GAN)}
ZHI_YINYANG = {z: ("阳" if i % 2 == 0 else "阴") for i, z in enumerate(ZHI)}

# 十二神名（月将名），底本第二册："登明为首逆布，逆布者谓之月将"
ZHI_SHEN = {
    "子": "神后", "丑": "大吉", "寅": "功曹", "卯": "太冲", "辰": "天罡", "巳": "太乙",
    "午": "胜光", "未": "小吉", "申": "传送", "酉": "从魁", "戌": "河魁", "亥": "登明",
}

# ---------- 五行与生克 ----------
GAN_WUXING = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}
ZHI_WUXING = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水",
}
# 克：木克土 土克水 水克火 火克金 金克木
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
# 生：木生火 火生土 土生金 金生水 水生木
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}


def wuxing(x: str) -> str:
    """干或支的五行。"""
    if x in GAN_WUXING:
        return GAN_WUXING[x]
    return ZHI_WUXING[x]


def ke(a: str, b: str) -> bool:
    """a 克 b。参数可为干或支。"""
    return KE[wuxing(a)] == wuxing(b)


def sheng(a: str, b: str) -> bool:
    """a 生 b。"""
    return SHENG[wuxing(a)] == wuxing(b)


def relation(a: str, b: str) -> str:
    """a 对 b 的关系：克 / 生 / 被克 / 被生 / 同。"""
    wa, wb = wuxing(a), wuxing(b)
    if wa == wb:
        return "同"
    if KE[wa] == wb:
        return "克"
    if KE[wb] == wa:
        return "被克"
    if SHENG[wa] == wb:
        return "生"
    return "被生"


# ---------- 十干寄宫 ----------
# [底本] 第一册·入手法·十干寄宫：
#   "甲课寅兮乙课辰，丙戊课巳不须论。丁己课未庚申上，辛戌壬亥是其真。
#    癸课原来丑宫坐，分明不用四正神。"
JIGONG = {
    "甲": "寅", "乙": "辰", "丙": "巳", "丁": "未", "戊": "巳",
    "己": "未", "庚": "申", "辛": "戌", "壬": "亥", "癸": "丑",
}

# ---------- 刑冲合害 ----------
# 三刑：子刑卯 卯刑子｜寅刑巳 巳刑申 申刑寅｜丑刑戌 戌刑未 未刑丑｜辰午酉亥自刑
XING = {
    "子": "卯", "卯": "子", "寅": "巳", "巳": "申", "申": "寅",
    "丑": "戌", "戌": "未", "未": "丑", "辰": "辰", "午": "午", "酉": "酉", "亥": "亥",
}
SELF_XING = {"辰", "午", "酉", "亥"}

LIUHE = {  # 支六合
    "子": "丑", "丑": "子", "寅": "亥", "亥": "寅", "卯": "戌", "戌": "卯",
    "辰": "酉", "酉": "辰", "巳": "申", "申": "巳", "午": "未", "未": "午",
}
GAN_HE = {  # 干五合：甲己 乙庚 丙辛 丁壬 戊癸
    "甲": "己", "己": "甲", "乙": "庚", "庚": "乙", "丙": "辛",
    "辛": "丙", "丁": "壬", "壬": "丁", "戊": "癸", "癸": "戊",
}

# 三合局
SANHE = {
    "水": ("申", "子", "辰"), "木": ("亥", "卯", "未"),
    "火": ("寅", "午", "戌"), "金": ("巳", "酉", "丑"),
}

MENG = ("寅", "申", "巳", "亥")   # 四孟
ZHONG = ("子", "午", "卯", "酉")  # 四仲
JI = ("辰", "戌", "丑", "未")     # 四季


def zhi_class(z: str) -> str:
    if z in MENG:
        return "孟"
    if z in ZHONG:
        return "仲"
    return "季"


def chong(z: str) -> str:
    return shift(z, 6)


# 驿马：申子辰马寅｜寅午戌马申｜巳酉丑马亥｜亥卯未马巳
YIMA = {}
for _grp, _ma in ((("申", "子", "辰"), "寅"), (("寅", "午", "戌"), "申"),
                  (("巳", "酉", "丑"), "亥"), (("亥", "卯", "未"), "巳")):
    for _z in _grp:
        YIMA[_z] = _ma


# ---------- 位移工具 ----------
def zidx(z: str) -> int:
    return ZHI.index(z)


def shift(z: str, n: int) -> str:
    """支位移 n（正为顺行）。"""
    return ZHI[(ZHI.index(z) + n) % 12]


def gz_index(gz: str) -> int:
    """干支 -> 0..59。"""
    g, z = gz[0], gz[1]
    gi, zi = GAN.index(g), ZHI.index(z)
    for k in range(60):
        if k % 10 == gi and k % 12 == zi:
            return k
    raise ValueError(f"非法干支：{gz}")


def gz_name(idx: int) -> str:
    idx %= 60
    return GAN[idx % 10] + ZHI[idx % 12]


# ---------- 旬遁与空亡 ----------
def xun_shou(gz: str) -> str:
    """旬首干支，如 甲子。"""
    return gz_name(gz_index(gz) - gz_index(gz) % 10)


def dungan(gz: str, z: str) -> str | None:
    """某日某支的遁干；落空亡返回 None。

    验证：甲子日，午 -> 庚。底本第六册元首课"午上遁得庚金"。
    """
    head_zhi = xun_shou(gz)[1]
    off = (ZHI.index(z) - ZHI.index(head_zhi)) % 12
    return GAN[off] if off < 10 else None


def kongwang(gz: str) -> tuple[str, str]:
    """旬空二支。"""
    head_zhi = xun_shou(gz)[1]
    return (shift(head_zhi, 10), shift(head_zhi, 11))


# ---------- 天将 ----------
TIANJIANG = ("贵人", "螣蛇", "朱雀", "六合", "勾陈", "青龙",
             "天空", "白虎", "太常", "玄武", "太阴", "天后")

# [底本] 第一册·先天贵神·起日贵人歌（昼）：
#   "甲羊戊庚牛，乙猴己鼠求。丙鸡丁猪位，壬兔癸蛇游。六辛逢虎上，阳贵日中传。"
# [底本] 起夜贵人歌：
#   "甲戊庚牛羊，乙鼠己猴乡。丙猪丁鸡位，壬蛇癸兔藏。六辛逢午马，阴贵夜时当。"
GUIREN_BOOK = {  # 干: (昼贵, 夜贵)
    "甲": ("未", "丑"), "戊": ("丑", "未"), "庚": ("丑", "未"),
    "乙": ("申", "子"), "己": ("子", "申"),
    "丙": ("酉", "亥"), "丁": ("亥", "酉"),
    "壬": ("卯", "巳"), "癸": ("巳", "卯"),
    "辛": ("寅", "午"),
}
# [通行] "甲戊庚牛羊，乙己鼠猴乡。丙丁猪鸡位，壬癸蛇兔藏。六辛逢马虎。"
# 达注亦称此版认同度最高。与底本相差在 甲/乙/丙/辛 四干的昼夜互换。
GUIREN_COMMON = {
    "甲": ("丑", "未"), "戊": ("丑", "未"), "庚": ("丑", "未"),
    "乙": ("子", "申"), "己": ("子", "申"),
    "丙": ("亥", "酉"), "丁": ("亥", "酉"),
    "壬": ("巳", "卯"), "癸": ("巳", "卯"),
    "辛": ("午", "寅"),
}
GUIREN_TABLES = {"book": GUIREN_BOOK, "common": GUIREN_COMMON}

# 贵人顺逆：[底本] 第二册·天将总论"以课之天盘起贵神之例，地盘定顺逆之序。
# 顺布者则背天门（亥），逆布者则向地户（巳）。"
SHUN_GONG = ("亥", "子", "丑", "寅", "卯", "辰")


# ---------- 涉害数法：地盘本气 + 十干寄宫 ----------
# 自上神所临地盘宫前行至本家宫（首尾不计），逐宫展开：
#   1. 地支本气；
#   2. 寄居该宫的天干。
# 多重下贼上时，数其中克候选上神的地神；多重上克下时，数候选上神所克的地神。
# 《大全》丁卯例“辰、戊、未、己、戌土五重”即辰支、巳宫戊、未支、未宫己、戌支；
# 《观月经》“巳上戊土、未上未土、己土，前又戌土，共四重”与此完全一致。
SHEHAI_ITEMS = {
    z: (ZHI_WUXING[z],) + tuple(GAN_WUXING[g] for g in GAN if JIGONG[g] == z)
    for z in ZHI
}

# 保留旧参数名以兼容已有课例卡；两者不再代表不同算法。
SHEHAI_TABLES = {"kejing": SHEHAI_ITEMS, "guanyue": SHEHAI_ITEMS}


def shehai_count(gong: str, up: str, xia_ze_shang: bool,
                  table: str = "kejing") -> int:
    """按四课克向统计某地盘宫中与候选上神相克的地神数。"""
    up_wx = wuxing(up)
    if xia_ze_shang:
        return sum(1 for ground_wx in SHEHAI_TABLES[table][gong]
                   if KE[ground_wx] == up_wx)
    return sum(1 for ground_wx in SHEHAI_TABLES[table][gong]
               if KE[up_wx] == ground_wx)


def bihe(gan: str, z: str) -> bool:
    """与日干比和：同类或生日干。相克（无论谁克谁）皆为不比。

    底本第六册涉害课比用格："辰土畏甲木克，则取子加戌，子生甲木比者为用也"；
    第十一册第九十三法："缘甲木与子水比和，戌土畏甲木而不比"。
    """
    wg, wz = wuxing(gan), wuxing(z)
    if wg == wz:
        return True
    return SHENG[wz] == wg      # 上神生日干
