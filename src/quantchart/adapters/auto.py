"""输入编排：Excel 为主通道；auto（API优先降级拼装）属二期，绝不静默降级。"""
import pandas as pd

from .excel_wind import QualityReport, load_wind_pair


class NeedsExcelError(RuntimeError):
    pass


def auto_load(input_cfg: dict) -> tuple[pd.DataFrame, QualityReport]:
    mode = input_cfg.get("mode", "excel")
    if mode == "excel":
        return load_wind_pair(input_cfg["excel"]["future"], input_cfg["excel"]["index"],
                              *input_cfg.get("range", [None, None]))
    if mode == "api":
        raise NeedsExcelError("API 模式暂只支持通过 auto 使用（需指数侧 Excel 对照）")
    # auto：规划为“新浪期货分钟 + Excel 指数”拼装，属二期。免费源无指数分钟历史，
    # 本期直接明确要求 Excel，不发起无意义的网络请求，也绝不静默降级。
    raise NeedsExcelError(
        "auto 模式（API优先降级）属二期，本期请改用 mode=excel 提供两份 Excel 表。")
