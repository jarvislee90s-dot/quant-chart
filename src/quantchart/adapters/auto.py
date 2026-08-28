"""输入编排：excel 主通道；api/auto 走 local-datasource（契约§1 v1.1 CSV 读回）。"""
import pandas as pd

from .excel_wind import load_wind_pair
from .local_ds import CoverageGap, LocalDsNotInstalled, load_via_local_ds


class NeedsExcelError(RuntimeError):
    pass


def auto_load(input_cfg: dict) -> tuple[pd.DataFrame, object]:
    mode = input_cfg.get("mode", "excel")
    if mode == "excel":
        return load_wind_pair(input_cfg["excel"]["future"], input_cfg["excel"]["index"],
                              *input_cfg.get("range", [None, None]))

    try:
        return load_via_local_ds(input_cfg)
    except LocalDsNotInstalled:
        raise
    except CoverageGap as e:
        hint = (f"分钟数据自 {e.start_date} 始，更早区间请从 Wind 导出 Excel 提供补数")
        if mode == "api":
            raise NeedsExcelError(f"{hint}（改用 mode: excel）")
        if input_cfg.get("excel"):
            df, rep = load_wind_pair(input_cfg["excel"]["future"],
                                     input_cfg["excel"]["index"],
                                     *input_cfg.get("range", [None, None]))
            rep.source = f"Wind Excel（API自{e.start_date}日始，已整体改用Excel）"
            return df, rep
        raise NeedsExcelError(f"{hint}（补 input.excel.future/index 两表后重跑）")