"""适配器共用：日网格对齐、前值填充、质量报告（excel_wind 与 local_ds 同源）。"""
from dataclasses import dataclass, field

import pandas as pd

from ..core.session import day_grid


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


def aligned(frame: pd.DataFrame, grid: list, prefix: str):
    """frame 含 dt 列 → 按 grid reindex + 前值填充，返回 (加前缀宽表, 填充数)。"""
    s = frame.set_index("dt").reindex(grid)
    filled = int(s["close"].isna().sum())
    out = s.ffill().add_prefix(f"{prefix}_")
    return out.reset_index(drop=True), filled


def align_pair(fut: pd.DataFrame, idx: pd.DataFrame, source: str):
    """两表（含 dt 列）→ 规范宽表 + 质量报告。"""
    days = sorted(set(fut["dt"].dt.date) & set(idx["dt"].dt.date))
    grid = [t for d in days for t in day_grid(d)]
    fa, ff = aligned(fut, grid, "fut")
    ia, fi = aligned(idx, grid, "idx")
    df = pd.concat([pd.Series(grid, name="datetime"), fa, ia], axis=1)
    return df, QualityReport(source, len(days), len(grid), ff, fi)


@dataclass
class DailyQualityReport:
    source: str
    days: int
    rows: int
    bpd: float = 1.0            # 每交易日根数（>1.5 即日内周期，脚注回显）
    notes: list = field(default_factory=list)   # 覆盖/无量等提示，附在脚注尾

    def footnote(self) -> str:
        s = f"数据来源:{self.source}；交易日{self.days}天"
        if self.bpd > 1.5:
            s += f"（每交易日约{self.bpd:.0f}根，日内周期）"
        s += "。"
        return s + "".join(f" {n}" for n in self.notes)