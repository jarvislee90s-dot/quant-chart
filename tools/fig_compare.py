"""改动前后成品对比：场景 fig → JSON 快照 dump / 两份 dump 语义 diff。

全部场景用确定性种子的合成数据（不依赖 data/、E:/、local-datasource），分两类：
- legacy/既有 config（11 个）：日内单/双面板、日线单面板/e2e + configs/ 下既有
  YAML 逐份**原样渲染**（仅数据路径替换为同构合成文件——Wind 同构 xlsx /
  同区间同周期 CSV，params 原样走 run_pipeline）。改动前后必须 0 diff；
- probe_*（3 个）：P2#3 to-only 锚点、P2#4 超包络/破下限贴水——修复目标场景，
  diff 即修复本身，字段须落在 xref/tickvals/range 修复面。

复跑「改动前后渲染一致」（基线 9fd55e1）：
  git archive 9fd55e1 | tar -x -C /tmp/qc_base           # 基线代码（不碰工作区/其他 worktree）
  PYTHONPATH=/tmp/qc_base/src python tools/fig_compare.py --dump /tmp/before
  python tools/fig_compare.py --dump /tmp/after          # 当前 HEAD
  python tools/fig_compare.py --diff /tmp/before /tmp/after
或一键门禁（上述流程自动完成 + 分类判读 + 退出码，可直接挂 CI）：
  python tools/fig_compare.py --gate [REF]               # 默认基线 9fd55e1

注：工具在基线 checkout 上同样可跑（仅依赖 quantchart 与已装依赖）；
--dump 把异常也落成 {"__error__": ...}，两侧同错即行为一致。
"""
import argparse
import datetime as dtm
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))      # 复用 Wind 同构夹具生成器（基线至今未改）


def _flatten(obj, prefix="", out=None):
    if out is None:
        out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(v, f"{prefix}.{k}" if prefix else str(k), out)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _flatten(v, f"{prefix}[{i}]", out)
    else:
        out[prefix] = obj
    return out


# ───────────────────────── 合成数据（种子固定，两侧一致） ─────────────────────────

def _intraday_df(seed=11, basis0=300.0, basis_slope=0.1):
    """单日 242 分钟合成宽表（与 tests/test_figure.py 同构）。"""
    from quantchart.core.session import build_slots, day_grid
    d = dtm.date(2026, 8, 19)
    df = pd.DataFrame([{"datetime": t, "fut_close": 7000.0 + i, "fut_vwap": 7000.0 + i,
                        "basis": basis0 - i * basis_slope, "idx_close": 7500.0}
                       for i, t in enumerate(day_grid(d))])
    return build_slots(df)


def _daily_df(n=10, seed=5, start="2026-06-01"):
    idx = pd.bdate_range(start, periods=n)
    rng = np.random.default_rng(seed)
    close = 7000 + np.cumsum(rng.normal(0, 20, n))
    return pd.DataFrame({"datetime": idx, "open": close - rng.uniform(0, 10, n),
                         "high": close + rng.uniform(5, 25, n),
                         "low": close - rng.uniform(5, 25, n),
                         "close": close,
                         "volume": rng.integers(1000, 5000, n)})


def _wind_xlsx(path, days, base, seed=7):
    """Wind 导出同构两表（代码/名称/日期/OHLC(元)/...，含 Wind 脚注行）。"""
    from make_fixtures import make
    make(str(path / "fut.xlsx"), "IM2612.CFE", days, base, zero_vol_minute="10:00")
    make(str(path / "idx.xlsx"), "000852.SH", days, base + 300, drop_minutes=2)


def _ohlcv_csv(path, dates, base, seed=3, minutes=()):
    """OHLCV CSV：minutes 非空 → 日内多根/日（09:30-11:30 + 13:00-15:00 各 9 根，
    每 15 分钟，含 11:30/15:00 首尾——覆盖 config 里 09:45/15:00 等时刻引用）。"""
    rng = np.random.default_rng(seed)
    rows = []
    for d in dates:
        if minutes:
            ts = ([d + pd.Timedelta(hours=9, minutes=30) + k * pd.Timedelta(minutes=15)
                   for k in range(9)]
                  + [d + pd.Timedelta(hours=13) + k * pd.Timedelta(minutes=15)
                     for k in range(9)])
        else:
            ts = [pd.Timestamp(d)]
        for t in ts:
            c = base + float(rng.normal(0, 1))
            base = c
            rows.append((t, c - rng.uniform(0, 8), c + rng.uniform(2, 15),
                         c - rng.uniform(2, 15), c, int(rng.integers(500, 5000))))
    pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"]) \
        .to_csv(path, index=False, date_format="%Y-%m-%d %H:%M" if minutes else "%Y-%m-%d")


# ───────────────────────────── 场景定义 ─────────────────────────────

def _sc_intraday_single():
    from quantchart.adapters.excel_wind import QualityReport
    from quantchart.render.figure import build_figure
    slots = _intraday_df()
    panels = [{"title": "主图", "layers": [
        {"type": "line", "col": "fut_close"}, {"type": "line", "col": "fut_vwap", "dash": "dash"},
        {"type": "area", "col": "basis"}, {"type": "day_seps"}, {"type": "day_labels"},
        {"type": "hline", "col_last": "fut_close", "axis": "y", "label": "现价"},
        {"type": "hline", "value": 250.0, "axis": "y2", "from": "2026-08-19 11:30",
         "to": "2026-08-19 15:00", "label": "触发线"}]}]
    return build_figure(slots.df, slots, panels, QualityReport("test", 1, 242, 0, 0), title="T")


def _sc_probe_p2_3_to_only():
    """探针：P2#3 修复目标——只给 to 不给 from 的 hline 标注锚点。
    基线标注 xref 退化为 paper（错位），HEAD 为 x 数据坐标（预期 1 处 diff）。"""
    from quantchart.adapters.excel_wind import QualityReport
    from quantchart.render.figure import build_figure
    slots = _intraday_df()
    panels = [{"title": "主图", "layers": [
        {"type": "hline", "value": 260.0, "axis": "y2", "to": "2026-08-19 15:00",
         "label": "仅to端"}]}]
    return build_figure(slots.df, slots, panels, QualityReport("test", 1, 242, 0, 0), title="T")


def _sc_intraday_multi():
    from quantchart.adapters.excel_wind import QualityReport
    from quantchart.render.figure import build_figure
    slots = _intraday_df()
    df = slots.df.copy()
    df["position_lots"] = 0.0
    df.loc[100:, "position_lots"] = 1.0
    panels = [{"title": "主图", "layers": [{"type": "line", "col": "fut_close"},
                                           {"type": "area", "col": "basis"}]},
              {"title": "仓位", "y_title": "仓位（手）", "range_cols": ["position_lots"],
               "layers": [{"type": "line", "col": "position_lots", "shape": "hv"}]}]
    return build_figure(df, slots, panels, QualityReport("test", 1, 242, 0, 0), title="T")


def _sc_probe_p2_4_beyond_400():
    """探针：P2#4 修复目标——贴水 530–650 超出 240–400 包络（基线数据区无刻度）。"""
    from quantchart.adapters.excel_wind import QualityReport
    from quantchart.render.figure import build_figure
    slots = _intraday_df(basis0=650.0, basis_slope=0.5)
    return build_figure(slots.df, slots, [{"title": "主图", "layers": [
        {"type": "line", "col": "fut_close"}, {"type": "area", "col": "basis"}]}],
        QualityReport("test", 1, 242, 0, 0), title="T")


def _sc_probe_p2_4_negative_floor():
    """探针：P2#4 修复目标——贴水 -50..-38 破 -15 下限（基线裁切）。"""
    from quantchart.adapters.excel_wind import QualityReport
    from quantchart.render.figure import build_figure
    slots = _intraday_df(basis0=-50.0, basis_slope=-0.05)
    return build_figure(slots.df, slots, [{"title": "主图", "layers": [
        {"type": "line", "col": "fut_close"}, {"type": "area", "col": "basis"}]}],
        QualityReport("test", 1, 242, 0, 0), title="T")


def _sc_daily_single():
    from quantchart.adapters.common import DailyQualityReport
    from quantchart.core.session import build_daily_slots
    from quantchart.render.figure_daily import build_daily_figure
    df = _daily_df()
    slots = build_daily_slots(df)
    slots.df["ma5"] = slots.df["close"].rolling(5).mean()
    return build_daily_figure(slots.df, slots,
                              [{"title": "主图", "layers": [{"type": "candle"},
                                                            {"type": "line", "col": "ma5", "name": "MA5"}]}],
                              DailyQualityReport("x", 10, 10), title="测试",
                              notes=["n1"], forecast_days=2)


def _sc_daily_e2e():
    import tempfile
    from quantchart.core.config import load_config
    from quantchart.core.pipeline import run_pipeline
    tmp = Path(tempfile.mkdtemp(prefix="qc_e2e_"))
    csv = tmp / "d.csv"
    with open(csv, "w", encoding="utf-8") as f:
        f.write("date,open,high,low,close,volume\n")
        for i, d in enumerate(range(20, 28)):
            f.write(f"2026-08-{d:02d},{7000 + i},{7100 + i},{6950 + i},{7050 + i},100\n")
    cfg_p = tmp / "c.yaml"
    cfg_p.write_text(
        f'input: {{mode: daily_csv, csv: "{csv}", range: [2026-08-20, 2026-08-27]}}\n'
        'strategy: daily_candle\nparams: {ma: [5], annotations:\n'
        '  [{type: hline, value: 7100, color: "#ff5b5b", label: 压力},\n'
        '   {type: tag, value: 7157, text: "7157", color: "#ff8c00"}]}\n'
        'title: 快照日线端到端\n', encoding="utf-8")
    fig, _ = run_pipeline(load_config(cfg_p))
    return fig


def _cfg_scenario(name, data_fn):
    """载入 configs/<name>.yaml，仅替换 input 数据路径为同构合成文件，params 原样。"""
    from quantchart.core.config import load_config
    from quantchart.core.pipeline import run_pipeline
    cfg = load_config(str(ROOT / "configs" / f"{name}.yaml"))
    inp = dict(cfg["input"])
    cfg["input"] = data_fn(inp)
    fig, _ = run_pipeline(cfg)
    return fig


def _data_basis_zones(inp):
    """3 份 basis 配置：Wind 同构两表（2026-08-17..27 九个交易日，覆盖 zones/trades 日期）。"""
    out = dict(inp)
    tmp = Path(tempfile.mkdtemp(prefix="qc_wind_"))
    days = [dtm.date(2026, 8, d) for d in (17, 18, 19, 20, 21, 24, 25, 26, 27)]
    _wind_xlsx(tmp, days, 7000.0)
    out.update(mode="excel",
               excel={"future": str(tmp / "fut.xlsx"), "index": str(tmp / "idx.xlsx")})
    return out


def _data_15min_csv(inp):
    out = dict(inp)
    tmp = Path(tempfile.mkdtemp(prefix="qc_15m_"))
    start, end = inp.get("range", ["2026-06-01", "2026-08-28"])
    _ohlcv_csv(tmp / "d.csv", pd.bdate_range(start, end), 7000.0, minutes=(15,))
    out.update(mode="daily_csv", csv=str(tmp / "d.csv"))
    return out


def _data_daily_csv(inp):
    out = dict(inp)
    tmp = Path(tempfile.mkdtemp(prefix="qc_daily_"))
    start, end = inp.get("range", ["2025-09-01", "2026-08-28"])
    _ohlcv_csv(tmp / "d.csv", pd.bdate_range(start, end), 7000.0)
    out.update(mode="daily_csv", csv=str(tmp / "d.csv"))
    return out


# 场景分两类（--diff 输出按注册序排列，探针在最后）：
# - legacy/既有 config：改动前后必须 0 diff（意外 diff = 回归）
# - probe_*：P2 修复目标场景，diff 是修复本身（预期 diff，字段须落在修复面）
SCENARIOS = {
    "intraday_single": _sc_intraday_single,
    "intraday_multi": _sc_intraday_multi,
    "daily_single": _sc_daily_single,
    "daily_e2e": _sc_daily_e2e,
    "cfg_basis_review": lambda: _cfg_scenario("basis_review", _data_basis_zones),
    "cfg_basis_zones": lambda: _cfg_scenario("basis_zones", _data_basis_zones),
    "cfg_basis_zones_position": lambda: _cfg_scenario("basis_zones_position", _data_basis_zones),
    "cfg_daily_candle": lambda: _cfg_scenario("daily_candle", _data_15min_csv),
    "cfg_chart_01_xau": lambda: _cfg_scenario("chart_01_xau", _data_daily_csv),
    "cfg_chart_02_cu0": lambda: _cfg_scenario("chart_02_cu0", _data_daily_csv),
    "cfg_chart_03_tl0": lambda: _cfg_scenario("chart_03_tl0", _data_daily_csv),
    "probe_p2_3_to_only": _sc_probe_p2_3_to_only,
    "probe_p2_4_beyond_400": _sc_probe_p2_4_beyond_400,
    "probe_p2_4_negative_floor": _sc_probe_p2_4_negative_floor,
}


def _dump_dir(names, out_dir, pythonpath_src):
    """用指定 src（PYTHONPATH 隔离）渲染场景 dump——基线/当前两侧复用同一脚本。"""
    env = dict(os.environ, PYTHONPATH=str(pythonpath_src))
    cmd = [sys.executable, str(Path(__file__).resolve()), "--dump", str(out_dir)]
    if names:
        cmd += ["--only", ",".join(names)]
    r = subprocess.run(cmd, cwd=str(ROOT), env=env, check=False,
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"gate: dump 失败（PYTHONPATH={pythonpath_src}）")


def _gate(ref, only=None):
    """一键回归门禁：git archive 物化 <ref> 为基线 → 两侧 dump → 分类判读。

    判读与退出码（可直接挂 CI / pytest 包装）：
    - 既有场景（legacy/cfg_*）出现 diff = REGRESSION（回归）；
    - probe_* 探针 0 diff = FIX_LOST（修复目标不再可观察）；
    - dump 缺失 = MISSING；任一存在即退出码 1。
    """
    if subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=str(ROOT),
                      capture_output=True).returncode != 0:
        raise SystemExit("gate: 需要 git 仓库上下文")
    names = only.split(",") if only else None
    with tempfile.TemporaryDirectory(prefix="qc_gate_") as td:
        base = Path(td) / "base"
        base.mkdir()
        archive = subprocess.Popen(["git", "archive", ref], cwd=str(ROOT),
                                   stdout=subprocess.PIPE)
        subprocess.run(["tar", "-x", "-C", str(base)], stdin=archive.stdout, check=True)
        archive.stdout.close()
        if archive.wait() != 0:
            raise SystemExit(f"gate: git archive {ref} 失败（未知引用？）")
        before, after = Path(td) / "before", Path(td) / "after"
        _dump_dir(names, before, base / "src")
        _dump_dir(names, after, ROOT / "src")

        regression, fix_lost, missing = [], [], []
        for name in (names or SCENARIOS):
            pa, pb = before / f"{name}.json", after / f"{name}.json"
            if not (pa.exists() and pb.exists()):
                missing.append(name)
                continue
            fa = _flatten(json.load(open(pa)))
            fb = _flatten(json.load(open(pb)))
            n = sum(1 for k in set(fa) | set(fb) if fa.get(k) != fb.get(k))
            if name.startswith("probe_"):
                if n == 0:
                    fix_lost.append(name)
            elif n:
                regression.append((name, n))
        for name, n in regression:
            print(f"REGRESSION  {name}: {n} 处意外 diff")
        for name in fix_lost:
            print(f"FIX_LOST    {name}: 探针 0 diff（修复目标不再可观察）")
        for name in missing:
            print(f"MISSING     {name}: dump 缺失")
        ok = not (regression or fix_lost or missing)
        print(f"GATE {'PASS' if ok else 'FAIL'}（回归 {len(regression)}，"
              f"修复丢失 {len(fix_lost)}，缺失 {len(missing)}；基线 {ref} vs 当前工作树）")
        sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dump", metavar="DIR", help="渲染全部场景 → DIR/<场景>.json")
    ap.add_argument("--diff", nargs=2, metavar=("A", "B"), help="对比两份 dump 目录")
    ap.add_argument("--gate", nargs="?", const="9fd55e1", metavar="REF",
                    help="一键回归门禁：物化 REF 为基线 → 两侧 dump → 分类判读；"
                         "意外 diff/探针丢失/缺 dump 任一存在即退出码 1（默认基线 9fd55e1）")
    ap.add_argument("--only", help="只跑指定场景（逗号分隔）")
    args = ap.parse_args()
    names = [s for s in SCENARIOS if not args.only or s in args.only.split(",")]

    if args.dump:
        out = Path(args.dump)
        out.mkdir(parents=True, exist_ok=True)
        for name in names:
            try:
                fig = SCENARIOS[name]()
                payload, status = fig.to_dict(), "ok"
            except Exception as e:        # 两侧同错也算行为一致，落盘留证
                payload, status = {"__error__": f"{type(e).__name__}: {e}"}, "ERROR"
            with open(out / f"{name}.json", "w", encoding="utf-8") as f:
                json.dump(payload, f, sort_keys=True, ensure_ascii=False, default=str)
            print(f"{status:5} {name}")
        print(f"dump -> {out}")
    elif args.diff:
        a, b = Path(args.diff[0]), Path(args.diff[1])
        total = 0
        for name in names:
            pa, pb = a / f"{name}.json", b / f"{name}.json"
            if not pa.exists() or not pb.exists():
                print(f"???   {name}: dump 缺失（{pa.exists()=}, {pb.exists()=}）")
                continue
            fa, fb = _flatten(json.load(open(pa))), _flatten(json.load(open(pb)))
            diffs = [(k, fa.get(k, "<缺>"), fb.get(k, "<缺>"))
                     for k in sorted(set(fa) | set(fb)) if fa.get(k) != fb.get(k)]
            total += len(diffs)
            if not diffs:
                print(f"0 diff {name}")
            else:
                print(f"{len(diffs)} diff {name}")
                for k, va, vb in diffs[:6]:
                    sa, sb = str(va), str(vb)
                    print(f"    {k}: {sa[:50]}{'…' if len(sa) > 50 else ''}"
                          f" -> {sb[:50]}{'…' if len(sb) > 50 else ''}")
                if len(diffs) > 6:
                    print(f"    … 另有 {len(diffs) - 6} 处")
        print(f"合计 {total} 处差异")
    elif args.gate is not None:
        _gate(args.gate, args.only)


if __name__ == "__main__":
    main()
