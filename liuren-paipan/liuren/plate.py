"""天地盘、四课、三传（九宗门）、十二天将。

规则全部依《六壬大全》第一册·入手法原文实现，口诀原文写在各函数 docstring 里。
凡原文未定、需要在通行说法中择一的地方，都用 Options 显式开关，默认值在
README 与 docstring 里标注理由，便于日后按唐宋佐证书回改。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import timeutil
from .astro import yuejiang
from .ganzhi import (GAN_HE, GAN_YINYANG, GUIREN_TABLES, JIGONG, LIUHE, SANHE,
                     SELF_XING, SHENG, SHUN_GONG, TIANJIANG, XING, YIMA, ZHI,
                     ZHI_SHEN, ZHI_YINYANG, bihe, chong, dungan, gz_index, ke,
                     kongwang, relation, shehai_count, sheng, shift, wuxing,
                     xun_shou, zhi_class, zidx)


@dataclass
class Options:
    """可回改的口径开关。"""
    # 贵人表：common=通行"甲戊庚牛羊"｜book=底本第一册"先天贵神"昼夜贵人歌
    # 默认 common 的理由（底本内证）：
    #   1. 该章末自云"其说甚有理，而近不用"；
    #   2. 底本第六册元首课例（甲子日卯时子将）明言午乘青龙、卯乘朱雀、酉乘太常、
    #      子乘天后，反推贵人在丑顺行 —— 即通行表的甲日昼贵丑，非先天歌的甲羊(未)。
    # 结论：底本正文课例用通行表，先天贵神歌仅存目。详见 70-待查。
    guiren: str = "common"
    daynight: str = "sun"       # sun=实际日出日入（底本第三十九法主张）｜fixed=卯申界
    day_boundary: str = "zi23"  # zi23=子时换日｜midnight=子夜换日【待考】
    # 涉害深浅：count=《大全》逐位计重（教程默认）｜direct=《占事略决》直取孟仲季
    shehai_method: str = "count"
    shehai_table: str = "kejing"  # 兼容旧参数；两名均用“地支本气 + 十干寄宫”
    shehai_class: str = "gong"  # 涉害取孟仲：gong=按所临地盘宫｜shen=按上神本身
    # 涉害用神若与日干不比，是否改取比和者（底本"比用格"）。底本自相矛盾：
    #   开 —— 第六册涉害课"比用格"、第十一册第九十三法订讹，两处明言当取比和者
    #   关 —— 第六册"见机格"例（庚子日戌时申将取午加庚）走的是纯涉害
    # 教程默认采用纯计重，不追加底本内部有冲突的后置比用格。
    shehai_bihe: bool = False
    bieze_rou: str = "+4"       # 柔日"支前三合"：+4=顺数第五位｜-4=逆数第五位
    strict: bool = False        # True 时遇到规则歧义直接抛错，不做兜底


@dataclass
class Ke:
    idx: int          # 课序 1..4
    low: str          # 下神（第一课为日干）
    low_zhi: str      # 下神所占地盘支（第一课取寄宫）
    up: str           # 上神（天盘）
    rel: str          # 下对上的关系

    @property
    def xia_ze_shang(self) -> bool:
        """下贼上（下克上）。"""
        return self.rel == "克"

    @property
    def shang_ke_xia(self) -> bool:
        return self.rel == "被克"


@dataclass
class Plate:
    # 输入
    day_gz: str
    jiang: str
    shi: str
    opts: Options = field(default_factory=Options)
    # 时空信息（抽象排盘时为 None）
    when: datetime | None = None
    place: "timeutil.Place | None" = None
    daynight: str = "昼"
    daynight_why: str = ""
    jiang_source: str = ""
    # 推导结果
    k: int = 0
    tian: dict = field(default_factory=dict)     # 地盘支 -> 天盘支
    di: dict = field(default_factory=dict)       # 天盘支 -> 地盘支
    kes: list = field(default_factory=list)
    chuan: tuple = ()
    keshi: str = ""
    keshi_sub: str = ""
    reason: list = field(default_factory=list)
    jiang12: dict = field(default_factory=dict)  # 天盘支 -> 天将
    guiren: str = ""
    guiren_dir: str = ""
    kong: tuple = ()
    divergences: list = field(default_factory=list)

    # ---------- 构造 ----------
    def __post_init__(self):
        self.k = (ZHI.index(self.jiang) - ZHI.index(self.shi)) % 12
        self.tian = {z: shift(z, self.k) for z in ZHI}
        self.di = {v: k for k, v in self.tian.items()}
        self.kong = kongwang(self.day_gz)
        self._build_kes()
        self._build_tianjiang()
        self._derive_chuan()

    @property
    def gan(self) -> str:
        return self.day_gz[0]

    @property
    def zhi(self) -> str:
        return self.day_gz[1]

    @property
    def jigong(self) -> str:
        return JIGONG[self.gan]

    @property
    def is_gang(self) -> bool:
        """刚日（阳日）。"""
        return GAN_YINYANG[self.gan] == "阳"

    @property
    def gan_shang(self) -> str:
        """干上神。"""
        return self.tian[self.jigong]

    @property
    def zhi_shang(self) -> str:
        """支上神。"""
        return self.tian[self.zhi]

    # ---------- 四课 ----------
    def _build_kes(self):
        g, z = self.gan, self.zhi
        jg = self.jigong
        pairs = [
            (1, g, jg, self.tian[jg]),
            (2, self.tian[jg], self.tian[jg], self.tian[self.tian[jg]]),
            (3, z, z, self.tian[z]),
            (4, self.tian[z], self.tian[z], self.tian[self.tian[z]]),
        ]
        self.kes = [Ke(i, low, low_zhi, up, relation(low, up))
                    for i, low, low_zhi, up in pairs]

    @property
    def distinct_ke(self) -> int:
        """四课去重后的课数。第一课下神按寄宫比对（八专、别责由此判定）。"""
        return len({(k.low_zhi, k.up) for k in self.kes})

    # ---------- 十二天将 ----------
    def _build_tianjiang(self):
        table = GUIREN_TABLES[self.opts.guiren]
        day_g, night_g = table[self.gan]
        self.guiren = day_g if self.daynight == "昼" else night_g
        gong = self.di[self.guiren]              # 贵人所临地盘宫
        forward = gong in SHUN_GONG              # 背天门则顺，向地户则逆
        self.guiren_dir = "顺" if forward else "逆"
        step = 1 if forward else -1
        self.jiang12 = {shift(self.guiren, step * i): name
                        for i, name in enumerate(TIANJIANG)}

    def jiang_on(self, tian_zhi: str) -> str:
        return self.jiang12[tian_zhi]

    # ---------- 三传 ----------
    def _note(self, s: str):
        self.reason.append(s)

    def _bi(self, cands: list[str]) -> list[str]:
        """比用法：'常将天日比神用，阳日用阳阴用阴。'"""
        yy = GAN_YINYANG[self.gan]
        return [c for c in cands if ZHI_YINYANG[c] == yy]

    def _shehai_is_xia_ze_shang(self, up: str) -> bool:
        """返回候选所循克向：True 为下贼上，False 为上克下。"""
        has_ze = any(k.xia_ze_shang for k in self.kes)
        matches = [
            k for k in self.kes
            if k.up == up and (k.xia_ze_shang if has_ze else k.shang_ke_xia)
        ]
        if not matches:
            raise ValueError(f"{up}不是本课涉害候选")
        return has_ze

    def _shehai_depth(self, up: str) -> int:
        """涉害深浅：归本家途中按原四课克向逐项计重。

        底本第六册涉害课订讹："从地盘历数归本家，受克深者……午加庚金，前行历酉、
        辛金二重归本家地盘午位。戌加子水，前行历癸水一重归本家地盘戌位。"
        多重下贼上数沿途地神克候选天神，多重上克下数候选天神克沿途地神。
        计数表见 ganzhi.SHEHAI_ITEMS。首尾两宫都不计。
        """
        start = self.di[up]
        xia_ze_shang = self._shehai_is_xia_ze_shang(up)
        depth = 0
        cur = shift(start, 1)
        for _ in range(12):
            if cur == up:                 # 行来本家止
                break
            depth += shehai_count(cur, up, xia_ze_shang, self.opts.shehai_table)
            cur = shift(cur, 1)
        return depth

    def shehai_depth(self, up: str) -> int:
        """公开接口，便于用底本算例校验重数。"""
        return self._shehai_depth(up)

    def _cls_of(self, up: str) -> str:
        target = self.di[up] if self.opts.shehai_class == "gong" else up
        return zhi_class(target)

    def _shehai_direct(self, cands: list[str]) -> str:
        """《占事略决》直取法：加孟为深，加仲为半，加季为浅。

        同级时依该书第四法“若涉害俱深，以先举者为用”，即按四课先干后支的
        候选顺序取第一神。不逐位计重，也不追加《大全》比用格。
        """
        rank = {"孟": 3, "仲": 2, "季": 1}
        classes = {c: self._cls_of(c) for c in cands}
        best = max(rank[classes[c]] for c in cands)
        tied = [c for c in cands if rank[classes[c]] == best]
        pick = tied[0]
        self._note("涉害直取孟仲季：" + "、".join(
            f"{c}临{self.di[c] if self.opts.shehai_class == 'gong' else c}"
            f"为{classes[c]}" for c in cands))
        if len(tied) > 1:
            self._note(f"{classes[pick]}位复等，依《占事略决》取先举之{pick}")
        else:
            self._note(f"取{classes[pick]}位之{pick}为用")
        self.keshi = "涉害"
        self.keshi_sub = f"临{classes[pick]}"
        return pick

    def _shehai_counted(self, cands: list[str]) -> str:
        """《六壬大全》口径：涉归本家逐位计重，复等再取孟仲季。"""
        depths = {c: self._shehai_depth(c) for c in cands}
        best = max(depths.values())
        tied = [c for c in cands if depths[c] == best]
        self._note("涉害深浅：" + "、".join(f"{c}{depths[c]}重" for c in cands))
        fudeng = False
        if len(tied) == 1:
            pick = tied[0]
        else:
            # 订讹层的完整次序：重数相等先取孟、无孟取仲、无孟仲取季；
            # 同级仍有多个，才是复等，刚日取干两课先见、柔日取支两课先见。
            rank = {"孟": 3, "仲": 2, "季": 1}
            best_class = max(rank[self._cls_of(c)] for c in tied)
            same_class = [c for c in tied if rank[self._cls_of(c)] == best_class]
            fu_pick = self.gan_shang if self.is_gang else self.zhi_shang
            wanted_class = self._cls_of(same_class[0])
            if len(same_class) == 1:
                pick = same_class[0]
                self._note(f"深浅相等，取临四{wanted_class}者")
                if fu_pick in tied and fu_pick != pick:
                    self.divergences.append({
                        "规则": "涉害·见机／缀瑕",
                        "本盘取": pick, "另一说": fu_pick,
                        "依据": f"订讹层：重数相等先取临四{wanted_class}者",
                        "另说依据": "课经正文缀瑕例可读作重数一等即"
                                    + ("刚日取干上先见神" if self.is_gang
                                       else "柔日取支上先见神"),
                    })
            else:
                fudeng = True
                side_order = self.kes[:2] if self.is_gang else self.kes[2:]
                other_order = self.kes[2:] if self.is_gang else self.kes[:2]
                ordered = [k.up for k in (*side_order, *other_order)]
                pick = next(c for c in ordered if c in same_class)
                self._note(
                    f"深浅与{wanted_class}位复等，"
                    + ("刚日取干两课先见神" if self.is_gang
                       else "柔日取支两课先见神")
                )
        # 格名：临孟见机、临仲察微、临季即涉害、复等缀瑕
        sub = {"孟": "见机", "仲": "察微", "季": "涉害"}[self._cls_of(pick)]
        if fudeng:
            sub = "缀瑕"
        self.keshi, self.keshi_sub = "涉害", sub
        # 比用格：涉害之用神与日干不比者，改取比和者
        if not bihe(self.gan, pick):
            alts = [c for c in cands if c != pick and bihe(self.gan, c)]
            if alts:
                alt = max(alts, key=lambda c: depths[c])
                if self.opts.shehai_bihe:
                    self.divergences.append({
                        "规则": "涉害·比用格",
                        "本盘取": alt, "另一说": pick,
                        "依据": f"底本第六册涉害课比用格、第十一册第九十三法：{pick}"
                                f"与{self.gan}不比，当取比和之{alt}",
                        "另说依据": f"纯涉害（见机格例）取{pick}",
                    })
                    self._note(f"{pick}与日干不比，依比用格改取比和之{alt}")
                    self.keshi_sub = "比用格"
                    return alt
                self.divergences.append({
                    "规则": "涉害·比用格",
                    "本盘取": pick, "另一说": alt,
                    "依据": f"纯涉害取{pick}",
                    "另说依据": f"底本比用格当取比和之{alt}",
                })
        return pick

    def _shehai(self, cands: list[str]) -> str:
        if self.opts.shehai_method == "direct":
            return self._shehai_direct(cands)
        if self.opts.shehai_method == "count":
            return self._shehai_counted(cands)
        raise ValueError(f"未知涉害口径：{self.opts.shehai_method}")

    def _from_ke_candidates(self) -> str | None:
        """贼克法 + 比用法 + 涉害法。返回初传，无克返回 None。

        '一下克上曰重审，一上克下曰元首。取课先从下贼呼，如无下贼上克初。'
        '下贼或三二四侵，若逢上克亦同云。常将天日比神用，阳日用阳阴用阴。
         若或俱比俱不比，立法别有涉害陈。'
        """
        ze = [k.up for k in self.kes if k.xia_ze_shang]
        keu = [k.up for k in self.kes if k.shang_ke_xia]
        if ze:
            cands, single, multi = ze, "重审", "下贼上"
        elif keu:
            cands, single, multi = keu, "元首", "上克下"
        else:
            return None
        cands = list(dict.fromkeys(cands))
        if len(cands) == 1:
            self.keshi = self.keshi_sub = single
            self._note(f"{multi}一处，取{cands[0]}为用")
            return cands[0]
        self._note(f"{multi}凡{len(cands)}处：{'、'.join(cands)}")
        bi = self._bi(cands)
        if len(bi) == 1:
            self.keshi, self.keshi_sub = "知一", "比用"
            self._note(f"取与日干比者（{GAN_YINYANG[self.gan]}日用{GAN_YINYANG[self.gan]}）")
            return bi[0]
        self._note("俱比或俱不比，入涉害")
        return self._shehai(cands)

    def _yaoke(self) -> str | None:
        """遥克法：'先取神遥克其日，如无方取日来遥。……择与日干比者用。'"""
        ups = list(dict.fromkeys(k.up for k in self.kes))
        hao = [u for u in ups if ke(u, self.gan)]      # 神遥克日：蒿矢
        tan = [u for u in ups if ke(self.gan, u)]      # 日遥克神：弹射
        cands, sub = (hao, "蒿矢") if hao else ((tan, "弹射") if tan else ([], ""))
        if not cands:
            return None
        self.keshi, self.keshi_sub = "遥克", sub
        if len(cands) > 1:
            bi = self._bi(cands)
            if len(bi) == 1:
                cands = bi
                self._note("遥克两神，取与日干比者")
            else:
                if self.opts.strict:
                    raise ValueError("遥克俱比俱不比，原文未定")
                self._note("遥克俱比俱不比（原文未定），暂取先见者【待查】")
        return cands[0]

    def _maoxing(self) -> tuple[str, str, str]:
        """昴星法：'无遥无克昴星穷，阳仰阴俯酉位中。
        刚日先辰而后日，柔日先日而后辰。'"""
        if self.is_gang:
            self.keshi, self.keshi_sub = "昴星", "虎视转蓬"
            chu = self.tian["酉"]                # 仰视：地盘酉上之神
            return chu, self.zhi_shang, self.gan_shang
        self.keshi, self.keshi_sub = "昴星", "冬蛇掩目"
        chu = self.di["酉"]                      # 俯视：天盘酉所临之宫
        return chu, self.gan_shang, self.zhi_shang

    def _bieze(self) -> tuple[str, str, str]:
        """别责法：'四课不全三课备，无遥无克别责例。
        刚日干合上头神，柔日支前三合取。皆以天上作初传，阴阳中末干中寄。'"""
        self.keshi = self.keshi_sub = "别责"
        if self.is_gang:
            he_gong = JIGONG[GAN_HE[self.gan]]
            chu = self.tian[he_gong]
            self._note(f"刚日取干合（{self.gan}合{GAN_HE[self.gan]}）寄宫{he_gong}之上神")
        else:
            step = 4 if self.opts.bieze_rou == "+4" else -4
            base = shift(self.zhi, step)
            chu = self.tian[base]
            self._note(f"柔日取支前三合{base}之上神")
        return chu, self.gan_shang, self.gan_shang

    def _bazhuan(self) -> tuple[str, str, str]:
        """八专法：'论克不论遥。两课无克号八专，阳日日阳顺行三（连本位数），
        阴日辰阴逆三位，中末总向日上眠。'"""
        self.keshi = self.keshi_sub = "八专"
        if self.is_gang:
            chu = shift(self.gan_shang, 2)
            self._note("阳日自干上神顺行三位（连本位数）")
        else:
            chu = shift(self.kes[3].up, -2)
            self._note("阴日自第四课上神逆行三位")
        return chu, self.gan_shang, self.gan_shang

    def _fuyin_chain(self, chu: str) -> tuple[str, str, str]:
        """伏吟中末：迤逦刑之。初传自刑则中传取日辰中另一个，再自刑则以冲代刑。

        据《景祐六壬神定经·释用式第三十一》：
        「伏吟无克者，刚日以日上神为用，柔日以辰上神为用，为课首，
        　皆尽其三刑为中、末传。若得自刑者，刚日则先传日，次传辰，
        　辰所刑为末传；柔则先传辰，次传日，日所刑为终传。
        　更若次传自刑者，即以冲为末传也。」
        """
        if chu in SELF_XING:
            zhong = self.zhi_shang if chu == self.gan_shang else self.gan_shang
            self._note("初传自刑，次传颠倒日辰")
        else:
            zhong = XING[chu]
        if zhong in SELF_XING:
            self._note("次传自刑，冲取末传")
            return chu, zhong, chong(zhong)
        return chu, zhong, XING[zhong]

    def _fuyin(self) -> tuple[str, str, str]:
        """伏吟法。中末一律走刑链，**有克无克同法**。

        据《景祐六壬神定经·释用式第三十一》：
        「伏吟，六癸日有克者，当以克处为课首，尽刑为三传。」
        「六乙日有克自刑者，当以克处为课首，次传其辰，冲动所刑为中、末传。」
        伏吟天盘即地盘，故中末**不能**取天盘上神（那会得出三传全同），
        必须取刑。全六十日中第一课有克者恰只有六乙（辰土受乙木克）、
        六癸（丑土克癸水）两组，与《景祐》所举日数吻合，可反证该条不误。
        后世口诀「伏吟有克还为用，无克刚干柔取辰，迤逦刑之作中末」即此。
        """
        chu = self._from_ke_candidates()
        if chu is not None:
            self.keshi, self.keshi_sub = "伏吟", f"有克·{self.keshi_sub}"
            return self._fuyin_chain(chu)
        self.keshi = "伏吟"
        self.keshi_sub = "自任" if self.is_gang else "自信"
        chu = self.gan_shang if self.is_gang else self.zhi_shang
        return self._fuyin_chain(chu)

    def _fanyin(self) -> tuple[str, str, str]:
        """返吟法：'返吟有克亦为用，无克别有井栏名。若知六日该无克，丑未同干丁己辛。
        丑日登明未太乙，辰中日末识原因（辰上作中，日上作末）。'"""
        chu = self._from_ke_candidates()
        if chu is not None:
            self.keshi, self.keshi_sub = "返吟", f"有克·{self.keshi_sub}"
            zhong = self.tian[chu]
            return chu, zhong, self.tian[zhong]
        self.keshi, self.keshi_sub = "返吟", "井栏射"
        chu = "亥" if self.zhi == "丑" else ("巳" if self.zhi == "未" else YIMA[self.zhi])
        self._note("无克，取驿马为初（丑日登明、未日太乙）")
        return chu, self.zhi_shang, self.gan_shang

    def _derive_chuan(self):
        if self.k == 0:
            self.chuan = self._fuyin()
            return
        if self.k == 6:
            self.chuan = self._fanyin()
            return
        chu = self._from_ke_candidates()
        if chu is not None:
            zhong = self.tian[chu]
            self.chuan = (chu, zhong, self.tian[zhong])
            return
        if self.jigong == self.zhi:                 # 八专：论克不论遥
            self.chuan = self._bazhuan()
            return
        chu = self._yaoke()
        if chu is not None:
            zhong = self.tian[chu]
            self.chuan = (chu, zhong, self.tian[zhong])
            return
        if self.distinct_ke == 3:
            self.chuan = self._bieze()
            return
        self.chuan = self._maoxing()

    # ---------- 附加信息 ----------
    def dun(self, z: str) -> str | None:
        return dungan(self.day_gz, z)

    def is_kong(self, z: str) -> bool:
        return z in self.kong

    def chuan_detail(self) -> list[dict]:
        out = []
        for name, z in zip(("初传", "中传", "末传"), self.chuan):
            out.append({
                "位": name, "支": z, "神": ZHI_SHEN[z], "将": self.jiang_on(z),
                "遁干": self.dun(z), "五行": wuxing(z),
                "空亡": self.is_kong(z), "对日干": relation(z, self.gan),
                "临宫": self.di[z],
            })
        return out

    def summary(self) -> str:
        c = "、".join(self.chuan)
        return (f"{self.day_gz}日 {self.shi}时 {self.jiang}将｜{self.keshi}"
                f"（{self.keshi_sub}）｜三传 {c}")


# ---------- 工厂函数 ----------
def from_ganzhi(day_gz: str, shi: str, jiang: str, *, daynight: str = "昼",
                opts: Options | None = None) -> Plate:
    """抽象排盘：直接给日干支、占时、月将（复现书中课例用）。"""
    p = Plate(day_gz=day_gz, jiang=jiang, shi=shi, opts=opts or Options(),
              daynight=daynight, daynight_why="抽象排盘，昼夜由参数指定",
              jiang_source="参数指定")
    return p


def from_jia(day_gz: str, tian_zhi: str, di_zhi: str, *, shi: str | None = None,
             daynight: str = "昼", opts: Options | None = None) -> Plate:
    """由"某加某"复原全盘。

    天地盘是刚体旋转，一组"天盘X加地盘Y"即确定整盘。
    若不另给占时，则以地盘 Y 为占时、天盘 X 为月将（等价盘）。
    """
    # 底本常写"午加庚"，庚为日干，按寄宫落地盘
    tian_zhi = JIGONG.get(tian_zhi, tian_zhi)
    di_zhi = JIGONG.get(di_zhi, di_zhi)
    k = (ZHI.index(tian_zhi) - ZHI.index(di_zhi)) % 12
    shi = shi or di_zhi
    jiang = shift(shi, k)
    return from_ganzhi(day_gz, shi, jiang, daynight=daynight, opts=opts)


def from_time(clock: datetime, place_spec: str | None = None, *,
              lon: float | None = None, lat: float | None = None,
              tz: float | None = None, opts: Options | None = None) -> Plate:
    """真实时空排盘：钟表时 + 地点 -> 全盘。"""
    opts = opts or Options()
    place = timeutil.resolve_place(place_spec, lon, lat, tz)
    lmt = timeutil.to_lmt(clock, place)
    shi, _ = timeutil.shichen(lmt)
    gz = timeutil.day_ganzhi(lmt, opts.day_boundary)
    utc = clock - timedelta(hours=place.tz)
    jiang, qi, qi_start = yuejiang(utc)
    dn, why = timeutil.day_night(clock, place, opts.daynight)
    p = Plate(day_gz=gz, jiang=jiang, shi=shi, opts=opts, when=clock, place=place,
              daynight=dn, daynight_why=why,
              jiang_source=f"{qi}后用{jiang}将（{qi} 起于 "
                           f"{(qi_start + timedelta(hours=place.tz)):%Y-%m-%d %H:%M} 当地钟表时）")
    return p
