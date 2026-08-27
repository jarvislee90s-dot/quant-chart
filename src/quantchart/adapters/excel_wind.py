"""Wind 导出分钟表适配器：期货+指数两表 → 规范宽表 + 质量报告。"""
from dataclasses import dataclass

import pandas as pd

from ..core.session import day_grid

REN = {"日期": "dt", "开盘价(元)": "open", "最高价(元)": "high", "最低价(元)": "low",
       "收盘价(元)": "close", "成交额(百万)": "amount", "成交量(股)": "volume"}
KEEP = ["dt", "open", "high", "low", "close", "amount", "volume"]


@dataclass
class QualityReport:
    source: str
    days: int
    rows: int
    filled_future: int
    filled_index: int

    def footnote(self) -> str:
        return (f"数据来源:{self.source}；交易日{self.days}天/分钟槽位{self.rows}个，"
                f"期货前值填充{self.filled_future}分钟，指数前值填充{self.filled_index}分钟。")


def _read_sheet(path: str) -> pd.DataFrame:
    try:
        raw = pd.read_excel(path, sheet_name=0)
    except Exception:                       # openpyxl 遇 Wind 非法页面设置
        raw = pd.read_excel(path, sheet_name=0, engine="calamine")
    raw = raw.rename(columns={str(k): v for k, v in REN.items()})
    raw["dt"] = pd.to_datetime(raw["dt"])
    return raw.dropna(subset=["dt", "close"])[KEEP]


def _aligned(frame: pd.DataFrame, grid: list, prefix: str):
    s = frame.set_index("dt").reindex(grid)
    filled = int(s["close"].isna().sum())
    out = s.ffill().add_prefix(f"{prefix}_")
    return out.reset_index(drop=True), filled


def load_wind_pair(future_xlsx: str, index_xlsx: str,
                   start: str | None = None, end: str | None = None
                   ) -> tuple[pd.DataFrame, QualityReport]:
    fut, idx = _read_sheet(future_xlsx), _read_sheet(index_xlsx)
    lo = pd.Timestamp(start) if start else None
    hi = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1) if end else None
    if lo is not None:
        fut, idx = fut[fut.dt >= lo], idx[idx.dt >= lo]
    if hi is not None:
        fut, idx = fut[fut.dt <= hi], idx[idx.dt <= hi]
    days = sorted(set(fut["dt"].dt.date) & set(idx["dt"].dt.date))
    grid = [t for d in days for t in day_grid(d)]
    fa, ff = _aligned(fut, grid, "fut")
    ia, fi = _aligned(idx, grid, "idx")
    df = pd.concat([pd.Series(grid, name="datetime"), fa, ia], axis=1)
    return df, QualityReport("Wind Excel", len(days), len(grid), ff, fi)
