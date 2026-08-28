import os
import pandas as pd
import pytest

DATA = os.environ.get("QUANT_CHART_TEST_DATA",
                      "E:/LLMproject/PersonalAffairs/Backset")
pytestmark = pytest.mark.skipif(
    not os.path.exists(f"{DATA}/IM2612.CFE原始.xlsx"),
    reason="真实Wind数据不可用（设 QUANT_CHART_TEST_DATA 指向 Backset）")

def _cfg():
    from quantchart.core.config import load_config
    return load_config("configs/basis_zones_position.yaml")

def test_e2e_dual_panel_trades(tmp_path):
    from quantchart.core.pipeline import run_pipeline
    fig, rep = run_pipeline(_cfg())
    assert rep.rows == 2178
    assert fig.layout.xaxis2 is not None                    # 仓位面板存在
    g = lambda ts: pd.Timestamp(ts)
    from quantchart.core.position import expand_trades
    # 直接断言展开语义（渲染管线共用同一函数）
    from quantchart.adapters.auto import auto_load
    from quantchart.core.session import build_slots
    df, _ = auto_load(_cfg()["input"])
    slots = build_slots(df)
    from quantchart.core.indicators import apply_indicators
    df = apply_indicators(slots.df, [{"name": "vwap"}, {"name": "basis"}])
    out, evs = expand_trades(df, _cfg()["trades"], 200)
    i = out.index[out["datetime"] == g("2026-08-21 09:39")][0]
    assert out.loc[i - 1, "position_lots"] == 0 and out.loc[i, "position_lots"] == 1
    j = out.index[out["datetime"] == g("2026-08-25 09:46")][0]
    assert out.loc[j, "position_lots"] == 2
    k = out.index[out["datetime"] == g("2026-08-27 14:30")][0]
    assert out.loc[k, "position_lots"] == 0
    assert [e.kind for e in evs] == ["trade_exec:buy", "trade_exec:buy", "trade_exec:close"]

def test_e2e_render_png(tmp_path):
    from quantchart.core.pipeline import run_pipeline
    fig, _ = run_pipeline(_cfg())
    p = tmp_path / "p2.png"
    fig.write_image(str(p), width=1600, height=900)
    assert p.stat().st_size > 100_000