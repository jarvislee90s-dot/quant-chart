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


def test_non_coverage_error_keeps_excel_hint(monkeypatch, tmp_path):
    # 评审 Minor：非覆盖类异常原样上报，但须附"可改用 mode: excel"提示（spec §四）
    import sys, types
    pkgs = types.ModuleType("local_datasource"); pkgs.__path__ = []
    prov = types.ModuleType("local_datasource.providers"); prov.__path__ = []
    common = types.ModuleType("local_datasource.providers.common")
    class CoverageError(ValueError): pass
    common.CoverageError = CoverageError
    fut_m = types.ModuleType("local_datasource.providers.futures")
    def boom(**kw): raise ValueError("合约代码不存在: XXX")   # 非"补数"类异常
    fut_m.query_futures = boom
    idx_m = types.ModuleType("local_datasource.providers.index")
    idx_m.query_index = lambda **kw: ("x.csv", "ok")
    for k, v in {"local_datasource": pkgs, "local_datasource.providers": prov,
                 "local_datasource.providers.common": common,
                 "local_datasource.providers.futures": fut_m,
                 "local_datasource.providers.index": idx_m}.items():
        monkeypatch.setitem(sys.modules, k, v)
    cfg = {"mode": "auto", "api": {"future": "XXX", "index": "000852"}}
    with pytest.raises(ValueError) as e:
        auto_load(cfg)
    assert "合约代码不存在" in str(e.value)          # 原样上报
    assert "mode: excel" in str(e.value)              # 附改道提示