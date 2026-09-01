import datetime as dtm
import numpy as np
import pandas as pd
import pytest
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

def _panels2(df_extra=None):
    slots, panels, rep = _frame()          # 既有夹具：单日、basis 列
    p2 = {"title": "仓位", "y_title": "仓位（手）", "range_cols": ["position_lots"],
          "layers": [{"type": "line", "col": "position_lots", "shape": "hv"}]}
    df = slots.df.copy()
    df["position_lots"] = 0.0
    df.loc[100:, "position_lots"] = 1.0
    return df, slots, panels + [p2], rep

def test_multi_panel_axes_and_rows():
    df, slots, panels, rep = _panels2()
    fig = build_figure(df, slots, panels, rep, title="T")
    assert fig.layout.xaxis2 is not None                 # 第二行存在
    assert fig.layout.xaxis.matches == "x2"              # 共享X（plotly 以主轴 matches 副轴实现）
    names = [t.name for t in fig.data]
    assert "position_lots" in names                       # 阶梯线已入图
    # 面板0 贴水 overlay：y2 被行2占用，overlay 重映射到 y3/y4
    assert fig.layout.yaxis3.overlaying == "y"
    # 非面板0 的 line 落到本面板轴（plotly 默认落主图 y，不显式指定则下面板空白）
    lots = [t for t in fig.data if t.name == "position_lots"][0]
    assert lots.yaxis == "y2"
    # 时间刻度画在最底面板（spec §2.1）：刻度配置在底轴且可见；
    # 顶轴被 shared_xaxes 隐藏刻度
    bottom = len(panels)
    bx = fig.layout[f"xaxis{bottom}"] if bottom > 1 else fig.layout.xaxis
    assert bx.showticklabels is not False                 # 底部轴刻度可见
    assert bx.tickvals is not None and len(list(bx.tickvals)) > 5
    assert fig.layout.xaxis.showticklabels is False       # 顶轴仍隐藏（不重复画刻度）

def test_multi_panel_leader_tag_on_own_panel():
    # 评审 Minor：_leader_tag 的 trace/标注须绑定所在面板轴（放 extra_panels 不落主图）
    df, slots, panels, rep = _panels2()
    from quantchart.core.signals import window_min_events
    evs = window_min_events(df, [("2026-08-19 11:30", "2026-08-19 15:00")], "fut_close")
    panels[1]["layers"] = panels[1]["layers"] + [
        {"type": "leader_tag", "ref": "window_min", "events": {"window_min": evs},
         "ref_value_col": "fut_close"}]
    fig = build_figure(df, slots, panels, rep, title="T")
    # leader_tag 每事件追加 2 个 trace（连线+圆点），均在面板2：全部绑定 y2，不落主图
    lt_traces = list(fig.data[-2 * len(evs):])
    assert len(lt_traces) == 2 * len(evs) > 0
    assert all(t.yaxis == "y2" for t in lt_traces)
    lt_anns = [a for a in fig.layout.annotations if a.yref == "y2"]
    assert len(lt_anns) >= 2 * len(evs)          # 价差标注与价格标签均绑定面板2

def test_multi_panel_panel0_default_axis_remap():
    # 评审 Minor：用户 panels 整体替换时，面板0 原语缺省 axis（area/hline 默认 y2）
    # 须重映射到本图贴水 overlay 轴（y3/y4），而非字面 y2（那是面板1 主轴）
    df, slots, panels, rep = _panels2()
    panels[0]["layers"] = panels[0]["layers"] + [{"type": "area", "col": "basis"}]
    fig = build_figure(df, slots, panels, rep, title="T")
    area_traces = [t for t in fig.data if t.fill == "tozeroy"]
    assert area_traces and all(t.yaxis == "y3" for t in area_traces)   # 落 overlay 轴而非 y2（面板1 主轴）

def test_single_panel_unchanged():
    slots, panels, rep = _frame()
    fig = build_figure(slots.df, slots, panels, rep, title="T")
    assert "xaxis2" not in fig.layout                     # 未生成第二面板轴
    assert fig.layout.yaxis2.overlaying == "y"            # 贴水 overlay 仍在 y2（MVP 原样）


def test_basis_axis_legacy_envelope_identical():
    # P2#4 回归：包络内（b0≥-15、b1≤400）刻度与范围保持历史值，既有图零变化
    slots, panels, rep = _frame()
    fig = build_figure(slots.df, slots, panels, rep, title="T")
    lay = fig.layout
    b0, b1 = float(slots.df["basis"].min()), float(slots.df["basis"].max())
    assert list(lay.yaxis2.tickvals) == [0] + list(np.arange(240, 400, 20))
    assert list(lay.yaxis2.range) == [-15.0, b1 + (b1 - b0) * .42]
    assert list(lay.yaxis3.tickvals) == list(np.arange(0, 5.51, .5))


def test_basis_axis_beyond_envelope_not_clipped():
    # P2#4 回归：贴水超出 400 → 刻度覆盖数据范围、上限不裁切（原硬编码 240–400 无刻度）
    slots, panels, rep = _frame()
    slots.df["basis"] = 650.0 - slots.df.index.to_series() * 0.5   # 530–650
    fig = build_figure(slots.df, slots, panels, rep, title="T")
    lay = fig.layout
    b0, b1 = float(slots.df["basis"].min()), float(slots.df["basis"].max())
    assert lay.yaxis2.range[1] >= b1
    tv = list(lay.yaxis2.tickvals)
    assert max(tv) >= b1 and min(tv) <= b0                # 刻度覆盖数据范围
    assert len(tv) <= 16                                   # 刻度数受控


def test_basis_axis_negative_floor_extends():
    # P2#4 回归：贴水 < -15 → 下限随数据下扩、刻度延伸到负区（原硬编码 -15 裁切）
    slots, panels, rep = _frame()
    slots.df["basis"] = -50.0 + slots.df.index.to_series() * 0.05   # -50..-38
    fig = build_figure(slots.df, slots, panels, rep, title="T")
    lay = fig.layout
    assert lay.yaxis2.range[0] <= -50.0
    assert min(lay.yaxis2.tickvals) <= -50.0


@pytest.mark.parametrize("b0,b1", [(-10.0, 100.0),    # leak 区：0.1*span=11 > b0+15=5
                                   (-14.0, 380.0),    # leak 区：41.4 > 1
                                   (20.0, 380.0),     # leak 区：36 > 35（贴着边界）
                                   (-15.0, 300.0),    # b0 恰在包络下边界
                                   (100.0, 300.0)])   # 非 leak 对照：0.1*span < b0+15
def test_basis_axis_envelope_floor_pinned_at_minus15(b0, b1):
    # P2#4 补漏回归：包络内（b0≥-15、b1≤400）下限一律钉死 -15——
    # 0.1*span > b0+15 的"leak 区"曾让 min(b0-10%span) 突破 -15，与
    # test_basis_axis_legacy_envelope_identical 钉死的"包络内逐值不变"矛盾
    # （该测试 fixture 的贴水在 300 附近，恰好不覆盖 leak 区）。
    slots, panels, rep = _frame()
    slots.df["basis"] = np.linspace(b0, b1, len(slots.df))
    fig = build_figure(slots.df, slots, panels, rep, title="T")
    lay = fig.layout
    byhi = b1 + (b1 - b0) * .42
    assert list(lay.yaxis2.range) == [-15.0, byhi]
    assert list(lay.yaxis2.tickvals) == [0] + list(np.arange(240, 400, 20))
    rf = 75.0   # fixture 无 idx_close → rate_factor 走缺省
    assert list(lay.yaxis3.range) == [-15.0 / rf, byhi / rf]
