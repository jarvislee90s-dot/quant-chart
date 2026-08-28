"""01 伦敦金现货（XAU 日线）三层验收清单（对照 reference/01，数值均经 zoom 读图确认+数据交叉验证）。

L1 要素：深色蜡烛红涨青跌；MA×5（字面根数）；周线级别下降通道（黄绿虚线成对）；
        水平线×3+右缘药丸×3（4841.255/4384.642/3928.818）；多空分界（黄字+红↑绿↓）；
        区间价差红竖箭头×2+蓝字×2（455USD）；BULL/BEAR；大字"伦敦金现货"（红）；
        历史高点价签 5598.750（红字+灰白小箭头）；通道标签"周线级别下降通道"（亮绿大字）。
L2 相对位置：药丸与水平线同高（±3）；多空分界文字距中线（±30）；价差箭头整体位于相邻两水平线所夹区域；
        BULL/BEAR 在最后K线右侧预测区；高点价签锚在数据最高K线（±5根/±30点）；大字不压K线密集区。
L3 数学：通道两轨平行且==fit_channel 重算（渲染保真）；下轨包裹窗口最深低点；上轨压住峰值高点；
        价差标注数值==箭头两端 y 差（±2）；MA5/10/20/30/60 末值==rolling 末值（±1e-6）。
"""
import pandas as pd

from quantchart.core.channel import fit_channel
from quantchart.core.session import build_daily_slots
from quantchart.qa.verify import Verifier

# ── 读图确认位阶（Step 2，证据 out/refs/chart_01/zoom_*.png） ──
TOP, MID, BOT = 4841.255, 4384.642, 3928.818     # 顶线/多空分界线/前低（8x zoom 逐字确认）
SPREAD_LABEL = 455.0                              # "区间价差455USD"（非缩略图视觉的 555）
PEAK_HIGH = 5596.33                               # 本批数据峰值（2026-01-29）；价签文字用样张原值 5598.750
CHAN_COLOR = "#67c805"
C_TOP, C_MID, C_BOT = "#ff8888", "#fe9b00", "#3d94a8"


def run(fig, df, rep, cfg) -> Verifier:
    d = build_daily_slots(df).df
    v = Verifier(fig, d, name="chart_01_xau")
    peak_pos = float(d.loc[d["high"].idxmax(), "pos"])
    last_pos = float(d["pos"].iloc[-1])                       # 最后一根 K 线 pos（257 交易日，0 基）

    # ── L1 要素层 ──
    v.expect_candle("#ff0000", "#3acccc")
    v.expect_channel(CHAN_COLOR, "dash")                      # 周线级别下降通道双轨
    v.expect_shape_lines(3)                                   # 三条水平线
    for substr in ("周线级别下降通道", "多空分界线", "区间价差455USD",
                   "BULL", "BEAR", "5598.750"):
        v.expect_text(substr)
    big = [a for a in fig.layout.annotations if a.text == "伦敦金现货"]
    if not big:                                               # 精确匹配，避免命中页眉标题
        v._fail("L1", '缺少品种大字"伦敦金现货"')
    pills = {c: [a for a in fig.layout.annotations
                 if getattr(a, "bgcolor", None) == c] for c in (C_TOP, C_MID, C_BOT)}
    for c, name in ((C_TOP, "顶"), (C_MID, "中"), (C_BOT, "底")):
        if not pills[c]:
            v._fail("L1", f"缺少{name}药丸(#{c})")

    # ── L2 相对位置层 ──
    hlines = {s.line.color: s.y0 for s in fig.layout.shapes
              if s.type == "line" and s.y0 == s.y1}
    for c, val, name in ((C_TOP, TOP, "顶"), (C_MID, MID, "中"), (C_BOT, BOT, "底")):
        if c not in hlines:                               # 缺失或被改色（expect_shape_lines 只计数不查色，此处按颜色兜底）
            v._fail("L2", f"颜色 {c} 的{name}水平线缺失")
        elif abs(hlines[c] - val) > 1e-6:
            v._fail("L2", f"{name}水平线值不符: {hlines[c]} ≠ {val}")
        if pills[c]:
            if abs(float(pills[c][0].y) - val) > 3:           # 药丸与水平线同高 ±3
                v._fail("L2", f"{name}药丸 y={pills[c][0].y} 与水平线 {val} 不同高(±3)")
    duokong = [a for a in fig.layout.annotations if a.text and "多空分界线" in a.text]
    if duokong and abs(float(duokong[0].y) - MID) > 30:       # 多空分界文字距中线 ±30
        v._fail("L2", f"多空分界文字 y={duokong[0].y} 距中线 {MID} 超出 ±30")
    # 价差箭头×2：整体位于相邻两水平线所夹区域；标注数值==两端 y 差（L3）
    spreads = [a for a in fig.layout.annotations
               if getattr(a, "arrowcolor", None) == "#cc0607"]
    if len(spreads) != 2:
        v._fail("L2", f"区间价差红箭头数量 {len(spreads)} ≠ 2")
    else:
        spreads = sorted(spreads, key=lambda a: min(a.y, a.ay))
        bands = [(BOT, MID), (MID, TOP)]                      # 低箭头→下夹区，高箭头→上夹区
        for a, (lo, hi) in zip(spreads, bands):
            if not (lo - 3 <= min(a.y, a.ay) and max(a.y, a.ay) <= hi + 3):
                v._fail("L2", f"价差箭头 [{min(a.y,a.ay):.1f},{max(a.y,a.ay):.1f}] 越出夹区 [{lo},{hi}]")
            v.expect_span(float(a.y), float(a.ay), SPREAD_LABEL, tol=2)
    # BULL/BEAR（含其箭头）整体位于最后K线右侧预测区
    fc = [a for a in fig.layout.annotations
          if (a.text in ("BULL", "BEAR")) or (getattr(a, "arrowcolor", None) in ("#f04a4a", "#6fc80a"))]
    if fc:
        tails = [float(a.ax) if a.ax is not None else float(a.x) for a in fc]
        v.expect_last_candle_right_of(last_pos, min(float(a.x) for a in fc))
        v.expect_last_candle_right_of(last_pos, min(tails))
    else:
        v._fail("L2", "缺少 BULL/BEAR 预测区元素")
    # 高点价签锚在数据最高K线（±5根、±30点），且锚点略高于峰值
    tag = [a for a in fig.layout.annotations if a.text == "5598.750"]
    if not tag:
        v._fail("L2", "缺少历史高点价签 5598.750")
    else:
        v.expect_point_on((float(tag[0].x), float(tag[0].y)), peak_pos, PEAK_HIGH + 2.7, tol=5)
        if not (-5 <= float(tag[0].x) - peak_pos <= 5 and 0 <= float(tag[0].y) - PEAK_HIGH <= 30):
            v._fail("L2", f"价签锚点 ({tag[0].x},{tag[0].y}) 未紧邻峰值K线 ({peak_pos},{PEAK_HIGH}) 右上方")
    # 大字位于下部空白区、不压 K 线密集区（对照样张：26-03 下部，低于 3-4 月窗口最低低点 80 点以上）
    if big:
        w = d[(d["datetime"] >= pd.Timestamp("2026-03-01")) & (d["datetime"] <= pd.Timestamp("2026-04-30"))]
        if not (100 <= float(big[0].x) <= 190):
            v._fail("L2", f"大字 x={big[0].x} 不在图幅中段（样张 26-03/26-04 处）")
        if float(big[0].y) > float(w["low"].min()) - 80:
            v._fail("L2", f"大字 y={big[0].y} 压到 K 线密集区（窗口最低 {w['low'].min():.1f}）")

    # ── L3 数学关系层 ──
    fit = fit_channel(d, "2026-01-29", "2026-08-28", tilt=0.12, press=1.0)
    v.expect_render_matches_fit(CHAN_COLOR, fit, tol=3.0)     # R 渲染保真（与 expect_lower_wraps 成对使用）
    v.expect_parallel(CHAN_COLOR)
    v.expect_lower_wraps(d, CHAN_COLOR, [(143.0, 4099.02), (214.0, 3960.10)])
    rails = sorted([t for t in fig.data
                    if t.type == "scatter" and getattr(t.line, "color", None) == CHAN_COLOR],
                   key=lambda t: t.y[0])
    if len(rails) >= 2:
        if abs(float(rails[-1].y[0]) - PEAK_HIGH) > 5:        # 上轨 ≥ 窗口内最高高点（±5）
            v._fail("L3", f"上轨起点 {rails[-1].y[0]:.1f} 未压住峰值 {PEAK_HIGH}(±5)")
    for name, window in (("MA5", 5), ("MA10", 10), ("MA20", 20), ("MA30", 30), ("MA60", 60)):
        v.expect_ma_last(name, window)
    return v
