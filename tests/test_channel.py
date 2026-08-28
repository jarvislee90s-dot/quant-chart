import numpy as np
import pandas as pd
import pytest

from quantchart.core.channel import fit_channel


def _synth_df(n=200, slope=2.0, base=100.0):
    """已知参数的合成通道：中枢 slope*x+base；低点带中枢−50±10（谷值 −60）、高点带中枢+60±10（峰值 +70）。"""
    idx = pd.date_range("2026-06-01", periods=n, freq="B")
    x = np.arange(n, dtype=float)
    mid = slope * x + base
    lo = mid - 50 - 10 * np.abs(np.sin(2 * np.pi * x / 40))          # 低点带：谷值 mid-60
    hi = mid + 60 + 10 * np.abs(np.sin(2 * np.pi * x / 40))          # 高点带：峰值 mid+70（与低点谷同相位，几何对称）
    return pd.DataFrame({"datetime": idx, "pos": x, "open": mid, "high": hi,
                         "low": lo, "close": mid})


def test_fit_recovers_known_channel():
    df = _synth_df()
    fit = fit_channel(df, "2026-06-01", df["datetime"].iloc[-1])
    assert fit.slope == pytest.approx(2.0, abs=0.05)
    assert fit.slope_mid == pytest.approx(2.0, abs=0.05)
    assert fit.d_lo == pytest.approx(65.0, abs=3)      # 最深摆动低点 = 中枢−65（上下带±50/60使中枢抬5）
    assert fit.d_hi == pytest.approx(65.0, abs=3)      # 最高摆动高点 = 中枢+65
    assert fit.coverage == pytest.approx(1.0)


def test_fit_presses_deep_lows():
    df = _synth_df()
    df.loc[60, "low"] -= 30.0     # 制造两个深低点（再挖30点）
    df.loc[100, "low"] -= 30.0
    fit = fit_channel(df, "2026-06-01", df["datetime"].iloc[-1])
    # 两个深低点必须被下轨压住（低点在下轨之上，容差5点）
    for p in (60, 100):
        rail_at = fit.lower[0][1] + fit.slope * (p - fit.lower[0][0])
        assert df.loc[p, "low"] >= rail_at - 5.0


def test_fit_tilt_is_small():
    df = _synth_df()
    fit = fit_channel(df, "2026-06-01", df["datetime"].iloc[-1])
    assert abs(fit.slope - fit.slope_mid) <= 0.12 * abs(fit.slope_mid) + 1e-9


def test_empty_window_raises():
    df = _synth_df(5)
    with pytest.raises(ValueError, match="通道窗口内无数据"):
        fit_channel(df, "2030-01-01", "2030-02-01")