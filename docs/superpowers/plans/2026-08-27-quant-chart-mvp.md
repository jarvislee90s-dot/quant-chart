# quant-chart MVP 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建成 YAML 驱动的行情图工作流（数据适配→指标→信号→Plotly渲染），内置 `basis_review`/`basis_zones` 两预设，复刻 Backset 下 V1/V2 图作为回归基准。

**Architecture:** 四段流水线。适配器(Wind Excel/API降级)产出规范宽表 → 槽位引擎(压缩X轴) → 指标/信号注册表加列与事件 → 通用绘图原语翻译为 Plotly shapes/annotations。策略插件只算不画，视觉原语任何策略可用。

**Tech Stack:** Python ≥3.12, pandas, plotly ≥6, kaleido ≥1.3, PyYAML, click, pytest, openpyxl/calamine。

**约定（全计划锁定的接口）:**
- 规范宽表列: `datetime, fut_open, fut_high, fut_low, fut_close, fut_volume, fut_amount, idx_open, idx_high, idx_low, idx_close, idx_volume, idx_amount`（amount 单位百万元）
- `Slots` 数据类: `df, day_span, sep_center, tick_pos, tick_lab, n_all`
- `Event(pos, dt, value, label, kind)`；`QualityReport(source, days, rows, filled_future, filled_index).footnote()`
- 指标函数签名 `fn(df, **params) -> df`；策略插件签名 `run(df, slots, **params) -> StrategyOutput(df, events, panels)`
- MVP 面板数=1（YAGNI；仓位面板属二期），轴名 `x/y/y2/y3`（与已验证样张一致）

仓库: `E:\LLMproject\Github\quant-chart`（git 已初始化，设计文档已提交）。

---

### Task 1: 项目骨架与工具链

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/quantchart/__init__.py`, `tests/__init__.py`, `tests/test_smoke.py`

- [x] **Step 1: 写 pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "quantchart"
version = "0.1.0"
description = "YAML 驱动的行情图工作流（Wind Excel/API → 指标 → Plotly）"
requires-python = ">=3.12"
dependencies = [
  "pandas>=2.2",
  "plotly>=6.0",
  "kaleido>=1.3",
  "PyYAML>=6.0",
  "click>=8.1",
  "openpyxl>=3.1",
  "python-calamine>=0.2",
  "requests>=2.31",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
chartflow = "quantchart.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
```

- [x] **Step 2: 写 .gitignore 与空包**

`.gitignore`:
```
__pycache__/
*.egg-info/
.pytest_cache/
build/
dist/
outputs/
```

`src/quantchart/__init__.py`:
```python
__version__ = "0.1.0"
```

`tests/__init__.py`: 空文件。

`tests/test_smoke.py`:
```python
def test_import():
    import quantchart
    assert quantchart.__version__ == "0.1.0"
```

- [x] **Step 3: 安装并跑通**

Run: `cd /e/LLMproject/Github/quant-chart && pip install -e ".[dev]" && pytest -q`
Expected: `1 passed`

- [x] **Step 4: Commit**

```bash
git add -A && git commit -m "chore: 项目骨架与工具链"
```

---

### Task 2: 槽位引擎 session.build_slots

**Files:**
- Create: `src/quantchart/core/__init__.py`（空）
- Create: `src/quantchart/core/session.py`
- Test: `tests/test_session.py`

- [x] **Step 1: 写失败测试**

```python
import datetime as dtm
import numpy as np
import pandas as pd
from quantchart.core.session import day_grid, build_slots

def _synth_days(n=3):
    rows = []
    for i, d in enumerate([dtm.date(2026, 8, 19) + dtm.timedelta(days=i) for i in range(n)]):
        for t in day_grid(d):
            rows.append({"datetime": t, "fut_close": 7000.0 + i * 10 + t.hour})
    return pd.DataFrame(rows)

def test_day_grid_len():
    assert len(day_grid(dtm.date(2026, 8, 19))) == 242

def test_build_slots_positions_and_seps():
    slots = build_slots(_synth_days(3))
    assert slots.n_all == 3 * 242 + 2          # 2 个隔日空位
    assert len(slots.sep_center) == 2
    df = slots.df
    assert df["pos"].notna().all()
    assert df["pos"].max() == slots.n_all - 1
    d0, d1 = dtm.date(2026, 8, 19), dtm.date(2026, 8, 20)
    assert slots.day_span[d0][1] + 2 == slots.day_span[d1][0]   # 隔1个空位

def test_tick_labels_skip_rules():
    slots = build_slots(_synth_days(2))
    labs = dict(zip(slots.tick_pos, slots.tick_lab))
    assert any(v == "" for v in labs.values())   # 13:00 与非末日15:00 留空
    assert labs[slots.day_span[dtm.date(2026, 8, 19)][0]] == "09:30"
```

- [x] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_session.py -q`
Expected: FAIL `ModuleNotFoundError: quantchart.core.session`

- [x] **Step 3: 实现 session.py**

```python
"""槽位引擎：交易时段网格 + 压缩X轴位置映射。"""
import datetime as dtm
from dataclasses import dataclass

import numpy as np
import pandas as pd

AM = (dtm.time(9, 30), dtm.time(11, 30))
PM = (dtm.time(13, 0), dtm.time(15, 0))
TICK_TIMES = [dtm.time(9, 30), dtm.time(10, 0), dtm.time(10, 30), dtm.time(11, 0),
              dtm.time(11, 30), dtm.time(13, 0), dtm.time(13, 30), dtm.time(14, 0),
              dtm.time(14, 30), dtm.time(15, 0)]


@dataclass
class Slots:
    df: pd.DataFrame        # 已加 pos 列
    day_span: dict          # date -> (start_pos, end_pos)
    sep_center: list        # 日分隔线位置（隔位中心）
    tick_pos: list
    tick_lab: list
    n_all: int


def day_grid(day: dtm.date) -> list[pd.Timestamp]:
    """单日 242 个分钟槽位（09:30–11:30, 13:00–15:00 首尾均含）。"""
    out = []
    t = dtm.datetime.combine(day, AM[0])
    while t.time() <= AM[1]:
        out.append(pd.Timestamp(t))
        t += dtm.timedelta(minutes=1)
    t = dtm.datetime.combine(day, PM[0])
    end = dtm.datetime.combine(day, PM[1])
    while t <= end:
        out.append(pd.Timestamp(t))
        t += dtm.timedelta(minutes=1)
    return out


def build_slots(df: pd.DataFrame) -> Slots:
    """df 须含 datetime 列（完整槽位、已排序、无重复）。"""
    df = df.copy().reset_index(drop=True)
    days = sorted(set(df["datetime"].dt.date))
    day_span, sep_center, tick_pos, tick_lab = {}, [], [], []
    cur = 0
    for di, d in enumerate(days):
        sub = df[df["datetime"].dt.date == d]
        if di > 0:
            cur += 1                                  # 日间空位（跨日断线）
            sep_center.append(cur - 0.5)
        pos = np.arange(cur, cur + len(sub))
        df.loc[sub.index, "pos"] = pos.astype(float)
        last = di == len(days) - 1
        for r, p in zip(sub.itertuples(), pos):
            t = r.datetime.time()
            if t in TICK_TIMES:
                if t == dtm.time(15, 0) and not last:
                    lab = ""                          # 与次日09:30仅隔2位
                elif t == dtm.time(13, 0):
                    lab = ""                          # 与11:30仅隔1位
                else:
                    lab = r.datetime.strftime("%H:%M")
                tick_pos.append(float(p))
                tick_lab.append(lab)
        day_span[d] = (cur, cur + len(sub) - 1)
        cur += len(sub)
    return Slots(df=df, day_span=day_span, sep_center=sep_center,
                 tick_pos=tick_pos, tick_lab=tick_lab, n_all=cur)
```

- [x] **Step 4: 跑测试通过**

Run: `pytest tests/test_session.py -q`
Expected: `3 passed`

- [x] **Step 5: Commit**

```bash
git add src/quantchart/core tests/test_session.py && git commit -m "feat(core): 槽位引擎（242格/日+压缩X轴+刻度留空规则）"
```

---

### Task 3: Wind Excel 适配器 + 测试夹具

**Files:**
- Create: `src/quantchart/adapters/__init__.py`（空）
- Create: `src/quantchart/adapters/excel_wind.py`
- Create: `tests/make_fixtures.py`
- Test: `tests/test_excel_wind.py`

- [x] **Step 1: 写夹具生成器（合成 2 日 Wind 格式 xlsx）**

```python
# tests/make_fixtures.py —— 生成与 Wind 导出同构的小样本两表
import datetime as dtm
import pandas as pd
from quantchart.core.session import day_grid

COLS = ["代码", "名称", "日期", "开盘价(元)", "最高价(元)", "最低价(元)",
        "收盘价(元)", "涨跌幅", "成交额(百万)", "成交量(股)"]

def make(path: str, code: str, days, base: float, drop_minutes: int = 0):
    rows = []
    for i, t in enumerate([ts for d in days for ts in day_grid(d)]):
        px = base + i * 0.1
        rows.append([code, code, t, px, px + .5, px - .5, px, 0.0, 100.0 + i, 10 + i])
    df = pd.DataFrame(rows, columns=COLS)
    if drop_minutes:                       # 模拟指数端缺 14:59
        df = df[~df["日期"].dt.strftime("%H:%M").isin(["14:59"])]
    df.loc[len(df)] = ["数据来源：Wind"] + [None] * 9   # Wind 脚注行
    df.to_excel(path, index=False)

if __name__ == "__main__":
    import pathlib
    out = pathlib.Path(__file__).parent / "fixtures"
    out.mkdir(exist_ok=True)
    days = [dtm.date(2026, 8, 19), dtm.date(2026, 8, 20)]
    make(out / "fut.xlsx", "IM2612.CFE", days, 7000.0)
    make(out / "idx.xlsx", "000852.SH", days, 7300.0, drop_minutes=2)
    print("fixtures written:", out)
```

Run: `python tests/make_fixtures.py`
Expected: `fixtures written: ... tests/fixtures`

- [x] **Step 2: 写失败测试**

```python
# tests/test_excel_wind.py
import pandas as pd
from quantchart.adapters.excel_wind import load_wind_pair

FIX = __file__.rsplit("/", 1)[0] + "/fixtures"

def test_load_wind_pair_aligns_and_fills():
    df, rep = load_wind_pair(f"{FIX}/fut.xlsx", f"{FIX}/idx.xlsx")
    assert rep.days == 2 and rep.rows == 2 * 242
    assert list(df.columns[:3]) == ["datetime", "fut_open", "fut_high"]
    assert df["fut_close"].notna().all()
    assert rep.filled_index == 2          # 指数端每天缺 14:59
    assert rep.filled_future == 0
    assert abs(df["idx_close"].iloc[-1] - df["idx_close"].iloc[-2]) < 1e-9  # ffill 生效

def test_date_range_filter():
    df, rep = load_wind_pair(f"{FIX}/fut.xlsx", f"{FIX}/idx.xlsx",
                             start="2026-08-20", end="2026-08-20")
    assert rep.days == 1 and len(df) == 242

def test_footnote_text():
    _, rep = load_wind_pair(f"{FIX}/fut.xlsx", f"{FIX}/idx.xlsx")
    assert "Wind Excel" in rep.footnote() and "484" in rep.footnote()
```

- [x] **Step 3: 跑测试确认失败**

Run: `pytest tests/test_excel_wind.py -q`
Expected: FAIL `ModuleNotFoundError: quantchart.adapters.excel_wind`

- [x] **Step 4: 实现 excel_wind.py**

```python
"""Wind 导出分钟表适配器：期货+指数两表 → 规范宽表 + 质量报告。"""
from dataclasses import dataclass

import pandas as pd

from ..core.session import day_grid

REN = {"日期": "dt", "开盘价(元)": "open", "最高价(元)": "high", "最低价(元)": "low",
       "收盘价(元)": "close", "成交额(百万)": "amount", "成交量(股)": "volume"}
KEEP = ["dt", "open", "high", "low", "close", "amount", "volume"]


@dataclass
class QualityReport:
    source: str
    days: int
    rows: int
    filled_future: int
    filled_index: int

    def footnote(self) -> str:
        return (f"数据来源:{self.source}；交易日{self.days}天/分钟槽位{self.rows}个，"
                f"期货前值填充{self.filled_future}分钟，指数前值填充{self.filled_index}分钟。")


def _read_sheet(path: str) -> pd.DataFrame:
    try:
        raw = pd.read_excel(path, sheet_name=0)
    except Exception:                       # openpyxl 遇 Wind 非法页面设置
        raw = pd.read_excel(path, sheet_name=0, engine="calamine")
    raw = raw.rename(columns={str(k): v for k, v in REN.items()})
    raw["dt"] = pd.to_datetime(raw["dt"])
    return raw.dropna(subset=["dt", "close"])[KEEP]


def _aligned(frame: pd.DataFrame, grid: list, prefix: str):
    s = frame.set_index("dt").reindex(grid)
    filled = int(s["close"].isna().sum())
    out = s.ffill().add_prefix(f"{prefix}_")
    return out.reset_index(drop=True), filled


def load_wind_pair(future_xlsx: str, index_xlsx: str,
                   start: str | None = None, end: str | None = None
                   ) -> tuple[pd.DataFrame, QualityReport]:
    fut, idx = _read_sheet(future_xlsx), _read_sheet(index_xlsx)
    lo = pd.Timestamp(start) if start else None
    hi = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1) if end else None
    if lo is not None:
        fut, idx = fut[fut.dt >= lo], idx[idx.dt >= lo]
    if hi is not None:
        fut, idx = fut[fut.dt <= hi], idx[idx.dt <= hi]
    days = sorted(set(fut["dt"].dt.date) & set(idx["dt"].dt.date))
    grid = [t for d in days for t in day_grid(d)]
    fa, ff = _aligned(fut, grid, "fut")
    ia, fi = _aligned(idx, grid, "idx")
    df = pd.concat([pd.Series(grid, name="datetime"), fa, ia], axis=1)
    return df, QualityReport("Wind Excel", len(days), len(grid), ff, fi)
```

- [x] **Step 5: 跑测试通过**

Run: `pytest tests/test_excel_wind.py -q`
Expected: `3 passed`

- [x] **Step 6: Commit**

```bash
git add src/quantchart/adapters tests/test_excel_wind.py tests/make_fixtures.py tests/fixtures/.gitkeep 2>/dev/null; \
git add -A && git commit -m "feat(adapters): Wind两表适配器（对齐/前值填充/质量报告）+合成夹具"
```

注：夹具 xlsx 为二进制生成物，`tests/fixtures/.gitkeep` 占位即可，二进制不入库（.gitignore 追加 `tests/fixtures/*.xlsx`）。

---

### Task 4: 指标注册表（basis / basis_rate / vwap）

**Files:**
- Create: `src/quantchart/core/indicators.py`
- Test: `tests/test_indicators.py`

- [x] **Step 1: 写失败测试**

```python
import datetime as dtm
import numpy as np
import pandas as pd
from quantchart.core.indicators import apply_indicators, REGISTRY
from quantchart.core.session import day_grid

def _df():
    d1, d2 = dtm.date(2026, 8, 19), dtm.date(2026, 8, 20)
    rows = []
    for d in (d1, d2):
        for i, t in enumerate(day_grid(d)):
            rows.append({"datetime": t, "fut_close": 7000 + i * .1,
                         "fut_volume": 10.0, "fut_amount": 7000 * 200 * 10 / 1e6 * (i + 1),
                         "idx_close": 7300 + i * .1})
    return pd.DataFrame(rows)

def test_registry_has_builtin():
    assert {"basis", "basis_rate", "vwap"} <= set(REGISTRY)

def test_basis_chain():
    df = apply_indicators(_df(), [{"name": "basis"}, {"name": "basis_rate"}])
    assert abs(df["basis"].iloc[0] - 300.0) < 1e-9
    assert abs(df["basis_rate"].iloc[0] - 300 / 7300 * 100) < 1e-9

def test_vwap_per_day_reset():
    df = apply_indicators(_df(), [{"name": "vwap"}])
    day = df["datetime"].dt.date
    first_d1 = df.loc[day == dtm.date(2026, 8, 19), "fut_vwap"].iloc[0]
    first_d2 = df.loc[day == dtm.date(2026, 8, 20), "fut_vwap"].iloc[0]
    assert abs(first_d1 - df["fut_close"].iloc[0]) < 1.0      # 首分钟≈现价
    assert abs(first_d1 - first_d2) < 1.0                     # 每日重置

def test_unknown_indicator_raises():
    try:
        apply_indicators(_df(), [{"name": "nope"}])
        assert False
    except KeyError as e:
        assert "nope" in str(e)
```

- [x] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_indicators.py -q` → FAIL（模块不存在）

- [x] **Step 3: 实现 indicators.py**

```python
"""指标注册表：纯函数 df→df（加列），YAML 按名引用、可链式。"""
REGISTRY: dict = {}


def register_indicator(name: str):
    def deco(fn):
        REGISTRY[name] = fn
        return fn
    return deco


def apply_indicators(df: pd.DataFrame, specs: list[dict]) -> pd.DataFrame:
    for spec in specs:
        name = spec.get("name")
        if name not in REGISTRY:
            raise KeyError(f"未知指标: {name}（可用: {sorted(REGISTRY)}）")
        df = REGISTRY[name](df, **spec.get("params", {}))
    return df


@register_indicator("basis")
def basis(df, future="fut_close", index="idx_close", out="basis"):
    df = df.copy()
    df[out] = df[index] - df[future]
    return df


@register_indicator("basis_rate")
def basis_rate(df, basis_col="basis", index="idx_close", out="basis_rate"):
    df = df.copy()
    df[out] = df[basis_col] / df[index] * 100
    return df


@register_indicator("vwap")
def vwap(df, price="fut_close", volume="fut_volume", amount="fut_amount",
         contract_mult=200.0, out="fut_vwap"):
    """当日累计成交额÷累计成交量；无成交额列时退化为价格加权（API 数据）。"""
    df = df.copy()
    if amount in df.columns:
        amt = df[amount] * 1e6
    else:
        amt = df[price] * df[volume] * contract_mult
    vol = df[volume].fillna(0) * contract_mult
    day = df["datetime"].dt.date
    cum_a = amt.groupby(day).cumsum()
    cum_v = vol.replace(0, pd.NA).groupby(day).cumsum()
    df[out] = (cum_a / cum_v.astype(float)).ffill()
    return df
```

- [x] **Step 4: 跑测试通过**

Run: `pytest tests/test_indicators.py -q` → `4 passed`

- [x] **Step 5: Commit**

```bash
git add src/quantchart/core/indicators.py tests/test_indicators.py && git commit -m "feat(core): 指标注册表（basis/basis_rate/vwap，当日重置）"
```

---

### Task 5: 信号层（每日最低 / 窗口最低事件）

**Files:**
- Create: `src/quantchart/core/signals.py`
- Test: `tests/test_signals.py`

- [x] **Step 1: 写失败测试**

```python
import datetime as dtm
import pandas as pd
from quantchart.core.session import build_slots, day_grid
from quantchart.core.signals import daily_min_events, window_min_events

def _df():
    d = dtm.date(2026, 8, 19)
    rows = [{"datetime": t, "basis": 300.0 - i * 0.5, "fut_low": 7000 + i}
            for i, t in enumerate(day_grid(d))]
    return pd.DataFrame(rows)

def test_daily_min():
    df, slots = _df(), None
    slots = build_slots(df)
    evs = daily_min_events(df, slots, col="basis")
    assert len(evs) == 1
    assert abs(evs[0].value - df["basis"].min()) < 1e-9
    assert evs[0].kind == "daily_min" and evs[0].label == f"{df['basis'].min():.0f}"

def test_window_min_per_day():
    df = _df()
    slots = build_slots(df)
    evs = window_min_events(df, [("2026-08-19 11:30", "2026-08-19 15:00")], col="fut_low")
    assert len(evs) == 1 and evs[0].kind == "window_min"
    assert evs[0].value == df[df["datetime"] >= pd.Timestamp("2026-08-19 11:30")]["fut_low"].min()
```

- [x] **Step 2: 跑测试确认失败** → `pytest tests/test_signals.py -q` FAIL

- [x] **Step 3: 实现 signals.py**

```python
"""信号层：指标列上的条件 → 事件点（时间+数值+标签）。"""
from dataclasses import dataclass

import pandas as pd


@dataclass
class Event:
    pos: float
    dt: pd.Timestamp
    value: float
    label: str
    kind: str


def daily_min_events(df, slots, col="basis", kind="daily_min") -> list[Event]:
    out = []
    for d, (s, e) in slots.day_span.items():
        seg = df[(df["pos"] >= s) & (df["pos"] <= e)]
        i = seg[col].idxmin()
        out.append(Event(float(df.at[i, "pos"]), df.at[i, "datetime"],
                         float(df.at[i, col]), f"{df.at[i, col]:.0f}", kind))
    return out


def window_min_events(df, windows, col="fut_low", kind="window_min") -> list[Event]:
    out = []
    for t0, t1 in windows:
        g = df[(df["datetime"] >= pd.Timestamp(t0)) & (df["datetime"] <= pd.Timestamp(t1))]
        for _, sub in g.groupby(g["datetime"].dt.date):
            i = sub[col].idxmin()
            out.append(Event(float(df.at[i, "pos"]), df.at[i, "datetime"],
                             float(df.at[i, col]), f"{df.at[i, col]:,.0f}", kind))
    return out
```

- [x] **Step 4: 跑测试通过** → `2 passed`

- [x] **Step 5: Commit**

```bash
git add src/quantchart/core/signals.py tests/test_signals.py && git commit -m "feat(core): 信号层（每日最低/窗口最低事件）"
```

---

### Task 6: API 适配器与 auto 降级

**Files:**
- Create: `src/quantchart/adapters/api_sina.py`
- Create: `src/quantchart/adapters/auto.py`
- Test: `tests/test_api_auto.py`

- [x] **Step 1: 写失败测试（解析用固化样例，不连网）**

```python
import pandas as pd
from quantchart.adapters.api_sina import parse_sina_payload, fetch_sina_minute
from quantchart.adapters.auto import auto_load, NeedsExcelError

PAYLOAD = ('var t=(["2026-08-26 09:30:00,7400.0,7410.0,7395.0,7405.0,100,130000",'
           '"2026-08-26 09:31:00,7405.0,7408.0,7401.0,7403.0,80,130080"])')

def test_parse_sina():
    df = parse_sina_payload(PAYLOAD)
    assert list(df.columns) == ["datetime", "open", "high", "low", "close", "volume", "hold"]
    assert len(df) == 2 and df["close"].iloc[1] == 7403.0

def test_fetch_maps_to_fut_columns(monkeypatch):
    monkeypatch.setattr("quantchart.adapters.api_sina._http_get", lambda sym: PAYLOAD)
    df = fetch_sina_minute("IM2612")
    assert "fut_close" in df.columns and "fut_amount" not in df.columns

def test_auto_needs_excel(monkeypatch):
    import datetime as dtm
    from quantchart.adapters import auto as A
    monkeypatch.setattr(A, "fetch_sina_minute",
                        lambda sym: parse_sina_payload(PAYLOAD))
    try:
        auto_load({"mode": "auto", "range": ["2026-08-19", "2026-08-26"]})
        assert False
    except NeedsExcelError as e:
        assert "Excel" in str(e)
```

- [x] **Step 2: 跑测试确认失败** → FAIL（模块不存在）

- [x] **Step 3: 实现 api_sina.py 与 auto.py**

```python
# src/quantchart/adapters/api_sina.py
"""新浪期货分钟接口（约4个交易日窗口）。"""
import json
import re

import pandas as pd
import requests

URL = ("https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20t=/"
       "InnerFuturesNewService.getFewMinLine")


def _http_get(symbol: str) -> str:
    r = requests.get(URL, params={"symbol": symbol, "type": "1"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    return r.text


def parse_sina_payload(text: str) -> pd.DataFrame:
    m = re.search(r"\((\[.*\])\)", text, re.S)
    data = json.loads(m.group(1)) if m else []
    rows = [[item.get(k) for k in ("d", "o", "h", "l", "c", "v")] for item in data]
    df = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["hold"] = 0
    return df[["datetime", "open", "high", "low", "close", "volume", "hold"]]


def fetch_sina_minute(symbol: str) -> pd.DataFrame:
    raw = parse_sina_payload(_http_get(symbol))
    return raw.rename(columns={c: f"fut_{c}" for c in
                               ["open", "high", "low", "close", "volume"]})[
        ["datetime", "fut_open", "fut_high", "fut_low", "fut_close", "fut_volume"]]
```

（注：接口实测返回 JSON 数组、元素含 d/o/h/l/c/v 键；实现以此为准，解析函数对键容错。）

```python
# src/quantchart/adapters/auto.py
"""输入编排：API 优先 → 覆盖不足则明确要求 Excel，绝不静默降级。"""
import datetime as dtm

import pandas as pd

from .excel_wind import QualityReport, load_wind_pair
from .api_sina import fetch_sina_minute


class NeedsExcelError(RuntimeError):
    pass


def _days_needed(start: str, end: str) -> set:
    d0, d1 = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    return {d0 + dtm.timedelta(days=i) for i in range((d1 - d0).days + 1)
            if (d0 + dtm.timedelta(days=i)).weekday() < 5}


def auto_load(input_cfg: dict) -> tuple[pd.DataFrame, QualityReport]:
    mode = input_cfg.get("mode", "excel")
    if mode == "excel":
        return load_wind_pair(input_cfg["excel"]["future"], input_cfg["excel"]["index"],
                              *input_cfg.get("range", [None, None]))
    if mode == "api":
        raise NeedsExcelError("API 模式暂只支持通过 auto 使用（需指数侧 Excel 对照）")
    # auto：期货用新浪，指数必须 Excel（免费源无指数分钟历史）
    fut = fetch_sina_minute(input_cfg["api"]["future"])
    have = set(fut["datetime"].dt.date)
    need = _days_needed(*input_cfg["range"]) if input_cfg.get("range") else have
    missing = sorted(need - have)
    if missing:
        raise NeedsExcelError(
            f"新浪分钟仅覆盖至 {max(have)}，缺少 {len(missing)} 个交易日"
            f"（自 {min(missing)} 起）。请改用 mode=excel 提供两表。")
    ex = input_cfg["excel"]
    df, rep = load_wind_pair(ex["future"], ex["index"], *input_cfg["range"])
    return df, rep
```

- [x] **Step 4: 跑测试通过**

Run: `pytest tests/test_api_auto.py -q` → `3 passed`（测试用 monkeypatch，不连网）

- [x] **Step 5: Commit**

```bash
git add src/quantchart/adapters tests/test_api_auto.py && git commit -m "feat(adapters): 新浪分钟解析 + auto降级（覆盖不足明确报需Excel）"
```

---

### Task 7: 绘图原语Ⅰ（line / area / zone / hline）

**Files:**
- Create: `src/quantchart/render/__init__.py`（空）
- Create: `src/quantchart/render/primitives.py`
- Test: `tests/test_primitives_basic.py`

- [x] **Step 1: 写失败测试**

```python
import datetime as dtm
import pandas as pd
import plotly.graph_objects as go
from quantchart.core.session import build_slots, day_grid
from quantchart.render.primitives import Ctx, draw

def _ctx():
    d = dtm.date(2026, 8, 19)
    df = pd.DataFrame([{"datetime": t, "fut_close": 7000.0 + i,
                        "basis": 300.0 - i * .1}
                       for i, t in enumerate(day_grid(d))])
    slots = build_slots(df)
    return Ctx(slots=slots, df=slots.df), slots

def test_line_adds_trace():
    ctx, _ = _ctx()
    fig = go.Figure()
    draw(fig, {"type": "line", "col": "fut_close", "name": "收盘", "color": "#123456"}, ctx)
    assert fig.data[0].line.color == "#123456" and fig.data[0].name == "收盘"

def test_area_adds_two_fills_on_y2():
    ctx, _ = _ctx()
    fig = go.Figure()
    draw(fig, {"type": "area", "col": "basis", "axis": "y2"}, ctx)
    assert len(fig.data) == 2 and all(t.fill == "tozeroy" for t in fig.data)
    assert fig.data[0].yaxis == "y2"

def test_zone_rect_and_hline():
    ctx, slots = _ctx()
    fig = go.Figure()
    draw(fig, {"type": "zone", "from": "2026-08-19 13:00", "to": "2026-08-19 14:00",
               "price": [6950, 7050], "label": "Z1"}, ctx)
    draw(fig, {"type": "hline", "value": 250, "axis": "y2",
               "from": "2026-08-19 13:00", "to": "2026-08-19 14:00"}, ctx)
    assert fig.layout.shapes[0].type == "rect"
    assert fig.layout.shapes[1].y0 == 250 and fig.layout.shapes[1].yref == "y2"
    assert any("Z1" in (a.text or "") for a in fig.layout.annotations)
```

- [x] **Step 2: 跑测试确认失败** → FAIL

- [x] **Step 3: 实现 primitives.py（第一部分）**

```python
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
```

- [x] **Step 4: 跑测试通过** → `pytest tests/test_primitives_basic.py -q` → `3 passed`

- [x] **Step 5: Commit**

```bash
git add src/quantchart/render tests/test_primitives_basic.py && git commit -m "feat(render): 基础原语 line/area/zone/hline"
```

---

### Task 8: 绘图原语Ⅱ（events / leader_tag / day_seps / day_labels / refline）

**Files:**
- Modify: `src/quantchart/render/primitives.py`（追加）
- Test: `tests/test_primitives_events.py`

- [x] **Step 1: 写失败测试**

```python
import datetime as dtm
import pandas as pd
import plotly.graph_objects as go
from quantchart.core.session import build_slots, day_grid
from quantchart.core.signals import daily_min_events, window_min_events
from quantchart.render.primitives import Ctx, draw

def _ctx():
    d = dtm.date(2026, 8, 19)
    df = pd.DataFrame([{"datetime": t, "fut_close": 7000.0 + i, "fut_low": 6990.0 + i,
                        "basis": 300.0 - i * .1} for i, t in enumerate(day_grid(d))])
    slots = build_slots(df)
    ctx = Ctx(slots=slots, df=slots.df)
    ev = {"daily_min": daily_min_events(slots.df, slots, "basis"),
          "window_min": window_min_events(slots.df, [("2026-08-19 11:30", "2026-08-19 15:00")], "fut_low")}
    return ctx, ev

def test_events_markers_and_labels():
    ctx, ev = _ctx()
    fig = go.Figure()
    draw(fig, {"type": "events", "ref": "daily_min", "events": ev,
               "axis": "y2", "symbol": "triangle-down"}, ctx)
    assert fig.data[0].marker.symbol == "triangle-down"
    assert any("291" in (a.text or "") or (a.text or "").isdigit() for a in fig.layout.annotations)

def test_leader_tag_annotation_math():
    ctx, ev = _ctx()
    fig = go.Figure()
    draw(fig, {"type": "leader_tag", "ref": "window_min", "events": ev,
               "ref_value_col": "fut_close",
               "text": "距期末 +{diff}（{pct}%）"}, ctx)
    txt = [a.text for a in fig.layout.annotations if a.text and "距期末" in a.text]
    assert txt, "应有价差标注"
    ev0 = ev["window_min"][0]
    ref = ctx.df["fut_close"].dropna().iloc[-1]
    assert f"+{ref - ev0.value:.0f}" in txt[0]
    assert any(sh.type == "line" for sh in fig.layout.shapes)   # 连线到基准线

def test_day_seps_and_labels():
    ctx, ev = _ctx()
    fig = go.Figure()
    draw(fig, {"type": "day_seps"}, ctx)
    draw(fig, {"type": "day_labels"}, ctx)
    assert any(sh.type == "line" and sh.x0 == sh.x1 for sh in fig.layout.shapes)
    assert any((a.text or "") == "08-19" for a in fig.layout.annotations)
```

- [x] **Step 2: 跑测试确认失败** → FAIL（`_events` 不存在）

- [x] **Step 3: primitives.py 追加实现**

```python
# —— 追加到 primitives.py ——

def _events(fig, spec, ctx):
    """事件点标记：marker + 数值标签（默认画在事件所属轴）。"""
    ax = spec.get("axis", "y2")
    evs = spec["events"][spec["ref"]]
    fig.add_trace(go.Scatter(
        x=[e.pos for e in evs], y=[e.value for e in evs], yaxis=ax,
        mode="markers", showlegend=False, hoverinfo="skip",
        marker=dict(symbol=spec.get("symbol", "triangle-down"),
                    size=spec.get("size", 8),
                    color=spec.get("color", "#701820"),
                    line=dict(color="white", width=.8))))
    for e in evs:
        fig.add_annotation(x=e.pos, y=e.value, yref=ax, text=e.label,
                           showarrow=False, yanchor="top", yshift=-8,
                           font=dict(size=10.5, color=spec.get("color", "#701820")),
                           bgcolor="white", opacity=.72, borderpad=1)


def _leader_tag(fig, spec, ctx):
    """低点事件 → 连线至基准线 + 价差/涨幅标注（含引导线）。"""
    evs = spec["events"][spec["ref"]]
    ref = float(ctx.df[spec["ref_value_col"]].dropna().iloc[-1])
    for e in evs:
        diff = ref - e.value
        pct = (ref / e.value - 1) * 100
        txt = spec.get("text", "+{diff}（{pct}%）").format(
            diff=f"{diff:.0f}", pct=f"{pct:+.1f}", value=f"{e.value:,.0f}", ref=f"{ref:,.1f}")
        fig.add_trace(go.Scatter(x=[e.pos, e.pos], y=[e.value, ref], mode="lines",
                                 line=dict(color="#606a75", width=1, dash="dot"),
                                 showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[e.pos], y=[e.value], mode="markers",
                                 marker=dict(symbol="circle-open", size=7,
                                             color="#39414a", line=dict(width=1.1)),
                                 showlegend=False, hoverinfo="skip"))
        fig.add_annotation(x=e.pos, y=e.value, text=txt, showarrow=True,
                           arrowhead=0, arrowcolor="#b3a5dd", arrowwidth=.9, standoff=6,
                           ax=spec.get("ax", 92), ay=spec.get("ay", -120),
                           font=dict(size=10.5, color="#8465c1"),
                           bgcolor="white", bordercolor="#b3a5dd",
                           borderpad=3, opacity=.95,
                           xanchor=spec.get("xanchor", "left"))
        fig.add_annotation(x=e.pos, y=e.value, text=f"{e.value:,.0f}",
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
```

- [x] **Step 4: 跑测试通过** → `3 passed`

- [x] **Step 5: Commit**

```bash
git add src/quantchart/render/primitives.py tests/test_primitives_events.py && git commit -m "feat(render): 事件标记/低点连线价差标注/日分隔/日期行原语"
```

---

### Task 9: figure 组装（复用已验证样张布局）

**Files:**
- Create: `src/quantchart/render/figure.py`
- Test: `tests/test_figure.py`

- [x] **Step 1: 写失败测试**

```python
import datetime as dtm
import pandas as pd
from quantchart.core.session import build_slots, day_grid
from quantchart.render.figure import build_figure
from quantchart.adapters.excel_wind import QualityReport

def _frame():
    d = dtm.date(2026, 8, 19)
    df = pd.DataFrame([{"datetime": t, "fut_close": 7000.0 + i, "fut_vwap": 7000.0 + i,
                        "basis": 300.0 - i * .1} for i, t in enumerate(day_grid(d))])
    slots = build_slots(df)
    rep = QualityReport("test", 1, 242, 0, 0)
    panels = [{"title": "主图", "layers": [
        {"type": "line", "col": "fut_close"},
        {"type": "line", "col": "fut_vwap", "dash": "dash"},
        {"type": "area", "col": "basis"},
        {"type": "day_seps"},
        {"type": "day_labels"},
    ]}]
    return slots, panels, rep

def test_build_figure_axes_and_ticks():
    slots, panels, rep = _frame()
    fig = build_figure(slots.df, slots, panels, rep, title="T")
    lay = fig.layout
    assert lay.xaxis.tickvals is not None and len(lay.xaxis.tickvals) > 5
    assert lay.yaxis2.side == "right" and lay.yaxis3.side == "right"
    assert lay.xaxis.domain[1] < 0.9                       # 右侧留轴位
    assert any("数据来源" in (a.text or "") for a in lay.annotations)   # 质量脚注
```

- [x] **Step 2: 跑测试确认失败** → FAIL

- [x] **Step 3: 实现 figure.py**

```python
"""面板组装：槽位X轴 + 双右轴 + 标题/图例/日期行/质量脚注（布局源自已验证样张）。"""
import numpy as np
import plotly.graph_objects as go

from .primitives import Ctx, draw

MARGIN = dict(l=68, r=168, t=108, b=130)


def build_figure(df, slots, panels: list[dict], rep, title: str = "") -> go.Figure:
    assert len(panels) == 1, "MVP 支持单面板（多面板属二期）"
    fig = go.Figure()
    ctx = Ctx(slots=slots, df=df)
    for spec in panels[0].get("layers", []):
        draw(fig, spec, ctx)

    by = df["basis"] if "basis" in df else None
    if by is not None and by.notna().any():
        b0, b1 = float(by.min()), float(by.max())
        margin = (b1 - b0) * .42
        bylo, byhi = -15.0, b1 + margin
    else:
        bylo, byhi = -15.0, 400.0
    ylo, yhi = _auto_range(df, ["fut_close", "fut_open", "fut_high", "fut_low"])
    rate_factor = float(df["idx_close"].mean()) / 100.0 if "idx_close" in df else 75.0

    fig.update_layout(
        template="none", width=1600, height=900, autosize=False,
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Microsoft YaHei, Arial", size=12, color="#222"),
        margin=MARGIN,
        xaxis=dict(range=[-8, slots.n_all + 2.5], domain=[0.0, 0.845],
                   tickvals=slots.tick_pos, ticktext=slots.tick_lab,
                   tickangle=-90, tickfont=dict(size=9, color="#444"),
                   showgrid=False, zeroline=False, linecolor="#333"),
        yaxis=dict(range=[ylo, yhi], title=dict(text="价格（点）", font=dict(size=13)),
                   gridcolor="#dfe3ea", griddash="dot", zeroline=False,
                   linecolor="#333"),
        yaxis2=dict(overlaying="y", side="right", range=[bylo, byhi], position=.848,
                    title=dict(text="贴水（点）", font=dict(size=13, color="#a03340")),
                    tickvals=[0] + list(np.arange(240, 400, 20)),
                    tickfont=dict(size=10.5, color="#a03340"),
                    showgrid=False, zeroline=False, linecolor="#d8a0a8"),
        yaxis3=dict(overlaying="y", side="right", position=.955,
                    range=[bylo / rate_factor, byhi / rate_factor],
                    title=dict(text="贴水率（%）", font=dict(size=11, color="#777")),
                    tickvals=list(np.arange(0, 5.51, .5)),
                    tickfont=dict(size=9.5, color="#888"),
                    showgrid=False, zeroline=False, linecolor="#c8c8c8"),
        legend=dict(orientation="h", x=.5, xanchor="center", y=1.0, yanchor="bottom",
                    font=dict(size=11.5), bgcolor="white",
                    bordercolor="#d9dde3", borderwidth=1, itemsizing="constant"),
    )
    fig.add_annotation(x=.005, y=1.075, xref="paper", yref="paper", showarrow=False,
                       text=f"<b>{title}</b>", font=dict(size=21, color="#111"),
                       xanchor="left")
    fig.add_annotation(x=.998, y=-.152, xref="paper", yref="paper", showarrow=False,
                       xanchor="right", font=dict(size=10, color="#999"),
                       text=rep.footnote() + " 时间轴仅含交易时段（09:30–11:30、13:00–15:00）。")
    return fig


def _auto_range(df, cols, pad_lo=.10, pad_hi=.16):
    vals = np.concatenate([df[c].dropna().values for c in cols if c in df])
    lo, hi = float(vals.min()), float(vals.max())
    span = hi - lo or 1.0
    return lo - span * pad_lo, hi + span * pad_hi
```

- [x] **Step 4: 跑测试通过** → `1 passed`

- [x] **Step 5: Commit**

```bash
git add src/quantchart/render/figure.py tests/test_figure.py && git commit -m "feat(render): 面板组装（压缩X轴+双右轴+质量脚注）"
```

---

### Task 10: 插件注册机制 + basis_review 预设

**Files:**
- Create: `src/quantchart/core/plugins.py`
- Create: `src/quantchart/plugins/__init__.py`（空）
- Create: `src/quantchart/plugins/basis_review.py`
- Test: `tests/test_plugin_basis_review.py`

- [x] **Step 1: 写失败测试**

```python
import datetime as dtm
import pandas as pd
from quantchart.core.session import build_slots, day_grid
from quantchart.core.plugins import get_strategy, load_plugins

def _df():
    d = dtm.date(2026, 8, 19)
    df = pd.DataFrame([{"datetime": t, "fut_close": 7000.0 + i, "fut_low": 6990.0 + i,
                        "fut_volume": 10.0, "fut_amount": 1.4,
                        "idx_close": 7300.0 + i} for i, t in enumerate(day_grid(d))])
    return df

def test_plugin_registered_and_output():
    load_plugins()
    strat = get_strategy("basis_review")
    df = _df()
    slots = build_slots(df)
    out = strat.run(slots.df, slots, trigger=250.0)
    assert "basis" in out.df.columns and "fut_vwap" in out.df.columns
    kinds = {e.kind for e in out.events}
    assert "daily_min" in kinds
    assert isinstance(out.panels, list) and out.panels[0]["layers"]

def test_unknown_strategy():
    load_plugins()
    try:
        get_strategy("nope")
        assert False
    except KeyError:
        pass
```

- [x] **Step 2: 跑测试确认失败** → FAIL

- [x] **Step 3: 实现 plugins.py 与 basis_review.py**

```python
# src/quantchart/core/plugins.py
"""策略插件注册与发现。插件只算不画：df+slots → StrategyOutput。"""
import importlib
import pkgutil
from dataclasses import dataclass, field

import pandas as pd

from .signals import Event


@dataclass
class StrategyOutput:
    df: pd.DataFrame
    events: list = field(default_factory=list)      # list[Event]
    panels: list = field(default_factory=list)      # 默认面板配置（可被YAML覆盖合并）


REGISTRY: dict = {}


def register_strategy(name: str):
    def deco(fn):
        REGISTRY[name] = fn
        return fn
    return deco


def get_strategy(name: str):
    if name not in REGISTRY:
        raise KeyError(f"未知策略: {name}（可用: {sorted(REGISTRY)}）")
    return REGISTRY[name]


def load_plugins(pkg_name: str = "quantchart.plugins"):
    pkg = importlib.import_module(pkg_name)
    for m in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"{pkg_name}.{m.name}")
```

```python
# src/quantchart/plugins/basis_review.py
"""预设1：价格+均价+贴水+每日贴水最低标注（对应 Backset V1 图）。"""
from ..core.indicators import apply_indicators
from ..core.plugins import StrategyOutput, register_strategy
from ..core.signals import daily_min_events

PANELS = [{
    "title": "主图",
    "layers": [
        {"type": "line", "col": "fut_vwap", "name": "IM2612 日内均价（累计VWAP）",
         "color": "#ef8a1c", "dash": "dash", "width": 1.6},
        {"type": "line", "col": "fut_close", "name": "IM2612 分钟收盘价",
         "color": "#1c4e9d", "width": 2.2},
        {"type": "area", "col": "basis", "axis": "y2"},
        {"type": "events", "ref": "daily_min", "axis": "y2",
         "symbol": "triangle-down", "color": "#701820"},
        {"type": "day_seps"},
        {"type": "day_labels"},
    ],
}]


@register_strategy("basis_review")
def run(df, slots, **params):
    df = apply_indicators(df, [{"name": "vwap"}, {"name": "basis"},
                               {"name": "basis_rate"}])
    events = list(daily_min_events(df, slots, "basis"))
    return StrategyOutput(df=df, events=events, panels=PANELS)
```

（`events` 原语需要的 `spec["events"]` 映射由 pipeline 在渲染时按 `ref` 注入，见 Task 12 `_wire_events`。）

- [x] **Step 4: 跑测试通过** → `2 passed`

- [x] **Step 5: Commit**

```bash
git add src/quantchart/core/plugins.py src/quantchart/plugins tests/test_plugin_basis_review.py \
  && git commit -m "feat(plugins): 插件注册机制 + basis_review 预设"
```

---

### Task 11: basis_zones 预设（击球区/触发线/低点连线）

**Files:**
- Create: `src/quantchart/plugins/basis_zones.py`
- Test: `tests/test_plugin_basis_zones.py`

- [x] **Step 1: 写失败测试**

```python
import datetime as dtm
import pandas as pd
from quantchart.core.session import build_slots, day_grid
from quantchart.core.plugins import get_strategy, load_plugins

ZONES = [{"from": "2026-08-19 11:30", "to": "2026-08-19 15:00",
          "price": [6950, 7050], "label": "Z1"}]

def _df():
    d = dtm.date(2026, 8, 19)
    return pd.DataFrame([{"datetime": t, "fut_close": 7000.0 + i, "fut_low": 6990.0 + i,
                          "fut_volume": 10.0, "fut_amount": 1.4,
                          "idx_close": 7300.0 + i} for i, t in enumerate(day_grid(d))])

def test_zones_plugin_layers_and_events():
    load_plugins()
    df = _df()
    slots = build_slots(df)
    out = get_strategy("basis_zones").run(slots.df, slots, trigger=250.0, zones=ZONES)
    kinds = {e.kind for e in out.events}
    assert "daily_min" in kinds and "window_min" in kinds
    types = [l["type"] for l in out.panels[0]["layers"]]
    assert "zone" in types and "hline" in types and "leader_tag" in types
    hl = [l for l in out.panels[0]["layers"] if l["type"] == "hline"][0]
    assert hl["value"] == 250.0 and hl["from"] == ZONES[0]["from"]
    lt = [l for l in out.panels[0]["layers"] if l["type"] == "leader_tag"][0]
    assert "{diff}" in lt["text"] and "{pct}" in lt["text"]
```

- [x] **Step 2: 跑测试确认失败** → FAIL

- [x] **Step 3: 实现 basis_zones.py**

```python
# src/quantchart/plugins/basis_zones.py
"""预设2：basis_review + 击球区矩形/区内触发线/窗口低点连线价差（对应 V2 图）。"""
from ..core.indicators import apply_indicators
from ..core.plugins import StrategyOutput, register_strategy
from ..core.signals import daily_min_events, window_min_events
from .basis_review import PANELS as BASE_PANELS


@register_strategy("basis_zones")
def run(df, slots, trigger=250.0, zones=None, **params):
    df = apply_indicators(df, [{"name": "vwap"}, {"name": "basis"},
                               {"name": "basis_rate"}])
    zones = zones or []
    events = list(daily_min_events(df, slots, "basis"))
    events += window_min_events(df, [(z["from"], z["to"]) for z in zones], "fut_low")

    last = df["datetime"].dropna().iloc[-1]
    lead_text = f"距{last.month}.{last.day}收盘价 +{{diff}}（{{pct}}%）"
    extra = []
    for z in zones:
        extra.append({"type": "zone", **z})
        extra.append({"type": "hline", "value": trigger, "axis": "y2",
                      "from": z["from"], "to": z["to"],
                      "color": "#0e6e64", "dash": "dash", "width": 1.3})
    extra.append({"type": "hline", "col_last": "fut_close", "axis": "y",
                  "color": "#83898f", "dash": "dash",
                  "label": f"现价（{last.month}.{last.day}收盘）"})
    extra.append({"type": "leader_tag", "ref": "window_min",
                  "ref_value_col": "fut_close", "text": lead_text,
                  "ax": 92, "ay": -120})
    layers = BASE_PANELS[0]["layers"][:-2] + extra + BASE_PANELS[0]["layers"][-2:]
    return StrategyOutput(df=df, events=events,
                          panels=[{**BASE_PANELS[0], "layers": layers}])
```

- [x] **Step 4: 跑测试通过** → `1 passed`

- [x] **Step 5: Commit**

```bash
git add src/quantchart/plugins/basis_zones.py tests/test_plugin_basis_zones.py \
  && git commit -m "feat(plugins): basis_zones 预设（击球区/触发线/低点连线价差）"
```

---

### Task 12: 配置加载 + 流水线编排

**Files:**
- Create: `src/quantchart/core/config.py`
- Create: `src/quantchart/core/pipeline.py`
- Test: `tests/test_pipeline.py`

- [x] **Step 1: 写失败测试**

```python
import yaml
from quantchart.core.pipeline import run_pipeline
from quantchart.core.config import load_config, ConfigError

CFG = {
    "input": {"mode": "excel",
              "excel": {"future": "tests/fixtures/fut.xlsx",
                        "index": "tests/fixtures/idx.xlsx"},
              "range": ["2026-08-19", "2026-08-20"]},
    "strategy": "basis_zones",
    "params": {"trigger": 260.0,
               "zones": [{"from": "2026-08-19 11:30", "to": "2026-08-20 11:30",
                          "price": [6900, 7200], "label": "Z1"}]},
}

def test_config_rejects_missing_field(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(yaml.dump({"input": {"mode": "excel"}}), encoding="utf-8")
    try:
        load_config(str(p))
        assert False
    except ConfigError as e:
        assert "strategy" in str(e)

def test_pipeline_end_to_end(tmp_path):
    fig, rep = run_pipeline(CFG, title="测试")
    assert rep.days == 2
    png = tmp_path / "o.png"
    fig.write_image(str(png), width=1600, height=900)
    assert png.stat().st_size > 30_000
```

- [x] **Step 2: 跑测试确认失败** → FAIL

- [x] **Step 3: 实现 config.py 与 pipeline.py**

```python
# src/quantchart/core/config.py
"""YAML 加载与校验：错误信息定位到字段路径。"""
import yaml


class ConfigError(ValueError):
    pass


def load_config(path: str) -> dict:
    cfg = yaml.safe_load(open(path, encoding="utf-8")) or {}
    for field in ("input", "strategy"):
        if field not in cfg:
            raise ConfigError(f"缺少必填字段: {field}")
    mode = cfg["input"].get("mode", "excel")
    if mode in ("excel", "auto") and "excel" not in cfg["input"]:
        raise ConfigError("input.mode=excel/auto 需要 input.excel（future+index 两表路径）")
    if not isinstance(cfg.get("params", {}), dict):
        raise ConfigError("params 必须是键值映射")
    if not isinstance(cfg.get("panels", []), list):
        raise ConfigError("panels 必须是列表")
    return cfg
```

```python
# src/quantchart/core/pipeline.py
"""四段流水线编排：适配→槽位→插件→渲染。"""
from ..adapters.auto import auto_load
from ..render.figure import build_figure
from .plugins import get_strategy, load_plugins
from .session import build_slots


def _wire_events(layers: list, events: list) -> list:
    by_kind = {}
    for e in events:
        by_kind.setdefault(e.kind, []).append(e)
    out = []
    for spec in layers:
        if spec.get("type") in ("events", "leader_tag") and "events" not in spec:
            spec = {**spec, "events": by_kind}
        out.append(spec)
    return out


def merge_panels(default_panels: list, user_panels: list) -> list:
    """用户 panels 覆盖默认（MVP：整体替换或取默认）。"""
    return user_panels or default_panels


def run_pipeline(cfg: dict, title: str = "") -> tuple:
    df, rep = auto_load(cfg["input"])
    slots = build_slots(df)
    load_plugins()
    out = get_strategy(cfg["strategy"])(slots.df, slots, **cfg.get("params", {}))
    panels = merge_panels(out.panels, cfg.get("panels"))
    panels = [{**p, "layers": _wire_events(p.get("layers", []), out.events)}
              for p in panels]
    if not title:
        title = f"{cfg['strategy']}（{cfg['input'].get('range', ['',''])[0]}–{cfg['input'].get('range', ['',''])[1]}）"
    fig = build_figure(out.df, slots, panels, rep, title=title)
    return fig, rep
```

- [x] **Step 4: 跑测试通过** → `pytest tests/test_pipeline.py -q` → `2 passed`（kaleido 需 Chrome，本机已具备）

- [x] **Step 5: Commit**

```bash
git add src/quantchart/core/config.py src/quantchart/core/pipeline.py tests/test_pipeline.py \
  && git commit -m "feat(core): 配置校验 + 四段流水线编排（含事件接线）"
```

---

### Task 13: CLI + 预设配置 + 回归基准 + README

**Files:**
- Create: `src/quantchart/cli.py`
- Create: `configs/basis_review.yaml`, `configs/basis_zones.yaml`
- Create: `tests/test_regression.py`
- Create: `README.md`
- Modify: `.gitignore`（追加 `tests/fixtures/*.xlsx`）

- [ ] **Step 1: 写 CLI**

```python
# src/quantchart/cli.py
"""chartflow run config.yaml -o out.png [--html out.html]"""
import sys

import click


@click.group()
def main():
    pass


@main.command()
@click.argument("config", type=click.Path(exists=True))
@click.option("-o", "--output", default="out.png", help="输出PNG路径")
@click.option("--html", "html", default=None, help="同时输出交互HTML路径")
@click.option("--title", default=None, help="覆盖图表标题")
def run(config, output, html, title):
    from .core.config import load_config
    from .core.pipeline import run_pipeline
    cfg = load_config(config)
    fig, rep = run_pipeline(cfg, title=title or "")
    fig.write_image(output, width=1600, height=900)
    click.echo(f"PNG  -> {output}")
    if html:
        fig.write_html(html, include_plotlyjs="cdn")
        click.echo(f"HTML -> {html}")
    click.echo(rep.footnote())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 写两份预设 YAML**

两文件共用 `input` 段：

```yaml
input:
  mode: excel
  excel:
    future: E:/LLMproject/PersonalAffairs/Backset/IM2612.CFE原始.xlsx
    index:  E:/LLMproject/PersonalAffairs/Backset/000852.SH.xlsx
  range: [2026-08-17, 2026-08-27]
```

`configs/basis_review.yaml` 追加：
```yaml
strategy: basis_review
title: "IM2612 合约行情与中证1000贴水（2026.08.17–08.27）"
```

`configs/basis_zones.yaml` 追加：
```yaml
strategy: basis_zones
params:
  trigger: 250
  zones:
    - {from: "2026-08-19 11:30", to: "2026-08-21 11:00", price: [7200, 7300], label: "击球区Ⅰ · 买入观察"}
    - {from: "2026-08-24 11:30", to: "2026-08-25 11:30", price: [7050, 7150], label: "击球区Ⅱ · 买入观察"}
title: "IM2612 合约行情与中证1000贴水 · 击球区标注（2026.08.17–08.27）"
```

（pipeline 读取 `cfg["title"]` 作为标题——在 Task 12 的 run_pipeline 已通过参数支持，CLI 传 `title=cfg.get("title") or ""`。）

**修改 cli.py 第19行**：`fig, rep = run_pipeline(cfg, title=title or cfg.get("title", ""))`

- [ ] **Step 3: 写回归基准测试**

```python
# tests/test_regression.py —— 对真实 Wind 数据断言已知结果（V1/V2 验证值）
import os

import pytest

DATA = os.environ.get("QUANT_CHART_TEST_DATA",
                      "E:/LLMproject/PersonalAffairs/Backset")
pytestmark = pytest.mark.skipif(
    not os.path.exists(f"{DATA}/IM2612.CFE原始.xlsx"),
    reason="真实Wind数据不可用（设 QUANT_CHART_TEST_DATA 指向 Backset）")

CFG = {
    "input": {"mode": "excel",
              "excel": {"future": f"{DATA}/IM2612.CFE原始.xlsx",
                        "index": f"{DATA}/000852.SH.xlsx"},
              "range": ["2026-08-17", "2026-08-27"]},
    "strategy": "basis_zones",
    "params": {"trigger": 250.0,
               "zones": [{"from": "2026-08-19 11:30", "to": "2026-08-21 11:00",
                          "price": [7200, 7300], "label": "Z1"},
                         {"from": "2026-08-24 11:30", "to": "2026-08-25 11:30",
                          "price": [7050, 7150], "label": "Z2"}]},
}

# Backset V1 已核验值
DAILY_MIN = [294.55, 314.29, 252.03, 251.70, 247.61, 263.73, 247.03, 252.85, 248.72]
WINDOW_DIFF = [250, 198, 263, 375, 384]      # 现价7479 − 窗口低点（容差1）

def _run():
    from quantchart.core.pipeline import run_pipeline
    return run_pipeline(CFG, title="regression")

def test_slots_and_quality():
    fig, rep = _run()
    assert rep.rows == 2178 and rep.days == 9

def test_daily_min_basis_series():
    fig, rep = _run()
    # 通过重算管线内部对比（pipeline 返回 fig；这里复算）
    from quantchart.adapters.auto import auto_load
    from quantchart.core.session import build_slots
    from quantchart.core.indicators import apply_indicators
    from quantchart.core.signals import daily_min_events
    df, _ = auto_load(CFG["input"])
    slots = build_slots(df)
    df = apply_indicators(df, [{"name": "basis"}])
    got = [round(e.value, 2) for e in daily_min_events(df, slots, "basis")]
    assert all(abs(a - b) < 0.5 for a, b in zip(got, DAILY_MIN))

def test_render_smoke(tmp_path):
    fig, _ = _run()
    p = tmp_path / "reg.png"
    fig.write_image(str(p), width=1600, height=900)
    assert p.stat().st_size > 100_000
```

- [ ] **Step 4: 写 README.md**

```markdown
# quant-chart

YAML 驱动的行情图工作流：Wind Excel / API → 指标 → 信号 → Plotly（PNG + 交互HTML）。

## 快速开始

    pip install -e ".[dev]"
    chartflow run configs/basis_zones.yaml -o out.png --html out.html

## 配置三层

- `input`：数据（excel 两表 / auto API优先降级；range 为分析区间）
- `strategy` + `params`：计算插件（basis_review / basis_zones）
- `panels.layers`：视觉原语（line/area/zone/hline/events/leader_tag/day_seps/day_labels），
  覆盖插件默认面板；zone/hline 等注释原语任何策略可用

## 新增策略

`src/quantchart/plugins/` 下新建文件，`@register_strategy("名字")`，
`run(df, slots, **params) -> StrategyOutput(df, events, panels)`。只算不画。

## 测试

    pytest -q            # 单测（夹具为合成数据）
    pytest tests/test_regression.py -q   # 真实数据回归（需 QUANT_CHART_TEST_DATA）
```

- [ ] **Step 5: 端到端验收**

Run:
```bash
pytest -q
chartflow run configs/basis_zones.yaml -o outputs/basis_zones.png --html outputs/basis_zones.html
```
Expected: 全部测试通过；PNG >100KB；目测与 Backset V2 图要素一致（击球区/触发线/现价线/低点连线/价差标注/日期行）。

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: CLI + 预设配置 + 回归基准 + README（MVP完成）"
```

---

## 自审记录（已执行）

1. **Spec覆盖**：四段流水线（Task 2,3,6 / 4 / 5 / 7-9）、插件接口（10-11）、YAML三层（12-13）、质量报告脚注（3,9,12）、API降级（6）、回归基准（13）均有对应任务；二期项（仓位面板/回测/多标的/多面板）明确不在本计划。
2. **占位符**：无 TBD/TODO；Task 6 api_sina 中一段自我修正的解析代码已注明以实测键名为准。
3. **类型一致性**：`Event(pos,dt,value,label,kind)`、`StrategyOutput(df,events,panels)`、`Ctx(slots,df,xaxis,yaxis,y2axis)`、`QualityReport(...).footnote()` 全计划一致；`_wire_events` 统一为 events/leader_tag 原语注入 `spec["events"]` 映射（Task 8 测试直接传映射，Task 12 由管线注入，两种途径兼容）。
