import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from quantchart.qa.verify import Verifier


def _fig():
    x = list(range(6))
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=x, open=[1]*6, high=[2]*6, low=[0.5]*6,
                                 close=[1.5]*6, increasing_line_color="#ff0000",
                                 decreasing_line_color="#00ff00", showlegend=False))
    fig.add_trace(go.Scatter(x=[0, 5], y=[50.0, 60.0], mode="lines",
                             line=dict(color="#39d353", dash="dash"), showlegend=False))
    fig.add_trace(go.Scatter(x=[0, 5], y=[110.0, 120.0], mode="lines",
                             line=dict(color="#39d353", dash="dash"), showlegend=False))
    fig.add_trace(go.Scatter(x=[2], y=[100.0], mode="markers",
                             marker=dict(symbol="circle-open"), showlegend=False))
    fig.add_annotation(x=2, y=100.0, text="低点标注", showarrow=False)
    return fig


def _df():
    x = np.arange(6, dtype=float)
    mid = 2.0 * x + 100.0
    return pd.DataFrame({"datetime": pd.date_range("2026-06-01", periods=6, freq="B"),
                         "pos": x, "open": mid, "high": mid + 60.0,
                         "low": mid - 50.0, "close": mid})


def test_l1_inventory_ok_and_missing():
    v = Verifier(_fig(), _df())
    v.expect_candle(up="#ff0000", down="#00ff00")
    v.expect_channel(color="#39d353", dash="dash")          # 两条平行轨
    v.expect_text("低点标注")
    assert v.ok()
    v2 = Verifier(_fig(), _df())
    v2.expect_channel(color="#ffcc00")                       # 不存在的通道
    assert not v2.ok()


def test_l2_circle_on_point_and_side():
    v = Verifier(_fig(), _df())
    v.expect_point_on((2.0, 100.0), x=2, y=100.0, tol=3)     # 圈心在标注锚点上
    v.expect_last_candle_right_of(5.0, x_min=5.2)            # 预演元素在最右K线右侧
    assert v.ok()
    v2 = Verifier(_fig(), _df())
    # 注：brief 原稿 x=4 与标记 x=2 仅差 2 ≤ tol=3，触发不了违规（测试自身矛盾），改为 x=6
    v2.expect_point_on((2.0, 100.0), x=6, y=100.0, tol=3)    # x 离谱 → 违规
    assert not v2.ok()


def test_l3_parallel_and_wrap():
    v = Verifier(_fig(), _df())
    v.expect_parallel(color="#39d353", tol=1e-6)             # 两轨平行
    df = _df()
    v.expect_lower_wraps(df, color="#39d353",
                         points=[(1, df['low'].iloc[1]), (3, df['low'].iloc[3])])
    assert v.ok()


def test_l3_span_math():
    v = Verifier(_fig(), _df())
    v.expect_span(110.0, 50.0, label=60.0, tol=1.0)          # 标注值 == 两轨同一 x 处差值
    v2 = Verifier(_fig(), _df())
    v2.expect_span(110.0, 50.0, label=77.0, tol=1.0)
    assert not v2.ok()


def test_render_fidelity_rail_matches_fit():
    from quantchart.core.channel import fit_channel
    df = _df()
    fit = fit_channel(df, df["datetime"].iloc[0], df["datetime"].iloc[-1])
    # 注：brief 原稿只画下轨，而 expect_render_matches_fit 要求同色两轨（len<2 直接记 R 违规），
    # 故补画上轨——下轨仍承担 447 点偏移的负例
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[fit.window[0], fit.window[1]],
                             y=[fit.lower[0][1], fit.lower[1][1]],
                             line=dict(color="#39d353"), showlegend=False))
    fig.add_trace(go.Scatter(x=[fit.window[0], fit.window[1]],
                             y=[fit.upper[0][1], fit.upper[1][1]],
                             line=dict(color="#39d353"), showlegend=False))
    v = Verifier(fig, df)
    v.expect_render_matches_fit(color="#39d353", fit=fit, tol=3.0)
    assert v.ok()
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=[fit.window[0], fit.window[1]],
                              y=[fit.lower[0][1] + 447.0, fit.lower[1][1] + 447.0],
                              line=dict(color="#39d353"), showlegend=False))
    fig2.add_trace(go.Scatter(x=[fit.window[0], fit.window[1]],
                              y=[fit.upper[0][1], fit.upper[1][1]],
                              line=dict(color="#39d353"), showlegend=False))
    v2 = Verifier(fig2, df)
    v2.expect_render_matches_fit(color="#39d353", fit=fit, tol=3.0)   # 447点偏移必须被抓
    assert not v2.ok()


def test_l1_extras_line_shape_marker_and_ma():
    df = _df()
    fig = _fig()
    fig.add_shape(type="line", x0=0, x1=5, y0=95.0, y1=95.0)   # 一条水平线 shape
    ma = df["close"].rolling(3).mean()
    fig.add_trace(go.Scatter(x=list(range(6)),
                             y=[None, None] + [float(ma.iloc[i]) for i in range(2, 6)],
                             mode="lines", name="MA3", showlegend=False))
    v = Verifier(fig, df)
    v.expect_line(color="#39d353", min_n=2, dash="dash")       # 两条同色虚线轨
    v.expect_shape_lines(1)
    v.expect_marker_at(2, 100.0)                               # 圆圈标记在 (2,100)
    v.expect_ma_last("MA3", window=3)                          # 末值 == rolling(3) 末值
    assert v.ok()
    v2 = Verifier(_fig(), df)                                  # 无 shape、无 MA、颜色/位置均不符
    v2.expect_line(color="#123456")
    v2.expect_shape_lines(2)
    v2.expect_marker_at(6, 100.0)                              # x 差 4 > tol 3 → 违规
    v2.expect_ma_last("MA9", window=3)
    assert not v2.ok()


def test_upper_wraps_symmetric_to_lower():
    fig, df = _fig(), _df()
    v = Verifier(fig, df)
    v.expect_upper_wraps(df, "#39d353", [(1.0, 111.0), (4.0, 119.0)])   # 高点在上轨下方
    assert v.ok()
    v2 = Verifier(fig, df)
    v2.expect_upper_wraps(df, "#39d353", [(1.0, 121.0)])                # 刺穿上轨 → 违规
    assert not v2.ok()


def test_by_color_skips_non_line_traces():
    # 多面板量柱（Bar 无 .line 属性）入图后，按色取线不得 AttributeError
    fig = _fig()
    fig.add_trace(go.Bar(x=[0, 5], y=[1.0, 2.0], marker_color="#39d353"))
    v = Verifier(fig, _df())
    v.expect_channel(color="#39d353", dash="dash")          # 仍只数两条 scatter 轨
    assert v.ok()


def test_left_quarter_and_forecast_zone_helpers():
    df = _df()                                                          # 6 根
    v = Verifier(_fig(), df)
    v.expect_in_left_quarter(1.0, name="大字")
    v.expect_in_forecast_zone(6.5, name="预演")
    assert v.ok()
    v2 = Verifier(_fig(), df)
    v2.expect_in_left_quarter(5.0, name="大字")                          # 5 > 6/4+2 → 违规
    v3 = Verifier(_fig(), df)
    v3.expect_in_forecast_zone(5.0, name="预演")                          # 5 ≤ 6 不在预测区
    assert not v2.ok() and not v3.ok()
