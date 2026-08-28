"""日线/日内条形数据通道：daily_csv（通用CSV）/ daily_api（local-datasource 期货日线）→ 规范宽表。

宽表列规范：datetime + open/high/low/close（volume 可选——无量品种如伦敦金现货自动省略）。
中文表头自动映射。核心库无网络依赖：daily_api 库直调 local-datasource provider（锁定基线 d106144）。
"""
import tempfile
from pathlib import Path

import pandas as pd

from .common import DailyQualityReport
from .local_ds import LocalDsNotInstalled

CN_REN = {"日期": "datetime", "开盘价": "open", "最高价": "high",
          "最低价": "low", "收盘价": "close", "成交量": "volume"}
REQUIRED = ["datetime", "open", "high", "low", "close"]


def _normalize(raw: pd.DataFrame, start, end, source: str, strict_range: bool = False):
    df = raw.rename(columns=lambda c: str(c).strip())
    df = df.rename(columns=CN_REN)
    if "date" in df.columns:
        df = df.rename(columns={"date": "datetime"})
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"{source} 缺少必需列: {missing}"
                         f"（需含 datetime/date 与 open/high/low/close；volume 可选，无量品种可省略）")
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.dropna(subset=["datetime", "close"]).sort_values("datetime")
    if df["datetime"].duplicated().any():
        raise ValueError(f"{source} 存在重复日期，请检查数据")

    # 覆盖校验：请求起点早于数据实际覆盖时，不得静默截短——脚注明示（strict 时直接报错）
    notes = []
    lo = pd.Timestamp(start) if start else None
    hi = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1) if end else None
    if lo is not None and not df.empty and df["datetime"].iloc[0] > lo + pd.Timedelta(days=1):
        note = (f"数据自{df['datetime'].iloc[0]:%Y-%m-%d}始，"
                f"请求起点{lo:%Y-%m-%d}早于覆盖——早于部分未画出")
        if strict_range:
            raise ValueError(f"{source} {note}（input.strict_range=true）")
        notes.append(note)
    if lo is not None:
        df = df[df["datetime"] >= lo]
    if hi is not None:
        df = df[df["datetime"] <= hi]
    if df.empty:
        raise ValueError(f"{source} 在区间 [{start}, {end}] 内无数据")
    if "volume" not in df.columns:
        df["volume"] = float("nan")
        notes.append("无量（volume 缺失，量相关图层自动省略）")
    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    days = int(df["datetime"].dt.date.nunique())
    bpd = round(len(df) / max(1, days), 1)
    rep = DailyQualityReport(source=source, days=days, rows=len(df), bpd=bpd, notes=notes)
    keep = REQUIRED + (["volume"] if df["volume"].notna().any() else [])
    return df[keep], rep


def load_daily_csv(path: str, start=None, end=None, strict_range: bool = False):
    try:
        raw = pd.read_csv(path, encoding="utf-8-sig")
    except FileNotFoundError as e:
        raise FileNotFoundError(f"日线CSV不存在: {path}") from e
    return _normalize(raw, start, end, source=f"条形CSV({Path(path).name})",
                      strict_range=strict_range)


def load_daily_api(symbol: str, start=None, end=None, strict_range: bool = False):
    try:
        from local_datasource.providers import futures as fut
    except ImportError as e:
        raise LocalDsNotInstalled(
            "未安装 local-datasource（pip install -e <local-datasource 仓库路径>，"
            "联调基线 commit d106144），或改用 mode: daily_csv") from e
    out = Path(tempfile.mkdtemp(prefix="quantchart_daily_")) / "daily.csv"
    kwargs = {"symbol": symbol, "period": "daily", "file_path": str(out)}
    if start:
        kwargs["start_date"] = str(start)
    if end:
        kwargs["end_date"] = str(end)
    try:
        file_path, _summary = fut.query_futures(**kwargs)
    except ValueError:
        raise                       # 覆盖不足/代码不存在：对方已附指引，原样上报
    raw = pd.read_csv(file_path, encoding="utf-8-sig")
    return _normalize(raw, start, end, source=f"local-datasource({symbol})",
                      strict_range=strict_range)


def load_daily(input_cfg: dict):
    mode = input_cfg.get("mode", "daily_csv")
    start, end = input_cfg.get("range", [None, None])
    strict = bool(input_cfg.get("strict_range", False))
    if mode == "daily_csv":
        return load_daily_csv(input_cfg["csv"], start, end, strict)
    if mode == "daily_api":
        return load_daily_api(input_cfg["api"]["symbol"], start, end, strict)
    raise ValueError(f"未知日线模式: {mode}（可用: daily_csv / daily_api）")