"""日线多面板（主图+成交量子图）三层验收清单。

演示数据 examples/daily_volume_demo.csv（tools/make_demo_daily.py 合成，种子 20260831）；
数值全部按 df 动态重算，唯支撑线 6900 为配置与清单双端钉死的读图位阶。
经 tests/test_acceptance_charts.py 登记即跑（CSV 随仓，不 skip）。

L1 要素：深色蜡烛红涨青跌；MA×3（5/10/20）；成交量 bar trace；双面板轴（yaxis2）；
        量轴标题"成交量"；演示通道双轨（#fdfd52）；支撑水平线+右缘药丸 6900。
L2 相对位置：量柱 x 与 K 线 x 逐柱同位（shared_xaxes 对齐）；量柱落 y2 不混入主图；
        量柱峰值 == 数据最大量；时间刻度只在底轴（顶轴隐藏）；药丸与支撑线同高（±3）。
L3 数学：量柱红涨青跌与 df 逐柱一致；MA5/10/20 末值 == rolling 末值（±1e-6）；
        通道两轨平行且 == fit_channel 重算（R 渲染保真）；支撑线值 == 6900。
"""
import numpy as np

from quantchart.core.channel import fit_channel
from quantchart.core.session import build_daily_slots
from quantchart.qa.verify import Verifier
from quantchart.render.theme import DARK

SUPPORT = 6900.0                              # 支撑线（与 configs/daily_volume_demo.yaml 双端钉死）
CHAN_COLOR = "#fdfd52"


def run(fig, df, rep, cfg) -> Verifier:
    d = build_daily_slots(df).df
    v = Verifier(fig, d, name="daily_volume_demo")

    # ── L1 要素层 ──
    v.expect_candle(DARK["up"], DARK["down"])
    bars = [t for t in fig.data if t.type == "bar"]
    if not bars:
        v._fail("L1", "缺少成交量子图 bar trace")
    for name in ("MA5", "MA10", "MA20"):
        if not [t for t in fig.data if t.name == name]:
            v._fail("L1", f"缺少 {name}")
    if getattr(fig.layout.yaxis2.title, "text", None) != "成交量":
        v._fail("L1", f"量轴标题不符: {fig.layout.yaxis2.title.text!r}")
    v.expect_channel(CHAN_COLOR, "dash")                       # 演示通道双轨
    v.expect_text("6900")                                      # 右缘药丸

    # ── L2 相对位置层 ──
    if bars:
        b = bars[0]
        candles = [t for t in fig.data if t.type == "candlestick"]
        if list(b.x) != list(candles[0].x):                    # 逐柱同位（共享X对齐）
            v._fail("L2", "量柱 x 与 K 线 x 未逐柱对齐")
        if b.yaxis != "y2":                                     # 落量轴而非主图
            v._fail("L2", f"量柱落在 {b.yaxis}（应在 y2 量轴）")
        if abs(float(np.max(b.y)) - float(d["volume"].max())) > 1e-6:
            v._fail("L2", f"量柱峰值 {np.max(b.y):.0f} ≠ 数据最大量 {d['volume'].max():.0f}")
        if float(fig.layout.yaxis2.range[0]) != 0.0:           # 量轴 0 基线
            v._fail("L2", f"量轴下限 {fig.layout.yaxis2.range[0]} ≠ 0（量柱应锁 0 基线）")
    if fig.layout.xaxis.showticklabels is not False:          # 顶轴刻度隐藏
        v._fail("L2", "多面板顶轴刻度未隐藏（时间刻度应只画底轴）")
    bx = fig.layout.xaxis2
    if bx.showticklabels is False or not list(getattr(bx, "tickvals", []) or []):
        v._fail("L2", "底轴刻度缺失（时间刻度应画在最底面板）")
    hlines = {s.line.color: s.y0 for s in fig.layout.shapes
              if s.type == "line" and s.y0 == s.y1}
    if "#e47b7c" not in hlines:
        v._fail("L2", "支撑水平线（#e47b7c）缺失")
    elif abs(float(hlines["#e47b7c"]) - SUPPORT) > 1e-6:
        v._fail("L2", f"支撑线值 {hlines['#e47b7c']} ≠ {SUPPORT}")
    pills = [a for a in fig.layout.annotations
             if getattr(a, "bgcolor", None) == "#ff8888"]
    if pills and abs(float(pills[0].y) - SUPPORT) > 3:         # 药丸与支撑线同高 ±3
        v._fail("L2", f"药丸 y={pills[0].y} 与支撑线 {SUPPORT} 不同高(±3)")

    # ── L3 数学关系层 ──
    if bars:
        up = (d["close"] >= d["open"]).to_numpy()
        want = [DARK["up"] if u else DARK["down"] for u in up]
        got = [str(c) for c in bars[0].marker.color]
        if got != want:                                         # 红涨青跌逐柱一致
            v._fail("L3", f"量柱涨跌色与 df 不符（首柱 {got[0]} ≠ {want[0]}）")
    for name, window in (("MA5", 5), ("MA10", 10), ("MA20", 20)):
        v.expect_ma_last(name, window)
    fit = fit_channel(d, "2026-06-15", "2026-08-15", tilt=0.12, press=1.0)
    v.expect_render_matches_fit(CHAN_COLOR, fit, tol=3.0)      # R 渲染保真
    v.expect_parallel(CHAN_COLOR)
    return v
