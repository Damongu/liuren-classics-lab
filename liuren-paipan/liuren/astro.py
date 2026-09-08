"""历法与天文：现代算法算太阳视黄经、中气换将、日出日入。

口径（规格 v0.3 第七节）：算法现代、规则宋制。
- 节气与日月位置：现代天文算法（Meeus《Astronomical Algorithms》低精度太阳位置，误差 < 0.01°）
- 时辰：地方平太阳时（按经度换算），不做均时差修正
- 月将：中气换将
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

# ---------- 儒略日 ----------
def to_jd(dt: datetime) -> float:
    """UTC datetime -> 儒略日。"""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    y, m = dt.year, dt.month
    d = (dt.day + dt.hour / 24 + dt.minute / 1440
         + (dt.second + dt.microsecond / 1e6) / 86400)
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5


def from_jd(jd: float) -> datetime:
    """儒略日 -> UTC naive datetime。"""
    jd += 0.5
    z = math.floor(jd)
    f = jd - z
    if z >= 2299161:
        alpha = math.floor((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - alpha // 4
    else:
        a = z
    b = a + 1524
    c = math.floor((b - 122.1) / 365.25)
    d = math.floor(365.25 * c)
    e = math.floor((b - d) / 30.6001)
    day = b - d - math.floor(30.6001 * e) + f
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    di = int(day)
    frac = day - di
    secs = round(frac * 86400)
    return datetime(year, month, di) + timedelta(seconds=secs)


# ---------- 太阳视黄经 ----------
def solar_longitude(jd: float) -> float:
    """太阳视黄经（度，0-360），含光行差与主要黄经章动。"""
    t = (jd - 2451545.0) / 36525.0
    # 几何平黄经
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    # 平近点角
    m = 357.52911 + 35999.05029 * t - 0.0001537 * t * t
    mr = math.radians(m % 360)
    # 中心差
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(mr)
         + (0.019993 - 0.000101 * t) * math.sin(2 * mr)
         + 0.000289 * math.sin(3 * mr))
    true_long = l0 + c
    # 黄经章动 + 光行差
    omega = 125.04 - 1934.136 * t
    apparent = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega % 360))
    return apparent % 360


def solar_longitude_at(dt: datetime) -> float:
    return solar_longitude(to_jd(dt))


def solve_longitude(target: float, near: datetime) -> datetime:
    """求太阳视黄经等于 target（度）的最近时刻（UTC naive）。"""
    def diff(dt: datetime) -> float:
        d = (solar_longitude_at(dt) - target) % 360
        return d - 360 if d > 180 else d

    # 以每日约 0.9856° 的速率粗定位，再二分
    dt = near
    for _ in range(6):
        dt = dt - timedelta(days=diff(dt) / 0.98565)
    lo, hi = dt - timedelta(days=1), dt + timedelta(days=1)
    for _ in range(60):
        mid = lo + (hi - lo) / 2
        if diff(lo) * diff(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return lo + (hi - lo) / 2


# ---------- 中气与月将 ----------
# 中气黄经 -> 月将支（底本口径：雨水后登明亥 …… 大寒后神后子）
ZHONGQI = [
    (330.0, "雨水", "亥"), (0.0, "春分", "戌"), (30.0, "谷雨", "酉"),
    (60.0, "小满", "申"), (90.0, "夏至", "未"), (120.0, "大暑", "午"),
    (150.0, "处暑", "巳"), (180.0, "秋分", "辰"), (210.0, "霜降", "卯"),
    (240.0, "小雪", "寅"), (270.0, "冬至", "丑"), (300.0, "大寒", "子"),
]


def yuejiang_branch(dt_utc: datetime) -> str:
    """只求月将支，单次太阳位置计算，供批量检索用。"""
    lon = solar_longitude_at(dt_utc)
    return {int(q[0] // 30): q[2] for q in ZHONGQI}[int(lon // 30)]


def yuejiang(dt_utc: datetime) -> tuple[str, str, datetime]:
    """中气换将：返回 (月将支, 当前所在中气名, 该中气起始时刻 UTC)。

    太阳视黄经落在 [中气黄经, 下一中气黄经) 区间内即用该中气之将。
    """
    lon = solar_longitude_at(dt_utc)
    seg = int(lon // 30)              # 0..11，对应 0°,30°,...
    # 黄经 330-360 属雨水段；0-30 属春分段 ……
    table = {int(q[0] // 30): q for q in ZHONGQI}
    q_lon, q_name, jiang = table[seg]
    start = solve_longitude(q_lon, dt_utc)
    if start > dt_utc:  # 边界抖动兜底
        start = solve_longitude(q_lon, dt_utc - timedelta(days=3))
    return jiang, q_name, start


# ---------- 日出日入 ----------
def sun_events(date_local: datetime, lon: float, lat: float, tz_hours: float):
    """给定当地日期，返回 (日出, 日入) 的当地钟表时（naive datetime）。

    NOAA 简化算法，太阳中心高度 -0.833°（含蒙气差与视半径）。
    极昼极夜返回 (None, None)。
    """
    jd = to_jd(datetime(date_local.year, date_local.month, date_local.day, 12)
               - timedelta(hours=tz_hours))
    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + 36000.76983 * t + 0.0003032 * t * t) % 360
    m = (357.52911 + 35999.05029 * t - 0.0001537 * t * t) % 360
    mr = math.radians(m)
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(mr)
         + (0.019993 - 0.000101 * t) * math.sin(2 * mr)
         + 0.000289 * math.sin(3 * mr))
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    lam = math.radians(true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega)))
    eps0 = (23 + 26 / 60 + 21.448 / 3600
            - (46.815 * t + 0.00059 * t * t - 0.001813 * t ** 3) / 3600)
    eps = math.radians(eps0 + 0.00256 * math.cos(math.radians(omega)))
    decl = math.asin(math.sin(eps) * math.sin(lam))
    # 均时差（分钟）
    y = math.tan(eps / 2) ** 2
    eot = 4 * math.degrees(
        y * math.sin(2 * math.radians(l0))
        - 2 * 0.016708634 * math.sin(mr)
        + 4 * 0.016708634 * y * math.sin(mr) * math.cos(2 * math.radians(l0))
        - 0.5 * y * y * math.sin(4 * math.radians(l0))
        - 1.25 * 0.016708634 ** 2 * math.sin(2 * mr))
    latr = math.radians(lat)
    cos_ha = ((math.cos(math.radians(90.833)) / (math.cos(latr) * math.cos(decl)))
              - math.tan(latr) * math.tan(decl))
    if cos_ha > 1 or cos_ha < -1:
        return None, None
    ha = math.degrees(math.acos(cos_ha))
    noon = 720 - 4 * lon - eot + tz_hours * 60          # 当地钟表时（分钟）
    base = datetime(date_local.year, date_local.month, date_local.day)
    return (base + timedelta(minutes=noon - 4 * ha),
            base + timedelta(minutes=noon + 4 * ha))
