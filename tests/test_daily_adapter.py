import pandas as pd
import pytest

from quantchart.adapters.common import DailyQualityReport
from quantchart.adapters.daily import load_daily, load_daily_api, load_daily_csv

CN = """日期,开盘价,最高价,最低价,收盘价,成交量,持仓量
2026-08-25,7500,7560,7440,7520,100,1
2026-08-26,7510,7600,7480,7590,110,1
2026-08-27,7600,7700,7550,7680,120,1
"""
CN_PAD = """日期 ,开盘价 ,最高价 ,最低价 ,收盘价 ,成交量 ,持仓量
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


def test_csv_padded_cn_headers_stripped(tmp_path):
    df, rep = load_daily_csv(_write(tmp_path, CN_PAD, name="pad.csv"))
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

def test_csv_volume_optional(tmp_path):
    csv = _write(tmp_path, "date,open,high,low,close\n"
                            "2026-08-25,7500,7560,7440,7520\n"
                            "2026-08-26,7510,7600,7480,7590\n")
    df, rep = load_daily_csv(csv)
    assert "volume" not in df.columns
    assert "无量" in rep.footnote()


def test_csv_coverage_note_and_strict(tmp_path):
    csv = _write(tmp_path, CN)                     # 数据自 2026-08-25 始
    df, rep = load_daily_csv(csv, start="2026-08-01", end="2026-08-28")
    assert "数据自2026-08-25始" in rep.footnote()  # 默认：脚注明示，不静默截短
    with pytest.raises(ValueError, match="早于覆盖"):
        load_daily_csv(csv, start="2026-08-01", end="2026-08-28", strict_range=True)
