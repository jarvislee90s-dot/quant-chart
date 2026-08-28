"""Wind 导出分钟表适配器：期货+指数两表 → 规范宽表 + 质量报告（对齐逻辑在 common）。"""
import pandas as pd

from .common import QualityReport, align_pair          # QualityReport re-export 兼容旧 import

REN = {"日期": "dt", "开盘价(元)": "open", "最高价(元)": "high", "最低价(元)": "low",
       "收盘价(元)": "close", "成交额(百万)": "amount", "成交量(股)": "volume"}
KEEP = ["dt", "open", "high", "low", "close", "amount", "volume"]


def _read_sheet(path: str) -> pd.DataFrame:
    try:
        raw = pd.read_excel(path, sheet_name=0)
    except Exception:                       # openpyxl 遇 Wind 非法页面设置
        raw = pd.read_excel(path, sheet_name=0, engine="calamine")
    raw = raw.rename(columns={str(k): v for k, v in REN.items()})
    raw["dt"] = pd.to_datetime(raw["dt"])
    return raw.dropna(subset=["dt", "close"])[KEEP]


def load_wind_pair(future_xlsx, index_xlsx, start=None, end=None):
    fut, idx = _read_sheet(future_xlsx), _read_sheet(index_xlsx)
    lo = pd.Timestamp(start) if start else None
    hi = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1) if end else None
    if lo is not None:
        fut, idx = fut[fut.dt >= lo], idx[idx.dt >= lo]
    if hi is not None:
        fut, idx = fut[fut.dt <= hi], idx[idx.dt <= hi]
    return align_pair(fut, idx, source="Wind Excel")