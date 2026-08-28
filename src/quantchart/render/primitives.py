"""通用绘图原语 → Plotly traces/shapes/annotations 翻译。不含任何计算。"""
import sys
from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go

from .theme import DARK


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
    # 主轴引用名 "y" 是 plotly 默认（不设等价）；副轴必须显式绑定，否则 trace 落主图
    yax = None if ctx.yaxis == "y" else ctx.yaxis
    fig.add_trace(go.Scatter(
        x=ctx.df["pos"], y=ctx.df[spec["col"]], yaxis=yax,
        mode="lines", name=spec.get("name", spec["col"]),
        line=dict(color=spec.get("color", "#1c4e9d"),
                  width=spec.get("width", 2),
                  dash=spec.get("dash", "solid"),
                  shape=spec.get("shape", "linear"))))


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
                            width=.9, dash=spec.get("dash", "dash")), layer="above")
    if spec.get("label"):
        fig.add_annotation(x=(x0 + x1) / 2, y=plo, yref=ctx.yaxis,
                           text=spec["label"], showarrow=False,
                           yanchor="bottom", yshift=6,
                           font=dict(size=11, color=spec.get("label_color", "#3a3f46")),
                           bgcolor=spec.get("label_bgcolor", "white"),
                           bordercolor=spec.get("label_bordercolor", "#c4c9d0"),
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
                           font=dict(size=10.5, color=spec.get("label_color",
                                     spec.get("color", "#55595f"))),
                           bgcolor=spec.get("label_bgcolor", "white"), opacity=.9)


def _events(fig, spec, ctx):
    """事件点标记：marker + 数值标签；style_map 按事件 meta.action 覆盖样式。

    按样式（符号,颜色）分组出 trace：单一样式时仅一个 trace、symbol 为标量
    （与 MVP 行为一致）；混合样式时各组分属不同 trace，避免 plotly 把
    symbol 归一成元组导致断言/下游取值形态改变。
    """
    ax = spec.get("axis", "y2")
    evs = spec["events"][spec["ref"]]
    style_map = spec.get("style_map", {})
    groups: dict[tuple, list] = {}
    for e in evs:
        st = style_map.get((e.meta or {}).get("action"), {})
        key = (st.get("symbol", spec.get("symbol", "triangle-down")),
               st.get("color", spec.get("color", "#701820")))
        groups.setdefault(key, []).append(e)
    for (sym, col), ge in groups.items():
        fig.add_trace(go.Scatter(
            x=[e.pos for e in ge], y=[e.value for e in ge], yaxis=ax,
            mode="markers", showlegend=False, hoverinfo="skip",
            marker=dict(symbol=sym, size=spec.get("size", 8), color=col,
                        line=dict(color="white", width=.8))))
        for e in ge:
            fig.add_annotation(x=e.pos, y=e.value, yref=ax, text=e.label,
                               showarrow=False, yanchor="top", yshift=-8,
                               font=dict(size=10.5, color=col),
                               bgcolor="white", opacity=.72, borderpad=1)


def _leader_tag(fig, spec, ctx):
    """低点事件 → 连线至基准线 + 价差/涨幅标注（含引导线）。trace 绑定所在面板轴。"""
    evs = spec["events"][spec["ref"]]
    ref = float(ctx.df[spec["ref_value_col"]].dropna().iloc[-1])
    # 主轴引用名 "y" 是 plotly 默认（不设等价）；副轴必须显式绑定，否则 trace 落主图
    yax = None if ctx.yaxis == "y" else ctx.yaxis
    for e in evs:
        diff = ref - e.value
        pct = (ref / e.value - 1) * 100
        txt = spec.get("text", "+{diff}（{pct}%）").format(
            diff=f"{diff:.0f}", pct=f"{pct:+.1f}", value=f"{e.value:,.0f}", ref=f"{ref:,.1f}")
        fig.add_trace(go.Scatter(x=[e.pos, e.pos], y=[e.value, ref], yaxis=yax,
                                 mode="lines",
                                 line=dict(color="#606a75", width=1, dash="dot"),
                                 showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[e.pos], y=[e.value], yaxis=yax, mode="markers",
                                 marker=dict(symbol="circle-open", size=7,
                                             color="#39414a", line=dict(width=1.1)),
                                 showlegend=False, hoverinfo="skip"))
        fig.add_annotation(x=e.pos, y=e.value, yref=yax, xref=ctx.xaxis, text=txt,
                           showarrow=True,
                           arrowhead=0, arrowcolor="#b3a5dd", arrowwidth=.9, standoff=6,
                           ax=spec.get("ax", 92), ay=spec.get("ay", -120),
                           font=dict(size=10.5, color="#8465c1"),
                           bgcolor="white", bordercolor="#b3a5dd",
                           borderpad=3, opacity=.95,
                           xanchor=spec.get("xanchor", "left"))
        fig.add_annotation(x=e.pos, y=e.value, yref=yax, xref=ctx.xaxis,
                           text=f"{e.value:,.0f}",
                           showarrow=False, yanchor="top", yshift=-7,
                           font=dict(size=10, color="#454b52"),
                           bgcolor="white", opacity=.75, borderpad=1)


def _day_seps(fig, spec, ctx):
    for p in ctx.slots.sep_center:
        fig.add_shape(type="line", x0=p, x1=p, y0=0, y1=1,
                      xref=ctx.xaxis, yref="paper",
                      line=dict(color=spec.get("color", "#b3b9c2"),
                                width=1, dash="dash"))


def _day_labels(fig, spec, ctx):
    for d, (s, e) in ctx.slots.day_span.items():
        fig.add_annotation(x=(s + e) / 2, y=spec.get("y", -.108), yref="paper",
                           text=d.strftime("%m-%d"), showarrow=False,
                           font=dict(size=11.5),
                           bgcolor="#f2f3f5", bordercolor="#d5d8dd", borderpad=3)


def _candle(fig, spec, ctx):
    """日线蜡烛：红涨青跌，颜色可配；x=pos 数值轴。"""
    yax = None if ctx.yaxis == "y" else ctx.yaxis
    fig.add_trace(go.Candlestick(
        x=ctx.df["pos"],
        open=ctx.df[spec.get("open", "open")],
        high=ctx.df[spec.get("high", "high")],
        low=ctx.df[spec.get("low", "low")],
        close=ctx.df[spec.get("close", "close")],
        yaxis=yax,
        increasing=dict(line=dict(color=spec.get("up", DARK["up"]), width=1)),
        decreasing=dict(line=dict(color=spec.get("down", DARK["down"]), width=1)),
        name=spec.get("name", "K线"), showlegend=False))


def _trendline(fig, spec, ctx):
    """两点趋势线/通道边线：from/to=[日期或pos, 价]，可带中点标签。"""
    (x0v, y0), (x1v, y1) = spec["from"], spec["to"]
    x0, x1 = _xof(ctx, x0v), _xof(ctx, x1v)
    yax = None if ctx.yaxis == "y" else ctx.yaxis
    fig.add_trace(go.Scatter(
        x=[x0, x1], y=[float(y0), float(y1)], yaxis=yax, mode="lines",
        line=dict(color=spec.get("color", "#dfe3ea"),
                  width=spec.get("width", 1.2), dash=spec.get("dash", "solid")),
        showlegend=False, hoverinfo="skip"))
    if spec.get("label"):
        fig.add_annotation(x=(x0 + x1) / 2, y=(float(y0) + float(y1)) / 2,
                           xref=ctx.xaxis, yref=ctx.yaxis, text=spec["label"],
                           showarrow=False,
                           font=dict(size=spec.get("label_size", 10.5),
                                     color=spec.get("label_color", spec.get("color", "#dfe3ea"))),
                           bgcolor=spec.get("label_bgcolor"), borderpad=2)


def _arrow(fig, spec, ctx):
    """带箭头引线：头点=to（或 from 本点），尾点=from；可选文字。全部数据坐标。"""
    fx, fy = spec["from"]
    fx = _xof(ctx, fx)
    yref = ctx.yaxis
    if "to" in spec:
        tx, ty = spec["to"]
        tx = _xof(ctx, tx)
        ax, ay = fx, fy
    else:
        tx, ty = fx, fy
        ax, ay = fx - float(spec.get("dx", 0)), fy - float(spec.get("dy", 0))
    # 注解没有 textposition 属性（scatter 专属），按 scatter 语义映射为锚点
    xa, ya = {"middle right": ("left", "middle"), "middle left": ("right", "middle"),
              "top center": ("center", "bottom"), "bottom center": ("center", "top"),
              "top right": ("left", "bottom"), "top left": ("right", "bottom"),
              "bottom right": ("left", "top"), "bottom left": ("right", "top"),
              "middle center": ("center", "middle")}.get(
        spec.get("text_position") or "middle right", ("left", "middle"))
    fig.add_annotation(x=tx, y=ty, ax=ax, ay=ay,
                       xref=ctx.xaxis, yref=yref, axref=ctx.xaxis, ayref=yref,
                       showarrow=True, arrowhead=spec.get("arrowhead", 2),
                       arrowsize=1.1, arrowwidth=spec.get("width", 1.6),
                       arrowcolor=spec.get("color", "#e0312f"),
                       standoff=spec.get("standoff", 3),
                       text=spec.get("text", ""),
                       xanchor=xa, yanchor=ya,
                       font=dict(size=spec.get("text_size", 11.5),
                                 color=spec.get("text_color", spec.get("color", "#e0312f"))))


def _tag(fig, spec, ctx):
    """右缘彩色药丸标签：价格数字 / BULL / BEAR / BASE。"""
    fig.add_annotation(xref="paper", x=1.002, xanchor="left",
                       y=float(spec["value"]), yref=ctx.yaxis,
                       text=str(spec["text"]), showarrow=False,
                       font=dict(size=spec.get("size", 11),
                                 color=spec.get("text_color", "#10131a")),
                       bgcolor=spec.get("color", "#ff8c00"),
                       borderpad=2.5, opacity=.95)


def _circle(fig, spec, ctx):
    """关键点圆圈标记，可带序号文字（at=[日期, 价]）。"""
    x, y = spec["at"]
    x = _xof(ctx, x)
    yax = None if ctx.yaxis == "y" else ctx.yaxis
    label = spec.get("label")
    fig.add_trace(go.Scatter(
        x=[x], y=[float(y)], yaxis=yax,
        mode="markers+text" if label else "markers",
        marker=dict(symbol="circle-open", size=spec.get("size", 14),
                    color=spec.get("color", "#f1c40f"), line=dict(width=1.6)),
        text=[str(label)] if label else None,
        textposition="top center",
        textfont=dict(size=10.5, color=spec.get("color", "#f1c40f")),
        showlegend=False, hoverinfo="skip"))


def _text(fig, spec, ctx):
    """自由彩字标注（品种大字/说明文字/高低点价签）。"""
    x, y = spec["at"]
    x = _xof(ctx, x)
    fig.add_annotation(x=x, y=float(y), xref=ctx.xaxis, yref=ctx.yaxis,
                       text=str(spec["text"]), showarrow=False,
                       font=dict(size=spec.get("size", 12),
                                 color=spec.get("color", "#dfe3ea")),
                       bgcolor=spec.get("bgcolor"), borderpad=2 if spec.get("bgcolor") else 0)
