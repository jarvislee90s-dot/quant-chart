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
