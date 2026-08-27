# tests/test_regression.py —— 对真实 Wind 数据断言已知结果（V1/V2 验证值）
import os

import pytest

DATA = os.environ.get("QUANT_CHART_TEST_DATA",
                      "E:/LLMproject/PersonalAffairs/Backset")
pytestmark = pytest.mark.skipif(
    not os.path.exists(f"{DATA}/IM2612.CFE原始.xlsx"),
    reason="真实Wind数据不可用（设 QUANT_CHART_TEST_DATA 指向 Backset）")

CFG = {
    "input": {"mode": "excel",
              "excel": {"future": f"{DATA}/IM2612.CFE原始.xlsx",
                        "index": f"{DATA}/000852.SH.xlsx"},
              "range": ["2026-08-17", "2026-08-27"]},
    "strategy": "basis_zones",
    "params": {"trigger": 250.0,
               "zones": [{"from": "2026-08-19 11:30", "to": "2026-08-21 11:00",
                          "price": [7200, 7300], "label": "Z1"},
                         {"from": "2026-08-24 11:30", "to": "2026-08-25 11:30",
                          "price": [7050, 7150], "label": "Z2"}]},
}

# Backset V1 已核验值
DAILY_MIN = [294.55, 314.29, 252.03, 251.70, 247.61, 263.73, 247.03, 252.85, 248.72]
WINDOW_DIFF = [250, 198, 263, 375, 384]      # 现价7479 − 窗口低点（容差1）

def _run():
    from quantchart.core.pipeline import run_pipeline
    return run_pipeline(CFG, title="regression")

def test_slots_and_quality():
    fig, rep = _run()
    assert rep.rows == 2178 and rep.days == 9

def test_daily_min_basis_series():
    fig, rep = _run()
    # 通过重算管线内部对比（pipeline 返回 fig；这里复算）
    from quantchart.adapters.auto import auto_load
    from quantchart.core.session import build_slots
    from quantchart.core.indicators import apply_indicators
    from quantchart.core.signals import daily_min_events
    df, _ = auto_load(CFG["input"])
    slots = build_slots(df)
    df = apply_indicators(slots.df, [{"name": "basis"}])
    got = [round(e.value, 2) for e in daily_min_events(df, slots, "basis")]
    assert all(abs(a - b) < 0.5 for a, b in zip(got, DAILY_MIN))

def test_render_smoke(tmp_path):
    fig, _ = _run()
    p = tmp_path / "reg.png"
    fig.write_image(str(p), width=1600, height=900)
    assert p.stat().st_size > 100_000
