"""出图自检 CLI：对配置+fig 跑三层验收清单（清单以 python 函数形式随测试交付）。

用法（示例）:
  .venv/bin/python tools/verify_chart.py configs/chart_01_xau.yaml out/chart_01_xau.png --checks tests/acceptance_checks/chart_01.py
"""
import argparse
import importlib.util


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("config")
    ap.add_argument("png")
    ap.add_argument("--checks", required=True, help="验收清单 py 文件（含 run(fig, df, cfg) 函数）")
    args = ap.parse_args()
    spec = importlib.util.spec_from_file_location("checks", args.checks)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from quantchart.adapters.daily import load_daily
    from quantchart.core.config import load_config
    from quantchart.core.pipeline import run_pipeline
    cfg = load_config(args.config)
    df, _rep = load_daily(cfg["input"])
    fig, rep = run_pipeline(cfg)
    v = mod.run(fig, df, rep, cfg)
    v.assert_ok()
    print(f"验收通过: {args.png}（{len(v.violations)} 违规）")


if __name__ == "__main__":
    main()
