"""时间与地点：钟表时 -> 地方平太阳时 -> 时辰，以及日干支。

规格 v0.3：时辰用地方平太阳时，按占事地经度换算，不做均时差修正，
暂不考虑纬度太阳修正；排盘必须带地点字段。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import astro
from .ganzhi import GAN, ZHI, gz_name

# 常用地点：经度、纬度、行政时区（小时）
PLACES = {
    "北京": (116.407, 39.904, 8.0),
    "上海": (121.474, 31.230, 8.0),
    "广州": (113.264, 23.129, 8.0),
    "深圳": (114.058, 22.543, 8.0),
    "成都": (104.066, 30.573, 8.0),
    "重庆": (106.551, 29.563, 8.0),
    "杭州": (120.155, 30.274, 8.0),
    "南京": (118.797, 32.060, 8.0),
    "武汉": (114.305, 30.593, 8.0),
    "西安": (108.940, 34.341, 8.0),
    "郑州": (113.625, 34.747, 8.0),
    "长沙": (112.939, 28.228, 8.0),
    "沈阳": (123.429, 41.796, 8.0),
    "哈尔滨": (126.535, 45.803, 8.0),
    "济南": (117.121, 36.651, 8.0),
    "青岛": (120.383, 36.067, 8.0),
    "天津": (117.190, 39.125, 8.0),
    "福州": (119.296, 26.074, 8.0),
    "厦门": (118.089, 24.480, 8.0),
    "昆明": (102.833, 24.880, 8.0),
    "贵阳": (106.630, 26.647, 8.0),
    "兰州": (103.834, 36.061, 8.0),
    "乌鲁木齐": (87.617, 43.793, 8.0),
    "拉萨": (91.140, 29.645, 8.0),
    "香港": (114.174, 22.320, 8.0),
    "台北": (121.565, 25.033, 8.0),
    "新加坡": (103.820, 1.352, 8.0),
    "东京": (139.692, 35.690, 9.0),
    "洛阳": (112.454, 34.619, 8.0),   # 宋西京
    "开封": (114.307, 34.797, 8.0),   # 宋东京
    "杭州府": (120.155, 30.274, 8.0),  # 宋临安
}
ALIAS = {
    "chengdu": "成都", "beijing": "北京", "shanghai": "上海", "guangzhou": "广州",
    "shenzhen": "深圳", "hangzhou": "杭州", "kaifeng": "开封", "luoyang": "洛阳",
}


@dataclass(frozen=True)
class Place:
    name: str
    lon: float
    lat: float
    tz: float

    @property
    def lmt_offset_minutes(self) -> float:
        """地方平太阳时相对行政时区的偏移（分钟）。"""
        return (self.lon - self.tz * 15.0) * 4.0


def resolve_place(spec: str | None, lon: float | None = None,
                  lat: float | None = None, tz: float | None = None) -> Place:
    """--place 成都 或 --lon/--lat/--tz 三件套。"""
    if spec:
        key = ALIAS.get(spec.lower(), spec)
        if key in PLACES:
            plon, plat, ptz = PLACES[key]
            return Place(key, lon if lon is not None else plon,
                         lat if lat is not None else plat,
                         tz if tz is not None else ptz)
        raise ValueError(f"未知地点：{spec}（可用 --lon/--lat/--tz 直接给经纬度）")
    if lon is None:
        raise ValueError("必须给 --place 或 --lon（排盘必须带地点）")
    return Place(f"自定义{lon:.3f}E", lon, lat if lat is not None else 34.0,
                 tz if tz is not None else round(lon / 15.0))


# ---------- 地方平太阳时 ----------
def to_lmt(clock: datetime, place: Place) -> datetime:
    """行政区钟表时 -> 地方平太阳时（不做均时差修正）。"""
    return clock + timedelta(minutes=place.lmt_offset_minutes)


def shichen(lmt: datetime) -> tuple[str, int]:
    """地方平太阳时 -> (时支, 时辰序号 0..11)。子时含 23:00-01:00。"""
    idx = int(((lmt.hour + lmt.minute / 60 + lmt.second / 3600) + 1) // 2) % 12
    return ZHI[idx], idx


def shichen_span(lmt: datetime) -> tuple[datetime, datetime]:
    """该时辰的地方平太阳时区间。"""
    _, idx = shichen(lmt)
    start_hour = (idx * 2 - 1) % 24
    base = lmt.replace(hour=0, minute=0, second=0, microsecond=0)
    start = base + timedelta(hours=start_hour)
    if idx == 0 and lmt.hour < 1:
        start -= timedelta(days=1)
    return start, start + timedelta(hours=2)


# ---------- 日干支 ----------
JD_GZ_EPOCH = 49  # (JDN(正午) + 49) % 60 == 0 时为甲子日；已用 2000-01-01=戊午 校验


def day_ganzhi(lmt: datetime, boundary: str = "zi23") -> str:
    """由地方平太阳时求日干支。

    boundary:
      zi23     —— 子时起日（23:00 换日），六壬通行做法【规格待考项】
      midnight —— 子夜换日
    """
    d = lmt
    if boundary == "zi23" and lmt.hour >= 23:
        d = lmt + timedelta(days=1)
    elif boundary not in ("zi23", "midnight"):
        raise ValueError("boundary 只能是 zi23 或 midnight")
    jdn = int(math.floor(astro.to_jd(datetime(d.year, d.month, d.day, 12))))
    return gz_name(jdn + JD_GZ_EPOCH)


def next_day_gz(gz: str, n: int = 1) -> str:
    from .ganzhi import gz_index
    return gz_name(gz_index(gz) + n)


def find_days(gz: str, start: datetime, end: datetime,
              boundary: str = "zi23") -> list[datetime]:
    """在 [start, end) 内找出所有日干支为 gz 的日期（按当地日期返回）。"""
    out = []
    d = datetime(start.year, start.month, start.day)
    while d < end:
        if day_ganzhi(d.replace(hour=12), boundary) == gz:
            out.append(d)
        d += timedelta(days=1)
    return out


def day_night(clock: datetime, place: Place, mode: str = "sun") -> tuple[str, str]:
    """判定昼夜，用于取昼贵/夜贵。

    mode:
      sun   —— 实际日出日入为界。底本第十册第三十九法："如推究节气，日出日入者
               …… 尤宜逐季推寻，日出日入之时极准"，并明确批评"止以卯为日出、
               酉为日入"的简化做法。
      fixed —— 卯至申为昼、酉至寅为夜（通行简化）。
    """
    if mode == "fixed":
        _, idx = shichen(to_lmt(clock, place))
        return ("昼" if 3 <= idx <= 8 else "夜"), "卯至申为昼"
    rise, set_ = astro.sun_events(clock, place.lon, place.lat, place.tz)
    if rise is None:
        _, idx = shichen(to_lmt(clock, place))
        return ("昼" if 3 <= idx <= 8 else "夜"), "极昼极夜，退回卯申界"
    label = "昼" if rise <= clock < set_ else "夜"
    return label, f"日出 {rise:%H:%M}／日入 {set_:%H:%M}（当地钟表时）"
