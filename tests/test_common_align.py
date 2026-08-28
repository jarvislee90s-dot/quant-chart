import datetime as dtm
import pandas as pd
from quantchart.adapters.common import QualityReport, aligned, align_pair

def _frame(day, base):
    from quantchart.core.session import day_grid
    return pd.DataFrame({"dt": day_grid(day), "open": base, "high": base,
                         "low": base, "close": base + 1, "amount": 1.0, "volume": 2.0})

def test_aligned_counts_fill_and_prefix():
    f = _frame(dtm.date(2026, 8, 19), 7000.0).iloc[:-2]      # 缺最后2分钟
    grid = list(f["dt"]) + [f["dt"].iloc[-1] + pd.Timedelta(minutes=1),
                            f["dt"].iloc[-1] + pd.Timedelta(minutes=2)]
    out, filled = aligned(f, grid, "fut")
    assert filled == 2 and out["fut_close"].notna().all()

def test_align_pair_intersects_days_and_reports():
    d1, d2 = dtm.date(2026, 8, 19), dtm.date(2026, 8, 20)
    fut = pd.concat([_frame(d1, 7000.0), _frame(d2, 7000.0)], ignore_index=True)
    idx = _frame(d1, 7300.0)                                  # 指数只有一天
    df, rep = align_pair(fut, idx, source="test")
    assert rep.days == 1 and rep.rows == 242 and rep.source == "test"
    assert "fut_close" in df.columns and "idx_close" in df.columns