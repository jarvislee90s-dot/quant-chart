# tests/test_api_auto.py —— 全量替换为：
import sys, types
import pandas as pd
import pytest

from quantchart.adapters.auto import auto_load, NeedsExcelError


def _fake_with_gap(monkeypatch, tmp_path, cov_start="2026-08-25"):
    from tests.test_local_ds import _install_fake
    _install_fake(monkeypatch, tmp_path, cov_start=cov_start)


def test_api_mode_gap_raises_with_hint(monkeypatch, tmp_path):
    _fake_with_gap(monkeypatch, tmp_path)
    cfg = {"mode": "api", "api": {"future": "IM2612", "index": "000852"},
           "range": ["2026-08-17", "2026-08-27"]}
    with pytest.raises(NeedsExcelError) as e:
        auto_load(cfg)
    assert "2026-08-25" in str(e.value) and "补数" in str(e.value)


def test_auto_mode_falls_back_to_excel(monkeypatch, tmp_path):
    _fake_with_gap(monkeypatch, tmp_path)
    cfg = {"mode": "auto", "api": {"future": "IM2612", "index": "000852"},
           "excel": {"future": "tests/fixtures/fut.xlsx",
                     "index": "tests/fixtures/idx.xlsx"},
           "range": ["2026-08-17", "2026-08-27"]}
    df, rep = auto_load(cfg)
    assert "Excel" in rep.source and "2026-08-25" in rep.source   # 标注降级来源


def test_auto_mode_no_excel_hint(monkeypatch, tmp_path):
    _fake_with_gap(monkeypatch, tmp_path)
    cfg = {"mode": "auto", "api": {"future": "IM2612", "index": "000852"},
           "range": ["2026-08-17", "2026-08-27"]}
    with pytest.raises(NeedsExcelError) as e:
        auto_load(cfg)
    assert "input.excel" in str(e.value)


def test_auto_mode_api_ok(monkeypatch, tmp_path):
    from tests.test_local_ds import _install_fake
    _install_fake(monkeypatch, tmp_path)                      # 无 gap
    cfg = {"mode": "auto", "api": {"future": "IM2612", "index": "000852"},
           "range": ["2026-08-25", "2026-08-27"]}
    df, rep = auto_load(cfg)
    assert rep.source == "local-datasource"