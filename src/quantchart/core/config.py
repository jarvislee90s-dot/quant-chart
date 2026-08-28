"""YAML 加载与校验：错误信息定位到字段路径。"""
import yaml


class ConfigError(ValueError):
    pass


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    for field in ("input", "strategy"):
        if field not in cfg:
            raise ConfigError(f"缺少必填字段: {field}")
    inp = cfg["input"]
    if not isinstance(inp, dict):
        raise ConfigError("input 必须是键值映射")
    mode = inp.get("mode", "excel")
    if mode in ("excel", "auto"):
        excel = inp.get("excel")
        for key in ("future", "index"):
            if not isinstance(excel, dict) or not excel.get(key):
                raise ConfigError(
                    f"input.mode={mode} 需要 input.excel.future 与 input.excel.index "
                    f"两表路径（缺失: input.excel.{key}）")
    if not isinstance(cfg.get("params", {}), dict):
        raise ConfigError("params 必须是键值映射")
    if not isinstance(cfg.get("panels", []), list):
        raise ConfigError("panels 必须是列表")
    trades = cfg.get("trades")
    if trades is not None:
        if not isinstance(trades, list) or not trades:
            raise ConfigError("trades 必须是非空列表（或改用 trades_csv）")
        for k, t in enumerate(trades):
            if not isinstance(t, dict):
                raise ConfigError(f"trades[{k}] 必须是键值映射")
            for f in ("time", "action"):
                if f not in t:
                    raise ConfigError(f"trades[{k}] 缺少 {f}")
            if t["action"] not in ("buy", "sell", "close"):
                raise ConfigError(f"trades[{k}].action 非法: {t['action']}（buy/sell/close）")
            if t["action"] != "close" and not t.get("lots"):
                raise ConfigError(f"trades[{k}].lots 缺失（close 动作可省略）")
    if not isinstance(cfg.get("extra_panels", []), list):
        raise ConfigError("extra_panels 必须是列表")
    mult = cfg.get("contract_mult", 200)
    if isinstance(mult, bool) or not isinstance(mult, (int, float)) or mult <= 0:
        raise ConfigError("contract_mult 必须是正数")
    return cfg
