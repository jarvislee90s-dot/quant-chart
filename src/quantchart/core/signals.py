"""信号层：指标列上的条件 → 事件点（时间+数值+标签）。"""
from dataclasses import dataclass

import pandas as pd


@dataclass
class Event:
    pos: float
    dt: pd.Timestamp
    value: float
    label: str
    kind: str
    meta: dict | None = None


def daily_min_events(df, slots, col="basis", kind="daily_min") -> list[Event]:
    out = []
    for d, (s, e) in slots.day_span.items():
        seg = df[(df["pos"] >= s) & (df["pos"] <= e)]
        i = seg[col].idxmin()
        out.append(Event(float(df.at[i, "pos"]), df.at[i, "datetime"],
                         float(df.at[i, col]), f"{df.at[i, col]:.0f}", kind))
    return out


def window_min_events(df, windows, col="fut_low", kind="window_min") -> list[Event]:
    out = []
    for t0, t1 in windows:
        g = df[(df["datetime"] >= pd.Timestamp(t0)) & (df["datetime"] <= pd.Timestamp(t1))]
        for _, sub in g.groupby(g["datetime"].dt.date):
            i = sub[col].idxmin()
            out.append(Event(float(df.at[i, "pos"]), df.at[i, "datetime"],
                             float(df.at[i, col]), f"{df.at[i, col]:,.0f}", kind))
    return out
