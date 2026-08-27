"""输入编排：API 优先 → 覆盖不足则明确要求 Excel，绝不静默降级。"""
import datetime as dtm

import pandas as pd

from .excel_wind import QualityReport, load_wind_pair
from .api_sina import fetch_sina_minute


class NeedsExcelError(RuntimeError):
    pass


def _days_needed(start: str, end: str) -> set:
    d0, d1 = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    return {d0 + dtm.timedelta(days=i) for i in range((d1 - d0).days + 1)
            if (d0 + dtm.timedelta(days=i)).weekday() < 5}


def auto_load(input_cfg: dict) -> tuple[pd.DataFrame, QualityReport]:
    mode = input_cfg.get("mode", "excel")
    if mode == "excel":
        return load_wind_pair(input_cfg["excel"]["future"], input_cfg["excel"]["index"],
                              *input_cfg.get("range", [None, None]))
    if mode == "api":
        raise NeedsExcelError("API 模式暂只支持通过 auto 使用（需指数侧 Excel 对照）")
    # auto：期货用新浪，指数必须 Excel（免费源无指数分钟历史）
    fut = fetch_sina_minute(input_cfg["api"]["future"])
    have = set(fut["datetime"].dt.date)
    need = _days_needed(*input_cfg["range"]) if input_cfg.get("range") else have
    missing = sorted(need - have)
    if missing:
        raise NeedsExcelError(
            f"新浪分钟仅覆盖至 {max(have)}，缺少 {len(missing)} 个交易日"
            f"（自 {min(missing)} 起）。请改用 mode=excel 提供两份 Excel 表。")
    ex = input_cfg["excel"]
    df, rep = load_wind_pair(ex["future"], ex["index"], *input_cfg["range"])
    return df, rep
