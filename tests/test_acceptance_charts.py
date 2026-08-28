"""三张样张复刻图的三层验收装载器：登记即跑（CSV 缺席自动 skip，本批后续图直接登记）。

每图的验收清单在 tests/acceptance_checks/<name>.py 的 run(fig, df, rep, cfg) -> Verifier，
清单内 L1/L2/L3 数值全部来自该任务读图确认结果（zoom 证据 + 数据交叉验证）。
"""
import importlib.util
from pathlib import Path

import pytest


CHARTS = [("chart_01_xau", "data/xau_daily.csv"),
          ("chart_02_cu0", "data/cu0_daily.csv"),
          ("chart_03_tl0", "data/tl0_daily.csv")]


@pytest.mark.parametrize("name,csv", CHARTS)
def test_acceptance_chart(name, csv):
    if not Path(csv).exists():
        pytest.skip(f"数据缺席: {csv}")
    # 清单文件名不带数据后缀：chart_01_xau -> tests/acceptance_checks/chart_01.py
    checklist = Path("tests/acceptance_checks") / f"{name.rsplit('_', 1)[0]}.py"
    spec = importlib.util.spec_from_file_location(name, checklist)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from quantchart.adapters.daily import load_daily
    from quantchart.core.config import load_config
    from quantchart.core.pipeline import run_pipeline
    cfg = load_config(f"configs/{name}.yaml")
    df, rep = load_daily(cfg["input"])
    fig, _ = run_pipeline(cfg)
    v = mod.run(fig, df, rep, cfg)
    v.name = name
    v.assert_ok()
