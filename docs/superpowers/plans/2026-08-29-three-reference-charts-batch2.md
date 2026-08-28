# 深色蜡烛图产品线 · 第二批次（剩余三图）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在一期通用能力上以纯 YAML + 少量前置代码复刻剩余三幅深色策略图（01 伦敦金 XAU、02 沪铜 CU0、03 国债 TL0），并交付**三层机器可验的出图自检工具**，杜绝"自己认为做好了但实际没有"。

**Architecture:** 出图走一期已交付的旁路管线（daily_csv → build_daily_slots → daily_candle 插件 → figure_daily），本批次**不改分钟路径**；新增的是验收侧：`quantchart.qa.verify` 提供三层断言（L1 要素 / L2 相对位置 / L3 数学关系 + R 渲染保真），每幅图一个 pytest 验收测试（真实数据缺席自动 skip），目检只做风格兜底。

**Tech Stack:** Python 3.12（`.venv`）、plotly、pandas、numpy、local-datasource @ d106144、akshare（外盘）。

**Spec:** `docs/superpowers/specs/2026-08-29-three-reference-charts-design.md`（第二批次）+ `docs/superpowers/specs/2026-08-28-daily-candle-charting-design.md`（通用能力，实现对象）

## Global Constraints

- **分钟路径零改动**：本批次只新增 `src/quantchart/qa/`、`configs/`、`data/`、`tests/`、`tools/` 文件；`render/`、`core/`、`adapters/` 一律不动。
- **读图规范三步**（每图必做，出处：第二批次 spec §5）：①位阶数字**局部放大逐个确认**，禁止整图认数；②读出的位阶必须落在该品种数据 min/max 合理区间，矛盾即重读；③原报告正文写明的位阶（如 7560/6999.8）优先于图上读数。zoom 证据截图存 `out/refs/<chart>/`。
- **日期锚点优先**：标注锚点用日期（或日期+时刻）字符串精确匹配 bar datetime；数字 pos 仅允许用于右缘画布外元素（x ≥ n_all）。
- **验收三层缺一不可**：L1 要素层 / L2 相对位置层 / L3 数学关系层全部由 `Verifier` 机器断言；**任何一条失败 = 图不可交付**；目检对照图仅做风格兜底。
- **渲染保真检查**：通道验收必须**重算 `fit_channel` 并与 fig 上的轨坐标比对**——防止"画出来的 ≠ 算出来的"（第一批次曾发生 447 点偏移 bug）。
- 数据 CSV 属内部资料不入库（`data/` 已 gitignore）；zoom 证据存 `out/refs/`（已 gitignore）。
- 提交信息中文 conventional 风格；每图一个提交。

## File Structure

```
src/quantchart/qa/__init__.py     # 新建：空包标记
src/quantchart/qa/verify.py       # 新建：Verifier 三层断言 + 渲染保真
tools/verify_chart.py             # 新建：CLI（对任意图跑验收清单，人也可用）
configs/chart_01_xau.yaml         # 新建：伦敦金
configs/chart_02_cu0.yaml         # 新建：沪铜
configs/chart_03_tl0.yaml         # 新建：国债TL
data/xau_daily.csv / cu0_daily.csv / tl0_daily.csv   # 取数产物（gitignore）
tests/test_qa_verify.py           # 新建：Verifier 单测（合成数据）
tests/test_acceptance_charts.py   # 新建：三图三层验收（真实数据缺席自动 skip）
README.md                         # 修改：补日线/日内章节
```

## 验收三层模型（本批次的核心标准，逐图实例化）

- **L1 要素层**：图上必须存在的元素清单——类型、数量、颜色、线型、文字内容（从 reference 样张盘点，值经读图规范确认）。
- **L2 相对位置层**：元素两两之间的空间关系——如"圆圈圆心落在压力线水平线上（±3 点）""药丸与水平线同高""BULL/BEAR 折线整体位于最后一根 K 线右侧（预测区内）""大字位于上方空白区（不压 K 线）""价差箭头两端分别落在相邻两条水平线上"。
- **L3 数学关系层**：元素间数值等式——如"区间宽度标注值 == 其箭头跨越的两条水平线之差（±1）""通道两轨斜率相等（±1e-6）且下轨 ≤ 窗口内最深低点、上轨 ≥ 最高高点""fig 上通道轨坐标 == `fit_channel` 重算输出（±3）""MA 末值 == `rolling(工作日×根数).mean()` 末值"。

---

### Task 1: 出图自检模块 `quantchart.qa.verify` + 单测

**Files:**
- Create: `src/quantchart/qa/__init__.py`（空文件）
- Create: `src/quantchart/qa/verify.py`
- Create: `tests/test_qa_verify.py`

**Interfaces:**
- Consumes: `fit_channel`（core/channel.py）；plotly fig（pipeline 产物）；df（含 datetime/pos/high/low/close）
- Produces: `Verifier(fig, df)` 与断言方法（见下）；`Violation(layer, msg)`。所有断言**记录违规不抛异常**，`assert_ok()` 汇总抛 `AssertionError`（全部违规一次看全）。CLI/验收测试的清单模块契约：`run(fig, df, rep, cfg) -> Verifier`。

- [ ] **Step 1: 写失败测试 `tests/test_qa_verify.py`**

合成一个 30 根的管道行情 df（每根 low=mid−50−10|sin|、high=mid+60+10|sin|，与 test_channel 同构），跑 `run_pipeline` 级别太重——直接手工组装 fig：candle trace + 两条 trendline 模拟通道轨 + 一个 hline shape + 三个注解。断言：

```python
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
    v2.expect_point_on((2.0, 100.0), x=4, y=100.0, tol=3)    # x 离谱 → 违规
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
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[fit.window[0], fit.window[1]],
                             y=[fit.lower[0][1], fit.lower[1][1]],
                             line=dict(color="#39d353"), showlegend=False))
    v = Verifier(fig, df)
    v.expect_render_matches_fit(color="#39d353", fit=fit, tol=3.0)
    assert v.ok()
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=[fit.window[0], fit.window[1]],
                              y=[fit.lower[0][1] + 447.0, fit.lower[1][1] + 447.0],
                              line=dict(color="#39d353"), showlegend=False))
    v2 = Verifier(fig2, df)
    v2.expect_render_matches_fit(color="#39d353", fit=fit, tol=3.0)   # 447点偏移必须被抓
    assert not v2.ok()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/test_qa_verify.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'quantchart.qa'`

- [ ] **Step 3: 实现 `src/quantchart/qa/verify.py`**

```python
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
```

注意 `expect_render_matches_fit` 的比对基准是 **fit 对象本身**（执行时由 `fit_channel(df, 同参数)` 重算传入）——这正是第一批次 447 点偏移 bug 的复检器。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/pytest tests/test_qa_verify.py -q`
Expected: 6 passed

- [ ] **Step 5: 新增 CLI 包装 `tools/verify_chart.py`（人也可用）**

```python
"""出图自检 CLI：对配置+fig 跑三层验收清单（清单以 python 函数形式随测试交付）。

用法（示例）:
  .venv/bin/python tools/verify_chart.py configs/chart_01_xau.yaml out/chart_01_xau.png --checks tests/acceptance_checks/chart_01.py
"""
import argparse
import importlib.util


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("config")
    ap.add_argument("png")
    ap.add_argument("--checks", required=True, help="验收清单 py 文件（含 run(fig, df, cfg) 函数）")
    args = ap.parse_args()
    spec = importlib.util.spec_from_file_location("checks", args.checks)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from quantchart.adapters.daily import load_daily
    from quantchart.core.config import load_config
    from quantchart.core.pipeline import run_pipeline
    cfg = load_config(args.config)
    df, _rep = load_daily(cfg["input"])
    fig, rep = run_pipeline(cfg)
    v = mod.run(fig, df, rep, cfg)
    v.assert_ok()
    print(f"验收通过: {args.png}（{len(v.violations)} 违规）")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 全量回归 + 提交**

Run: `.venv/bin/pytest -q` → 全绿
```bash
git add src/quantchart/qa tools/verify_chart.py tests/test_qa_verify.py
git commit -m "feat(qa): 出图自检模块——三层验收断言(L1要素/L2相对位置/L3数学+渲染保真)与CLI"
```

---

### Task 2: 01 伦敦金现货（XAU 日线）

**Files:**
- Create: `configs/chart_01_xau.yaml`、`data/xau_daily.csv`（gitignore）
- Create: `tests/acceptance_checks/chart_01.py`（该图的三层验收清单）
- Modify: `tests/test_acceptance_charts.py`（新增该图验收测试）

**Interfaces:**
- Consumes: `tools/fetch_daily.py`（--foreign 落 CSV）、一期管线、Task 1 Verifier
- Produces: `out/chart_01_xau.png/html` + 该图三层验收清单（后续图同构复用）

**三层验收清单（对照 `reference/01`；数值类标注执行时按读图规范 zoom 确认后填入，且必须通过数据交叉验证）:**

- **L1 要素层**：深色蜡烛（红涨青跌）；MA×5（工作日语义，日线图=字面 5/10/20/30/60 根）；**周线级别下降通道**（黄绿虚线成对，`channel` 自动拟合 + label"周线级别下降通道"）；水平线×3 + 右缘药丸×3（值 zoom 确认；与样张 4841.255/4334.642/3928.818 对应层级一致）；多空分界（红字 + 红/绿小箭头）；"区间价差"红竖箭头×2 + 蓝字×2；BULL（红字）+ BEAR（绿字+绿箭头）；大字"伦敦金现货"（红）；历史高点价签（白字+小箭头）。
- **L2 相对位置层**：三个药丸分别与三条水平线**同高**（y 相等 ±3）；多空分界文字位于中间水平线附近（±30）；两条价差箭头整体位于两条水平线所夹区域；BULL/BEAR 在最后一根 K 线**右侧预测区**；高点价签紧邻数据最高 K 线右上方（±5 根、±30 点）；大字位于图幅上部且不压 K 线密集区。
- **L3 数学关系层**：通道两轨平行（±1e-6）且斜率与 `fit_channel` 一致（±1e-6）；下轨 ≤ 窗口内最深低点、上轨 ≥ 最高高点（±5）；**渲染保真**：fig 通道轨 == `fit_channel` 重算（±3）；MA5/MA10 末值 == rolling(5)/rolling(10) 末值（±1e-6）；价差标注数值 == 箭头两端 y 差（±2）。

- [ ] **Step 1: 抓数**

Run: `.venv/bin/python tools/fetch_daily.py XAU --start 2025-09-01 --end 2026-08-28 -o data/xau_daily.csv --foreign`
Expected: 约 250 交易日（2025-09-01→2026-08-28）

- [ ] **Step 2: 读图确认位阶（读图规范三步，证据存 `out/refs/chart_01/`）**

对 `reference/01` 逐个 zoom：三条水平线的确切数值与颜色、通道标签文字、大字、药丸数值。每个数字：①放大确认；②与 XAU 数据 min/max 交叉验证（位阶必须落在 [low_min×0.95, high_max×1.05] 内，否则重读）；③与原报告正文对照。**记录进 YAML 注释。**

- [ ] **Step 3: 写 `configs/chart_01_xau.yaml`**

结构（价格为 Step 2 确认值）：

```yaml
input:
  mode: daily_csv
  csv: data/xau_daily.csv
  range: [2025-09-01, 2026-08-28]
strategy: daily_candle
title: "伦敦金现货 · 日线策略同款复刻"
params:
  ma: [5, 10, 20, 30, 60]
  annotations:
    # 下降通道（channel 自动拟合，label 走 label 参数）
    # 三条水平线 + 三药丸（值=Step2 确认值）
    # 多空分界（text + 箭头用 trendline 两段）
    # 区间价差箭头×2 + 蓝字
    # BULL/BEAR、大字、高点价签
```

（schema 与一期样板 `configs/daily_candle.yaml` 完全一致；标注值确认后填入。）

- [ ] **Step 4: 渲染 + 三层验收**

先建验收装载器 `tests/test_acceptance_charts.py`（parametrize 三图，CSV 缺席自动 skip，本批后续图直接登记即可）：

```python
import importlib.util
from pathlib import Path

import pytest


CHARTS = [("chart_01_xau", "data/xau_daily.csv"),
          ("chart_02_cu0", "data/cu0_daily.csv"),
          ("chart_03_tl0", "data/tl0_daily.csv")]


@pytest.mark.parametrize("name,csv", CHARTS)
def test_acceptance_chart(name, csv):
    if not Path(csv).exists():
        pytest.skip(f"数据缺席: {csv}")
    spec = importlib.util.spec_from_file_location(name, f"tests/acceptance_checks/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from quantchart.adapters.daily import load_daily
    from quantchart.core.config import load_config
    from quantchart.core.pipeline import run_pipeline
    from quantchart.qa.verify import Verifier
    cfg = load_config(f"configs/{name}.yaml")
    df, rep = load_daily(cfg["input"])
    fig, _ = run_pipeline(cfg)
    v = mod.run(fig, df, rep, cfg)
    v.name = name
    v.assert_ok()
```

`tests/acceptance_checks/chart_01.py` 的 `run(fig, df, rep, cfg) -> Verifier` 按上方三层清单逐条调用 Verifier 断言（L1/L2/L3 数值全部来自本任务 Step 2 的读图确认结果，禁止臆造）。

Run: `.venv/bin/chartflow run configs/chart_01_xau.yaml -o out/chart_01_xau.png --html out/chart_01_xau.html`
Run: `.venv/bin/pytest tests/test_acceptance_charts.py -k xau -q`
Expected: 全部三层断言通过（任何一条失败 → 回 Step 2/3 校准）

- [ ] **Step 5: 目检对照（风格兜底）**

PIL 拼接 `out/chart_01_xau.png` 与 `reference/01`，zoom 走查：通道走势贴合、水平线压位、标注位置与 L2 断言一致。风格差异（非要素缺失）记录不阻塞。

- [ ] **Step 6: 提交**

```bash
git add configs/chart_01_xau.yaml tests/acceptance_checks/chart_01.py tests/test_acceptance_charts.py
git commit -m "feat(configs): 01伦敦金XAU日线复刻（三层验收清单+读图规范证据）"
```

---

### Task 3: 02 沪铜主力合约（CU0 日线）

**Files:**
- Create: `configs/chart_02_cu0.yaml`、`data/cu0_daily.csv`
- Create: `tests/acceptance_checks/chart_02.py`
- Modify: `tests/test_acceptance_charts.py`

**Interfaces:** 同 Task 2（管线 + Verifier 复用）。

**三层验收清单（对照 `reference/02`；数值 zoom 确认）:**

- **L1**：深色蜡烛；MA×5；水平线×3 + 药丸×3（红/绿/黄，值 zoom 确认）；白色长上升趋势线；黄圈≥3（circle）；红色竖直箭头×2 + 红字×2；蓝字≥2（形态/位置说明）；红字形态说明≥1；BULL/BEAR；大字"沪铜主力合约"。
- **L2**：黄圈群集中在最上方水平线附近（各圈 y 与该线差 ≤30）；白色趋势线起点在窗口左侧低点带、终点在右侧（低点在趋势线下方 ±10）；两支红箭头落在最上与中间水平线之间区域；药丸与对应水平线同高（±3）。
- **L3**：白色趋势线斜率与窗口中枢斜率**同号**且 |s − s_mid| ≤ tilt·s_mid（趋势线由 fit_channel 或中枢 LSQ 复算比对，±1e-6）；价差标注 == 箭头跨距（±2）；渲染保真（通道若有则同 Task 1 规则）；MA20 末值 == rolling(20)。

- [ ] **Step 1: 抓数**：`.venv/bin/python tools/fetch_daily.py CU0 --start 2025-09-01 --end 2026-08-28 -o data/cu0_daily.csv`
- [ ] **Step 2: 读图确认位阶**（同 Task 2 步骤，证据 `out/refs/chart_02/`；沪铜价格 7 万量级，交叉验证防错位）
- [ ] **Step 3: 写 `configs/chart_02_cu0.yaml`**（schema 同样板）
- [ ] **Step 4: 渲染 + 三层验收**（`-k cu0`）
- [ ] **Step 5: 目检对照**
- [ ] **Step 6: 提交**

```bash
git commit -m "feat(configs): 02沪铜CU0日线复刻（三层验收清单）"
```

---

### Task 4: 03 30年国债期货TL（TL0 日线）

**Files:** 同 Task 3（`configs/chart_03_tl0.yaml`、`data/tl0_daily.csv`、`tests/acceptance_checks/chart_03.py`）。

**三层验收清单（对照 `reference/03`）:**

- **L1**：深色蜡烛；MA×5；**周线级别下行通道**（黄绿虚线成对 + label"周线级别下行通道"，斜率为负）；白/灰趋势线；水平线×3 + 药丸×3；区间价差红箭头×2 + 蓝字×2（−110BP 口径换算）；多空分界（红字+绿箭头）；「短期通道上轨117附近」绿字+绿箭头；BULL/BEAR；大字"30年国债期货TL"。
- **L2**：下行通道上轨压在反弹高点带上、下轨托在低点带上（±5）；「上轨117附近」文字紧邻通道上轨（±10）；药丸与水平线同高（±3）；多空分界位于上下轨之间。
- **L3**：通道斜率 < 0 且 == `fit_channel` 斜率（±1e-6）；两轨平行（±1e-6）；价差标注 == 跨线间距（±1，国债价格小数一位）；MA30 末值 == rolling(30)；渲染保真（±3）。

- [ ] **Step 1: 抓数**：`CU0`→`TL0` 同款命令
- [ ] **Step 2: 读图确认位阶**（证据 `out/refs/chart_03/`；国债价格 105-120、一位小数，交叉验证）
- [ ] **Step 3: 写 `configs/chart_03_tl0.yaml`**
- [ ] **Step 4: 渲染 + 三层验收**（`-k tl0`）
- [ ] **Step 5: 目检对照**
- [ ] **Step 6: 提交**

```bash
git commit -m "feat(configs): 03国债TL0日线复刻（三层验收清单）"
```

---

### Task 5: README 日线/日内章节

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 在「五、常见改法速查」之后新增「五之二、深色策略图（日线/日内）」章节**，内容定性覆盖：`daily_*` 双通道与 `granularity/tick_anchor/strict_range` 三参数；`channels` 自动拟合声明（中枢主导三步法一句话）；8 类 `annotations` 语法速查表（type/关键参数/示例一列）；出图自检 CLI（`tools/verify_chart.py`）；`out/refs/` 读图证据约定。给出最小 YAML 示例（摘自 `configs/daily_candle.yaml` 头部）。

- [ ] **Step 2: 提交**

```bash
git add README.md
git commit -m "docs(readme): 深色策略图（日线/日内）章节——双通道/周期参数/channels拟合/8类标注/自检CLI"
```

---

### Task 6: 收尾——全量回归 + 留档

- [ ] **Step 1: 全量测试**：`.venv/bin/pytest -q` → 全绿（三图验收测试在 CSV 缺席时自动 skip，本机必须真实跑过）
- [ ] **Step 2: 三图对照留档**：`out/_compare_01.png/_02/_03`（成品 vs 样张并排）
- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "feat: 第二批次收官——伦敦金/沪铜/国债三图三层验收通过并留档"
```

---

## 完成定义（对照第二批次 spec §5 总验收）

1. 三图各产出 PNG+HTML，脚注口径正确（含周期回显）；
2. 每图三层验收（L1/L2/L3+渲染保真）机器断言全过，违规清单为空；
3. 与样张并排目视：要素齐备 + 风格同款（L2 相对位置关系逐项核对）；
4. 全程零分钟路径改动、零 `src/` 既有文件改动（除新增 qa 包）。