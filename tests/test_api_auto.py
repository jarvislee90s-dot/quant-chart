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

def test_auto_requires_excel_without_network(monkeypatch):
    from quantchart.adapters import auto as A

    def _boom(sym):                        # auto 不应发起任何网络请求
        raise AssertionError("auto 模式不应发起网络请求")

    monkeypatch.setattr("quantchart.adapters.api_sina._http_get", _boom)
    try:
        A.auto_load({"mode": "auto", "api": {"future": "IM2612"},
                     "range": ["2026-08-19", "2026-08-26"]})
        assert False
    except A.NeedsExcelError as e:
        assert "Excel" in str(e)
