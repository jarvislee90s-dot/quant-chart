"""预设3：daily_candle —— 日线蜡烛同款复刻（深色）。只算不画，视觉交给通用原语。"""
from ..core.plugins import StrategyOutput, register_strategy
from ..render.theme import DARK

ANN_TYPES = {"hline", "zone", "trendline", "arrow", "tag", "circle", "text"}


@register_strategy("daily_candle")
def run(df, slots, ma=None, annotations=None, **params):
    ma = [int(n) for n in (ma or [5, 10, 20, 30, 60])]
    if any(n <= 0 for n in ma) or len(set(ma)) != len(ma):
        raise ValueError(f"ma 必须为正整数且不重复: {ma}")
    for n in ma:
        df[f"ma{n}"] = df["close"].rolling(n).mean()

    palette = DARK["ma_palette"]
    layers = [{"type": "candle", "name": "K线", "up": DARK["up"], "down": DARK["down"]}]
    layers += [{"type": "line", "col": f"ma{n}", "name": f"MA{n}",
                "color": palette[i % len(palette)], "width": 1.2}
               for i, n in enumerate(ma)]
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
    return StrategyOutput(df=df, events=[], panels=[{"title": "主图", "layers": layers}])
