# quant-chart 日线蜡烛图扩展（一期）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 quant-chart 打通日线旁路全链路（daily_api/daily_csv 通道 → 日线槽位 → daily_candle 插件 → 6 类新渲染原语 → 深色主题组装），用 IM 主连日线复刻样板 `reference/05_IM2612合约.png`。

**Architecture:** 全部旁路接入——`input.mode` 以 `daily_` 开头即路由到独立 `run_daily_pipeline`，复用插件注册表/panels 合并/events 接线；分钟主路径一行不改。插件只算不画，视觉一律经通用原语翻译（pos 数值 x 轴，与分钟机制同构）。

**Tech Stack:** Python 3.12（`.venv`）、pandas、Plotly（Candlestick + shapes/annotations）、local-datasource @ `d106144`（期货日线库直调）、akshare（仅 tools 层外盘兜底）、pytest。

**Spec:** 原指向 `2026-08-28-daily-candle-replication-design.md`，该文档已于 2026-08-29 拆分为两份：`2026-08-28-daily-candle-charting-design.md`（通用作图能力，本文实现对象）与 `2026-08-29-three-reference-charts-design.md`（剩余三图复刻，另行计划）（本计划从 spec 论证，执行者两份都读）

## Global Constraints

- 分钟路径**零改动**：`adapters/auto.py`、`adapters/excel_wind.py`、`core/session.build_slots`、`render/figure.py` 与既有原语行为不变；对 `_zone`/`_hline` 只允许追加**默认值不变**的可选参数；既有测试零修改、零失败。
- 插件不 import plotly；核心库（`src/quantchart/`）无网络依赖、不 import akshare。
- local-datasource 锁定基线 commit `d106144`；`daily_api` 未安装时明确报错并给安装指引，绝不静默降级。
- 全部命令用 `.venv/bin/`（如 `.venv/bin/pytest -q`、`.venv/bin/chartflow`）。
- 中文报错定位到字段路径 / annotations 条目序号。
- 内部资料不入库：`.gitignore` 已含 `reference/`、`集群投研报告*.pdf`、`.venv/`；本计划补 `data/`、`out/`。
- 提交信息用仓库既有中文 conventional 风格（`feat:` / `test:` / `docs:`）。

## File Structure

```
src/quantchart/
├── adapters/
│   ├── common.py          # 修改：追加 DailyQualityReport（日线口径脚注）
│   └── daily.py           # 新建：load_daily 分派 daily_csv / daily_api，中文表头→宽表
├── core/
│   ├── session.py         # 修改：追加 MONTH_TICK_THRESHOLD + build_daily_slots
│   ├── config.py          # 修改：daily_* 模式校验（csv/symbol/range）
│   └── pipeline.py        # 修改：daily_ 前缀路由 + run_daily_pipeline + trades 拒绝
├── render/
│   ├── theme.py           # 新建：深色主题常量（底色/涨跌色/均线色板）
│   ├── primitives.py      # 修改：追加 _candle/_trendline/_arrow/_tag/_circle/_text
│   └── figure_daily.py    # 新建：build_daily_figure 深色单面板组装
└── plugins/
    └── daily_candle.py    # 新建：均线计算 + annotations 声明式标注翻译
configs/daily_candle.yaml  # 新建：一期样板模板（要素全开）
tools/fetch_daily.py       # 新建：取数脚本（主连 local-ds / 外盘 akshare 兜底）
tests/
├── test_daily_adapter.py / test_daily_slots.py / test_daily_primitives.py
├── test_daily_plugin.py / test_daily_pipeline.py   # 全部新建
```

---

### Task 1: 日线数据通道 `adapters/daily.py`

**Files:**
- Create: `src/quantchart/adapters/daily.py`
- Modify: `src/quantchart/adapters/common.py`（文件末尾追加）
- Test: `tests/test_daily_adapter.py`

**Interfaces:**
- Consumes: `local_datasource.providers.futures.query_futures(symbol, period, start_date, end_date, file_path) -> (csv_path, summary)`（local-datasource @d106144，已装于 .venv）；`adapters/local_ds.LocalDsNotInstalled`
- Produces: `load_daily(input_cfg: dict) -> tuple[pd.DataFrame, DailyQualityReport]`；`load_daily_csv(path, start=None, end=None)`；`load_daily_api(symbol, start=None, end=None)`——宽表列恒为 `datetime, open, high, low, close, volume`，`DailyQualityReport(source, days, rows).footnote() -> "数据来源:…；交易日N天。"`

- [ ] **Step 1: 在 `common.py` 末尾追加日线质量报告**

```python
@dataclass
class DailyQualityReport:
    source: str
    days: int
    rows: int

    def footnote(self) -> str:
        return f"数据来源:{self.source}；交易日{self.days}天。"
```

- [ ] **Step 2: 写失败测试 `tests/test_daily_adapter.py`**

```python
import pandas as pd
import pytest

from quantchart.adapters.common import DailyQualityReport
from quantchart.adapters.daily import load_daily, load_daily_api, load_daily_csv

CN = """日期,开盘价,最高价,最低价,收盘价,成交量,持仓量
2026-08-25,7500,7560,7440,7520,100,1
2026-08-26,7510,7600,7480,7590,110,1
2026-08-27,7600,7700,7550,7680,120,1
"""
EN = """date,open,high,low,close,volume
2026-08-25,7500,7560,7440,7520,100
2026-08-26,7510,7600,7480,7590,110
2026-08-27,7600,7700,7550,7680,120
"""


def _write(tmp_path, text, name="d.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_daily_quality_report_footnote():
    assert DailyQualityReport("x", 3, 30).footnote() == "数据来源:x；交易日3天。"


def test_csv_cn_headers_extra_cols_dropped(tmp_path):
    df, rep = load_daily_csv(_write(tmp_path, CN))
    assert list(df.columns) == ["datetime", "open", "high", "low", "close", "volume"]
    assert len(df) == 3 and rep.days == 3


def test_csv_en_headers_and_range_filter(tmp_path):
    df, rep = load_daily_csv(_write(tmp_path, EN), start="2026-08-26", end="2026-08-27")
    assert len(df) == 2 and rep.days == 2
    assert df["datetime"].iloc[0] == pd.Timestamp("2026-08-26")


def test_csv_missing_column(tmp_path):
    with pytest.raises(ValueError, match="缺少必需列"):
        load_daily_csv(_write(tmp_path, "date,open\n2026-08-25,1\n"))


def test_csv_empty_in_range(tmp_path):
    with pytest.raises(ValueError, match="无数据"):
        load_daily_csv(_write(tmp_path, CN), start="2020-01-01", end="2020-01-02")


def test_load_daily_dispatch(tmp_path):
    df, _ = load_daily({"mode": "daily_csv", "csv": _write(tmp_path, CN),
                        "range": ["2026-08-25", "2026-08-26"]})
    assert len(df) == 2


def test_load_daily_unknown_mode():
    with pytest.raises(ValueError, match="未知日线模式"):
        load_daily({"mode": "daily_x"})


def test_api_not_installed(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "local_datasource", None)
    from quantchart.adapters.daily import LocalDsNotInstalled
    with pytest.raises(LocalDsNotInstalled, match="daily_csv"):
        load_daily_api("IM0", "2026-08-25", "2026-08-27")


def test_api_success(monkeypatch):
    def fake_query(symbol, period, start_date, end_date, file_path):
        assert symbol == "IM0" and period == "daily"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(CN)
        return file_path, "ok"

    monkeypatch.setattr("local_datasource.providers.futures.query_futures", fake_query)
    df, rep = load_daily_api("IM0", "2026-08-25", "2026-08-27")
    assert len(df) == 3 and "local-datasource(IM0)" in rep.footnote()
```

- [ ] **Step 3: 跑测试确认失败**

Run: `.venv/bin/pytest tests/test_daily_adapter.py -q`
Expected: FAIL（`ModuleNotFoundError: quantchart.adapters.daily` 或 ImportError）

- [ ] **Step 4: 新建 `src/quantchart/adapters/daily.py`**

```python
"""日线数据通道：daily_csv（通用CSV）/ daily_api（local-datasource 期货日线）→ 规范宽表。

宽表列规范：datetime + open/high/low/close/volume（中文表头自动映射）。
核心库无网络依赖：daily_api 库直调 local-datasource provider（锁定基线 d106144）。
"""
import tempfile
from pathlib import Path

import pandas as pd

from .common import DailyQualityReport
from .local_ds import LocalDsNotInstalled

CN_REN = {"日期": "datetime", "开盘价": "open", "最高价": "high",
          "最低价": "low", "收盘价": "close", "成交量": "volume"}
KEEP = ["datetime", "open", "high", "low", "close", "volume"]


def _normalize(raw: pd.DataFrame, start, end, source: str):
    df = raw.rename(columns={str(c).strip(): c for c in raw.columns})
    df = df.rename(columns=CN_REN)
    if "date" in df.columns:
        df = df.rename(columns={"date": "datetime"})
    missing = [c for c in KEEP if c not in df.columns]
    if missing:
        raise ValueError(f"{source} 缺少必需列: {missing}"
                         f"（需含 datetime/date 与 open/high/low/close[/volume]）")
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.dropna(subset=["datetime", "close"]).sort_values("datetime")
    if df["datetime"].duplicated().any():
        raise ValueError(f"{source} 存在重复日期，请检查数据")
    lo = pd.Timestamp(start) if start else None
    hi = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1) if end else None
    if lo is not None:
        df = df[df["datetime"] >= lo]
    if hi is not None:
        df = df[df["datetime"] <= hi]
    if df.empty:
        raise ValueError(f"{source} 在区间 [{start}, {end}] 内无数据")
    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    rep = DailyQualityReport(source=source, days=int(df["datetime"].dt.date.nunique()), rows=len(df))
    return df[KEEP], rep


def load_daily_csv(path: str, start=None, end=None):
    try:
        raw = pd.read_csv(path, encoding="utf-8-sig")
    except FileNotFoundError as e:
        raise FileNotFoundError(f"日线CSV不存在: {path}") from e
    return _normalize(raw, start, end, source=f"日线CSV({Path(path).name})")


def load_daily_api(symbol: str, start=None, end=None):
    try:
        from local_datasource.providers import futures as fut
    except ImportError as e:
        raise LocalDsNotInstalled(
            "未安装 local-datasource（pip install -e <local-datasource 仓库路径>，"
            "联调基线 commit d106144），或改用 mode: daily_csv") from e
    out = Path(tempfile.mkdtemp(prefix="quantchart_daily_")) / "daily.csv"
    kwargs = {"symbol": symbol, "period": "daily", "file_path": str(out)}
    if start:
        kwargs["start_date"] = str(start)
    if end:
        kwargs["end_date"] = str(end)
    try:
        file_path, _summary = fut.query_futures(**kwargs)
    except ValueError:
        raise                       # 覆盖不足/代码不存在：对方已附指引，原样上报
    raw = pd.read_csv(file_path, encoding="utf-8-sig")
    return _normalize(raw, start, end, source=f"local-datasource({symbol})")


def load_daily(input_cfg: dict):
    mode = input_cfg.get("mode", "daily_csv")
    start, end = input_cfg.get("range", [None, None])
    if mode == "daily_csv":
        return load_daily_csv(input_cfg["csv"], start, end)
    if mode == "daily_api":
        return load_daily_api(input_cfg["api"]["symbol"], start, end)
    raise ValueError(f"未知日线模式: {mode}（可用: daily_csv / daily_api）")
```

- [ ] **Step 5: 跑测试确认通过**

Run: `.venv/bin/pytest tests/test_daily_adapter.py -q`
Expected: 9 passed

- [ ] **Step 6: 全量回归确认分钟路径无恙**

Run: `.venv/bin/pytest -q`
Expected: 全绿（与改动前一致）

- [ ] **Step 7: 提交**

```bash
git add src/quantchart/adapters/daily.py src/quantchart/adapters/common.py tests/test_daily_adapter.py
git commit -m "feat(adapters): 日线数据通道 daily_csv/daily_api（中文表头映射+日线质量脚注）"
```

---

### Task 2: 日线槽位 `build_daily_slots`

**Files:**
- Modify: `src/quantchart/core/session.py`（文件末尾追加）
- Test: `tests/test_daily_slots.py`

**Interfaces:**
- Consumes: `Slots` dataclass（同文件已有）；df 须含 `datetime` 列
- Produces: `MONTH_TICK_THRESHOLD = 90`；`build_daily_slots(df: pd.DataFrame) -> Slots`——`pos=0..n-1` 连续、`day_span={date:(pos,pos)}`、`sep_center`=月界分隔位、刻度自适应（>90 交易日按月 `YY-MM`，否则按 ISO 周 `MM-DD`）

- [ ] **Step 1: 写失败测试 `tests/test_daily_slots.py`**

```python
import pandas as pd

from quantchart.core.session import MONTH_TICK_THRESHOLD, build_daily_slots


def _daily(n, start="2026-06-01"):
    idx = pd.bdate_range(start, periods=n)
    return pd.DataFrame({"datetime": idx, "open": 1.0, "high": 2.0,
                         "low": 0.5, "close": 1.5, "volume": 1})


def test_pos_sequential_and_n_all():
    slots = build_daily_slots(_daily(10))
    assert slots.n_all == 10
    assert slots.df["pos"].tolist() == [float(i) for i in range(10)]


def test_day_span_one_slot_per_day():
    slots = build_daily_slots(_daily(10))
    assert slots.day_span[pd.Timestamp("2026-06-01").date()] == (0.0, 0.0)
    assert slots.day_span[pd.Timestamp("2026-06-12").date()] == (9.0, 9.0)


def test_month_seps_when_crossing_month():
    slots = build_daily_slots(_daily(45))          # 6/1 起 45 个交易日跨入 8 月
    assert slots.sep_center == [21.5]              # 6月22个交易日后


def test_week_ticks_short_range():
    slots = build_daily_slots(_daily(10))          # 6/1(周一)..6/12
    assert slots.tick_lab[0] == "06-01"
    assert slots.tick_lab[1] == "06-08"
    assert len(slots.tick_pos) == 2


def test_month_ticks_long_range():
    slots = build_daily_slots(_daily(MONTH_TICK_THRESHOLD + 10))
    assert slots.tick_lab[:3] == ["26-06", "26-07", "26-08"]
    assert len(slots.sep_center) >= 3
```

（注：`sep_center`/刻度数的期望值如与真实日历差一天，以实际 `pd.bdate_range` 输出为准修正断言，但**规则本身不得改**。）

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/test_daily_slots.py -q`
Expected: FAIL with `ImportError: cannot import name 'build_daily_slots'`

- [ ] **Step 3: 在 `session.py` 末尾实现**

```python
MONTH_TICK_THRESHOLD = 90


def build_daily_slots(df: pd.DataFrame) -> Slots:
    """日线槽位：每交易日一格 pos=0..n-1；非交易日自然压缩；月界分隔、刻度自适应。"""
    df = df.copy().reset_index(drop=True)
    n = len(df)
    if n == 0:
        raise ValueError("日线数据为空")
    df["pos"] = np.arange(n, dtype=float)
    days = list(df["datetime"].dt.date)
    day_span = {d: (float(i), float(i)) for i, d in enumerate(days)}
    sep_center = [i - 0.5 for i in range(1, n)
                  if (days[i].year, days[i].month) != (days[i - 1].year, days[i - 1].month)]
    tick_pos, tick_lab = [], []
    if n > MONTH_TICK_THRESHOLD:
        seen = set()
        for i, d in enumerate(days):
            key = (d.year, d.month)
            if key not in seen:
                seen.add(key)
                tick_pos.append(float(i))
                tick_lab.append(d.strftime("%y-%m"))
    else:
        for i, d in enumerate(days):
            if i == 0 or d.isocalendar()[1] != days[i - 1].isocalendar()[1]:
                tick_pos.append(float(i))
                tick_lab.append(d.strftime("%m-%d"))
    return Slots(df=df, day_span=day_span, sep_center=sep_center,
                 tick_pos=tick_pos, tick_lab=tick_lab, n_all=n)
```

- [ ] **Step 4: 跑测试确认通过 + 全量回归**

Run: `.venv/bin/pytest tests/test_daily_slots.py -q` → 5 passed
Run: `.venv/bin/pytest -q` → 全绿

- [ ] **Step 5: 提交**

```bash
git add src/quantchart/core/session.py tests/test_daily_slots.py
git commit -m "feat(core): build_daily_slots 日线槽位（非交易日压缩+月/周自适应刻度）"
```

---

### Task 3: 深色主题常量 + 6 类新原语

**Files:**
- Create: `src/quantchart/render/theme.py`
- Modify: `src/quantchart/render/primitives.py`（末尾追加 6 个函数；`_zone`/`_hline` 标签样式加默认值不变的可选参数）
- Test: `tests/test_daily_primitives.py`

**Interfaces:**
- Consumes: `Ctx`、`_xof`、`draw` 分发机制（primitives.py 既有）；`spec["type"]` 命名约定 `_函数名`
- Produces: 图层 spec 类型 `candle / trendline / arrow / tag / circle / text`（参数见实现）；`render/theme.DARK` 常量（`bg/grid/font/axis/label_bg/up/down/ma_palette`）；`_zone`/`_hline` 新可选键 `label_bgcolor/label_color/label_bordercolor`（缺省值与旧行为逐像素一致）

- [ ] **Step 1: 新建 `src/quantchart/render/theme.py`**

```python
"""深色主题常量：色值对照 reference/05 取样，集中一处校准；暂不进 YAML。"""

DARK = {
    "bg": "#0d1117",            # 图底（深蓝黑，同参考图）
    "grid": "#252c36",          # 网格
    "font": "#c9d1d9",          # 主字体
    "axis": "#5a6472",          # 轴线/刻度
    "label_bg": "#161d26",      # 带底色标注的底
    "up": "#e0524d",            # 阳线（红涨，目视校准后可调）
    "down": "#2fc4c4",          # 阴线（青跌）
    "ma_palette": ["#3aa3e3", "#c678dd", "#e5c07b", "#56b6c2", "#98c379"],
}
```

- [ ] **Step 2: 写失败测试 `tests/test_daily_primitives.py`**

```python
import pandas as pd
import plotly.graph_objects as go

from quantchart.render.primitives import Ctx, draw


def _ctx():
    df = pd.DataFrame({
        "pos": [0.0, 1.0, 2.0],
        "datetime": pd.to_datetime(["2026-08-25", "2026-08-26", "2026-08-27"]),
        "open": [1.0, 2.0, 3.0], "high": [2.0, 3.0, 4.0],
        "low": [0.5, 1.5, 2.5], "close": [1.5, 2.5, 3.5],
    })
    return Ctx(slots=None, df=df)


def test_candle_trace_and_colors():
    fig = go.Figure()
    draw(fig, {"type": "candle"}, _ctx())
    tr = fig.data[0]
    assert tr.type == "candlestick"
    assert tr.increasing.line.color == "#e0524d"
    assert tr.decreasing.line.color == "#2fc4c4"
    assert tr.showlegend is False


def test_trendline_line_and_label():
    fig = go.Figure()
    draw(fig, {"type": "trendline", "from": ["2026-08-25", 1.0], "to": ["2026-08-27", 3.0],
               "color": "#f1c40f", "dash": "dash", "label": "通道"}, _ctx())
    tr = fig.data[0]
    assert list(tr.x) == [0.0, 2.0] and list(tr.y) == [1.0, 3.0]
    assert tr.line.dash == "dash" and tr.showlegend is False
    assert fig.layout.annotations[0].text == "通道"


def test_arrow_data_coords():
    fig = go.Figure()
    draw(fig, {"type": "arrow", "from": ["2026-08-25", 1.0], "to": ["2026-08-25", 3.0],
               "color": "#e0312f", "text": "区间宽度"}, _ctx())
    ann = fig.layout.annotations[0]
    assert ann.showarrow is True and ann.arrowhead == 2
    assert ann.arrowcolor == "#e0312f" and ann.text == "区间宽度"
    assert ann.axref == "x" and ann.ayref == "y"     # 尾点=from，头点=to（数据坐标）
    assert ann.x == 0.0 and ann.ax == 0.0


def test_tag_right_edge_pill():
    fig = go.Figure()
    draw(fig, {"type": "tag", "value": 2.5, "text": "7560", "color": "#ff8c00"}, _ctx())
    ann = fig.layout.annotations[0]
    assert ann.xref == "paper" and ann.xanchor == "left"
    assert ann.y == 2.5 and ann.bgcolor == "#ff8c00"
    assert ann.showarrow is False


def test_circle_marker_with_label():
    fig = go.Figure()
    draw(fig, {"type": "circle", "at": ["2026-08-26", 2.5], "color": "#f1c40f", "label": "1"}, _ctx())
    tr = fig.data[0]
    assert tr.marker.symbol == "circle-open"
    assert tr.mode == "markers+text" and tr.text[0] == "1"


def test_text_annotation():
    fig = go.Figure()
    draw(fig, {"type": "text", "at": ["2026-08-25", 3.5], "text": "IM2612合约",
               "size": 16, "color": "#e0312f"}, _ctx())
    ann = fig.layout.annotations[0]
    assert ann.showarrow is False and ann.text == "IM2612合约"
    assert ann.font.size == 16 and ann.font.color == "#e0312f"


def test_hline_label_bgcolor_default_white():
    fig = go.Figure()
    draw(fig, {"type": "hline", "value": 2.0, "label": "支撑", "from": "2026-08-25",
               "to": "2026-08-27"}, _ctx())
    assert fig.layout.annotations[0].bgcolor == "white"     # 分钟路径行为不变


def test_zone_label_bgcolor_default_white():
    fig = go.Figure()
    draw(fig, {"type": "zone", "from": "2026-08-25", "to": "2026-08-27",
               "price": [1.0, 2.0], "label": "观察区"}, _ctx())
    assert fig.layout.annotations[0].bgcolor == "white"     # 分钟路径行为不变
```

- [ ] **Step 3: 跑测试确认失败**

Run: `.venv/bin/pytest tests/test_daily_primitives.py -q`
Expected: FAIL with `未知绘图原语: candle`

- [ ] **Step 4: 在 `primitives.py` 末尾追加 6 个原语**

```python
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
        increasing=dict(line=dict(color=spec.get("up", "#e0524d"), width=1)),
        decreasing=dict(line=dict(color=spec.get("down", "#2fc4c4"), width=1)),
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
    fig.add_annotation(x=tx, y=ty, ax=ax, ay=ay,
                       xref=ctx.xaxis, yref=yref, axref=ctx.xaxis, ayref=yref,
                       showarrow=True, arrowhead=spec.get("arrowhead", 2),
                       arrowsize=1.1, arrowwidth=spec.get("width", 1.6),
                       arrowcolor=spec.get("color", "#e0312f"),
                       standoff=spec.get("standoff", 3),
                       text=spec.get("text", ""),
                       textposition=spec.get("text_position") or "middle right",
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
```

- [ ] **Step 5: `_zone` / `_hline` 标签样式加默认值不变的可选参数**

`_zone` 的标签 annotation 改为：

```python
    if spec.get("label"):
        fig.add_annotation(x=(x0 + x1) / 2, y=plo, yref=ctx.yaxis,
                           text=spec["label"], showarrow=False,
                           yanchor="bottom", yshift=6,
                           font=dict(size=11, color=spec.get("label_color", "#3a3f46")),
                           bgcolor=spec.get("label_bgcolor", "white"),
                           bordercolor=spec.get("label_bordercolor", "#c4c9d0"),
                           borderpad=3, opacity=.92)
```

`_hline` 的标签 annotation 中 `font=…` 与 `bgcolor=…` 两处改为：

```python
                           font=dict(size=10.5, color=spec.get("label_color",
                                     spec.get("color", "#55595f"))),
                           bgcolor=spec.get("label_bgcolor", "white"), opacity=.9)
```

- [ ] **Step 6: 跑测试确认通过 + 全量回归（分钟路径像素行为不变的证据）**

Run: `.venv/bin/pytest tests/test_daily_primitives.py tests/test_primitives_basic.py tests/test_primitives_events.py tests/test_figure.py -q`
Expected: 全绿

- [ ] **Step 7: 提交**

```bash
git add src/quantchart/render/theme.py src/quantchart/render/primitives.py tests/test_daily_primitives.py
git commit -m "feat(render): 深色主题常量 + candle/trendline/arrow/tag/circle/text 六原语"
```

---

### Task 4: 深色主题组装 `figure_daily.py`

**Files:**
- Create: `src/quantchart/render/figure_daily.py`
- Test: `tests/test_daily_pipeline.py`（本任务先写 figure 断言部分，Task 6 补路由后跑通；本任务测试先以直接调 `build_daily_figure` 的方式落地）

**Interfaces:**
- Consumes: `Ctx`/`draw`（primitives）；`DARK`（theme）；`slots` 为 Task 2 产物；`rep` 为含 `.footnote()` 的质量报告
- Produces: `build_daily_figure(df, slots, panels, rep, title="") -> go.Figure`——仅接受**单面板**（多面板明确报错）；深底浅网格、右缘留白、标题/脚注 annotation

- [ ] **Step 1: 写失败测试（`tests/test_daily_pipeline.py` 先建文件，本任务只放这组）**

```python
import pandas as pd
import plotly.graph_objects as go
import pytest

from quantchart.adapters.common import DailyQualityReport
from quantchart.core.session import build_daily_slots
from quantchart.render.figure_daily import build_daily_figure


def _daily_df(n=10):
    idx = pd.bdate_range("2026-06-01", periods=n)
    return pd.DataFrame({"datetime": idx, "open": [7000 + i for i in range(n)],
                         "high": [7100 + i for i in range(n)],
                         "low": [6950 + i for i in range(n)],
                         "close": [7050 + i for i in range(n)], "volume": 100.0})


def _panels():
    return [{"title": "主图", "layers": [{"type": "candle"}]}]


def test_build_daily_figure_dark_single_panel():
    df = _daily_df()
    slots = build_daily_slots(df)
    fig = build_daily_figure(df, slots, _panels(),
                             DailyQualityReport("x", 10, 10), title="测试")
    assert fig.layout.paper_bgcolor == "#0d1117"
    assert fig.layout.xaxis.rangeslider.visible is False
    assert fig.layout.yaxis.range[0] < df["low"].min()      # 下留白
    texts = [a.text for a in fig.layout.annotations]
    assert any("测试" in t for t in texts)
    assert any("交易日10天" in t for t in texts)


def test_build_daily_figure_rejects_multi_panel():
    df = _daily_df(3)
    slots = build_daily_slots(df)
    with pytest.raises(ValueError, match="单面板"):
        build_daily_figure(df, slots, [{"layers": []}, {"layers": []}],
                           DailyQualityReport("x", 3, 3))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/test_daily_pipeline.py -q`
Expected: FAIL with `ModuleNotFoundError: quantchart.render.figure_daily`

- [ ] **Step 3: 新建 `src/quantchart/render/figure_daily.py`**

```python
"""日线深色主题图组装：单面板，样式对照 reference/05 校准（色值见 theme.DARK）。"""
import numpy as np
import plotly.graph_objects as go

from .primitives import Ctx, draw
from .theme import DARK


def build_daily_figure(df, slots, panels, rep, title: str = "") -> go.Figure:
    if len(panels) != 1:
        raise ValueError(f"日线模式暂仅支持单面板（收到 {len(panels)} 个）")
    fig = go.Figure()
    ctx = Ctx(slots=slots, df=df)
    for spec in panels[0].get("layers", []):
        draw(fig, spec, ctx)

    fig.update_layout(
        template="none", width=1600, height=900, autosize=False,
        paper_bgcolor=DARK["bg"], plot_bgcolor=DARK["bg"],
        font=dict(family="Microsoft YaHei, Arial", size=12, color=DARK["font"]),
        margin=dict(l=64, r=150, t=92, b=88),
        xaxis=dict(range=[-2, slots.n_all + 1.5],
                   tickvals=slots.tick_pos, ticktext=slots.tick_lab,
                   tickfont=dict(size=10, color=DARK["font"]),
                   showgrid=False, zeroline=False, linecolor=DARK["axis"],
                   rangeslider=dict(visible=False)),
        yaxis=dict(range=_daily_range(df), gridcolor=DARK["grid"], griddash="dot",
                   zeroline=False, linecolor=DARK["axis"]),
        legend=dict(orientation="h", x=.5, xanchor="center", y=1.01, yanchor="bottom",
                    font=dict(size=11, color=DARK["font"]), bgcolor="rgba(0,0,0,0)"),
    )
    fig.add_annotation(x=.006, y=1.06, xref="paper", yref="paper", showarrow=False,
                       text=f"<b>{title}</b>", font=dict(size=20, color=DARK["font"]),
                       xanchor="left")
    fig.add_annotation(x=.998, y=-.128, xref="paper", yref="paper", showarrow=False,
                       xanchor="right", font=dict(size=10, color="#7a8494"),
                       text=rep.footnote() + " 时间轴仅含交易日（周末与节假日压缩）。")
    return fig


def _daily_range(df):
    cols = [c for c in ("open", "high", "low", "close") if c in df]
    vals = np.concatenate([df[c].dropna().values for c in cols])
    lo, hi = float(vals.min()), float(vals.max())
    span = hi - lo or 1.0
    return lo - span * .06, hi + span * .22
```

（Y 轴上留白 20% 给右缘标签/预演箭头让位，下留白 6%；比例属主题常量级微调，Task 8 可调。）

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/pytest tests/test_daily_pipeline.py -q`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/quantchart/render/figure_daily.py tests/test_daily_pipeline.py
git commit -m "feat(render): figure_daily 深色单面板组装（右缘留白+日线脚注）"
```

---

### Task 5: 策略插件 `daily_candle`

**Files:**
- Create: `src/quantchart/plugins/daily_candle.py`
- Test: `tests/test_daily_plugin.py`

**Interfaces:**
- Consumes: `register_strategy`/`StrategyOutput`（core/plugins）；`DARK`（render/theme）
- Produces: 注册名 `"daily_candle"`；`run(df, slots, ma=[5,10,20,30,60], annotations=None, **params) -> StrategyOutput`——df 新增 `ma{n}` 列；panels=[{"title": "主图", "layers": [candle, line×N, *annotations翻译]}]；用户标注允许 type：`hline/zone/trendline/arrow/tag/circle/text`（line/candle 由插件内部生成，不开放给用户，避免引用不存在列的错误延迟到渲染期）

- [ ] **Step 1: 写失败测试 `tests/test_daily_plugin.py`**

```python
import pandas as pd
import pytest

from quantchart.core.plugins import get_strategy, load_plugins
from quantchart.render.theme import DARK


def _df():
    return pd.DataFrame({"close": [float(i) for i in range(1, 31)],
                         "datetime": pd.date_range("2026-06-01", periods=30)})


def test_ma_columns_computed():
    load_plugins()
    out = get_strategy("daily_candle")(_df(), None, ma=[5, 10])
    assert out.df["ma5"].iloc[-1] == pytest.approx(28.0)      # mean(26..30)
    assert out.df["ma10"].iloc[-1] == pytest.approx(25.5)     # mean(21..30)


def test_default_layers_candle_plus_mas():
    load_plugins()
    out = get_strategy("daily_candle")(_df(), None, ma=[5, 10])
    types = [l["type"] for l in out.panels[0]["layers"]]
    assert types == ["candle", "line", "line"]
    assert out.panels[0]["layers"][0]["up"] == DARK["up"]
    assert out.panels[0]["layers"][1]["col"] == "ma5"


def test_annotation_passthrough_in_order():
    load_plugins()
    ann = [{"type": "text", "at": ["2026-06-10", 25], "text": "标注"},
           {"type": "trendline", "from": ["2026-06-01", 1], "to": ["2026-06-30", 30]}]
    out = get_strategy("daily_candle")(_df(), None, ma=[5], annotations=ann)
    assert out.panels[0]["layers"][-2:] == ann


def test_hline_defaults_to_main_axis():
    # 分钟路径 _hline 缺省 axis=y2（贴水副轴）；日线单面板必须注入主轴 y
    load_plugins()
    out = get_strategy("daily_candle")(_df(), None,
                                       annotations=[{"type": "hline", "value": 20}])
    h = out.panels[0]["layers"][-1]
    assert h["type"] == "hline" and h["axis"] == "y"


def test_annotation_missing_type():
    load_plugins()
    with pytest.raises(ValueError, match=r"annotations\[0\]"):
        get_strategy("daily_candle")(_df(), None, annotations=[{"value": 1}])


def test_annotation_unknown_type():
    load_plugins()
    with pytest.raises(ValueError, match=r"annotations\[1\].type 非法"):
        get_strategy("daily_candle")(_df(), None,
                                     annotations=[{"type": "hline", "value": 1},
                                                  {"type": "magic", "x": 1}])


def test_ma_validation():
    load_plugins()
    with pytest.raises(ValueError, match="ma"):
        get_strategy("daily_candle")(_df(), None, ma=[0])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/test_daily_plugin.py -q`
Expected: FAIL with `KeyError: '未知策略: daily_candle'`

- [ ] **Step 3: 新建 `src/quantchart/plugins/daily_candle.py`**

```python
"""预设3：daily_candle —— 日线蜡烛同款复刻（深色）。只算不画，视觉交给通用原语。"""
from ..core.plugins import StrategyOutput, register_strategy
from ..render.theme import DARK

ANN_TYPES = {"hline", "zone", "trendline", "arrow", "tag", "circle", "text"}


@register_strategy("daily_candle")
def run(df, slots, ma=None, annotations=None, **params):
    ma = [int(n) for n in (ma or [5, 10, 20, 30, 60])]
    if any(n <= 0 for n in ma) or len(set(ma)) != len(ma):
        raise ValueError(f"ma 必须为正整数且不重复: {ma}")
    for n in ma:
        df[f"ma{n}"] = df["close"].rolling(n).mean()

    palette = DARK["ma_palette"]
    layers = [{"type": "candle", "name": "K线", "up": DARK["up"], "down": DARK["down"]}]
    layers += [{"type": "line", "col": f"ma{n}", "name": f"MA{n}",
                "color": palette[i % len(palette)], "width": 1.2}
               for i, n in enumerate(ma)]
    for k, ann in enumerate(annotations or []):
        if not isinstance(ann, dict) or "type" not in ann:
            raise ValueError(f"annotations[{k}] 必须是含 type 的映射"
                             f"（可用 type: {sorted(ANN_TYPES)}）")
        if ann["type"] not in ANN_TYPES:
            raise ValueError(f"annotations[{k}].type 非法: {ann['type']}"
                             f"（可用: {sorted(ANN_TYPES)}）")
        a = dict(ann)
        if a["type"] == "hline":
            a.setdefault("axis", "y")   # 分钟路径缺省 y2（贴水副轴），日线单面板注入主轴
        layers.append(a)
    return StrategyOutput(df=df, events=[], panels=[{"title": "主图", "layers": layers}])
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/pytest tests/test_daily_plugin.py -q`
Expected: 7 passed

- [ ] **Step 5: 提交**

```bash
git add src/quantchart/plugins/daily_candle.py tests/test_daily_plugin.py
git commit -m "feat(plugins): daily_candle 策略（均线计算+声明式标注翻译）"
```

---

### Task 6: 配置校验 + 日线管线旁路路由

**Files:**
- Modify: `src/quantchart/core/config.py`（`load_config` 内 mode 分支重组）
- Modify: `src/quantchart/core/pipeline.py`（路由 + `run_daily_pipeline`）
- Test: `tests/test_daily_pipeline.py`（追加）

**Interfaces:**
- Consumes: Task 1 `load_daily`、Task 2 `build_daily_slots`、Task 4 `build_daily_figure`、既有 `get_strategy/merge_panels/_wire_events`
- Produces: `run_daily_pipeline(cfg, title="") -> (fig, rep)`；`run_pipeline` 对 `mode` 以 `daily` 开头的配置自动转投日线管线；CLI `chartflow run` 无需改动（`rep.footnote()` 鸭子类型）

- [ ] **Step 1: 追加失败测试到 `tests/test_daily_pipeline.py`**

```python
import pytest

from quantchart.core.config import ConfigError, load_config
from quantchart.core.pipeline import run_pipeline

CFG_TMPL = """
input:
  mode: daily_csv
  csv: {csv}
  range: [2026-08-20, 2026-08-27]
strategy: daily_candle
params:
  ma: [5]
  annotations:
    - {{type: hline, value: 7100, color: "#ff5b5b", label: 压力}}
    - {{type: tag, value: 7157, text: "7157", color: "#ff8c00"}}
title: 测试日线端到端
"""


def _write_cfg(tmp_path, text):
    csv = tmp_path / "d.csv"
    rows = "".join(
        f"2026-08-{d:02d},{7000 + i},{7100 + i},{6950 + i},{7050 + i},100\n"
        for i, d in enumerate(range(20, 28)))
    csv.write_text("date,open,high,low,close,volume\n" + rows, encoding="utf-8")
    p = tmp_path / "c.yaml"
    p.write_text(text.format(csv=csv.as_posix()), encoding="utf-8")
    return str(p)


def test_e2e_daily_csv_builds_dark_candle_figure(tmp_path):
    fig, rep = run_pipeline(load_config(_write_cfg(tmp_path, CFG_TMPL)))
    assert any(t.type == "candlestick" for t in fig.data)
    assert fig.layout.paper_bgcolor == "#0d1117"
    assert len([t for t in fig.data if t.type == "scatter" and t.name == "MA5"]) == 1
    assert "交易日8天" in rep.footnote()


def test_daily_csv_without_csv_path():
    import yaml
    with pytest.raises(ConfigError, match="input.csv"):
        load_cfg_text("input: {mode: daily_csv, range: [2026-08-20, 2026-08-21]}")


def test_daily_api_without_symbol():
    with pytest.raises(ConfigError, match="input.api.symbol"):
        load_cfg_text("input: {mode: daily_api, range: [2026-08-20, 2026-08-21]}")


def test_daily_api_without_range():
    with pytest.raises(ConfigError, match="input.range"):
        load_cfg_text("input: {mode: daily_api, api: {symbol: IM0}}")


def load_cfg_text(text):
    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("strategy: daily_candle\n" + text)
    try:
        return load_config(path)
    finally:
        os.remove(path)


def test_trades_rejected_in_daily_mode(tmp_path):
    cfg = load_config(_write_cfg(tmp_path, CFG_TMPL))
    cfg["trades"] = [{"time": "2026-08-20", "action": "buy", "lots": 1}]
    with pytest.raises(ValueError, match="trades"):
        run_pipeline(cfg)


def test_extra_panels_rejected(tmp_path):
    cfg = load_config(_write_cfg(tmp_path, CFG_TMPL))
    cfg["extra_panels"] = [{"title": "副图", "layers": []}]
    with pytest.raises(ValueError, match="单面板"):
        run_pipeline(cfg)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/pytest tests/test_daily_pipeline.py -q`
Expected: 新增用例 FAIL（e2e 因 `run_pipeline` 尚无 daily 路由走分钟路径报缺 fut_close 列；校验用例因 config 未拦截而 FAIL）

- [ ] **Step 3: 修改 `config.py` 的 mode 校验（分钟分支语义不变）**

把 `mode = inp.get("mode", "excel")` 起的两段校验重组为：

```python
    mode = inp.get("mode", "excel")
    if isinstance(mode, str) and mode.startswith("daily"):
        if mode == "daily_csv" and not inp.get("csv"):
            raise ConfigError("input.mode=daily_csv 需要 input.csv（日线CSV路径）")
        if mode == "daily_api" and not (isinstance(inp.get("api"), dict)
                                        and inp["api"].get("symbol")):
            raise ConfigError("input.mode=daily_api 需要 input.api.symbol（如 IM0/CU0/TL0）")
        rng = inp.get("range")
        if not (isinstance(rng, list) and len(rng) == 2):
            raise ConfigError(f"input.mode={mode} 需要 input.range（起止日期，闭区间）")
    else:
        if mode in ("excel", "auto"):
            excel = inp.get("excel")
            for key in ("future", "index"):
                if not isinstance(excel, dict) or not excel.get(key):
                    raise ConfigError(
                        f"input.mode={mode} 需要 input.excel.future 与 input.excel.index "
                        f"两表路径（缺失: input.excel.{key}）")
        if mode in ("api", "auto"):
            api = inp.get("api")
            for key in ("future", "index"):
                if not isinstance(api, dict) or not api.get(key):
                    raise ConfigError(
                        f"input.mode={mode} 需要 input.api.future 与 input.api.index "
                        f"两个代码（缺失: input.api.{key}）")
            rng = inp.get("range")
            if not (isinstance(rng, list) and len(rng) == 2):
                raise ConfigError(f"input.mode={mode} 需要 input.range（起止日期，分钟深度校验用）")
```

- [ ] **Step 4: 修改 `pipeline.py`——路由与 `run_daily_pipeline`**

顶部 import 改为：

```python
from ..adapters.auto import auto_load
from ..adapters.daily import load_daily
from ..render.figure import build_figure
from ..render.figure_daily import build_daily_figure
from .plugins import get_strategy, load_plugins
from .position import expand_trades
from .session import build_daily_slots, build_slots
```

`run_pipeline` 开头插入路由（其余主体不动）：

```python
def run_pipeline(cfg: dict, title: str = "", row_heights: list | None = None) -> tuple:
    if str(cfg["input"].get("mode", "excel")).startswith("daily"):
        return run_daily_pipeline(cfg, title=title)
    df, rep = auto_load(cfg["input"])          # ← 原第一行，以下原样
    ...
```

文件末尾追加：

```python
def run_daily_pipeline(cfg: dict, title: str = "") -> tuple:
    """日线旁路：daily_* 通道 → 日线槽位 → 插件 → 深色主题组装（单面板）。"""
    if cfg.get("trades") or cfg.get("trades_csv"):
        raise ValueError("日线模式暂不支持 trades/trades_csv 交易明细（接口保留，日线口径后续适配）")
    df, rep = load_daily(cfg["input"])
    slots = build_daily_slots(df)
    load_plugins()
    out = get_strategy(cfg["strategy"])(slots.df, slots, **cfg.get("params", {}))
    panels = merge_panels(out.panels, cfg.get("panels"), cfg.get("extra_panels"))
    panels = [{**p, "layers": _wire_events(p.get("layers", []), out.events)}
              for p in panels]
    if not title:
        title = (f"{cfg['strategy']}（{cfg['input'].get('range', ['',''])[0]}"
                 f"–{cfg['input'].get('range', ['',''])[1]}）")
    fig = build_daily_figure(out.df, slots, panels, rep, title=title)
    return fig, rep
```

- [ ] **Step 5: 跑测试确认通过 + 全量回归**

Run: `.venv/bin/pytest tests/test_daily_pipeline.py -q` → 8 passed
Run: `.venv/bin/pytest -q` → 全绿（含既有分钟测试）

- [ ] **Step 6: 提交**

```bash
git add src/quantchart/core/config.py src/quantchart/core/pipeline.py tests/test_daily_pipeline.py
git commit -m "feat(core): 日线管线旁路路由+daily_*配置校验（trades 日线明确拒绝）"
```

---

### Task 7: 模板 `configs/daily_candle.yaml` + 取数脚本 `tools/fetch_daily.py`

**Files:**
- Create: `configs/daily_candle.yaml`
- Create: `tools/fetch_daily.py`
- Modify: `.gitignore`（追加 `data/`、`out/`）

**Interfaces:**
- Consumes: Task 6 全链路（YAML 校验 → daily_api → daily_candle）
- Produces: 一期样板配置（annotations 全要素对照 05 图，坐标目视近似、Task 8 校准）；取数脚本 `python tools/fetch_daily.py SYMBOL --start … --end … -o data/x.csv [--foreign]`

- [ ] **Step 1: `.gitignore` 追加**

```gitignore
data/
out/
```

- [ ] **Step 2: 新建 `configs/daily_candle.yaml`**

```yaml
input:
  mode: daily_api
  api: {symbol: IM0}
  range: [2026-06-01, 2026-08-28]
strategy: daily_candle
title: "IM2612 合约 · 日线策略同款复刻（样板）"
params:
  ma: [5, 10, 20, 30, 60]
  annotations:
    # —— 线形：白趋势线 + 黄虚线上升通道×2 + 压力线 ——
    - {type: trendline, from: ["2026-07-24", 6900], to: ["2026-08-21", 7560], color: "#dfe3ea", width: 1.3}
    - {type: trendline, from: ["2026-07-06", 6750], to: ["2026-08-28", 8250], color: "#f1c40f", dash: dash, width: 1.2}
    - {type: trendline, from: ["2026-06-30", 7050], to: ["2026-08-28", 8360], color: "#f1c40f", dash: dash, width: 1.2}
    - {type: hline, value: 7650, color: "#e5a50a", width: 1.1}
    # —— 区域：红实线框 + 红虚线框×2（深色底透明填充） ——
    - {type: zone, from: "2026-06-01", to: "2026-07-10", price: [7300, 8360], edgecolor: "#e0312f", fillcolor: "rgba(224,49,47,.06)", label: 筹码密集区, label_color: "#e0312f", label_bgcolor: "rgba(0,0,0,0)", label_bordercolor: "rgba(0,0,0,0)"}
    - {type: zone, from: "2026-08-03", to: "2026-08-07", price: [7350, 7500], edgecolor: "#e0312f", fillcolor: "rgba(0,0,0,0)", label: 左侧集合区间Ⅰ, label_color: "#e0312f", label_bgcolor: "rgba(0,0,0,0)", label_bordercolor: "rgba(0,0,0,0)"}
    - {type: zone, from: "2026-08-10", to: "2026-08-25", price: [7050, 7300], edgecolor: "#e0312f", fillcolor: "rgba(0,0,0,0)", label: 右侧集合区间Ⅱ, label_color: "#e0312f", label_bgcolor: "rgba(0,0,0,0)", label_bordercolor: "rgba(0,0,0,0)"}
    # —— 圆圈①②③④ ——
    - {type: circle, at: ["2026-08-13", 7620], color: "#f1c40f", label: "1"}
    - {type: circle, at: ["2026-08-17", 7640], color: "#f1c40f", label: "2"}
    - {type: circle, at: ["2026-08-27", 7690], color: "#f1c40f", label: "3"}
    - {type: circle, at: ["2026-08-28", 7560], color: "#f1c40f", label: "4"}
    # —— 引线：区间宽度箭头 + 走势预演分叉（BULL/BEAR/BASE） ——
    - {type: arrow, from: ["2026-07-16", 6600], to: ["2026-07-16", 7500], color: "#e0312f", width: 2.2, text: 区间宽度560点, text_color: "#e0312f", text_size: 12}
    - {type: arrow, from: ["2026-08-21", 6900], to: ["2026-08-21", 7100], color: "#e0312f", width: 2.2, text: 区间宽度540点, text_color: "#e0312f", text_size: 12}
    - {type: arrow, from: ["2026-08-28", 7500], to: ["2026-08-28", 7560], color: "#e0312f", text: BULL, text_color: "#e0312f", text_size: 13}
    - {type: arrow, from: ["2026-08-28", 7480], to: ["2026-08-27", 7380], color: "#39d353", text: BEAR, text_color: "#39d353", text_size: 13}
    - {type: arrow, from: ["2026-08-28", 7490], to: ["2026-08-28", 7530], color: "#f1c40f", text: BASE, text_color: "#f1c40f", text_size: 13}
    # —— 文字：品种大字 / 高低点价签 ——
    - {type: text, at: ["2026-07-15", 8150], text: "IM2612 合约", size: 17, color: "#e0312f"}
    - {type: text, at: ["2026-06-30", 8370], text: "8350.0 →", size: 10.5, color: "#dfe3ea"}
    - {type: text, at: ["2026-07-24", 6410], text: "6450.6 ↓", size: 10.5, color: "#39d353"}
    # —— 右缘药丸 ——
    - {type: tag, value: 7560, text: "7560", color: "#ff8c00"}
    - {type: tag, value: 8098.8, text: "8098.8", color: "#f8a5c2"}
    - {type: tag, value: 6450.9, text: "6450.9", color: "#d4b106"}
```

（标注时间/价格为参考图目视近似值；Task 8 依真实数据逐条校准。）

- [ ] **Step 3: 新建 `tools/fetch_daily.py`**

```python
"""取数工具：期货主连/单合约/外盘现货 日线 → CSV（核心库保持无网络依赖）。

用法:
  .venv/bin/python tools/fetch_daily.py IM0 --start 2026-06-01 --end 2026-08-28 -o data/IM0_daily.csv
  .venv/bin/python tools/fetch_daily.py XAU --start 2025-09-01 --end 2026-08-28 -o data/XAU_daily.csv --foreign
"""
import argparse


def _foreign(symbol, start, end, out):
    import pandas as pd
    import akshare as ak
    df = ak.futures_foreign_hist(symbol=symbol)
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= start) & (df["date"] <= end + " 23:59:59")]
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return len(df)


def _domestic_fallback(symbol, start, end, out):
    import pandas as pd
    import akshare as ak
    df = ak.futures_zh_daily_sina(symbol=symbol.lower())
    df = df[(df["date"] >= start) & (df["date"] <= end)]
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return len(df)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("symbol", help="代码：IM0/CU0/TL0（主连）或 XAU（外盘，配 --foreign）")
    ap.add_argument("--start", required=True, help="起始日 YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="结束日 YYYY-MM-DD")
    ap.add_argument("-o", "--output", required=True, help="输出CSV路径")
    ap.add_argument("--foreign", action="store_true", help="外盘现货（akshare futures_foreign_hist）")
    args = ap.parse_args()

    if args.foreign:
        n = _foreign(args.symbol, args.start, args.end, args.output)
    else:
        try:
            from local_datasource.providers.futures import query_futures
        except ImportError:
            n = _domestic_fallback(args.symbol, args.start, args.end, args.output)
        else:
            path, _summary = query_futures(symbol=args.symbol, period="daily",
                                           start_date=args.start, end_date=args.end,
                                           file_path=args.output)
            print(f"CSV -> {path}（local-datasource）")
            return
    print(f"CSV -> {args.output} rows={n}（akshare）")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 冒烟验证取数脚本（联网，可选但推荐）**

Run: `.venv/bin/python tools/fetch_daily.py IM0 --start 2026-06-01 --end 2026-08-28 -o data/IM0_daily.csv`
Expected: `CSV -> data/IM0_daily.csv（local-datasource）`，64 行

- [ ] **Step 5: 提交**

```bash
git add configs/daily_candle.yaml tools/fetch_daily.py .gitignore
git commit -m "feat(configs/tools): daily_candle 模板与日线取数脚本（主连local-ds/外盘akshare兜底）"
```

---

### Task 8: 端到端出图 + 目视校准 + 全量验收

**Files:**
- Modify: `src/quantchart/render/theme.py`（色值校准，如需）
- Modify: `configs/daily_candle.yaml`（标注坐标校准，如需）
- Test: 全量 `pytest -q`；产物 `out/daily_candle_IM.png|html`

**Interfaces:**
- Consumes: 前 7 个任务全部产物
- Produces: 与 `reference/05_IM2612合约.png` 目视对齐的成品图；一期验收结论（spec §7 四条）

- [ ] **Step 1: 全量测试**

Run: `.venv/bin/pytest -q`
Expected: 全绿（旧测试零改动零失败）

- [ ] **Step 2: 拉真数据出图**

Run: `.venv/bin/python tools/fetch_daily.py IM0 --start 2026-06-01 --end 2026-08-28 -o data/IM0_daily.csv`
Run: `.venv/bin/chartflow run configs/daily_candle.yaml -o out/daily_candle_IM.png --html out/daily_candle_IM.html`
Expected: 控制台末行脚注 `数据来源:local-datasource(IM0)；交易日64天。`

- [ ] **Step 3: 并排目视对比**

用 PIL 拼接 `out/daily_candle_IM.png` 与 `reference/05_IM2612合约.png` 左右对照并查看，逐项核对 spec §7 要素：深色蜡烛、5 均线、压力线、趋势线×2、三处矩形区、①②③④圆圈、区间宽度箭头×2、BULL/BEAR/BASE 预演、大字标注、高低点价签、右缘药丸×3。

- [ ] **Step 4: 校准迭代（≤3 轮）**

对照差异只允许动两处：`theme.py` 的色值（底色/涨跌色/色板/网格）与 YAML 的标注坐标/数值；每轮改完重跑 Step 2 出图复看。禁止为对齐观感在原语里加特判。

- [ ] **Step 5: 验收确认 + 提交**

```bash
.venv/bin/pytest -q
git add -A
git commit -m "feat: 一期收官——IM主连日线复刻 reference/05 同款（主题色值与标注坐标校准）"
```

---

## 完成定义（对照 spec §7）

1. `pytest -q` 全绿，旧测试零改动 ✅（Task 1–8 各步回归）
2. `chartflow run configs/daily_candle.yaml -o out/daily_candle_IM.png --html out/daily_candle_IM.html` 成功，脚注日线口径 ✅（Task 8）
3. 与 `reference/05` 并排目视要素齐备 ✅（Task 8 Step 3）
4. 换品种仅改 YAML ✅（机制由 Task 1–6 保证，Task 8 Step 4 的约束兜底）