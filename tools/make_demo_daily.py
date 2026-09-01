"""生成日线演示数据（合成、确定性种子）：examples/daily_volume_demo.csv。

供多面板+成交量子图的示例配置（configs/daily_volume_demo.yaml）与验收清单
（tests/acceptance_checks/daily_volume.py）使用——验收数值全部由清单按 df
动态重算，本脚本只负责产出形态合理（趋势+波动、量价配合）的确定性数据。
重跑本脚本可原样复现 CSV（种子固定）。
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260831
N = 60                                      # 60 个交易日
OUT = Path(__file__).resolve().parent.parent / "examples" / "daily_volume_demo.csv"


def main():
    rng = np.random.default_rng(SEED)
    idx = pd.bdate_range("2026-06-01", periods=N)
    drift = np.linspace(0, 180, N)           # 温和上行趋势
    noise = rng.normal(0, 25, N).cumsum()    # 随机波动
    close = 7000 + drift + noise - noise.mean()
    open_ = np.concatenate([[close[0] - 5], close[:-1]]) + rng.normal(0, 8, N)
    high = np.maximum(open_, close) + rng.uniform(5, 30, N)
    low = np.minimum(open_, close) - rng.uniform(5, 30, N)
    ret = np.abs(np.diff(close, prepend=close[0])) / close
    volume = np.round(2000 + ret * 4000 + rng.uniform(0, 800, N)).astype(int)
    df = pd.DataFrame({"date": idx.strftime("%Y-%m-%d"),
                       "open": np.round(open_, 1), "high": np.round(high, 1),
                       "low": np.round(low, 1), "close": np.round(close, 1),
                       "volume": volume})
    OUT.parent.mkdir(exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"写入 {OUT}（{N} 行，种子 {SEED}）")
    print(df.describe().loc[["min", "max"]])


if __name__ == "__main__":
    main()
