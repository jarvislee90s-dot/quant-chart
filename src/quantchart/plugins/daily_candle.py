"""预设3：daily_candle —— 日线蜡烛同款复刻（深色）。只算不画，视觉交给通用原语。"""
import pandas as pd

from ..core.channel import fit_channel
from ..core.plugins import StrategyOutput, register_strategy
from ..render.theme import DARK

ANN_TYPES = {"hline", "zone", "channel", "trendline", "arrow", "tag", "circle", "text"}


def _resolve_anchor(df: pd.DataFrame, spec, kind: str):
    """通道端点解析：日期字符串原样返回；规则式——{above/below: 价, after?: 起始日}
    =该价位首破事件的那根 bar，{peak/trough: true} =窗口最高/最低价那根 bar。

    解决"硬编码日期在数据刷新后错位"的坑：通道起止点绑定业务事件而非日历日期。
    """
    if isinstance(spec, str):
        return spec
    if not isinstance(spec, dict):
        raise ValueError(f"通道{kind}锚点非法: {spec}（日期字符串，或 above/below/peak/trough 规则）")
    keys = set(spec) - {"after"}
    if "peak" in keys:
        return df.loc[df["high"].idxmax(), "datetime"]
    if "trough" in keys:
        return df.loc[df["low"].idxmin(), "datetime"]
    if "above" in keys:
        cond, what = df["close"] > float(spec["above"]), f"首次收盘站上{spec['above']}"
    elif "below" in keys:
        cond, what = df["close"] < float(spec["below"]), f"首次收盘跌破{spec['below']}"
    else:
        raise ValueError(f"通道{kind}锚点规则非法: {spec}（可用: above/below 价位、peak/trough）")
    hit = df[cond]
    if "after" in spec:
        hit = hit[hit["datetime"] >= pd.Timestamp(spec["after"])]
    if hit.empty:
        raise ValueError(f"通道{kind}锚点无命中: {spec}（数据窗口内未发生该事件）")
    return hit["datetime"].iloc[0]


@register_strategy("daily_candle")
def run(df, slots, ma=None, ma_unit="day", annotations=None, channels=None,
        volume_panel=False, **params):
    if not isinstance(volume_panel, bool):
        raise ValueError("volume_panel 必须是布尔值（params.volume_panel: true 追加成交量子图）")
    ma = [int(n) for n in (ma or [5, 10, 20, 30, 60])]
    if any(n <= 0 for n in ma) or len(set(ma)) != len(ma):
        raise ValueError(f"ma 必须为正整数且不重复: {ma}")
    if ma_unit not in ("day", "bar"):
        raise ValueError(f"ma_unit 非法: {ma_unit}（可用: day / bar）")
    # 频率高于日线时，均线默认按工作日换算：15分钟下 ma5 = 5日 = 16×5 根（ma_unit: bar 可特别约定按根数）
    bars_per_day = len(df) / max(1, df["datetime"].dt.date.nunique())
    windows = ([round(n * bars_per_day) for n in ma]
               if (bars_per_day > 1.5 and ma_unit == "day") else ma)
    for n, w in zip(ma, windows):
        df[f"ma{n}"] = df["close"].rolling(w).mean()

    # 窗口 > 数据长度时 rolling 全 NaN（无可用段——画"可用部分"须 min_periods=1，
    # 会把 MA20 算成 5 根均值、篡改语义）：该 MA 不画（图层移除、图例同步消失）+
    # 脚注回显。与 TradingView/通达信"窗口不足不画不报错"一致；多窗口混合时局部降级
    # 而非阻断整图。颜色按原序号取，缺失窗口不影响其余 MA 的配色。
    ch_notes = []
    palette = DARK["ma_palette"]
    skipped = [(n, w) for (n, w) in zip(ma, windows) if w > len(df)]
    layers = [{"type": "candle", "name": "K线", "up": DARK["up"], "down": DARK["down"]}]
    layers += [{"type": "line", "col": f"ma{n}", "name": f"MA{n}",
                "color": palette[i % len(palette)], "width": 1.2}
               for i, (n, w) in enumerate(zip(ma, windows)) if w <= len(df)]
    if skipped:
        ch_notes.append(f"MA 窗口超出数据长度（{len(df)}根），未绘制: "
                        + "、".join(f"MA{n}（{w}根）" for n, w in skipped))
    # 声明式通道：每条只写窗口+样式，两轨由 fit_channel 自动拟合（中枢主导三步法）。
    # 窗口端点支持事件式锚定（peak/trough/above/below），数据刷新自动重锚，杜绝硬编码日期漂移。
    for k, c in enumerate(channels or []):
        if not isinstance(c, dict) or not c.get("start") or not c.get("end"):
            raise ValueError(f"channels[{k}] 必须是含 start/end 的映射"
                             "（日期字符串，或 peak/trough/above/below 事件式锚点）")
        start = _resolve_anchor(df, c["start"], "起点")
        end = _resolve_anchor(df, c["end"], "终点")
        fit = fit_channel(df, start, end,
                          tilt=float(c.get("tilt", 0.12)),
                          press=float(c.get("press", 1.0)))
        layers.append({"type": "channel",
                       "from": [fit.window[0], fit.center[0][1]],
                       "to": [fit.window[1], fit.center[1][1]],
                       "lower": fit.d_lo, "upper": fit.d_hi,
                       "color": c.get("color", "#fdfd52"), "dash": c.get("dash", "dash"),
                       "line_width": c.get("line_width", 1.2), "label": c.get("label")})
        if isinstance(c["start"], dict) or isinstance(c["end"], dict):
            ch_notes.append(f"通道{k+1}锚点解析: {pd.Timestamp(start):%Y-%m-%d}→{pd.Timestamp(end):%Y-%m-%d}")
    for k, ann in enumerate(annotations or []):
        if not isinstance(ann, dict) or "type" not in ann:
            raise ValueError(f"annotations[{k}] 必须是含 type 的映射"
                             f"（可用 type: {sorted(ANN_TYPES)}）")
        if ann["type"] not in ANN_TYPES:
            raise ValueError(f"annotations[{k}].type 非法: {ann['type']}"
                             f"（可用: {sorted(ANN_TYPES)}）")
        a = dict(ann)
        if a["type"] == "hline":
            a.setdefault("axis", "y")   # 分钟路径缺省 y2（贴水副轴），日线单面板注入主轴
        layers.append(a)
    panels = [{"title": "主图", "layers": layers}]
    if volume_panel:
        # 成交量子图：多面板体系下的一种面板类型（与日内 extra_panels 同一机制，
        # 此处为最常用路径提供一键声明）；无量品种不追加空面板（适配器脚注已提示）
        if "volume" in df and df["volume"].notna().any():
            panels.append({"title": "成交量", "y_title": "成交量",
                           "range_cols": ["volume"],
                           "layers": [{"type": "volume", "col": "volume"}]})
    return StrategyOutput(df=df, events=[], notes=ch_notes, panels=panels)
