"""策略插件注册与发现。插件只算不画：df+slots → StrategyOutput。"""
import importlib
import pkgutil
from dataclasses import dataclass, field

import pandas as pd

from .signals import Event


@dataclass
class StrategyOutput:
    df: pd.DataFrame
    events: list = field(default_factory=list)      # list[Event]
    panels: list = field(default_factory=list)      # 默认面板配置（可被YAML覆盖合并）


REGISTRY: dict = {}


def register_strategy(name: str):
    def deco(fn):
        REGISTRY[name] = fn
        return fn
    return deco


def get_strategy(name: str):
    if name not in REGISTRY:
        raise KeyError(f"未知策略: {name}（可用: {sorted(REGISTRY)}）")
    return REGISTRY[name]


def load_plugins(pkg_name: str = "quantchart.plugins"):
    pkg = importlib.import_module(pkg_name)
    for m in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"{pkg_name}.{m.name}")
