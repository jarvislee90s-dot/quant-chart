"""03 30年国债期货TL（TL0 日线）三层验收清单（对照 reference/03，数值均经 zoom 读图确认+数据交叉验证）。

L1 要素：深色蜡烛红涨青跌；MA×5（字面根数）；周线级别下行通道（黄绿虚线 #74e602 成对 + 亮绿 label
        "周线级别下行通道"，斜率为负）；白/灰趋势线（样张灰白超长均线右段形态，以两点 trendline 复刻）；
        水平线×3+右缘药丸×3（116.53 橙/113.40 棕/110.32 青）；区间价差红竖箭头×2+蓝字"区间价差310BP"×2
        （zoom 证实两条同文 310BP——计划暂记"-110BP"系口径笔误，见 L3 换算说明）；多空分割线
        （黄字 #c8c800+线上红↑+线下青绿↓——计划暂记"红字"，zoom 证实为黄字）；「背靠通道上轨117做空」
        黄绿字+绿箭头；红点状箱体 zone×1+红点状上升虚线×1（样张 26-04~26-08 盘整带标注，清单外补全）；
        BULL/BEAR；大字"30年国债期货TL"（红）。
L2 相对位置：药丸与水平线同高（±3）；下行通道上轨压住两年窗最高 122.28（2025-02-07，±5）、右端 ≈117
        与"背靠通道上轨117"吻合；下轨托 24-09-30 低点 108.61（同样张左下角标注）及 110.3-110.6 低点带（±5）；
        「上轨117」文字紧邻通道上轨（±10，且在轨上方）；药丸与水平线同高（±3）；多空分割线 113.40
        位于上下轨之间；两条红竖箭头各落在相邻两水平线所夹带内；蓝字在其对应箭头夹带内；
        BULL/BEAR 文字锚定最后K线（482 根，pos 481）右侧预测区、其箭头头部入预测区（尾部可起自
        历史区末段，同样张长斜箭头构图）；白趋势线自左侧 1-3 月反弹带
        上方压过、终点达右侧；红点虚线斜率>0 且托在 26-07 低点 113.25 下方；箱体 zone 为历史区
        （右缘 ≤ 最后K线，无预测区裁剪风险）；大字在下部空白带不压K线。
L3 数学：通道斜率 < 0 且 == fit_channel 斜率（±1e-6）；两轨平行（±1e-6）；渲染==拟合（±3）；
        价差标注 == 跨线间距——箭头两端逐元=相邻水平线（±1e-6），标注 310BP 按"国债价格一位小数"
        口径换算：round(|跨距|,1)×100 == 310（±1；116.53−113.40=3.13→3.1、113.40−110.32=3.08→3.1）；
        MA5/10/20/30/60 末值==rolling 末值（±1e-6）。
  渲染保真口径：通道走 expect_render_matches_fit（与 expect_lower_wraps 配对）；白/灰趋势线与红点
        虚线为手写轨，以"fig 坐标==YAML 声明端点复算（±1e-6）"落实同一"画出来的==算出来的"定义；
        并沿用 chart_02 的**渲染可见性守卫**（面板0全部数据坐标元素——annotations 头/尾、traces 最右点、
        shapes 右缘——必须落在 xaxis 右界 n_all(241)+FORECAST_DAYS×1+1.5=244.5 内，超界即被 Plotly
        裁剪不可见）。
  读图三步证据：out/refs/chart_03/（pill_*_6x / spread_blue_*_4x / rail117_green_4x / duokong_4x /
        chan_label_3x / bullbear_4x / big_title_3x）；正文（004期 P11）："TL2612 合约在 116.5-117 区间
        逢高试空，第一目标 115.5 附近……9 月维持第一目标 114.5，第二目标 113.5"——顶线 116.53 落在
        正文 116.5-117 试空区下沿、113.40 与第二目标 113.5 同带、110.32 与数据窗口最低 110.31 差 1 跳。
  窗口差异说明：样张为 24-09~26-08 两年窗（x 轴合约切换非线性压缩），本图为其后半段一年窗
        （482 根，两年窗）；样张 122.28 顶药丸/108.61 低点价签已随窗口扩展复刻；样张灰白慢均线
        以右段两点趋势线复刻形态语义；大字因 110.32 线下画布不足 0.45 元置左下空白带。
"""
import pandas as pd

from quantchart.core.channel import fit_channel
from quantchart.core.session import build_daily_slots
from quantchart.qa.verify import Verifier

# ── 读图确认位阶（Step 2，证据 out/refs/chart_03/*_6x.png / *_4x.png / *_3x.png） ──
TOP, MID, BOT = 116.53, 113.40, 110.32                        # 顶线/多空分割线/底线（6x zoom 逐字确认）
SPREAD_LABEL = 310.0                                          # "区间价差310BP"（一位小数口径 3.1×100）
C_TOP, C_MID, C_BOT = "#fe9b00", "#8c4210", "#408080"         # 药丸底色
L_TOP, L_MID, L_BOT = "#f08a0a", "#703712", "#3e7d7d"         # 水平线色
CHAN = "#74e602"                                              # 通道黄绿虚线
BLUE, RED_ARR = "#0070b0", "#df0203"                          # 蓝字 / 价差红竖箭头
DK_UP, DK_DN, DK_TXT = "#d82818", "#3f9d78", "#c8c800"        # 多空分割线：红↑/青绿↓/黄字
GRAY_LINE, RED_DOT = "#7c828c", "#d82020"                     # 白/灰趋势线 / 红点上升虚线
BOX_EDGE = "#e03030"                                          # 红点箱体
BULL_RED, BEAR_GRN, RAIL117 = "#e05555", "#80c000", "#8cc000"
PEAK_HIGH, WINDOW_LOW = 122.28, 108.61                        # 数据窗口最高（25-02-07）/最低（24-09-30）——与样张两年窗逐元一致


def _anns(fig):
    return list(fig.layout.annotations)


def _pos_of(d, date):
    return float(d.loc[d["datetime"] == pd.Timestamp(date), "pos"].iloc[0])


def run(fig, df, rep, cfg) -> Verifier:
    d = build_daily_slots(df).df
    v = Verifier(fig, d, name="chart_03_tl0")
    last_pos = float(d["pos"].iloc[-1])                       # 最后一根 K 线 pos（241 交易日，0 基 240）

    # ── L1 要素层 ──
    v.expect_candle("#ff0000", "#3acccc")
    mas = {n: [t for t in fig.data if t.type == "scatter" and t.name == f"MA{n}"]
           for n in (5, 10, 20, 30, 60)}
    for n, ts in mas.items():
        if not ts:                                            # 存在性守卫：缺 MA 直接记录
            v._fail("L1", f"缺少 MA{n}")
    v.expect_channel(CHAN, "dash")                            # 周线级别下行通道双轨
    v.expect_shape_lines(3)                                   # 三条水平线
    hlines = {}
    for c in (L_TOP, L_MID, L_BOT):
        hlines[c] = [s for s in fig.layout.shapes
                     if s.type == "line" and s.y0 == s.y1 and s.line.color == c]
    for c, name in ((L_TOP, "顶"), (L_MID, "多空分割"), (L_BOT, "底")):
        if not hlines[c]:                                     # 按颜色存在性守卫（防漏报，同 4be2666 加固）
            v._fail("L1", f"颜色 {c} 的{name}水平线缺失")
    pills = {c: [a for a in _anns(fig) if getattr(a, "bgcolor", None) == c]
             for c in (C_TOP, C_MID, C_BOT)}
    for c, val, txt, name in ((C_TOP, TOP, "116.53", "顶"), (C_MID, MID, "113.40", "多空分割"),
                              (C_BOT, BOT, "110.32", "底")):
        if not pills[c]:
            v._fail("L1", f"缺少{name}药丸(#{c})")
        elif pills[c][0].text != txt:                         # 药丸数值逐字守卫（zoom 确认值，两位小数）
            v._fail("L1", f"{name}药丸文字 {pills[c][0].text} ≠ {txt}")
    for substr in ("周线级别下行通道", "多空分割线", "背靠通道上轨117", "做空",
                   "BULL", "BEAR"):
        v.expect_text(substr)
    blues = [a for a in _anns(fig) if a.text == "区间价差310BP"]
    if len(blues) != 2:
        v._fail("L1", f"蓝字'区间价差310BP'数量 {len(blues)} ≠ 2")
    big = [a for a in _anns(fig) if a.text == "30年国债期货TL"]
    if not big:                                               # 精确匹配，避免命中页眉标题
        v._fail("L1", '缺少品种大字"30年国债期货TL"')
    # 白/灰趋势线（两点）+ 红点状上升虚线（两点，dash=dot）
    gray = [t for t in fig.data if t.type == "scatter"
            and getattr(t.line, "color", None) == GRAY_LINE]
    if not gray or len(gray[0].x) != 2:
        v._fail("L1", "缺少白/灰趋势线（两点）")
    red_dot = [t for t in fig.data if t.type == "scatter" and getattr(t.line, "color", None) == RED_DOT]
    if not red_dot or len(red_dot[0].x) != 2 or red_dot[0].line.dash != "dot":
        v._fail("L1", "缺少红点状上升虚线（两点，dot）")
    # 红点状箱体 zone（历史区盘整带）
    boxes = [s for s in fig.layout.shapes if s.type == "rect"
             and getattr(s.line, "color", None) == BOX_EDGE]
    if not boxes:
        v._fail("L1", "缺少红点状箱体 zone")
    spreads = [a for a in _anns(fig) if getattr(a, "arrowcolor", None) == RED_ARR]
    if len(spreads) != 2:
        v._fail("L1", f"区间价差红竖箭头数量 {len(spreads)} ≠ 2")
    else:
        for a in spreads:                                     # 竖直守卫：头尾同 x
            if abs(float(a.x) - float(a.ax)) > 1e-6:
                v._fail("L1", "价差箭头非竖直")
    dk_up = [a for a in _anns(fig) if getattr(a, "arrowcolor", None) == DK_UP]
    dk_dn = [a for a in _anns(fig) if getattr(a, "arrowcolor", None) == DK_DN]
    if not dk_up:
        v._fail("L1", "缺少多空分割线红↑箭头")
    if not dk_dn:
        v._fail("L1", "缺少多空分割线青绿↓箭头")
    rail117_arr = [a for a in _anns(fig) if getattr(a, "arrowcolor", None) == RAIL117]
    if not rail117_arr:
        v._fail("L1", "缺少「背靠通道上轨117」绿箭头")
    if not [a for a in _anns(fig) if getattr(a, "arrowcolor", None) == BULL_RED]:
        v._fail("L1", "缺少 BULL 红斜上箭头")
    if not [a for a in _anns(fig) if getattr(a, "arrowcolor", None) == BEAR_GRN]:
        v._fail("L1", "缺少 BEAR 绿下行箭头")

    # ── L2 相对位置层 ──
    for c, lc, val, name in ((C_TOP, L_TOP, TOP, "顶"), (C_MID, L_MID, MID, "多空分割"),
                             (C_BOT, L_BOT, BOT, "底")):
        if hlines[lc] and abs(float(hlines[lc][0].y0) - val) > 1e-6:
            v._fail("L2", f"{name}水平线值不符: {hlines[lc][0].y0} ≠ {val}")
        if pills[c] and abs(float(pills[c][0].y) - val) > 3:  # 药丸与水平线同高 ±3
            v._fail("L2", f"{name}药丸 y={pills[c][0].y} 与水平线 {val} 不同高(±3)")
    rails = sorted([t for t in fig.data
                    if t.type == "scatter" and getattr(t.line, "color", None) == CHAN],
                   key=lambda t: t.y[0])
    if len(rails) >= 2:
        if abs(float(rails[-1].y[0]) - PEAK_HIGH) > 5:        # 上轨压住窗口最高高点（±5）
            v._fail("L2", f"上轨起点 {rails[-1].y[0]:.2f} 未压住窗口最高 {PEAK_HIGH}(±5)")
        # 多空分界位于上下轨之间（取窗口中段 x=last_pos/2 处两轨值）
        x_mid = last_pos / 2
        def _rail_at(t, x):
            return float(t.y[0]) + (float(t.y[1]) - float(t.y[0])) / \
                (float(t.x[1]) - float(t.x[0])) * (x - float(t.x[0]))
        lower_at120, upper_at120 = _rail_at(rails[0], x_mid), _rail_at(rails[-1], x_mid)
        if not (lower_at120 < MID < upper_at120):
            v._fail("L2", f"多空分界 {MID} 不在上下轨之间 ({lower_at120:.2f}, {upper_at120:.2f})")
    # 「上轨117附近」文字紧邻通道上轨（±10，且在轨上方）
    t117 = [a for a in _anns(fig) if a.text and "背靠通道上轨117" in a.text]
    if rails and t117:
        tx = float(t117[0].x)
        rail_at = float(rails[-1].y[0]) + (float(rails[-1].y[1]) - float(rails[-1].y[0])) / \
            (float(rails[-1].x[1]) - float(rails[-1].x[0])) * (tx - float(rails[-1].x[0]))
        gap = float(t117[0].y) - rail_at
        if not (0 <= gap <= 10):
            v._fail("L2", f"「上轨117」文字 y={t117[0].y} 距通道上轨 {rail_at:.2f} 不紧邻(0~10)：gap={gap:.2f}")
    # 价差箭头整体位于相邻两水平线所夹带内；蓝字在其对应箭头夹带内
    if len(spreads) == 2:
        spans = sorted(spreads, key=lambda a: min(float(a.y), float(a.ay)))
        bands = [(BOT, MID), (MID, TOP)]                      # 低箭头→底~分割带，高箭头→分割~顶带
        for a, (lo, hi) in zip(spans, bands):
            if not (lo - 3 <= min(float(a.y), float(a.ay)) and max(float(a.y), float(a.ay)) <= hi + 3):
                v._fail("L2", f"价差箭头 [{min(float(a.y), float(a.ay)):.2f},"
                              f"{max(float(a.y), float(a.ay)):.2f}] 越出夹带 [{lo},{hi}]")
    if len(blues) == 2:
        blues_s = sorted(blues, key=lambda a: float(a.y))
        for a, (lo, hi) in zip(blues_s, [(BOT, MID), (MID, TOP)]):
            if not (lo < float(a.y) < hi):
                v._fail("L2", f"蓝字 y={a.y} 不在夹带 ({lo},{hi}) 内")
    # 多空分割线：黄字在线下方、红↑在线上、青绿↓在线下
    dkt = [a for a in _anns(fig) if a.text and "多空分割线" in a.text]
    if dkt and not (BOT < float(dkt[0].y) < MID):
        v._fail("L2", f"多空分割线文字 y={dkt[0].y} 不在线下方 ({BOT},{MID})")
    if dk_up and not float(dk_up[0].y) > MID:
        v._fail("L2", f"红↑箭头头 y={dk_up[0].y} 不在线 {MID} 上方")
    if dk_dn and not float(dk_dn[0].y) < MID:
        v._fail("L2", f"青绿↓箭头头 y={dk_dn[0].y} 不在线 {MID} 下方")
    # BULL/BEAR：文字锚定最后K线右侧预测区；红斜上/绿下行箭头头部在预测区、尾部可起自历史区末段
    #   （样张 BULL 红斜上箭头即自末段K线下方空白带扫至药丸，长斜箭头构图；头尾均受 R 守卫 ≤244.5 约束）
    cand_txt = [a for a in _anns(fig) if a.text in ("BULL", "BEAR")]
    cand_arr = [a for a in _anns(fig)
                if getattr(a, "arrowcolor", None) in (BULL_RED, BEAR_GRN)]
    fc_txt = [a for a in cand_txt if float(a.x) > last_pos]
    if not any(a.text == "BULL" for a in fc_txt) or not any(a.text == "BEAR" for a in fc_txt):
        v._fail("L2", "缺少 BULL/BEAR 预测区文字")
    if not cand_arr or not any(float(a.x) > last_pos for a in cand_arr):
        v._fail("L2", "缺少头部位于预测区的 BULL/BEAR 箭头")
    else:
        v.expect_last_candle_right_of(last_pos, min(float(a.x) for a in cand_arr))
    # 白/灰趋势线：起点在左侧、压 1-3 月反弹带上方，终点达右侧，斜率 < 0
    if gray and len(gray[0].x) == 2:
        x0, x1 = float(gray[0].x[0]), float(gray[0].x[1])
        y0, y1 = float(gray[0].y[0]), float(gray[0].y[1])
        if x0 > 130:
            v._fail("L2", f"白趋势线起点 x={x0} 不在窗口左侧（≤130）")
        if x1 < 200:
            v._fail("L2", f"白趋势线终点 x={x1} 未达右侧（≥200）")
        if not (y1 - y0) / (x1 - x0) < 0:
            v._fail("L2", "白趋势线斜率非负（样张右段缓降）")
        p_feb = _pos_of(d, "2026-02-10")
        y_feb = y0 + (y1 - y0) / (x1 - x0) * (p_feb - x0)
        feb_high = float(d[(d["datetime"] >= pd.Timestamp("2026-02-01"))
                           & (d["datetime"] <= pd.Timestamp("2026-03-31"))]["high"].max())
        if y_feb < feb_high:                                  # 样张：1-3 月价格反弹被灰白线压在下方
            v._fail("L2", f"白趋势线在 26-02-10 处 y={y_feb:.2f} 低于 1-3 月反弹高点 {feb_high:.2f}，未压反弹上方")
    # 红点上升虚线：斜率 > 0 且托在 26-07 低点带下方
    if red_dot and len(red_dot[0].x) == 2:
        x0, x1 = float(red_dot[0].x[0]), float(red_dot[0].x[1])
        y0, y1 = float(red_dot[0].y[0]), float(red_dot[0].y[1])
        if not (y1 - y0) / (x1 - x0) > 0:
            v._fail("L2", "红点虚线斜率非正（样张为上升支撑线）")
        p_jul = _pos_of(d, "2026-07-01")
        y_jul = y0 + (y1 - y0) / (x1 - x0) * (p_jul - x0)
        jul_low = float(d[(d["datetime"] >= pd.Timestamp("2026-07-01"))
                          & (d["datetime"] <= pd.Timestamp("2026-07-31"))]["low"].min())
        if y_jul >= jul_low:
            v._fail("L2", f"红点虚线在 26-07-01 处 y={y_jul:.2f} 未托在 7 月低点 {jul_low:.2f} 下方")
    # 红点箱体：罩住 26-04~26-08 盘整带（113.3~114.6），右缘不越最后K线（历史区，防预测区裁剪）
    if boxes:
        b = boxes[0]
        if not (113.3 <= float(b.y0) and float(b.y1) <= 114.6):
            v._fail("L2", f"箱体价格带 [{b.y0},{b.y1}] 越出盘整带 [113.3,114.6]")
        if float(b.x1) > last_pos + 0.5 or float(b.x0) < 100:
            v._fail("L2", f"箱体 x 范围 [{b.x0},{b.x1}] 不是 26-04 起的历史区（右缘须 ≤ 最后K线）")
    # 大字位于下部空白带、不压 K 线密集区（对照样张"下部空白区"语义）
    if big:
        bx = float(big[0].x)
        w = d[(d["pos"] >= bx - 20) & (d["pos"] <= bx + 20)]
        if not (20 <= bx <= 80):
            v._fail("L2", f"大字 x={bx} 不在图幅左中部空白带（样张下部空白区语义，本图 20-80）")
        if float(big[0].y) > float(w["low"].min()) - 0.3:
            v._fail("L2", f"大字 y={big[0].y} 压到 K 线密集区（窗口最低 {w['low'].min():.2f}）")
    # 通道标签在通道上轨上方
    lab = [a for a in _anns(fig) if a.text and "周线级别下行通道" in a.text]
    if rails and lab:
        lx = float(lab[0].x)
        rail_at = float(rails[-1].y[0]) + (float(rails[-1].y[1]) - float(rails[-1].y[0])) / \
            (float(rails[-1].x[1]) - float(rails[-1].x[0])) * (lx - float(rails[-1].x[0]))
        if float(lab[0].y) <= rail_at:
            v._fail("L2", f"通道标签 y={lab[0].y} 未在通道上轨 {rail_at:.2f} 上方")

    # ── R 渲染可见性守卫（防"画的≠可见"，同 chart_02）：面板0全部数据坐标元素（annotations 头/尾、
    #    traces 最右点、shapes 右缘）必须落在 xaxis 右界（n_all + FORECAST_DAYS×bars_per_day + 1.5
    #    = 244.5）内，超界即被 Plotly 裁剪不可见。
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
        for s in fig.layout.shapes:
            if getattr(s, "xref", "x") == "x" and s.x1 is not None:
                if float(s.x1) > x_right or float(s.x0) > x_right:
                    v._fail("R", f"shape({s.type}) 右缘 {s.x1} 超出 xaxis 右界 {x_right}，成品中不可见")

    # ── L3 数学关系层 ──
    # 通道：斜率 < 0 且 == fit_channel 重算（±1e-6）；两轨平行；渲染==拟合（R 层，与 expect_lower_wraps 配对）
    fit = fit_channel(d, "2025-02-07", "2026-08-28", tilt=0.12, press=1.0)
    if not fit.slope < 0:
        v._fail("L3", f"通道斜率 {fit.slope:.6f} 非负（周线级别下行通道须向下）")
    if rails:
        s_fig = (float(rails[0].y[1]) - float(rails[0].y[0])) / (float(rails[0].x[1]) - float(rails[0].x[0]))
        if abs(s_fig - fit.slope) > 1e-6:
            v._fail("L3", f"fig 通道斜率 {s_fig:.8f} ≠ fit_channel 斜率 {fit.slope:.8f}")
    v.expect_render_matches_fit(CHAN, fit, tol=3.0)           # R 渲染保真
    v.expect_parallel(CHAN)
    v.expect_lower_wraps(d, CHAN, [(85.0, 110.40), (_pos_of(d, "2026-03-23"), WINDOW_LOW)])
    # 价差标注 == 跨线间距：箭头两端逐元=相邻水平线（±1e-6）；标注 310BP 按一位小数口径换算（±1）
    if len(spreads) == 2:
        spans = sorted(spreads, key=lambda a: min(float(a.y), float(a.ay)))
        expects = [(BOT, MID), (MID, TOP)]
        for a, (lo, hi) in zip(spans, expects):
            if abs(abs(float(a.y) - float(a.ay)) - (hi - lo)) > 1e-6:
                v._fail("L3", f"箭头跨距 {abs(float(a.y)-float(a.ay)):.3f} ≠ 线差 {hi-lo:.2f}")
            span_bp = round(abs(float(a.y) - float(a.ay)), 1) * 100   # 国债价格一位小数口径
            if abs(span_bp - SPREAD_LABEL) > 1:
                v._fail("L3", f"标注 {SPREAD_LABEL:.0f}BP 与跨距口径值 {span_bp:.0f}BP 不符（±1）")
    # 手写轨渲染保真：白/灰趋势线与红点虚线 fig 坐标 == YAML 声明端点复算（±1e-6，R 层）
    def _xof(val):
        if isinstance(val, str):
            return _pos_of(d, val)
        return float(val)
    for color, name in ((GRAY_LINE, "白/灰趋势线"), (RED_DOT, "红点虚线")):
        spec = next((a for a in cfg["params"]["annotations"]
                     if a.get("type") == "trendline" and a.get("color") == color), None)
        tr = [t for t in fig.data if t.type == "scatter" and getattr(t.line, "color", None) == color]
        if spec is None or not tr:
            v._fail("R", f"缺少{name}声明或 trace，无法做渲染保真比对")
        else:
            (fx, fy), (tx, ty) = spec["from"], spec["to"]
            e = [(_xof(fx), float(fy)), (_xof(tx), float(ty))]
            got = [(float(tr[0].x[0]), float(tr[0].y[0])), (float(tr[0].x[1]), float(tr[0].y[1]))]
            for (ex, ey), (gx, gy) in zip(e, got):
                if abs(ex - gx) > 1e-6 or abs(ey - gy) > 1e-6:
                    v._fail("R", f"{name}画出的点 ({gx},{gy}) ≠ 声明复算 ({ex},{ey})")
    # 数据漂移守卫：窗口极值必须仍等于读图确认时的本批数据（位阶交叉验证基准）
    if abs(float(d["high"].max()) - PEAK_HIGH) > 1e-6 or abs(float(d["low"].min()) - WINDOW_LOW) > 1e-6:
        v._fail("L3", f"数据极值 ({d['high'].max()},{d['low'].min()}) ≠ 读图基准 ({PEAK_HIGH},{WINDOW_LOW})"
                      f"（数据已漂移，需重走读图三步）")
    for name, window in (("MA5", 5), ("MA10", 10), ("MA20", 20), ("MA30", 30), ("MA60", 60)):
        v.expect_ma_last(name, window)
    return v
