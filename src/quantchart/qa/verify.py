"""出图自检：三层验收断言（L1要素 / L2相对位置 / L3数学关系 + R渲染保真）。只读不改 fig。

设计动机（第一批次踩坑）：覆盖率/拟合"算出来是对的"不等于"画出来是对的"——
渲染端点算错 447 点时 coverage 仍是 1.0。故验收必须回到 fig 上的实际坐标比对。
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class Violation:
    layer: str      # L1/L2/L3/R
    msg: str


class Verifier:
    """收集违规、汇总抛错：assert_ok() 一次性给出全部违规清单。"""

    def __init__(self, fig, df, name=""):
        self.fig = fig
        self.df = df
        self.name = name
        self.violations: list[Violation] = []

    # ── 基础 ──
    def _fail(self, layer, msg):
        self.violations.append(Violation(layer, f"[{self.name}] {msg}"))

    def _traces(self, kind):
        return [t for t in self.fig.data if t.type == kind]

    def _by_color(self, color, dash=None):
        return [t for t in self.fig.data
                if getattr(t.line, "color", None) == color
                and (dash is None or t.line.dash == dash)]

    def _ann_by_text(self, substr):
        return [a for a in self.fig.layout.annotations if a.text and substr in a.text]

    def assert_ok(self):
        if self.violations:
            raise AssertionError("验收违规 %d 条:\n" % len(self.violations)
                                 + "\n".join(f"  [{v.layer}] {v.msg}" for v in self.violations))

    def ok(self):
        """当前无违规时为 True；违规明细仍由 assert_ok() 汇总抛出。"""
        return not self.violations

    # ── L1 要素层 ──
    def expect_candle(self, up, down):
        cs = self._traces("candlestick")
        if not cs:
            return self._fail("L1", "缺少蜡烛图 trace")
        if cs[0].increasing.line.color != up or cs[0].decreasing.line.color != down:
            self._fail("L1", f"蜡烛涨跌色不符: {cs[0].increasing.line.color}/{cs[0].decreasing.line.color}")

    def expect_channel(self, color, dash="dash"):
        rails = self._by_color(color, dash)
        if len(rails) < 2:
            self._fail("L1", f"通道(#{color})轨数不足: {len(rails)} < 2")

    def expect_line(self, color, min_n=1, dash=None):
        if len(self._by_color(color, dash)) < min_n:
            self._fail("L1", f"线段(#{color})不足: < {min_n}")

    def expect_text(self, substr):
        if not self._ann_by_text(substr):
            self._fail("L1", f"缺少文字标注: 含 '{substr}'")

    def expect_shape_lines(self, min_n):
        if len([s for s in self.fig.layout.shapes if s.type == "line"]) < min_n:
            self._fail("L1", "水平线（shape line）数量不足")

    # ── L2 相对位置层 ──
    def expect_point_on(self, point, x, y, tol):
        """某标记（圆心等）落在 (x, y) 附近。point=(x, y)。"""
        px, py = point
        if abs(px - x) > tol or abs(py - y) > tol:
            self._fail("L2", f"标记 ({px},{py}) 未落在 ({x},{y})±{tol}")

    def expect_marker_at(self, x, y, symbol="circle-open", tol=3.0):
        hits = [t for t in self._traces("scatter")
                if getattr(t.marker, "symbol", None) == symbol
                and len(t.x) == 1
                and abs(t.x[0] - x) <= tol and abs(t.y[0] - y) <= tol]
        if not hits:
            self._fail("L2", f"未见 ({x},{y}) 附近的 {symbol} 标记")

    def expect_last_candle_right_of(self, x_last, x_min):
        """预测区元素必须整体位于最后一根 K 线右侧。"""
        if x_min <= x_last:
            self._fail("L2", f"预测区元素 x_min={x_min} 未完全位于最后K线({x_last})右侧")

    # ── L3 数学关系层 ──
    def expect_parallel(self, color, tol=1e-6):
        rails = self._by_color(color)
        if len(rails) < 2:
            return
        s = []
        for t in rails:
            s.append((t.y[-1] - t.y[0]) / (t.x[-1] - t.x[0]))
        if max(s) - min(s) > tol:
            self._fail("L3", f"通道两轨不平行: 斜率差 {max(s)-min(s):.2e}")

    def expect_lower_wraps(self, df, color, points):
        """下轨必须从给定低点 (pos, 价) 下方通过（低点 ≥ 下轨 − 5）。"""
        rails = self._by_color(color)
        if not rails:
            return self._fail("L3", "下轨缺失，无法校验包裹")
        t = rails[0]
        for pos, price in points:
            rail_at = t.y[0] + (t.y[1] - t.y[0]) / (t.x[1] - t.x[0]) * (pos - t.x[0])
            if price < rail_at - 5.0:
                self._fail("L3", f"低点 ({pos},{price}) 跌破下轨({rail_at:.1f})")

    def expect_span(self, y_a, y_b, label, tol=1.0):
        """区间宽度类标注：|标注数值 − 两轨/两线同一 x 处差值| ≤ tol。"""
        if abs((y_a - y_b) - label) > tol:
            self._fail("L3", f"标注 {label} 与实际差值 {y_a - y_b:.1f} 不符（±{tol}）")

    def expect_ma_last(self, name, window, col="close"):
        m = [t for t in self._traces("scatter") if t.name == name]
        if not m:
            return self._fail("L3", f"缺少 {name}")
        expect = float(self.df[col].rolling(window).mean().iloc[-1])
        got = float(m[0].y[-1])
        if abs(got - expect) > 1e-6:
            self._fail("L3", f"{name} 末值 {got} ≠ rolling({window}) 末值 {expect}")

    # ── R 渲染保真（防"画的≠算的"，第一批次 447 点偏移教训） ──
    def expect_render_matches_fit(self, color, fit, tol=3.0):
        """fig 上同色两轨必须与 fit_channel 的中枢±下探/上张一致。"""
        rails = self._by_color(color)
        if len(rails) < 2:
            return self._fail("R", f"通道(#{color})轨数不足，无法比对渲染保真")
        for t in rails:
            for xi, yi in zip(t.x, t.y):
                expect_lo = fit.lower[0][1] + fit.slope * (xi - fit.window[0])
                expect_hi = fit.upper[0][1] + fit.slope * (xi - fit.window[0])
                if not (min(expect_lo, expect_hi) - tol <= yi <= max(expect_lo, expect_hi) + tol):
                    self._fail("R", f"轨点 ({xi},{yi}) 偏离拟合通道（下{expect_lo:.1f}/上{expect_hi:.1f}±{tol}）")
