"""02 沪铜主力合约（CU0 日线）三层验收清单（对照 reference/02，数值均经 zoom 读图确认+数据交叉验证）。

L1 要素：深色蜡烛红涨青跌；MA×5（字面根数）；水平线×4+右缘药丸×4（112548/105431/98515/91558，
        计划暂记×3，zoom 证实样张实为 4 条——棕/粉/绿/黄，见 configs/chart_02_cu0.yaml 头注）；
        白色长上升趋势线；黄圈×4（≥3）；红竖箭头×2+蓝字"区间宽度6916元/6957元"×2（zoom 证实为蓝字，
        非计划暂记"红字"）；蓝字×2+蓝箭头×4；红字形态说明×2 行；颈线红箭头+序号 1-4+红指针；
        BULL/BEAR；峰值价签 114160（红字+灰白小箭头）；大字"沪铜主力合约"（红）。
L2 相对位置：药丸与水平线同高（±3）；黄圈群贴 105431 线（各圈 |y−105431|≤600，样张最大偏 15.5px×38.8元/px，
        计划"±30"为像素口径，此处按数据坐标系换算）；两条红竖箭头各落在相邻两水平线所夹带内
        （计划"最上与中间之间"按样张实际几何落地：上箭头绿~粉带、下箭头黄~绿带）；
        BULL/BEAR 在最后K线右侧预测区；白趋势线起点在左侧下部空白带、终点在右侧；蓝字位于上部带；
        颈线红箭头自"1"点峰值水平向右越出最后K线；价签锚在数据最高K线；大字在下部空白区不压K线。
L3 数学：白趋势线坐标==YAML 声明端点复算（渲染保真，±1e-6）；其斜率与窗口中枢 LSQ 斜率同号且
        |s−s_mid|≤0.55·|s_mid|（0.55 为实测标定：样张白线斜率相对窗口中枢斜率偏差 53%）；
        价差标注==箭头跨距（±2）且==相邻水平线之差（±1e-6，样张逐元相等）；
        白趋势线自窗口低点下方通过（expect_lower_wraps，与渲染保真配对）；
        MA5/10/20/30/60 末值==rolling 末值（±1e-6）。
  渲染保真口径说明：reference/02 无通道（zoom 证据：全图仅一条白色趋势线，无黄绿虚线对），
        故 Task 1 的 expect_render_matches_fit（针对 fit_channel 双轨）不适用；
        R 层以"fig 白趋势线坐标==YAML 声明端点复算（±1e-6）"落实同一定义——"画出来的==算出来的"；
        并加**渲染可见性守卫**：面板0全部数据坐标元素必须落在 xaxis 右界
        （n_all + FORECAST_DAYS×bars_per_day + 1.5 = 244.5）内，超界即被 Plotly 裁剪不可见
        （fix round 1：BULL/BEAR/绿V 曾置于 x=248-255.3 被裁掉，而纯坐标断言仍全绿——此守卫防复发）。
"""
import numpy as np
import pandas as pd

from quantchart.core.session import build_daily_slots
from quantchart.qa.verify import Verifier

# ── 读图确认位阶（Step 2，证据 out/refs/chart_02/*_8x.png / *_6x.png / *_3x.png） ──
TOP, MID, GRN, BOT = 112548.0, 105431.0, 98515.0, 91558.0      # 棕/粉/绿/黄 四线位阶
SPREAD_UP, SPREAD_DN = 6916.0, 6957.0                           # 区间宽度标注（== 相邻线差，逐元）
C_TOP, C_MID, C_GRN, C_BOT = "#9c4210", "#ff8890", "#26b500", "#868000"   # 药丸底色
L_TOP, L_MID, L_GRN, L_BOT = "#6b3a14", "#e07070", "#069106", "#565a0c"   # 水平线色
WHITE, CIRCLE = "#8b929a", "#f5d321"
RED_ARR, BLUE, YELLOW = "#df0203", "#0b7ec2", "#f0f000"
NECK_RED, BEAR_GRN = "#e04040", "#80c000"
PEAK_HIGH = 114160.0                                            # 数据峰值（2026-01-30，与样张价签一致）
TREND_TILT = 0.55                                               # 白线斜率 vs 中枢斜率容许偏差（实测标定）
CIRCLE_TOL = 600.0                                              # 圈心贴线容差（样张 15.5px × 38.8元/px）


def _anns(fig):
    return list(fig.layout.annotations)


def run(fig, df, rep, cfg) -> Verifier:
    d = build_daily_slots(df).df
    v = Verifier(fig, d, name="chart_02_cu0")
    last_pos = float(d["pos"].iloc[-1])                       # 最后一根 K 线 pos（241 交易日，0 基 240）
    peak_pos = float(d.loc[d["high"].idxmax(), "pos"])

    # ── L1 要素层 ──
    v.expect_candle("#ff0000", "#3acccc")
    mas = {n: [t for t in fig.data if t.type == "scatter" and t.name == f"MA{n}"]
           for n in (5, 10, 20, 30, 60)}
    for n, ts in mas.items():
        if not ts:                                            # 存在性守卫：缺 MA 直接记录
            v._fail("L1", f"缺少 MA{n}")
    v.expect_shape_lines(4)                                   # 四条水平线
    hlines = {}
    for c in (L_TOP, L_MID, L_GRN, L_BOT):
        hlines[c] = [s for s in fig.layout.shapes
                     if s.type == "line" and s.y0 == s.y1 and s.line.color == c]
    for c, val, name in ((L_TOP, TOP, "顶"), (L_MID, MID, "当前价"),
                         (L_GRN, GRN, "绿"), (L_BOT, BOT, "黄")):
        if not hlines[c]:                                     # 按颜色存在性守卫（防漏报，同 4be2666 加固）
            v._fail("L1", f"颜色 {c} 的{name}水平线缺失")
    pills = {c: [a for a in _anns(fig) if getattr(a, "bgcolor", None) == c]
             for c in (C_TOP, C_MID, C_GRN, C_BOT)}
    for c, val, name in ((C_TOP, TOP, "顶"), (C_MID, MID, "当前价"),
                         (C_GRN, GRN, "绿"), (C_BOT, BOT, "黄")):
        if not pills[c]:
            v._fail("L1", f"缺少{name}药丸(#{c})")
        elif pills[c][0].text != str(int(val)):               # 药丸数值逐字守卫（zoom 确认值）
            v._fail("L1", f"{name}药丸文字 {pills[c][0].text} ≠ {int(val)}")
    circles = [t for t in fig.data if t.type == "scatter"
               and getattr(t.marker, "symbol", None) == "circle-open"
               and getattr(t.marker, "color", None) == CIRCLE]
    if sum(len(t.x) for t in circles) < 3:
        v._fail("L1", f"黄圈数量 {sum(len(t.x) for t in circles)} < 3")
    white = [t for t in fig.data if t.type == "scatter"
             and getattr(t.line, "color", None) == WHITE]
    if not white or len(white[0].x) != 2:
        v._fail("L1", "缺少白色长上升趋势线（两点）")
    for substr in ("前期四次假突破", "本轮突破后已持续2周不破位",
                   "区间宽度6916元", "区间宽度6957元",
                   "黄色箭头趋势符合", "杯柄突破形态特征",
                   "BULL", "BEAR", "114160"):
        v.expect_text(substr)
    big = [a for a in _anns(fig) if a.text == "沪铜主力合约"]
    if not big:                                               # 精确匹配，避免命中页眉标题
        v._fail("L1", '缺少品种大字"沪铜主力合约"')
    nums = {a.text for a in _anns(fig)}
    for n in ("1", "2", "3", "4"):
        if n not in nums:
            v._fail("L1", f"缺少序号文字 {n}")
    spreads = [a for a in _anns(fig) if getattr(a, "arrowcolor", None) == RED_ARR]
    if len(spreads) != 2:
        v._fail("L1", f"区间价差红竖箭头数量 {len(spreads)} ≠ 2")
    else:
        for a in spreads:                                     # 竖直守卫：头尾同 x
            if abs(float(a.x) - float(a.ax)) > 1e-6:
                v._fail("L1", "价差箭头非竖直")
    blue_arrows = [a for a in _anns(fig) if getattr(a, "arrowcolor", None) == BLUE]
    if len(blue_arrows) < 3:
        v._fail("L1", f"蓝箭头数量 {len(blue_arrows)} < 3")
    yellow_arrows = [a for a in _anns(fig) if getattr(a, "arrowcolor", None) == YELLOW]
    if len(yellow_arrows) < 3:
        v._fail("L1", f"黄箭头数量 {len(yellow_arrows)} < 3")
    necks = [a for a in _anns(fig) if getattr(a, "arrowcolor", None) == NECK_RED
             and abs(float(a.y) - float(a.ay)) <= 1e-6]
    if not necks:
        v._fail("L1", "缺少颈线红箭头（水平）")
    ptrs = [a for a in _anns(fig) if getattr(a, "arrowcolor", None) == NECK_RED
            and abs(float(a.y) - float(a.ay)) > 1e-6]
    if not ptrs:
        v._fail("L1", "缺少红色下行指针箭头")
    green_arrows = [a for a in _anns(fig) if getattr(a, "arrowcolor", None) == BEAR_GRN]
    if len(green_arrows) < 2:
        v._fail("L1", f"BEAR 绿箭头数量 {len(green_arrows)} < 2")

    # ── L2 相对位置层 ──
    for c, lc, val, name in ((C_TOP, L_TOP, TOP, "顶"), (C_MID, L_MID, MID, "当前价"),
                             (C_GRN, L_GRN, GRN, "绿"), (C_BOT, L_BOT, BOT, "黄")):
        if hlines[lc] and abs(float(hlines[lc][0].y0) - val) > 1e-6:
            v._fail("L2", f"{name}水平线值不符: {hlines[lc][0].y0} ≠ {val}")
        if pills[c] and abs(float(pills[c][0].y) - val) > 3:  # 药丸与水平线同高 ±3
            v._fail("L2", f"{name}药丸 y={pills[c][0].y} 与水平线 {val} 不同高(±3)")
    for t in circles:                                         # 黄圈群贴 105431 线（换算容差 600）
        for x, y in zip(t.x, t.y):
            if abs(float(y) - MID) > CIRCLE_TOL:
                v._fail("L2", f"黄圈 ({float(x)},{float(y)}) 距当前价线 {MID} 超出 ±{CIRCLE_TOL:.0f}")
    if len(spreads) == 2:
        spans = sorted(spreads, key=lambda a: min(float(a.y), float(a.ay)))
        bands = [(BOT, GRN), (GRN, MID)]                      # 低箭头→黄~绿带，高箭头→绿~粉带（样张实际几何）
        for a, (lo, hi) in zip(spans, bands):
            if not (lo - 3 <= min(float(a.y), float(a.ay)) and max(float(a.y), float(a.ay)) <= hi + 3):
                v._fail("L2", f"价差箭头 [{min(float(a.y), float(a.ay)):.1f},"
                              f"{max(float(a.y), float(a.ay)):.1f}] 越出夹带 [{lo},{hi}]")
    # BULL/BEAR 预测区元素（文字+红↑绿V箭头——首尾端点均在最后K线右侧者）整体位于预测区；
    # 颈线红箭头/红色指针属历史区标注（样张亦压在历史K线上方），不参与该约束
    cand = [a for a in _anns(fig)
            if a.text in ("BULL", "BEAR") or getattr(a, "arrowcolor", None) in (NECK_RED, BEAR_GRN)]
    fc = [a for a in cand
          if float(a.x) > last_pos and (a.ax is None or float(a.ax) > last_pos)]
    if not any(a.text == "BULL" for a in fc) or not any(a.text == "BEAR" for a in fc):
        v._fail("L2", "缺少 BULL/BEAR 预测区元素")
    bull_arrow = [a for a in cand if getattr(a, "arrowcolor", None) == NECK_RED
                  and float(a.ax) > last_pos and abs(float(a.y) - float(a.ay)) > 1e-6]
    if not bull_arrow:
        v._fail("L2", "缺少 BULL 红色上攻箭头")
    if fc:
        tails = [float(a.ax) if a.ax is not None else float(a.x) for a in fc]
        v.expect_last_candle_right_of(last_pos, min(float(a.x) for a in fc))
        v.expect_last_candle_right_of(last_pos, min(tails))
    # 白趋势线：起点在窗口左侧下部空白带、终点在右侧（样张全程位于价格带下方）
    if white and len(white[0].x) == 2:
        x0, x1 = float(white[0].x[0]), float(white[0].x[1])
        y0, y1 = float(white[0].y[0]), float(white[0].y[1])
        if x0 > 130:
            v._fail("L2", f"白趋势线起点 x={x0} 不在窗口左侧（≤130）")
        if y0 > 85000:
            v._fail("L2", f"白趋势线起点 y={y0} 不在下部空白带（≤85000）")
        if x1 < 230:
            v._fail("L2", f"白趋势线终点 x={x1} 未达右侧（≥230）")
    # 蓝字位于上部带（样张两行蓝说明在棕线下方、粉线上方的 109k-112k 带）
    for substr, lo, hi in (("前期四次假突破", 109000, 112200), ("本轮突破后", 109000, 112200)):
        ts = [a for a in _anns(fig) if a.text and substr in a.text]
        if ts and not (lo <= float(ts[0].y) <= hi):
            v._fail("L2", f"蓝字'{substr}' y={ts[0].y} 不在上部带 [{lo},{hi}]")
    # 颈线红箭头：水平、贴"1"点峰值高度、向右越出最后K线
    if necks:
        nk = necks[0]
        p1 = float(d.loc[d["datetime"] == pd.Timestamp("2026-05-13"), "pos"].iloc[0])
        if not (108500 <= float(nk.y) <= 109000):
            v._fail("L2", f"颈线 y={nk.y} 不在峰值带 [108500,109000]")
        if abs(float(nk.ax) - p1) > 3:
            v._fail("L2", f"颈线起点 x={nk.ax} 未锚在'1'点峰值K线（pos {p1}±3）")
        if float(nk.x) <= last_pos:
            v._fail("L2", "颈线未越出最后K线")
    # 峰值价签锚在数据最高K线（±5根），锚点略高于峰值
    tag = [a for a in _anns(fig) if a.text == "114160"]
    if not tag:
        v._fail("L2", "缺少历史峰值价签 114160")
    else:
        if abs(float(tag[0].x) - peak_pos) > 5 or not (0 <= float(tag[0].y) - PEAK_HIGH <= 200):
            v._fail("L2", f"价签锚点 ({tag[0].x},{tag[0].y}) 未指向峰值K线 ({peak_pos},{PEAK_HIGH}) 上方")
    # 大字位于下部空白区、不压 K 线密集区（样张 26-04 下部）
    if big:
        w = d[(d["datetime"] >= pd.Timestamp("2026-04-01")) & (d["datetime"] <= pd.Timestamp("2026-05-31"))]
        if not (145 <= float(big[0].x) <= 175):
            v._fail("L2", f"大字 x={big[0].x} 不在图幅中段（样张 26-04 处）")
        if float(big[0].y) > float(w["low"].min()) - 80:
            v._fail("L2", f"大字 y={big[0].y} 压到 K 线密集区（窗口最低 {w['low'].min():.1f}）")

    # ── R 渲染可见性守卫（防"画的≠可见"）：面板0全部数据坐标元素（annotations 头/尾、traces 最右点）
    #    必须落在 xaxis 右界内（figure_daily: n_all + FORECAST_DAYS×bars_per_day + 1.5 = 244.5），
    #    超界元素会被 Plotly 裁剪而在成品 PNG 中不可见——fix round 1 中 BULL/BEAR/绿V 即因此丢失，
    #    而纯坐标断言（x>last_pos）恰被导致隐藏的超界位置满足。此守卫防该失败模式在后续图复发。
    x_right = fig.layout.xaxis.range
    if x_right is None:
        v._fail("R", "fig 未显式设置 xaxis.range，无法做渲染可见性守卫")
    else:
        x_right = float(x_right[1])
        for a in _anns(fig):
            if getattr(a, "xref", "x") == "x":
                if float(a.x) > x_right:
                    v._fail("R", f"标注 '{a.text}' 头点 x={a.x} 超出 xaxis 右界 {x_right}，成品中不可见")
                if (a.ax is not None and getattr(a, "axref", "x") == "x"
                        and float(a.ax) > x_right):
                    v._fail("R", f"标注 '{a.text}' 箭尾 ax={a.ax} 超出 xaxis 右界 {x_right}，成品中不可见")
        for t in fig.data:
            if t.type in ("scatter", "candlestick") and t.x is not None and len(t.x):
                if max(float(x0) for x0 in t.x) > x_right:
                    v._fail("R", f"trace {t.name or t.type} 最右点超出 xaxis 右界 {x_right}")

    # ── L3 数学关系层 ──
    # 价差标注 == 箭头跨距（±2），且 == 相邻水平线之差（样张逐元相等 ±1e-6）
    if len(spreads) == 2:
        spans = sorted(spreads, key=lambda a: min(float(a.y), float(a.ay)))
        expects = [(BOT, GRN, SPREAD_DN), (GRN, MID, SPREAD_UP)]
        for a, (lo, hi, label) in zip(spans, expects):
            v.expect_span(float(a.y), float(a.ay), label, tol=2)
            if abs(abs(float(a.y) - float(a.ay)) - (hi - lo)) > 1e-6:
                v._fail("L3", f"箭头跨距 {abs(float(a.y)-float(a.ay)):.1f} ≠ 线差 {hi-lo:.1f}")
    # 白趋势线渲染保真：fig 坐标 == YAML 声明端点复算（±1e-6，R 层——本图无通道，见模块 docstring）
    spec = next((a for a in cfg["params"]["annotations"]
                 if a.get("type") == "trendline" and a.get("color") == WHITE), None)
    if spec is None or not white:
        v._fail("R", "缺少白趋势线声明或 trace，无法做渲染保真比对")
    else:
        def _xof(val):
            if isinstance(val, str):
                return float(d.loc[d["datetime"] == pd.Timestamp(val), "pos"].iloc[0])
            return float(val)
        (fx, fy), (tx, ty) = spec["from"], spec["to"]
        e = [( _xof(fx), float(fy)), (_xof(tx), float(ty))]
        got = [(float(white[0].x[0]), float(white[0].y[0])), (float(white[0].x[1]), float(white[0].y[1]))]
        for (ex, ey), (gx, gy) in zip(e, got):
            if abs(ex - gx) > 1e-6 or abs(ey - gy) > 1e-6:
                v._fail("R", f"白趋势线画出的点 ({gx},{gy}) ≠ 声明复算 ({ex},{ey})")
        # 斜率与窗口中枢 LSQ 斜率同号，且 |s−s_mid| ≤ TREND_TILT·|s_mid|
        s = (got[1][1] - got[0][1]) / (got[1][0] - got[0][0])
        w = d[(d["pos"] >= got[0][0]) & (d["pos"] <= got[1][0])]
        s_mid = float(np.polyfit(w["pos"], w["close"], 1)[0])
        if s * s_mid <= 0:
            v._fail("L3", f"白趋势线斜率 {s:.2f} 与窗口中枢斜率 {s_mid:.2f} 异号")
        if abs(s - s_mid) > TREND_TILT * abs(s_mid):
            v._fail("L3", f"|白线斜率 {s:.2f} − 中枢斜率 {s_mid:.2f}| = {abs(s-s_mid):.2f}"
                          f" > {TREND_TILT}·|s_mid| = {TREND_TILT*abs(s_mid):.2f}")
        # 白趋势线自窗口低点下方通过（与渲染保真配对；样张低点均在白线上方 ≥2600）
        v.expect_lower_wraps(d, WHITE, [(131.0, 91500.0), (194.0, 100500.0)])
    # 数据漂移守卫：峰值价签值必须仍等于本批数据最高价
    if abs(float(d["high"].max()) - PEAK_HIGH) > 1e-6:
        v._fail("L3", f"数据峰值 {d['high'].max()} ≠ 价签 {PEAK_HIGH}（数据已漂移，需重走读图三步）")
    for name, window in (("MA5", 5), ("MA10", 10), ("MA20", 20), ("MA30", 30), ("MA60", 60)):
        v.expect_ma_last(name, window)
    return v
