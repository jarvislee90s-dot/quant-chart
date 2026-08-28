"""local-datasource 适配器：库直调 provider，CSV 读回（消费契约§1 v1.1，基线 98cd3bd）。

附加列（指数/个股 amount、期货日线 settle）忽略；粒度固定 1 分钟（freq="1"）。
"""
import importlib
import re
import tempfile
from pathlib import Path

import pandas as pd

from .common import align_pair


class LocalDsNotInstalled(RuntimeError):
    pass


class CoverageGap(RuntimeError):
    """对方 CoverageError 的本地镜像：start_date=数据覆盖起始日。"""
    def __init__(self, start_date: str, message: str):
        super().__init__(message)
        self.start_date = start_date


def _provider(mod: str, fn: str):
    try:
        m = importlib.import_module(f"local_datasource.providers.{mod}")
    except ImportError as e:
        raise LocalDsNotInstalled(
            "未安装 local-datasource（pip install -e E:/LLMproject/Github/local-datasource，"
            "联调基线 commit 98cd3bd），或改用 mode: excel") from e
    return getattr(m, fn)


def _fetch(module: str, fn: str, symbol: str, start, end, tmpdir: Path) -> pd.DataFrame:
    call = _provider(module, fn)
    out = tmpdir / f"{module}.csv"
    try:
        file_path, _summary = call(symbol=symbol, file_path=str(out), period="min",
                                   freq="1", start_date=start, end_date=end)
    except ValueError as e:                       # CoverageError 是 ValueError 子类（契约§4）
        msg = str(e)
        m = re.search(r"(\d{4}-\d{2}-\d{2})", msg)
        if "补数" in msg and m:
            raise CoverageGap(m.group(1), msg) from e
        raise
    df = pd.read_csv(file_path, encoding="utf-8-sig")
    df = df.rename(columns={"datetime": "dt"})
    df["dt"] = pd.to_datetime(df["dt"])
    keep = ["dt", "open", "high", "low", "close", "volume"]
    return df[keep + [c for c in ("hold", "amount") if c in df.columns]]


def load_via_local_ds(input_cfg: dict):
    api, rng = input_cfg["api"], input_cfg.get("range", [None, None])
    tmpdir = Path(tempfile.mkdtemp(prefix="quantchart_lds_"))
    fut = _fetch("futures", "query_futures", api["future"], rng[0], rng[1], tmpdir)
    idx = _fetch("index", "query_index", api["index"], rng[0], rng[1], tmpdir)
    return align_pair(fut, idx, source="local-datasource")