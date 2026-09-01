# 日线多面板/成交量子图边界自查：空数据、全 NaN、单根 K 线、量全零、跳日、列缺失、n≥3 布局
import sys
import types

import pandas as pd
import pytest

from quantchart.adapters.common import DailyQualityReport
from quantchart.adapters.daily import load_daily_api
from quantchart.core.session import build_daily_slots
from quantchart.render.figure_daily import build_daily_figure


def _df(rows, with_volume=True, vol_value=100.0, start="2026-06-01"):
    idx = pd.bdate_range(start, periods=len(rows))
    data = {"datetime": idx, "open": [r[0] for r in rows], "high": [r[1] for r in rows],
            "low": [r[2] for r in rows], "close": [r[3] for r in rows]}
    if with_volume:
        data["volume"] = [vol_value] * len(rows)
    return pd.DataFrame(data)


def _panels_vol():
    return [{"title": "主图", "layers": [{"type": "candle"}]},
            {"title": "成交量", "y_title": "成交量", "range_cols": ["volume"],
             "layers": [{"type": "volume", "col": "volume"}]}]


def _fig(df, panels=None, **kw):
    slots = build_daily_slots(df)
    return build_daily_figure(df, slots, panels or _panels_vol(),
                              DailyQualityReport("x", len(df), len(df)), **kw)


def test_empty_df_rejected_before_layout():
    # 空数据：槽位引擎先行报错，多面板路径不绕过该守卫
    with pytest.raises(ValueError, match="日线数据为空"):
        build_daily_slots(pd.DataFrame({"datetime": pd.Series([], dtype="datetime64[ns]"),
                                        "open": [], "high": [], "low": [], "close": []}))


def test_volume_panel_single_candle():
    # 单根 K 线：槽位/量柱/面板均不崩
    fig = _fig(_df([(1.0, 2.0, 0.5, 1.5)]))
    assert len([t for t in fig.data if t.type == "bar"]) == 1


def test_volume_all_zero_renders_flat():
    # 成交量全零：量柱零高度但成图不崩，量轴退化为 [0, 0.16]
    fig = _fig(_df([(1.0, 2.0, 0.5, 1.5), (2.0, 3.0, 1.5, 2.5)], vol_value=0.0))
    assert fig.layout.yaxis2.range == (0.0, pytest.approx(0.16))


def test_volume_all_nan_explicit_panel_no_crash():
    # 量全 NaN：原语省略（无量柱 trace），面板纵轴退化为 [0,1] 不崩
    fig = _fig(_df([(1.0, 2.0, 0.5, 1.5), (2.0, 3.0, 1.5, 2.5)], vol_value=float("nan")))
    assert len([t for t in fig.data if t.type == "bar"]) == 0
    assert tuple(fig.layout.yaxis2.range) == (0.0, 1.0)


def test_volume_column_absent_explicit_panel_no_crash():
    # 无量品种手写量面板：原语省略，range_cols 列缺失 → 纵轴退化 [0,1]
    fig = _fig(_df([(1.0, 2.0, 0.5, 1.5), (2.0, 3.0, 1.5, 2.5)], with_volume=False))
    assert tuple(fig.layout.yaxis2.range) == (0.0, 1.0)


def test_date_gap_bars_align_with_candles():
    # 跳日：pos 逐行连续压缩（06-01 与 06-03 相邻），量柱与 K 线逐柱同位
    df = pd.concat([_df([(1.0, 2.0, 0.5, 1.5)]),
                    _df([(3.0, 4.0, 2.5, 3.5)], start="2026-06-03")]).reset_index(drop=True)
    fig = _fig(df)
    bars = [t for t in fig.data if t.type == "bar"][0]
    candles = [t for t in fig.data if t.type == "candlestick"][0]
    assert list(bars.x) == list(candles.x) == [0.0, 1.0]


def test_three_panel_layout_ticks_and_heights():
    # n=3：中间面板刻度隐藏、底轴画刻度、第三行轴存在；row_heights 三行生效
    df = _df([(1.0, 2.0, 0.5, 1.5)] * 6)
    df["ma5"] = df["close"].rolling(5).mean()
    panels = _panels_vol() + [{"title": "MA5", "y_title": "MA5",
                               "layers": [{"type": "line", "col": "ma5", "name": "MA5"}]}]
    fig = _fig(df, panels, row_heights=[0.5, 0.25, 0.25])
    assert fig.layout.xaxis2.showticklabels is False       # 中间面板隐藏
    assert fig.layout.xaxis3.showticklabels is not False    # 底轴可见
    assert fig.layout.yaxis3 is not None                    # 第三行轴存在
    assert fig.layout.yaxis.domain[0] > 0.5                 # 主图 0.5 占比 → 域底高于 0.72 默认


def test_zero_floor_panel_key():
    # 面板显式 zero_floor: true：纵轴下限锁 0（对任意 col 图层生效）
    df = _df([(1.0, 2.0, 0.5, 1.5)] * 4)
    df["ma5"] = df["close"].rolling(2).mean()
    panels = [{"title": "主图", "layers": [{"type": "candle"}]},
              {"title": "MA5", "zero_floor": True, "layers": [
                  {"type": "line", "col": "ma5", "name": "MA5"}]}]
    fig = _fig(df, panels)
    assert fig.layout.yaxis2.range[0] == 0.0


CN = """日期,开盘价,最高价,最低价,收盘价,成交量,持仓量
2026-08-25,7500,7560,7440,7520,100,1
2026-08-26,7510,7600,7480,7590,110,1
2026-08-27,7600,7700,7550,7680,120,1
"""


def test_api_success_with_injected_fake(monkeypatch, tmp_path):
    """上轮存疑项收尾：不依赖真包——向 sys.modules 注入假 local_datasource，
    验证 load_daily_api 成功路径（与 integration_localds 标记的 test_api_success 同逻辑）。"""
    pkg = types.ModuleType("local_datasource")
    providers = types.ModuleType("local_datasource.providers")
    futures = types.ModuleType("local_datasource.providers.futures")

    def fake_query(symbol, period, start_date, end_date, file_path):
        assert symbol == "IM0" and period == "daily"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(CN)
        return file_path, "ok"

    futures.query_futures = fake_query
    providers.futures = futures
    pkg.providers = providers
    for name, mod in (("local_datasource", pkg),
                      ("local_datasource.providers", providers),
                      ("local_datasource.providers.futures", futures)):
        monkeypatch.setitem(sys.modules, name, mod)
    df, rep = load_daily_api("IM0", "2026-08-25", "2026-08-27")
    assert len(df) == 3 and "local-datasource(IM0)" in rep.footnote()


def test_visibility_guard_catches_subpanel_arrow_tail():
    # 副图（axref='x2'）箭尾超界也要进脚注警告——原守卫仅查 axref=='x'，箭尾漏检
    panels = [{"title": "主图", "layers": [{"type": "candle"}]},
              {"title": "副图", "layers": [{"type": "arrow", "from": [50.0, 1.0],
                                            "to": [5.0, 2.0], "color": "#ffffff"}]}]
    fig = _fig(_df([(1.0, 2.0, 0.5, 1.5)] * 10), panels)
    texts = " ".join(a.text or "" for a in fig.layout.annotations)
    assert "可见性警告" in texts
    assert "尾@50.0" in texts                      # 明确捕获越界箭尾


def test_undetermined_panel_range_note():
    # range_cols 指向缺失列：纵轴退化 [0,1] 不崩（既有语义），且脚注回显防呆提示不再静默
    fig = _fig(_df([(1.0, 2.0, 0.5, 1.5)] * 3, with_volume=False), _panels_vol())
    texts = " ".join(a.text or "" for a in fig.layout.annotations)
    assert tuple(fig.layout.yaxis2.range) == (0.0, 1.0)
    assert "无法确定 y 范围" in texts
    assert "zero_floor" in texts                       # 提示给排查方向
