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
def test_build_daily_figure_forecast_room():
    df = _daily_df(10)                          # 日线：bars_per_day=1 → 右界 = 10+2+1.5
    slots = build_daily_slots(df)
    fig = build_daily_figure(df, slots, _panels(), DailyQualityReport("x", 10, 10))
    assert fig.layout.xaxis.range[1] == pytest.approx(10 + 2 * 1 + 1.5)
    # 日内：16根/日×5日 → 右界 = 80 + 2×16 + 1.5
    idx = []
    for d in pd.bdate_range("2026-06-01", periods=5):
        for i in range(16):
            idx.append(d + pd.Timedelta(hours=9, minutes=30 + 15 * i))
    dfi = pd.DataFrame({"datetime": idx, "open": 7000.0, "high": 7100.0,
                        "low": 6950.0, "close": 7050.0, "volume": 1.0})
    slots_i = build_daily_slots(dfi)
    fig_i = build_daily_figure(dfi, slots_i, _panels(), DailyQualityReport("x", 5, 80))
    assert fig_i.layout.xaxis.range[1] == pytest.approx(80 + 2 * 16 + 1.5)


def test_granularity_mismatch_raises(tmp_path):
    cfg = load_config(_write_cfg(tmp_path, CFG_TMPL.replace("  mode: daily_csv", "  mode: daily_csv\n  granularity: 15min")))
    with pytest.raises(ValueError, match="周期校验失败"):
        run_pipeline(cfg)


def test_granularity_auto_and_pos_note_in_footnote(tmp_path):
    text = CFG_TMPL.replace(
        '    - {{type: tag, value: 7157, text: "7157", color: "#ff8c00"}}',
        '    - {{type: tag, value: 7157, text: "7157", color: "#ff8c00"}}\n'
        '    - {{type: text, at: [3.0, 7100], text: "pos标注"}}')
    fig, rep = run_pipeline(load_config(_write_cfg(tmp_path, text)))
    texts = [a.text for a in fig.layout.annotations]
    assert any("周期自动推断" in t for t in texts)
    assert any("pos锚点" in t for t in texts)


def test_config_granularity_invalid():
    with pytest.raises(ConfigError, match="input.granularity"):
        load_cfg_text("input: {mode: daily_csv, csv: x.csv, range: [2026-08-20, 2026-08-21], granularity: 5min}")


def test_config_tick_anchor_invalid():
    with pytest.raises(ConfigError, match="tick_anchor"):
        load_cfg_text("input: {mode: daily_csv, csv: x.csv, range: [2026-08-20, 2026-08-21], tick_anchor: ten}")


def test_config_strict_range_non_bool():
    with pytest.raises(ConfigError, match="strict_range"):
        load_cfg_text("input: {mode: daily_csv, csv: x.csv, range: [2026-08-20, 2026-08-21], strict_range: yes-please}")
