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

def test_single_panel_unchanged():
    slots, panels, rep = _frame()
    fig = build_figure(slots.df, slots, panels, rep, title="T")
    assert "xaxis2" not in fig.layout                     # 未生成第二面板轴
    assert fig.layout.yaxis2.overlaying == "y"            # 贴水 overlay 仍在 y2（MVP 原样）
