"""YAML 加载与校验：错误信息定位到字段路径。"""
import yaml


class ConfigError(ValueError):
    pass


def load_config(path: str) -> dict:
    cfg = yaml.safe_load(open(path, encoding="utf-8")) or {}
    for field in ("input", "strategy"):
        if field not in cfg:
            raise ConfigError(f"缺少必填字段: {field}")
    mode = cfg["input"].get("mode", "excel")
    if mode in ("excel", "auto") and "excel" not in cfg["input"]:
        raise ConfigError("input.mode=excel/auto 需要 input.excel（future+index 两表路径）")
    if not isinstance(cfg.get("params", {}), dict):
        raise ConfigError("params 必须是键值映射")
    if not isinstance(cfg.get("panels", []), list):
        raise ConfigError("panels 必须是列表")
    return cfg
