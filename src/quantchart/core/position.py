"""trades 交易明细 → 仓位列与执行事件（纯数据展开，不含任何策略逻辑）。"""
import numpy as np
import pandas as pd

from .signals import Event

VALID_ACTIONS = ("buy", "sell", "close")
ACTION_CN = {"buy": "买", "sell": "卖", "close": "平"}


def expand_trades(df: pd.DataFrame, trades: list[dict],
                  contract_mult: float = 200.0) -> tuple[pd.DataFrame, list[Event]]:
    """df 须为槽位表（含 datetime/pos/fut_close）。trades 按 time 升序执行。"""
    df = df.copy()
    pos = np.zeros(len(df))
    events, cur = [], 0.0
    for t in sorted(trades, key=lambda x: x["time"]):
        hit = df.index[df["datetime"] == pd.Timestamp(t["time"])]
        if len(hit) == 0:
            raise KeyError(f"时间点不在数据中: {t['time']}")
        i = hit[0]
        px = float(t["price"]) if t.get("price") is not None else float(df.at[i, "fut_close"])
        action = t["action"]
        if action == "close":
            step, n_txt = -cur, "all"
        else:
            step = float(t["lots"]) * (1.0 if action == "buy" else -1.0)
            n_txt = t["lots"]
        cur += step
        pos[i:] += step
        events.append(Event(pos=float(df.at[i, "pos"]), dt=df.at[i, "datetime"],
                            value=px, label=f"{ACTION_CN[action]}{n_txt}手@{px:.1f}",
                            kind=f"trade_exec:{action}", meta={"action": action}))
    df["position_lots"] = pos
    df["position_value"] = pos * contract_mult * df["fut_close"]
    return df, events