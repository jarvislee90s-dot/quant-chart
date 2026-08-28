"""通道拟合：中枢主导三步法（定中枢 → 小角度倾斜 → 张合压极值）。纯计算、不碰 plotly。

设计原则（用户定稿）：趋势中枢的角度与位置起主导作用，禁止用极值对反推斜率（会过拟合
局部细节、扭曲整体趋势）；双轨始终平行、只允许小角度倾斜；宽度不是输入而是张合输出——
每档斜率下两轨各自张合到压住窗口内的极值（press 分位容忍近似点），取宽度最小的斜率。
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class ChannelFit:
    window: tuple                  # (pos_start, pos_end)
    slope: float                   # 倾斜后斜率（双轨共用）
    slope_mid: float               # 中枢斜率
    center: tuple                  # 倾斜后中枢线端点 ((pos,价), (pos,价))
    lower: tuple                   # 下轨端点
    upper: tuple                   # 上轨端点
    d_lo: float                    # 下探量（中枢→下轨）
    d_hi: float                    # 上张量（中枢→上轨）
    coverage: float                # 窗口内整根蜡烛被包裹的比例
    pressed_lows: list = field(default_factory=list)   # 被下轨压住的最深低点 [(pos, 价)]
    pressed_highs: list = field(default_factory=list)  # 被上轨压住的最高高点 [(pos, 价)]


def fit_channel(df, start, end, tilt=0.12, press=1.0) -> ChannelFit:
    """中枢主导三步法拟合平行通道。

    df 需含 datetime/pos/high/low 列（build_daily_slots 产物）；start/end 为窗口时间点。
    tilt: 倾斜容差（相对中枢斜率的小角度比例，默认 ±12%）；
    press: 张合压住比例（1.0=下/上轨分别贴住最深低点/最高高点；<1 容忍最极端的一小部分）。
    coverage（整根蜡烛包裹率）是输出指标，不是输入。
    """
    w = df[(df["datetime"] >= pd.Timestamp(start)) & (df["datetime"] <= pd.Timestamp(end))]
    if w.empty:
        raise ValueError(f"通道窗口内无数据: {start} ~ {end}")
    xs = w["pos"].to_numpy(dtype=float)
    hi = w["high"].to_numpy(dtype=float)
    lo = w["low"].to_numpy(dtype=float)

    # ① 中枢：K 线中点 LSQ，趋势的角度与位置一次性锁定
    s_mid, b_mid = np.polyfit(xs, (hi + lo) / 2, 1)
    x_c = float(xs.mean())
    y_c = s_mid * x_c + b_mid

    # ② 小角度倾斜搜索；③ 每档斜率下张合压极值（对全窗口 bar 取分位），取宽度最小
    best = None
    for s in np.linspace(s_mid * (1 - tilt), s_mid * (1 + tilt), 25):
        center = y_c + s * (xs - x_c)
        d_lo = float(np.quantile(center - lo, press))
        d_hi = float(np.quantile(hi - center, press))
        cand = (d_lo + d_hi, abs(s - s_mid), s, d_lo, d_hi)
        if best is None or cand[:2] < best[:2]:
            best = cand
    _, _, s, d_lo, d_hi = best

    center = y_c + s * (xs - x_c)
    lower_line = center - d_lo
    upper_line = center + d_hi
    in_ch = float(((lo >= lower_line) & (hi <= upper_line)).mean())
    i_lo = int(np.argmax(center - lo))       # 被下轨压住的最深低点
    i_hi = int(np.argmax(hi - center))       # 被上轨压住的最高高点
    p0, p1 = float(xs[0]), float(xs[-1])
    return ChannelFit(window=(p0, p1), slope=float(s), slope_mid=float(s_mid),
                      center=((p0, float(y_c + s * (p0 - x_c))), (p1, float(y_c + s * (p1 - x_c)))),
                      lower=((p0, float(lower_line[0])), (p1, float(lower_line[-1]))),
                      upper=((p0, float(upper_line[0])), (p1, float(upper_line[-1]))),
                      d_lo=d_lo, d_hi=d_hi, coverage=in_ch,
                      pressed_lows=[(float(xs[i_lo]), float(lo[i_lo]))],
                      pressed_highs=[(float(xs[i_hi]), float(hi[i_hi]))])