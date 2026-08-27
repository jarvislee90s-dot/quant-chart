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
    return cfg
