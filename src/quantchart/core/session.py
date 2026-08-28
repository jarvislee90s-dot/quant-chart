"""槽位引擎：交易时段网格 + 压缩X轴位置映射。"""
import datetime as dtm
from dataclasses import dataclass

import numpy as np
import pandas as pd

AM = (dtm.time(9, 30), dtm.time(11, 30))
PM = (dtm.time(13, 0), dtm.time(15, 0))
TICK_TIMES = [dtm.time(9, 30), dtm.time(10, 0), dtm.time(10, 30), dtm.time(11, 0),
              dtm.time(11, 30), dtm.time(13, 0), dtm.time(13, 30), dtm.time(14, 0),
              dtm.time(14, 30), dtm.time(15, 0)]


@dataclass
class Slots:
    df: pd.DataFrame        # 已加 pos 列
    day_span: dict          # date -> (start_pos, end_pos)
    sep_center: list        # 日分隔线位置（隔位中心）
    tick_pos: list
    tick_lab: list
    n_all: int


def day_grid(day: dtm.date) -> list[pd.Timestamp]:
    """单日 242 个分钟槽位（09:30–11:30, 13:00–15:00 首尾均含）。"""
    out = []
    t = dtm.datetime.combine(day, AM[0])
    while t.time() <= AM[1]:
        out.append(pd.Timestamp(t))
        t += dtm.timedelta(minutes=1)
    t = dtm.datetime.combine(day, PM[0])
    end = dtm.datetime.combine(day, PM[1])
    while t <= end:
        out.append(pd.Timestamp(t))
        t += dtm.timedelta(minutes=1)
    return out


def build_slots(df: pd.DataFrame) -> Slots:
    """df 须含 datetime 列（完整槽位、已排序、无重复）。"""
    df = df.copy().reset_index(drop=True)
    days = sorted(set(df["datetime"].dt.date))
    day_span, sep_center, tick_pos, tick_lab = {}, [], [], []
    cur = 0
    for di, d in enumerate(days):
        sub = df[df["datetime"].dt.date == d]
        if di > 0:
            cur += 1                                  # 日间空位（跨日断线）
            sep_center.append(cur - 0.5)
        pos = np.arange(cur, cur + len(sub))
        df.loc[sub.index, "pos"] = pos.astype(float)
        last = di == len(days) - 1
        for r, p in zip(sub.itertuples(), pos):
            t = r.datetime.time()
            if t in TICK_TIMES:
                if t == dtm.time(15, 0) and not last:
                    lab = ""                          # 与次日09:30仅隔2位
                elif t == dtm.time(13, 0):
                    lab = ""                          # 与11:30仅隔1位
                else:
                    lab = r.datetime.strftime("%H:%M")
                tick_pos.append(float(p))
                tick_lab.append(lab)
        day_span[d] = (cur, cur + len(sub) - 1)
        cur += len(sub)
    return Slots(df=df, day_span=day_span, sep_center=sep_center,
                 tick_pos=tick_pos, tick_lab=tick_lab, n_all=cur)


MONTH_TICK_THRESHOLD = 90


def build_daily_slots(df: pd.DataFrame, tick_anchor: str | None = None) -> Slots:
    """日线/日内条形槽位：每 bar 一格 pos=0..n-1；非交易时段自然压缩。

    日线（每日一根）：月界分隔、月/周自适应刻度；
    日内多根/日（如 15 分钟）：日界分隔、按日自适应抽样打刻度（锚定该日 tick_anchor
    时刻那根，默认 10:30；该时刻缺失则退回日首根、只标日期——适配不同市场时段）。
    """
    df = df.copy().reset_index(drop=True)
    n = len(df)
    if n == 0:
        raise ValueError("日线数据为空")
    df["pos"] = np.arange(n, dtype=float)
    days = list(df["datetime"].dt.date)
    day_span = {d: (float(min(i for i, x in enumerate(days) if x == d)),
                    float(max(i for i, x in enumerate(days) if x == d)))
                for d in set(days)}
    uniq = sorted(day_span)
    bars_per_day = n / len(uniq)
    tick_pos, tick_lab = [], []
    if bars_per_day > 1.5:                          # 日内多根：日界分隔 + 按日刻度抽样（锚定该日10:30）
        sep_center = [i - 0.5 for i in range(1, n) if days[i] != days[i - 1]]
        k = max(1, int(np.ceil(len(uniq) / 12)))
        tser = list(df["datetime"].dt.time)
        hh, mm = map(int, (tick_anchor or "10:30").split(":"))
        t30 = dtm.time(hh, mm)
        for j, d in enumerate(uniq):
            if j % k:
                continue
            s, e = int(day_span[d][0]), int(day_span[d][1])
            anchor = next((p for p in range(s, e + 1) if tser[p] == t30), None)
            if anchor is None:                      # 该日无10:30 bar（如测试夹具）→ 退回日首根
                tick_pos.append(float(s))
                tick_lab.append(f"{d.month}.{d.day}")
            else:
                tick_pos.append(float(anchor))
                tick_lab.append(f"{d.month}.{d.day} {t30.strftime('%H:%M')}")
    else:                                           # 日线：月界分隔 + 月/周刻度
        sep_center = [i - 0.5 for i in range(1, n)
                      if (days[i].year, days[i].month) != (days[i - 1].year, days[i - 1].month)]
        if n > MONTH_TICK_THRESHOLD:
            seen = set()
            for i, d in enumerate(days):
                key = (d.year, d.month)
                if key not in seen:
                    seen.add(key)
                    tick_pos.append(float(i))
                    tick_lab.append(d.strftime("%y-%m"))
        else:
            for i, d in enumerate(days):
                if i == 0 or d.isocalendar()[1] != days[i - 1].isocalendar()[1]:
                    tick_pos.append(float(i))
                    tick_lab.append(d.strftime("%m-%d"))
    return Slots(df=df, day_span=day_span, sep_center=sep_center,
                 tick_pos=tick_pos, tick_lab=tick_lab, n_all=n)
