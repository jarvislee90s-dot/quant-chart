"""日线深色主题图组装：单面板，样式对照 reference/05 校准（色值见 theme.DARK）。"""
import numpy as np
import plotly.graph_objects as go

from .primitives import Ctx, draw
from .theme import DARK


FORECAST_DAYS = 2   # 右缘预测区：为三情形预演折线留出的工作日数（同原报告画法）


def build_daily_figure(df, slots, panels, rep, title: str = "", notes=None) -> go.Figure:
    if len(panels) != 1:
        raise ValueError(f"日线模式暂仅支持单面板（收到 {len(panels)} 个）")
    fig = go.Figure()
    # 原语按 ctx.df["pos"] 取坐标：统一用 slots.df（含 pos 列），兼容外部传入未加 pos 的 df
    ctx = Ctx(slots=slots, df=slots.df)
    for spec in panels[0].get("layers", []):
        draw(fig, spec, ctx)

    bars_per_day = len(df) / max(1, len(slots.day_span))
    fig.update_layout(
        template="none", width=1600, height=900, autosize=False,
        paper_bgcolor=DARK["bg"], plot_bgcolor=DARK["bg"],
        font=dict(family="Microsoft YaHei, Arial", size=12, color=DARK["font"]),
        margin=dict(l=64, r=150, t=92, b=88),
        xaxis=dict(range=[-2, slots.n_all + FORECAST_DAYS * bars_per_day + 1.5],
                   tickvals=slots.tick_pos, ticktext=slots.tick_lab,
                   tickfont=dict(size=10, color=DARK["font"]),
                   showgrid=False, zeroline=False, linecolor=DARK["axis"],
                   rangeslider=dict(visible=False)),
        yaxis=dict(range=_daily_range(df), gridcolor=DARK["grid"], griddash="dot",
                   zeroline=False, linecolor=DARK["axis"]),
        legend=dict(orientation="h", x=.5, xanchor="center", y=1.01, yanchor="bottom",
                    font=dict(size=11, color=DARK["font"]), bgcolor="rgba(0,0,0,0)"),
    )
    fig.add_annotation(x=.006, y=1.06, xref="paper", yref="paper", showarrow=False,
                       text=f"<b>{title}</b>", font=dict(size=20, color=DARK["font"]),
                       xanchor="left")
    extra = " ".join(notes) if notes else ""
    fig.add_annotation(x=.998, y=-.128, xref="paper", yref="paper", showarrow=False,
                       xanchor="right", font=dict(size=10, color="#7a8494"),
                       text=rep.footnote() + (" " + extra if extra else "")
                       + " 时间轴仅含交易日（周末与节假日压缩）。")
    return fig


def _daily_range(df):
    cols = [c for c in ("open", "high", "low", "close") if c in df]
    vals = np.concatenate([df[c].dropna().values for c in cols])
    lo, hi = float(vals.min()), float(vals.max())
    span = hi - lo or 1.0
    return lo - span * .06, hi + span * .22
