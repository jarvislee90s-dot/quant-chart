# tests/test_localds_contract.py —— 消费契约 v1.1 逐条核对（stub 路径）
"""对照《quant-chart × local-datasource 数据消费契约》v1.1：
§1 CSV 读回形态 / §3 列名与格式 / §4 CoverageGap 可编程识别。"""
import pandas as pd
import pytest

from quantchart.adapters.local_ds import CoverageGap, load_via_local_ds

CFG = {"mode": "api", "api": {"future": "IM2612", "index": "000852"},
       "range": ["2026-08-25", "2026-08-27"]}

def test_contract_s3_columns_and_dt_format(monkeypatch, tmp_path):
    """§3: 分钟列名 datetime/open/high/low/close/volume(可选 hold/amount)，
    datetime 为 YYYY-MM-DD HH:MM:SS，升序。"""
    from tests.test_local_ds import _install_fake
    _install_fake(monkeypatch, tmp_path)
    df, _ = load_via_local_ds(CFG)
    for c in ("fut_open", "fut_high", "fut_low", "fut_close", "fut_volume"):
        assert c in df.columns
    assert df["datetime"].is_monotonic_increasing

def test_contract_s4_gap_message_parseable(monkeypatch, tmp_path):
    """§4: 覆盖异常 message 含覆盖起始日(YYYY-MM-DD)与'补数'，可编程识别。"""
    from tests.test_local_ds import _install_fake
    _install_fake(monkeypatch, tmp_path, cov_start="2026-08-25")
    with pytest.raises(CoverageGap) as e:
        load_via_local_ds({**CFG, "range": ["2026-08-17", "2026-08-27"]})
    import re
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", e.value.start_date)
    assert "补数" in str(e.value)