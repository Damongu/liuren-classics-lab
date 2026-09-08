"""逆向检索：先在 720 课里挑结构，再落到真实时空。

底本第六册元首课自述："六壬总计七百二十课，内合元首课凡一百一十有五。"
720 = 60 日干支 × 12 局（月将加时的相对位移 k）。课式与三传只取决于这两者，
昼夜只影响天将。所以靶盘不必在真实时间里等，先枚举 720 局挑中结构，再反解时空。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import timeutil
from .astro import yuejiang_branch
from .ganzhi import ZHI, gz_name, shift
from .plate import Options, Plate, from_ganzhi


@dataclass
class Course:
    day_gz: str
    k: int              # 局：月将 - 占时（顺行位移）
    keshi: str
    sub: str
    chuan: tuple
    plate: Plate

    @property
    def desc(self) -> str:
        return f"{self.day_gz}日 第{self.k}局 {self.keshi}·{self.sub} 三传{''.join(self.chuan)}"


def enumerate720(opts: Options | None = None) -> list[Course]:
    """枚举全部 720 课。占时固定取子时，月将 = 子 + k（等价盘）。"""
    opts = opts or Options()
    out = []
    for i in range(60):
        gz = gz_name(i)
        for k in range(12):
            p = from_ganzhi(gz, "子", shift("子", k), opts=opts)
            out.append(Course(gz, k, p.keshi, p.keshi_sub, p.chuan, p))
    return out


def filter_courses(rows: list[Course], *, keshi: str | None = None,
                   sub: str | None = None, gan: str | None = None,
                   zhi: str | None = None, day_gz: str | None = None,
                   chuan_has: str | None = None, k: int | None = None,
                   kong_in_chuan: bool | None = None) -> list[Course]:
    out = rows
    if keshi:
        out = [r for r in out if r.keshi == keshi]
    if sub:
        out = [r for r in out if sub in r.sub]
    if gan:
        out = [r for r in out if r.day_gz[0] == gan]
    if zhi:
        out = [r for r in out if r.day_gz[1] == zhi]
    if day_gz:
        out = [r for r in out if r.day_gz == day_gz]
    if k is not None:
        out = [r for r in out if r.k == k]
    if chuan_has:
        out = [r for r in out if chuan_has in r.chuan]
    if kong_in_chuan is not None:
        out = [r for r in out
               if any(r.plate.is_kong(c) for c in r.chuan) == kong_in_chuan]
    return out


def keshi_distribution(rows: list[Course] | None = None,
                       opts: Options | None = None) -> Counter:
    rows = rows if rows is not None else enumerate720(opts)
    return Counter(r.keshi for r in rows)


def sub_distribution(rows: list[Course] | None = None,
                     opts: Options | None = None) -> Counter:
    rows = rows if rows is not None else enumerate720(opts)
    return Counter(f"{r.keshi}·{r.sub}" for r in rows)


# ---------- 落到真实时空 ----------
def _shi_center_clock(date_local: datetime, idx: int, place) -> datetime:
    """某地某日第 idx 时辰的中点（当地钟表时）。

    时辰按地方平太阳时划分：子时中点为 LMT 00:00，丑时 02:00 ……
    """
    lmt_center = datetime(date_local.year, date_local.month, date_local.day) \
        + timedelta(hours=2 * idx)
    return lmt_center - timedelta(minutes=place.lmt_offset_minutes)


def scan_real(start: datetime, end: datetime, place_spec: str | None = None, *,
              lon: float | None = None, lat: float | None = None,
              tz: float | None = None, opts: Options | None = None,
              cache: dict | None = None):
    """遍历真实时空的每个时辰，产出 (钟表时, 日干支, 时支, 月将, k)。

    只算月将支（单次太阳位置），不解中气时刻，故可整年扫描。
    """
    opts = opts or Options()
    place = timeutil.resolve_place(place_spec, lon, lat, tz)
    d = datetime(start.year, start.month, start.day)
    while d < end:
        for idx in range(12):
            clock = _shi_center_clock(d, idx, place)
            if not (start <= clock < end):
                continue
            lmt = timeutil.to_lmt(clock, place)
            gz = timeutil.day_ganzhi(lmt, opts.day_boundary)
            jiang = yuejiang_branch(clock - timedelta(hours=place.tz))
            shi = ZHI[idx]
            k = (ZHI.index(jiang) - idx) % 12
            yield clock, gz, shi, jiang, k
        d += timedelta(days=1)


def realize(day_gz: str, k: int, start: datetime, end: datetime,
            place_spec: str | None = None, *, lon: float | None = None,
            lat: float | None = None, tz: float | None = None,
            opts: Options | None = None, limit: int = 20) -> list[tuple[datetime, str, str]]:
    """把"某日某局"落成真实时刻：返回 [(钟表时, 时支, 月将)]。"""
    out = []
    for clock, gz, shi, jiang, kk in scan_real(start, end, place_spec, lon=lon,
                                               lat=lat, tz=tz, opts=opts):
        if gz == day_gz and kk == k:
            out.append((clock, shi, jiang))
            if len(out) >= limit:
                break
    return out


def real_frequency(start: datetime, end: datetime, place_spec: str | None = None, *,
                   lon: float | None = None, lat: float | None = None,
                   tz: float | None = None, opts: Options | None = None) -> Counter:
    """真实时间里各课式出现次数（按时辰计）。用于算稀有度。"""
    opts = opts or Options()
    table = {(c.day_gz, c.k): c for c in enumerate720(opts)}
    cnt = Counter()
    for _, gz, _, _, k in scan_real(start, end, place_spec, lon=lon, lat=lat,
                                    tz=tz, opts=opts):
        c = table[(gz, k)]
        cnt[c.keshi] += 1
    return cnt
