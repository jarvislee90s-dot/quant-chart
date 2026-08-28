import datetime as dtm
import pandas as pd
import pytest
from quantchart.core.session import build_slots, day_grid
from quantchart.core.position import expand_trades

def _df():
    d = dtm.date(2026, 8, 21)
    rows = [{"datetime": t, "fut_close": 7000.0 + i}
            for i, t in enumerate(day_grid(d))]
    return build_slots(pd.DataFrame(rows)).df

def test_buy_close_lifecycle():
    df = _df()
    trades = [
        {"time": "2026-08-21 09:39", "action": "buy", "lots": 1, "price": 7104.4},
        {"time": "2026-08-21 10:00", "action": "buy", "lots": 2},          # price 缺省
        {"time": "2026-08-21 14:00", "action": "close", "lots": "all"},
    ]
    out, evs = expand_trades(df, trades, contract_mult=200.0)
    g = lambda hhmm: out.index[out["datetime"] == pd.Timestamp(f"2026-08-21 {hhmm}")][0]
    assert out.loc[g("09:38"), "position_lots"] == 0
    assert out.loc[g("09:39"), "position_lots"] == 1
    assert out.loc[g("10:00"), "position_lots"] == 3
    assert out.loc[g("14:00"), "position_lots"] == 0
    assert out["position_value"].iloc[g("10:00")] == 3 * 200 * out["fut_close"].iloc[g("10:00")]
    assert [e.kind for e in evs] == ["trade_exec:buy", "trade_exec:buy", "trade_exec:close"]
    assert evs[0].meta == {"action": "buy"} and evs[0].value == 7104.4
    assert evs[1].value == out["fut_close"].iloc[g("10:00")]     # 缺省价
    assert "买1手@7104.4" == evs[0].label

def test_sell_allows_negative():
    df = _df()
    out, evs = expand_trades(df, [{"time": "2026-08-21 13:05", "action": "sell", "lots": 3}])
    assert out["position_lots"].iloc[-1] == -3

def test_time_not_in_data_raises():
    df = _df()
    with pytest.raises(KeyError):
        expand_trades(df, [{"time": "2026-08-22 09:30", "action": "buy", "lots": 1}])  # 周六

def test_trades_sorted_by_time():
    df = _df()
    out, evs = expand_trades(df, [
        {"time": "2026-08-21 14:00", "action": "close", "lots": "all"},
        {"time": "2026-08-21 09:39", "action": "buy", "lots": 1},
    ])
    assert out["position_lots"].iloc[-1] == 0 and out["position_lots"].iloc[10] == 1