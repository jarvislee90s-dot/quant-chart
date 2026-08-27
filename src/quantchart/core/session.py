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
