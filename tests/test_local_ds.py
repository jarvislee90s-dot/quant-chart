import sys, types
import pandas as pd
import pytest

from quantchart.adapters.local_ds import (
    CoverageGap, LocalDsNotInstalled, load_via_local_ds)

CFG = {"mode": "api", "api": {"future": "IM2612", "index": "000852"},
       "range": ["2026-08-25", "2026-08-27"]}

def _mkdtemp_csv(df, tmp_path, name):
    p = tmp_path / name
    df.to_csv(p, index=False, encoding="utf-8-sig")
    return str(p)

def _install_fake(monkeypatch, tmp_path, cov_start=None):
    """构造 fake local_datasource.providers.{futures,index,common}（契约§3/§4 形态）。"""
    pkgs = types.ModuleType("local_datasource"); pkgs.__path__ = []
    prov = types.ModuleType("local_datasource.providers"); prov.__path__ = []
    common = types.ModuleType("local_datasource.providers.common")
    class CoverageError(ValueError): pass
    common.CoverageError = CoverageError
    def _rows(kind):
        base = 7000.0 if kind == "future" else 7300.0
        ts = pd.date_range("2026-08-25 09:30", periods=242, freq="1min")
        d = pd.DataFrame({"datetime": ts.strftime("%Y-%m-%d %H:%M:%S"),
                          "open": base, "high": base, "low": base, "close": base,
                          "volume": 1.0, "amount": 1.0})
        return d
    def query_futures(symbol, file_path, kind="hist", period="daily", freq="1",
                      start_date=None, end_date=None, trade_date=None):
        if cov_start and start_date and start_date < cov_start:
            raise CoverageError(
                f"分钟数据仅覆盖 {cov_start} 至 2026-08-27(源: 新浪),"
                f"更早区间请从 Wind/终端导出 Excel 提供补数")
        return _mkdtemp_csv(_rows("future"), tmp_path, "fut.csv"), "ok"
    def query_index(symbol, file_path, period="daily", freq="1",
                    start_date=None, end_date=None):
        return _mkdtemp_csv(_rows("index"), tmp_path, "idx.csv"), "ok"
    fut_m = types.ModuleType("local_datasource.providers.futures")
    fut_m.query_futures = query_futures
    idx_m = types.ModuleType("local_datasource.providers.index")
    idx_m.query_index = query_index
    mods = {"local_datasource": pkgs, "local_datasource.providers": prov,
            "local_datasource.providers.common": common,
            "local_datasource.providers.futures": fut_m,
            "local_datasource.providers.index": idx_m}
    for k, v in mods.items():
        monkeypatch.setitem(sys.modules, k, v)

def test_load_via_local_ds_happy_path(monkeypatch, tmp_path):
    _install_fake(monkeypatch, tmp_path)
    df, rep = load_via_local_ds(CFG)
    assert rep.source == "local-datasource"
    assert list(df.columns[:2]) == ["datetime", "fut_open"]
    assert df["fut_close"].notna().all() and len(df) == 242
    assert str(df["datetime"].iloc[0]) == "2026-08-25 09:30:00"    # datetime 已解析

def test_coverage_gap_translated(monkeypatch, tmp_path):
    _install_fake(monkeypatch, tmp_path, cov_start="2026-08-25")
    with pytest.raises(CoverageGap) as e:
        load_via_local_ds({**CFG, "range": ["2026-08-17", "2026-08-27"]})
    assert e.value.start_date == "2026-08-25"
    assert "补数" in str(e.value)

def test_not_installed(monkeypatch):
    # None 哨兵强制 ImportError；须级联置 None 全部已缓存子模块——
    # 全量回归时 integration 测试会真装真库，子模块留存 sys.modules
    # 会让 import_module 直接命中缓存、绕过顶层哨兵
    for k in [k for k in sys.modules if k.startswith("local_datasource")]:
        monkeypatch.setitem(sys.modules, k, None)
    with pytest.raises(LocalDsNotInstalled) as e:
        load_via_local_ds(CFG)
    assert "mode: excel" in str(e.value)