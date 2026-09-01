"""YAML 加载与校验：错误信息定位到字段路径。"""
import re

import yaml


class ConfigError(ValueError):
    pass


# 周期 → 每交易日根数（中金所时段 09:30-11:30/13:00-15:00 = 240 分钟）
GRANULARITY_BPD = {"day": 1, "week": 1, "month": 1, "15min": 16, "30min": 8, "60min": 4}


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
    if isinstance(mode, str) and mode.startswith("daily"):
        if mode == "daily_csv" and not inp.get("csv"):
            raise ConfigError("input.mode=daily_csv 需要 input.csv（日线CSV路径）")
        if mode == "daily_api" and not (isinstance(inp.get("api"), dict)
                                        and inp["api"].get("symbol")):
            raise ConfigError("input.mode=daily_api 需要 input.api.symbol（如 IM0/CU0/TL0）")
        rng = inp.get("range")
        if not (isinstance(rng, list) and len(rng) == 2):
            raise ConfigError(f"input.mode={mode} 需要 input.range（起止日期，闭区间）")
        gran = inp.get("granularity", "auto")
        if gran not in ("auto", *GRANULARITY_BPD):
            raise ConfigError(f"input.granularity 非法: {gran}"
                              f"（可用: auto/day/week/month/15min/30min/60min）")
        strict = inp.get("strict_range", False)
        if not isinstance(strict, bool):
            raise ConfigError("input.strict_range 必须是布尔值")
        anchor = inp.get("tick_anchor", "10:30")
        if anchor is not None and not (isinstance(anchor, str)
                                       and re.fullmatch(r"\d{1,2}:\d{2}", anchor)):
            raise ConfigError('input.tick_anchor 必须是 "HH:MM" 格式（日内刻度锚定时刻）')
    else:
        if mode in ("excel", "auto"):
            excel = inp.get("excel")
            for key in ("future", "index"):
                if not isinstance(excel, dict) or not excel.get(key):
                    raise ConfigError(
                        f"input.mode={mode} 需要 input.excel.future 与 input.excel.index "
                        f"两表路径（缺失: input.excel.{key}）")
        if mode in ("api", "auto"):
            api = inp.get("api")
            for key in ("future", "index"):
                if not isinstance(api, dict) or not api.get(key):
                    raise ConfigError(
                        f"input.mode={mode} 需要 input.api.future 与 input.api.index "
                        f"两个代码（缺失: input.api.{key}）")
            rng = inp.get("range")
            if not (isinstance(rng, list) and len(rng) == 2):
                raise ConfigError(f"input.mode={mode} 需要 input.range（起止日期，分钟深度校验用）")
    if not isinstance(cfg.get("params", {}), dict):
        raise ConfigError("params 必须是键值映射")
    fd = cfg.get("forecast_days")
    if fd is not None and (isinstance(fd, bool) or not isinstance(fd, (int, float)) or fd <= 0):
        raise ConfigError("forecast_days 必须是正数（右缘预测区的工作日数）")
    proj = cfg.get("project")
    if proj is not None and (not isinstance(proj, str) or not proj.strip()):
        raise ConfigError("project 必须是非空字符串路径（项目归档文件夹：config 快照/PNG/HTML/refs）")
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
    rh = cfg.get("row_heights")
    if rh is not None and (
            not isinstance(rh, list) or not rh
            or any(isinstance(x, bool) or not isinstance(x, (int, float)) or x <= 0
                   for x in rh)):
        raise ConfigError("row_heights 必须是正数列表（每行面板高度占比，如 [0.72, 0.28]）")
    mult = cfg.get("contract_mult", 200)
    if isinstance(mult, bool) or not isinstance(mult, (int, float)) or mult <= 0:
        raise ConfigError("contract_mult 必须是正数")
    return cfg
