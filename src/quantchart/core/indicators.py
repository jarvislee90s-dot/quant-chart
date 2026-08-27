"""指标注册表：纯函数 df→df（加列），YAML 按名引用、可链式。"""
import pandas as pd

REGISTRY: dict = {}


def register_indicator(name: str):
    def deco(fn):
        REGISTRY[name] = fn
        return fn
    return deco


def apply_indicators(df: pd.DataFrame, specs: list[dict]) -> pd.DataFrame:
    for spec in specs:
        name = spec.get("name")
        if name not in REGISTRY:
            raise KeyError(f"未知指标: {name}（可用: {sorted(REGISTRY)}）")
        df = REGISTRY[name](df, **spec.get("params", {}))
    return df


@register_indicator("basis")
def basis(df, future="fut_close", index="idx_close", out="basis"):
    df = df.copy()
    df[out] = df[index] - df[future]
    return df


@register_indicator("basis_rate")
def basis_rate(df, basis_col="basis", index="idx_close", out="basis_rate"):
    df = df.copy()
    df[out] = df[basis_col] / df[index] * 100
    return df


@register_indicator("vwap")
def vwap(df, price="fut_close", volume="fut_volume", amount="fut_amount",
         contract_mult=200.0, out="fut_vwap"):
    """当日累计成交额÷累计成交量；无成交额列时退化为价格加权（API 数据）。"""
    df = df.copy()
    if amount in df.columns:
        amt = df[amount] * 1e6
    else:
        amt = df[price] * df[volume] * contract_mult
    vol = df[volume].fillna(0) * contract_mult
    day = df["datetime"].dt.date
    cum_a = amt.groupby(day).cumsum()
    cum_v = vol.where(vol > 0).groupby(day).cumsum()   # 零成交分钟记 NaN（保持float64），前值填充
    df[out] = (cum_a / cum_v).ffill()
    return df
