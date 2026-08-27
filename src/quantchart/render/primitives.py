"""通用绘图原语 → Plotly traces/shapes/annotations 翻译。不含任何计算。"""
import sys
from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go


@dataclass
class Ctx:
    slots: object
    df: pd.DataFrame
    xaxis: str = "x"
    yaxis: str = "y"
    y2axis: str = "y2"


def _xof(ctx: Ctx, v) -> float:
    """时间字符串或数值 → 槽位pos。"""
    if isinstance(v, str):
        row = ctx.df[ctx.df["datetime"] == pd.Timestamp(v)]
        if row.empty:
            raise KeyError(f"时间点不在数据中: {v}")
        return float(row["pos"].iloc[0])
    return float(v)


def draw(fig: go.Figure, spec: dict, ctx: Ctx):
    fn = getattr(sys.modules[__name__], f"_{spec['type']}", None)
    if fn is None:
        raise KeyError(f"未知绘图原语: {spec['type']}")
    fn(fig, spec, ctx)


def _line(fig, spec, ctx):
    fig.add_trace(go.Scatter(
        x=ctx.df["pos"], y=ctx.df[spec["col"]],
        mode="lines", name=spec.get("name", spec["col"]),
        line=dict(color=spec.get("color", "#1c4e9d"),
                  width=spec.get("width", 2),
                  dash=spec.get("dash", "solid"))))


def _area(fig, spec, ctx):
    y = ctx.df[spec["col"]]
    x = ctx.df["pos"]
    pos = y.where(y >= 0, other=None)
    neg = y.where(y < 0, other=None)
    ax = spec.get("axis", "y2")
    fig.add_trace(go.Scatter(x=x, y=pos, yaxis=ax, fill="tozeroy", mode="none",
                             fillcolor=spec.get("pos_color", "rgba(214,64,76,.30)"),
                             name=spec.get("name_pos", "贴水（现货>期货）")))
    fig.add_trace(go.Scatter(x=x, y=neg, yaxis=ax, fill="tozeroy", mode="none",
                             fillcolor=spec.get("neg_color", "rgba(46,158,99,.42)"),
                             name=spec.get("name_neg", "升水（现货<期货）")))
    fig.add_trace(go.Scatter(x=x, y=y, yaxis=ax, mode="lines",
                             line=dict(color=spec.get("line_color", "#d6404c"), width=1),
                             showlegend=False, hoverinfo="skip"))


def _zone(fig, spec, ctx):
    x0, x1 = _xof(ctx, spec["from"]), _xof(ctx, spec["to"])
    plo, phi = spec["price"]
    fig.add_shape(type="rect", x0=x0, x1=x1, y0=plo, y1=phi,
                  xref=ctx.xaxis, yref=ctx.yaxis,
                  fillcolor=spec.get("fillcolor", "#c2c7cf"),
                  opacity=spec.get("opacity", .32),
                  line=dict(color=spec.get("edgecolor", "#8f959d"),
                            width=.9, dash="dash"), layer="above")
    if spec.get("label"):
        fig.add_annotation(x=(x0 + x1) / 2, y=plo, yref=ctx.yaxis,
                           text=spec["label"], showarrow=False,
                           yanchor="bottom", yshift=6,
                           font=dict(size=11, color="#3a3f46"),
                           bgcolor="white", bordercolor="#c4c9d0",
                           borderpad=3, opacity=.92)


def _hline(fig, spec, ctx):
    yref = spec.get("axis", "y2")
    if spec.get("from") or spec.get("to"):
        x0 = _xof(ctx, spec.get("from", ctx.df["pos"].min()))
        x1 = _xof(ctx, spec.get("to", ctx.df["pos"].max()))
    else:
        x0, x1 = 0, 1
        xref = "paper"
        if yref != ctx.yaxis:
            raise ValueError("纸面全宽hline只支持主轴；副轴请给 from/to")
    yv = spec.get("value")
    if yv is None and spec.get("col_last"):
        yv = float(ctx.df[spec["col_last"]].dropna().iloc[-1])
    xref = ctx.xaxis if (spec.get("from") or spec.get("to")) else "paper"
    fig.add_shape(type="line", x0=x0, x1=x1, y0=yv, y1=yv, xref=xref, yref=yref,
                  line=dict(color=spec.get("color", "#83898f"),
                            width=spec.get("width", 1.1), dash=spec.get("dash", "dash")))
    if spec.get("label"):
        fig.add_annotation(x=x0, y=yv, yref=yref,
                           xref=ctx.xaxis if spec.get("from") else "paper",
                           text=spec["label"], showarrow=False,
                           xanchor="left", yanchor="bottom",
                           font=dict(size=10.5, color=spec.get("color", "#55595f")),
                           bgcolor="white", opacity=.9)
