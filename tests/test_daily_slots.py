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
    slots = build_daily_slots(_daily(45))          # 6/1 起 45 个交易日：6月22天+7月23天
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


def test_empty_df_raises_chinese():
    import pytest
    with pytest.raises(ValueError, match="日线数据为空"):
        build_daily_slots(pd.DataFrame({"datetime": pd.Series([], dtype="datetime64[ns]")}))
def _intraday(days=2, bars=4):
    rows = []
    for d in pd.bdate_range("2026-06-01", periods=days):
        for i in range(bars):
            rows.append({"datetime": d + pd.Timedelta(hours=9, minutes=30 + 15 * i),
                         "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1})
    return pd.DataFrame(rows)


def test_intraday_day_span_seps_and_n():
    slots = build_daily_slots(_intraday())
    d0 = pd.Timestamp("2026-06-01").date()
    d1 = pd.Timestamp("2026-06-02").date()
    assert slots.n_all == 8
    assert slots.day_span[d0] == (0.0, 3.0)
    assert slots.day_span[d1] == (4.0, 7.0)
    assert slots.sep_center == [3.5]


def test_intraday_ticks_anchor_1030():
    slots = build_daily_slots(_intraday(days=3, bars=8))    # 09:30..10:45，含10:30
    assert slots.tick_lab == ["6.1 10:30", "6.2 10:30", "6.3 10:30"]


def test_intraday_tick_sampling_long():
    slots = build_daily_slots(_intraday(days=25))           # 4根/日无10:30 → 退回日首根纯日期
    assert len(slots.tick_lab) == 9          # ceil(25/12)=3 → 每3天打标
    assert slots.tick_lab[0] == "6.1"


def test_intraday_tick_anchor_configurable():
    slots = build_daily_slots(_intraday(days=3, bars=8), tick_anchor="10:00")
    assert slots.tick_lab == ["6.1 10:00", "6.2 10:00", "6.3 10:00"]
    slots2 = build_daily_slots(_intraday(days=3, bars=8), tick_anchor="12:00")
    assert slots2.tick_lab == ["6.1", "6.2", "6.3"]      # 该时刻缺失 → 退回日首根
