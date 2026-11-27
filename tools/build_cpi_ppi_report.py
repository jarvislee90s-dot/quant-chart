#!/usr/bin/env python3
"""生成 CPI-PPI 剪刀差相关性分析的 HTML 报告（自包含单文件）。

读 outputs/cpi_ppi/ 下三张 PNG 与分析脚本产出的 CSV，产出 report.html：
  - 三张图逐面板讲读
  - 分析过程与口径定义
  - 可复现性：环境版本、数据指纹、复跑命令
  - 页面内复算：内嵌原始列，页面用 JS 重建整条派生链并复算统计量，
    与 pandas+scipy 的期望值逐项对账（断言表）

用法:
  python tools/build_cpi_ppi_report.py            # 生成 report.html
  python tools/build_cpi_ppi_report.py --selftest  # 用内嵌 JS 重验对齐 scipy（需 node）

设计要点（踩过的坑）:
  - 页面只内嵌 6 个原始列，派生列全部由 JS 现算——这样复现的是「方法」而不只是「算术」。
  - 期望值必须用「原始列重建」basis 计算，不能直接读 series_monthly.csv 的派生列：
    CSV 往返在 11 个月上有 1 ulp 级差异，会改变并列秩结构，使 Spearman 出现 8e-4 偏差。
    已验证「原始列重建」能逐位复现分析脚本的权威输出 corr_*.csv（Δ<1e-16）。
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import subprocess
import sys
import tempfile
from html import escape
from pathlib import Path

import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cpi_ppi"
SERIES = OUT / "series_monthly.csv"
FIGS = [("fig01_trend.png", "图一"), ("fig02_correlation.png", "图二"),
        ("fig03_decomposition.png", "图三")]

# 与 tools/analyze_cpi_ppi.py 的配色常量一致（浅色研报风格）
SHEET = "#ffffff"                      # 正文纸面
BG, CARD = "#eef1f5", "#f8fafc"        # 页底 / 卡片
FG, GRID, DIM = "#16191d", "#dde2e8", "#5b6470"
C_CPI, C_PPI, C_SPREAD = "#d9480f", "#1971c2", "#6d28d9"
C_IDX, C_SEC, C_BOND = "#c92a2a", "#2f9e44", "#0b7285"
C_NEG, C_OK = "#c92a2a", "#2b8a3e"

# 指数槽位：由 meta.json 覆盖（V1 = 沪深300，V2 = 上证指数）
IDX_SYM, IDX_NAME = "000300", "沪深300"
SEC_SYM, SEC_NAME = "000905", "中证500"

PRIM = ["cpi_yoy", "ppi_yoy", "y10", "idx", "sec"]
DERIVED = ["spread", "d_spread", "d_cpi", "d_ppi", "idx_ret", "sec_ret", "d_y10",
           "d12_spread", "d12_cpi", "d12_ppi", "idx_ret12", "sec_ret12", "d12_y10",
           "idx_norm", "sec_norm"]

# 每个口径：剪刀差列、CPI 腿列、PPI 腿列，以及三个市场变量（展示名, 列名）
# 注意：必须是函数——展示名依赖 IDX_NAME，模块级常量会在 main() 覆盖前就冻结。
def _led_specs():
    return [
        ("水平", "spread", "cpi_yoy", "ppi_yoy",
         [(IDX_NAME + "（点位）", "idx"), (SEC_NAME + "（点位）", "sec"),
          ("10年国债收益率（%）", "y10")]),
        ("月度变化", "d_spread", "d_cpi", "d_ppi",
         [(IDX_NAME + "（月收益率%）", "idx_ret"), (SEC_NAME + "（月收益率%）", "sec_ret"),
          ("10年国债（月变化pp）", "d_y10")]),
        ("12个月变化", "d12_spread", "d12_cpi", "d12_ppi",
         [(IDX_NAME + "（12月收益率%）", "idx_ret12"), (SEC_NAME + "（12月收益率%）", "sec_ret12"),
          ("10年国债（12月变化pp）", "d12_y10")]),
    ]


def all_pairs() -> list[dict]:
    """全部待验证配对：3 口径 × 3 市场 × (剪刀差 + CPI 腿 + PPI 腿) = 27。"""
    out = []
    for tag, sc, cc, pc, mkts in _led_specs():
        for label, m in mkts:
            for role, col in (("剪刀差", sc), ("CPI腿", cc), ("PPI腿", pc)):
                out.append({"tag": tag, "role": role, "a": col, "b": m, "label": label})
    return out



# ============================================================ JS：数学（已验证）
# 与 scipy 的一致性见 --selftest。此常量为唯一来源，页面用哪份、测试就测哪份。
JS_MATH = r"""
function pairs(a, b) {
  const out = [];
  for (let i = 0; i < a.length; i++) {
    const x = a[i], y = b[i];
    if (x === null || y === null || x === undefined || y === undefined) continue;
    if (Number.isNaN(x) || Number.isNaN(y)) continue;
    out.push([x, y]);
  }
  return out;
}
function pearson(x, y) {
  const n = x.length;
  if (n < 2) return NaN;
  let sx = 0, sy = 0;
  for (let i = 0; i < n; i++) { sx += x[i]; sy += y[i]; }
  const mx = sx / n, my = sy / n;
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < n; i++) {
    const dx = x[i] - mx, dy = y[i] - my;
    sxy += dx * dy; sxx += dx * dx; syy += dy * dy;
  }
  if (sxx === 0 || syy === 0) return NaN;
  return sxy / Math.sqrt(sxx * syy);
}
function rankArr(arr) {
  const idx = arr.map((v, i) => [v, i]).sort((p, q) => p[0] - q[0]);
  const r = new Array(arr.length);
  let i = 0;
  while (i < idx.length) {
    let j = i;
    while (j + 1 < idx.length && idx[j + 1][0] === idx[i][0]) j++;
    const avg = (i + j) / 2 + 1;
    for (let k = i; k <= j; k++) r[idx[k][1]] = avg;
    i = j + 1;
  }
  return r;
}
function spearman(x, y) { return pearson(rankArr(x), rankArr(y)); }
function gammaln(x) {
  const c = [76.18009172947146, -86.50532032941677, 24.01409824083091,
             -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5];
  let y = x, tmp = x + 5.5;
  tmp -= (x + 0.5) * Math.log(tmp);
  let ser = 1.000000000190015;
  for (let j = 0; j < 6; j++) ser += c[j] / ++y;
  return -tmp + Math.log(2.5066282746310005 * ser / x);
}
function betacf(a, b, x) {
  const MAXIT = 300, EPS = 3e-16, FPMIN = 1e-300;
  const qab = a + b, qap = a + 1, qam = a - 1;
  let c = 1, d = 1 - qab * x / qap;
  if (Math.abs(d) < FPMIN) d = FPMIN;
  d = 1 / d;
  let h = d;
  for (let m = 1; m <= MAXIT; m++) {
    const m2 = 2 * m;
    let aa = m * (b - m) * x / ((qam + m2) * (a + m2));
    d = 1 + aa * d; if (Math.abs(d) < FPMIN) d = FPMIN;
    c = 1 + aa / c; if (Math.abs(c) < FPMIN) c = FPMIN;
    d = 1 / d; h *= d * c;
    aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
    d = 1 + aa * d; if (Math.abs(d) < FPMIN) d = FPMIN;
    c = 1 + aa / c; if (Math.abs(c) < FPMIN) c = FPMIN;
    d = 1 / d;
    const del = d * c; h *= del;
    if (Math.abs(del - 1) < EPS) break;
  }
  return h;
}
function ibeta(a, b, x) {
  if (!(x > 0)) return 0;
  if (x >= 1) return 1;
  const bt = Math.exp(gammaln(a + b) - gammaln(a) - gammaln(b)
                      + a * Math.log(x) + b * Math.log(1 - x));
  if (x < (a + 1) / (a + b + 2)) return bt * betacf(a, b, x) / a;
  return 1 - bt * betacf(b, a, 1 - x) / b;
}
function pFromR(r, n) {
  if (!Number.isFinite(r) || n < 3) return NaN;
  const df = n - 2;
  if (Math.abs(r) >= 1) return 0;
  const t2 = r * r * df / (1 - r * r);
  return ibeta(df / 2, 0.5, df / (df + t2));
}
function std(a) {
  const v = a.filter(x => x !== null && !Number.isNaN(x));
  const n = v.length;
  if (n < 2) return NaN;
  const mu = v.reduce((s, x) => s + x, 0) / n;
  return Math.sqrt(v.reduce((s, x) => s + (x - mu) ** 2, 0) / (n - 1));
}

// ---- 从原始列重建整条派生链（页面与 --selftest 共用同一实现）----
function deriveAll(P) {
  const spread = P.cpi_yoy.map((c, i) => (c === null || P.ppi_yoy[i] === null) ? null : c - P.ppi_yoy[i]);
  const diffK = (a, k) => a.map((v, i) => (i < k || v === null || a[i - k] === null) ? null : v - a[i - k]);
  const pctK = (a, k) => a.map((v, i) => (i < k || v === null || a[i - k] === null || a[i - k] === 0) ? null : (v / a[i - k] - 1) * 100);
  const norm = a => { const b = a.find(v => v !== null); return a.map(v => v === null || !b ? null : v / b * 100); };
  const dv = {
    spread: spread,
    d_spread: diffK(spread, 1), d_cpi: diffK(P.cpi_yoy, 1), d_ppi: diffK(P.ppi_yoy, 1),
    idx_ret: pctK(P.idx, 1), sec_ret: pctK(P.sec, 1), d_y10: diffK(P.y10, 1),
    d12_spread: diffK(spread, 12), d12_cpi: diffK(P.cpi_yoy, 12), d12_ppi: diffK(P.ppi_yoy, 12),
    idx_ret12: pctK(P.idx, 12), sec_ret12: pctK(P.sec, 12), d12_y10: diffK(P.y10, 12),
    idx_norm: norm(P.idx), sec_norm: norm(P.sec)
  };
  return { spread: spread, dv: dv };
}
function pick(dv, P, k) { return (k in dv) ? dv[k] : P[k]; }
// 四元组：(r, p, ρ, n)。x/y 由原始数组成对剔除后给出。
function statOf(pr) {
  const x = pr.map(q => q[0]), y = pr.map(q => q[1]);
  const r = pr.length >= 4 ? pearson(x, y) : NaN;
  return { r: r, p: pFromR(r, pr.length), rho: Number.isFinite(r) ? spearman(x, y) : NaN, n: pr.length };
}
function statPair(a, b) { return statOf(pairs(a, b)); }
function computeScalars(P) {
  const spread = deriveAll(P).spread;
  const sp = spread.filter(v => v !== null);
  const mn = sp.length ? Math.min(...sp) : NaN, mx = sp.length ? Math.max(...sp) : NaN;
  const pr2 = pairs(spread, P.ppi_yoy);
  return {
    spread_min: mn, spread_max: mx,
    spread_min_idx: spread.indexOf(mn), spread_max_idx: spread.indexOf(mx),
    std_cpi: std(P.cpi_yoy), std_ppi: std(P.ppi_yoy),
    r2: statOf(pr2).r ** 2
  };
}
"""


# ============================================================ JS：复算与断言
JS_CHECK = r"""
(function () {
  const D = __DATA__, E = __EXP__;
  const P = D.primitives, N = D.months.length;

  // 与 --selftest 共用同一实现（deriveAll/statPair/computeScalars），不各自重写
  const derived = deriveAll(P);
  const dv = derived.dv, spread = derived.spread;
  const sc = computeScalars(P);

  const rows = [];
  const push = (group, label, exp, got, ok) => rows.push({ group, label, exp, got, ok });
  const missing = v => v === null || v === undefined || !Number.isFinite(v);
  const same = (a, b, tol = 1e-9) => missing(b) ? missing(a) : !missing(a) && Math.abs(a - b) <= tol;
  const label = (v, digits = 3) => missing(v) ? '不可用' : v.toFixed(digits);

  // ---- 1. 派生链逐值比对 ----
  let chainBad = 0, chainTot = 0;
  const relOk = (a, b) => {
    if (a === null && b === null) return true;
    if (typeof a === 'number' && typeof b === 'number') {
      return Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(b));
    }
    return false;
  };
  for (const col of E.derived_order) {
    for (let i = 0; i < N; i++) {
      chainTot++;
      if (!relOk(dv[col][i], E.derived[col][i])) chainBad++;
    }
  }
  push('派生链', E.derived_order.length + ' 个派生列 × ' + N + ' 行逐值复算比对（容差 1e-9）',
    '全部一致', chainBad ? chainBad + ' 项不符' : '全部一致', chainBad === 0);

  // ---- 2. 标量 ----
  for (const side of ['min', 'max']) {
    const key = 'spread_' + side, month = D.months[sc[key + '_idx']] ?? null;
    const describe = (value, date) => missing(value) ? '不可用' : label(value, 2) + ' @' + date;
    push('标量', '剪刀差' + (side === 'min' ? '最小值' : '最大值') + ' / 所在月',
      describe(E.scalars[key], E.scalars[key + '_month']), describe(sc[key], month),
      same(sc[key], E.scalars[key], 1e-12) && month === E.scalars[key + '_month']);
  }
  for (const key of ['idx', 'sec']) {
    const col = key + '_norm', exp = E.scalars[col + '_last'], got = dv[col][N - 1];
    push('标量', '归一化末值 ' + E.names[key], label(exp, 10), label(got, 10), same(got, exp));
  }
  for (const key of ['cpi', 'ppi']) {
    const field = 'std_' + key, exp = E.scalars[field], got = sc[field];
    push('标量', key.toUpperCase() + ' 同比样本标准差（ddof=1）',
      label(exp, 10), label(got, 10), same(got, exp, 1e-12));
  }

  // ---- 3. 相关系数（r / p / ρ / n）----
  let statBad = 0;
  for (const s of E.stats) {
    const got = statPair(pick(dv, P, s.a), pick(dv, P, s.b));
    const ok = same(got.r, s.r) && same(got.p, s.p, 1e-12) && got.n === s.n && same(got.rho, s.rs);
    if (!ok) statBad++;
    const describe = (r, p, rho, n) => 'r=' + label(r, 6) + '  p=' + label(p, 6) + '  ρ=' + label(rho, 6) + '  n=' + n;
    push('相关系数', s.tag + ' · ' + s.role + ' · ' + s.label,
      describe(s.r, s.p, s.rs, s.n), describe(got.r, got.p, got.rho, got.n), ok);
  }

  // ---- 4. 方差分解 ----
  push('方差分解', 'R²（剪刀差 ~ PPI 同比 水平）', label(E.scalars.r2, 10),
    label(sc.r2, 10), same(sc.r2, E.scalars.r2, 1e-12));

  // ---- 渲染 ----
  const bad = rows.filter(r => !r.ok).length;
  const tb = document.getElementById('chk-body');
  const addCell = (row, value, cls = '') => {
    const td = document.createElement('td');
    td.className = cls;
    td.textContent = String(value);
    row.appendChild(td);
    return td;
  };
  let lastG = '';
  for (const r of rows) {
    if (r.group !== lastG) {
      const gtr = document.createElement('tr');
      gtr.className = 'grp';
      addCell(gtr, r.group).colSpan = 4;
      tb.appendChild(gtr);
      lastG = r.group;
    }
    const tr = document.createElement('tr');
    tr.className = r.ok ? '' : 'bad';
    addCell(tr, r.label);
    addCell(tr, r.exp, 'mono');
    addCell(tr, r.got, 'mono');
    addCell(tr, r.ok ? '✓' : '✗', 'verdict ' + (r.ok ? 'ok' : 'fail'));
    tb.appendChild(tr);
  }
  const status = document.getElementById('chk-status');
  status.textContent = bad ? '存在失败' : '全部通过';
  status.className = 'verdict ' + (bad ? 'fail' : 'ok');
  document.getElementById('chk-summary').textContent = '共 ' + rows.length + ' 项校验，'
    + chainTot + ' 个派生数值，失败 ' + bad + ' 项（其中相关系数 ' + statBad + ' 项）。';
  window.__CHK__ = { total: rows.length, bad: bad, chainTot: chainTot };
})();
"""

# ============================================================ 取数与期望值
def _clean(v):
    return None if (v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))) else v


def build_panel() -> tuple[dict, pd.DataFrame, dict]:
    """读原始列并重建整条派生链（与页面 JS 同一 basis）。"""
    m = pd.read_csv(SERIES, encoding="utf-8-sig")
    m.index = pd.PeriodIndex(m.pop("month"), freq="M")
    if m.empty or m.index.hasnans or not m.index.is_unique:
        raise ValueError("月度面板为空、存在无效月份或重复月份")
    months = pd.period_range(m.index.min(), m.index.max(), freq="M").astype(str).tolist()
    m = m.reindex(pd.PeriodIndex(months, freq="M")).reset_index(drop=True)
    P = {k: m[k].astype(float).replace([math.inf, -math.inf], math.nan) for k in PRIM}
    d = pd.DataFrame(index=m.index)
    d["spread"] = P["cpi_yoy"] - P["ppi_yoy"]
    d["d_spread"] = d["spread"].diff()
    d["d_cpi"] = P["cpi_yoy"].diff()
    d["d_ppi"] = P["ppi_yoy"].diff()
    d["idx_ret"] = P["idx"].pct_change(fill_method=None) * 100
    d["sec_ret"] = P["sec"].pct_change(fill_method=None) * 100
    d["d_y10"] = P["y10"].diff()
    d["d12_spread"] = d["spread"].diff(12)
    d["d12_cpi"] = P["cpi_yoy"].diff(12)
    d["d12_ppi"] = P["ppi_yoy"].diff(12)
    d["idx_ret12"] = P["idx"].pct_change(12, fill_method=None) * 100
    d["sec_ret12"] = P["sec"].pct_change(12, fill_method=None) * 100
    d["d12_y10"] = P["y10"].diff(12)
    for c in ("idx", "sec"):
        valid = P[c].dropna()
        d[f"{c}_norm"] = P[c] / (valid.iloc[0] if len(valid) and valid.iloc[0] else math.nan) * 100
    d = d.replace([math.inf, -math.inf], math.nan)
    return months, P, d


def expected_payload(months: list[str], P: dict, d: pd.DataFrame) -> dict:
    def get(k):
        return d[k] if k in d.columns else P[k]

    def pair(a, b):
        x = pd.concat([a, b], axis=1).dropna()
        n = len(x)
        if n < 4 or min(x.iloc[:, 0].nunique(), x.iloc[:, 1].nunique()) < 2:
            return None, None, n, None
        r, p = stats.pearsonr(x.iloc[:, 0], x.iloc[:, 1])
        rho, _ = stats.spearmanr(x.iloc[:, 0], x.iloc[:, 1])
        return _clean(float(r)), _clean(float(p)), n, _clean(float(rho))

    st = []
    for spec in all_pairs():
        r, p, n, rho = pair(get(spec["a"]), get(spec["b"]))
        st.append({**spec, "r": r, "p": p, "n": n, "rs": rho})

    spread = d["spread"].dropna()
    r, _, _, _ = pair(d["spread"], P["ppi_yoy"])
    return {
        "names": {"idx": IDX_NAME, "sec": SEC_NAME},
        "derived_order": DERIVED,
        "derived": {k: [_clean(v) for v in d[k]] for k in DERIVED},
        "stats": st,
        "scalars": {
            "spread_min": float(spread.min()) if len(spread) else None,
            "spread_min_month": months[int(spread.idxmin())] if len(spread) else None,
            "spread_max": float(spread.max()) if len(spread) else None,
            "spread_max_month": months[int(spread.idxmax())] if len(spread) else None,
            "std_cpi": _clean(float(P["cpi_yoy"].std())),
            "std_ppi": _clean(float(P["ppi_yoy"].std())),
            "r2": r ** 2 if r is not None else None,
            "idx_norm_last": _clean(float(d["idx_norm"].iloc[-1])),
            "sec_norm_last": _clean(float(d["sec_norm"].iloc[-1])),
        },
    }


def data_payload(months: list[str], P: dict) -> dict:
    return {"months": months,
            "primitives": {k: [_clean(v) for v in P[k]] for k in PRIM}}


def png_data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


# ============================================================ 样式
CSS = """
:root{
  --bg:__C_BG__; --sheet:__C_SHEET__; --card:__C_CARD__; --ink:__C_FG__; --line:__C_GRID__;
  --dim:__C_DIM__;
  --cpi:__C_CPI__; --ppi:__C_PPI__; --spread:__C_SPREAD__;
  --idx:__C_IDX__; --sec:__C_SEC__; --bond:__C_BOND__;
  --neg:__C_NEG__; --ok:__C_OK__;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--ink);line-height:1.8;font-size:16px;
  font-family:"Microsoft YaHei","PingFang SC","Noto Sans SC",sans-serif;
  padding:28px 16px 60px;display:flex;justify-content:center}
#board{width:100%;max-width:1600px;background:var(--sheet);border:1px solid var(--line);
  border-radius:14px;padding:34px 40px 46px;box-shadow:0 2px 12px rgba(16,24,40,.06)}
header{border-bottom:2px solid var(--spread);padding-bottom:22px;margin-bottom:32px}
.kicker{font-size:13.5px;letter-spacing:2px;color:var(--dim)}
h1{font-size:35px;font-weight:800;margin:10px 0 12px;letter-spacing:.5px;line-height:1.3}
h1 em{font-style:normal;color:var(--spread)}
.lede{font-size:17px;color:#3c4550;max-width:1180px;line-height:1.85}
.meta{margin-top:16px;display:flex;flex-wrap:wrap;gap:10px}
.pill{font-size:13.5px;padding:5px 14px;border-radius:20px;background:var(--card);
  border:1px solid var(--line);color:var(--dim)}
.pill b{color:var(--ink)}

h2{font-size:25px;font-weight:800;margin:48px 0 10px;padding-left:16px;border-left:5px solid var(--spread)}
h2 .n{color:var(--dim);font-weight:600;margin-right:10px}
h3{font-size:19.5px;font-weight:700;margin:30px 0 10px}
h4{font-size:17px;font-weight:700;margin:20px 0 8px}
p{font-size:16.5px;margin:12px 0;max-width:1400px}
ul,ol{margin:12px 0 12px 26px;font-size:16.5px}
li{margin:8px 0}
b,strong{color:#000;font-weight:700}
.dim{color:var(--dim)}
code,.mono{font-family:"Cascadia Mono",Consolas,"SF Mono",monospace;font-size:14px}
code{background:#eef2f7;border:1px solid #dae2ec;border-radius:5px;padding:2px 7px;color:#1a4f8a}

.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:22px 26px;margin:18px 0}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:20px 0 8px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;
  border-top:4px solid var(--spread)}
.kpi .v{font-size:31px;font-weight:800;letter-spacing:.5px;font-variant-numeric:tabular-nums}
.kpi .k{font-size:14.5px;color:#3c4550;margin-top:4px;font-weight:600}
.kpi .s{font-size:14px;color:var(--dim);margin-top:10px;line-height:1.7}
.kpi.ok{border-top-color:var(--ok)} .kpi.warn{border-top-color:var(--neg)}
.kpi.neutral{border-top-color:var(--bond)}

table{width:100%;border-collapse:collapse;margin:16px 0;font-size:15px}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--dim);font-weight:700;font-size:14px;letter-spacing:.4px;background:#f1f4f8}
tbody tr:hover{background:#f7f9fc}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr.grp td{background:#eaeff6;color:var(--spread);font-weight:700;font-size:14px;letter-spacing:.6px}
tr.bad td{background:#fdeaea}
.tbl-wrap{overflow-x:auto}

.fig{margin:20px 0 8px;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff}
.fig img{display:block;width:100%;height:auto}
.cap{font-size:14px;color:var(--dim);margin:10px 0 24px;line-height:1.75}

.panelnote{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--ppi);
  border-radius:10px;padding:16px 20px;margin:14px 0}
.panelnote h4{margin-top:0;font-size:17px}
.panelnote .lbl{color:#3c4550;font-size:15px;font-weight:700}
.warnbox{background:#fdf3f3;border:1px solid #f2c9c9;border-left:5px solid var(--neg);
  border-radius:10px;padding:18px 22px;margin:16px 0}
.warnbox h4{margin-top:0;color:#a52525;font-size:17px}
.okbox{background:#f1f9f3;border:1px solid #c6e6cf;border-left:5px solid var(--ok);
  border-radius:10px;padding:18px 22px;margin:16px 0}

.formula{background:#f8fafc;border:1px solid var(--line);border-radius:10px;padding:16px 20px;margin:14px 0;
  font-family:"Cascadia Mono",Consolas,monospace;font-size:15px;color:#1f2937;overflow-x:auto;
  white-space:pre-wrap;line-height:1.9}
.formula .c{color:#8b95a1}
pre{background:#f8fafc;border:1px solid var(--line);border-radius:10px;padding:16px 20px;margin:14px 0;
  overflow-x:auto;font-family:"Cascadia Mono",Consolas,monospace;font-size:14px;color:#1f2937;line-height:1.8}
details{margin:14px 0;border:1px solid var(--line);border-radius:10px;background:var(--card)}
summary{cursor:pointer;padding:14px 20px;font-size:16px;font-weight:700;color:var(--spread)}
summary:hover{background:#eef2f7}
details pre{margin:0;border:0;border-top:1px solid var(--line);border-radius:0}

.verdict{font-weight:800}
.verdict.ok{color:var(--ok)} .verdict.fail{color:var(--neg)}
footer{margin-top:52px;padding-top:22px;border-top:1px solid var(--line);
  font-size:14px;color:var(--dim);line-height:1.8}
@media (max-width:1180px){.cards{grid-template-columns:repeat(2,1fr)}}
@media (max-width:640px){.cards{grid-template-columns:1fr}}
"""


# ============================================================ 正文

def _script_json(data) -> str:
    """序列化脚本内的数据，不让文本被 HTML 解析为标签。"""
    return json.dumps(data, ensure_ascii=True, allow_nan=False).translate(
        str.maketrans({"<": r"\u003c", ">": r"\u003e", "&": r"\u0026"}))


def _number(value, fmt="+.3f") -> str:
    try:
        v = float(value)
    except (ValueError, TypeError):
        return "不可用"
    return format(v, fmt) if math.isfinite(v) else "不可用"


def _table(headers, rows) -> str:
    head = "".join(f'<th scope="col">{escape(str(v))}</th>' for v in headers)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in row) + "</tr>"
                   for row in rows)
    return f'<div class="tbl-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def build_html(months, P, d, exp, data, imgs: dict[str, str], other: dict | None = None,
               monthly_schema: str | None = None) -> str:
    css = CSS
    for key, value in (("BG", BG), ("CARD", CARD), ("FG", FG), ("GRID", GRID),
                       ("SHEET", SHEET), ("DIM", DIM), ("CPI", C_CPI), ("PPI", C_PPI),
                       ("SPREAD", C_SPREAD), ("IDX", C_IDX), ("SEC", C_SEC),
                       ("BOND", C_BOND), ("NEG", C_NEG), ("OK", C_OK)):
        css = css.replace("__C_" + key + "__", value)
    idx, sec = escape(str(IDX_NAME)), escape(str(SEC_NAME))
    first, last = escape(str(months[0])), escape(str(months[-1]))
    count = int(d["spread"].notna().sum())
    h = [f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CPI-PPI 剪刀差与股债相关性</title><style>{css}</style></head><body><div id="board">
<header><div class="kicker">quant-chart · 宏观相关性分析</div>
<h1>CPI-PPI 剪刀差 <em>与股债相关性</em></h1>
<p class="lede">样本 {first} – {last}。对照{idx}、{sec}与10年国债，分别检验水平、月度变化和12个月变化口径。</p>
<div class="meta"><span class="pill">日历月 <b>{len(months)}</b></span>
<span class="pill">有效剪刀差 <b>{count}</b> 月</span>
<span class="pill">页面内复算 <b id="chk-status" role="status">待运行</b></span></div></header>"""]
    main_stats = [r for r in exp["stats"] if r["role"] == "剪刀差"]
    h.append("<h2>本次数据摘要</h2>")
    h.append(_table(("口径", "市场变量", "样本数", "Pearson r", "p 值", "Spearman ρ"),
                    ((r["tag"], r["label"], r["n"], _number(r["r"]),
                      _number(r["p"], ".3g"), _number(r["rs"])) for r in main_stats)))
    h.append(f"""<p>CPI 同比样本标准差 {_number(exp["scalars"]["std_cpi"], ".2f")} pp，PPI 为
{_number(exp["scalars"]["std_ppi"], ".2f")} pp。剪刀差与 PPI 的样本相关平方为
{_number(exp["scalars"]["r2"], ".1%")}，不表示因果贡献。</p>
<h2>数据与方法</h2><p>剪刀差为 CPI 同比减 PPI 同比。指数和国债使用日历月末最后有效值，
变化与收益率按相隔 1 或 12 个日历月的端点计算，不填充缺失值。相关系数按成对有效观测计算，
常规 Pearson p 值未校正序列相关或多重比较，不用它单独判断择时价值。</p>""")
    if count != len(months):
        h.append("<p>样本含缺月，缺失值未填充。</p>")
    if monthly_schema != "calendar-v1":
        h.append("<p><strong>历史图表口径未验证。</strong>下列图来自旧版或未标记的分析产物，可能压缩了缺月。"
                 "请重跑分析脚本后再与本页复算比较。</p>")
    notes = ["对照 CPI、PPI、剪刀差和指数。指数走势归一化只用于展示。",
             "比较水平、变化、领先滞后及滚动相关。滞后单位为日历月，数据发布时间与观测月份不同。",
             "分别展示 CPI、PPI 和剪刀差与市场的同期相关。"]
    for (key, label), note in zip(FIGS, notes):
        src = imgs[key]
        if not src.startswith("data:image/png;base64,"):
            raise ValueError("图表必须是 PNG 数据 URI")
        h.append(f'<figure><img alt="{label}" src="{escape(src, quote=True)}"><figcaption>{label} · {note}</figcaption></figure>')
    h.append("<h2>成分拆解</h2>")
    h.append(_table(("口径", "成分", "市场变量", "样本数", "Pearson r"),
                    ((r["tag"], r["role"], r["label"], r["n"], _number(r["r"])) for r in exp["stats"])))
    if other:
        h.append(build_compare_sec(compare_payload(OUT), other))
    h.append(f"""<h2 id="sec8">页面内复算</h2><p>校验只覆盖内嵌数据和计算，不验证历史图像、外部数据或解读。</p><p id="chk-summary">尚未运行。</p>
<div class="tbl-wrap"><table><thead><tr><th>项目</th><th>期望</th><th>复算</th><th>状态</th></tr></thead>
<tbody id="chk-body"></tbody></table></div>
<footer><p>数据输入为此运行的月度分析产物。相关不等于因果。</p></footer></div>
<script>
const __DATA__ = {_script_json(data)};
const __EXP__ = {_script_json(exp)};
{JS_MATH}
{JS_CHECK}
</script></body></html>""")
    return "\n".join(h)


def compare_payload(other: Path) -> dict | None:
    """读另一版本的主指数统计，不把本机目录带进页面。"""
    if not (other / "corr_level.csv").exists():
        return None
    meta = other / "meta.json"
    md = json.loads(meta.read_text(encoding="utf-8")) if meta.is_file() else {}
    out = {"name": md.get("index_name", other.name), "symbol": md.get("index_symbol", "?"),
           "schema": md.get("monthly_schema"), "stats": {}}
    for label, stem in (("水平", "level"), ("月度变化", "change"), ("12个月变化", "change12")):
        f = other / f"corr_{stem}.csv"
        if f.exists():
            df = pd.read_csv(f, encoding="utf-8-sig")
            sub = df[df["区间"] == "全样本"]
            if not sub.empty:
                out["stats"][label] = sub.iloc[0]
    return out


def build_compare_sec(cur: dict | None, other: dict | None) -> str:
    if not cur or not other:
        return ""
    if cur.get("schema") != "calendar-v1" or other.get("schema") != "calendar-v1":
        return "<h2>与另一版本对照</h2><p>两版未确认使用同一月历口径。请用当前分析脚本重跑后再比较。</p>"
    rows = []
    for label in ("水平", "月度变化", "12个月变化"):
        row = [label]
        for result in (cur, other):
            values = result["stats"].get(label)
            row.extend((_number(values["Pearson"]), values["n"]) if values is not None else ("不可用", "不可用"))
        rows.append(row)
    a, b = (f'{r["name"]}（{r["symbol"]}）' for r in (cur, other))
    return ("<h2>与另一版本对照</h2><p>两版的输入和样本可能不同，不把差异自动归因于主指数切换。</p>"
            + _table(("口径", a + " Pearson r", "样本数", b + " Pearson r", "样本数"), rows))


# ============================================================ 自检
SELFTEST_DRIVER = r"""
import { readFileSync } from 'node:fs';
const SRC = readFileSync(process.argv[2], 'utf8');
const fx = JSON.parse(readFileSync(process.argv[3], 'utf8'));
const mod = await import('data:text/javascript;base64,' + Buffer.from(SRC).toString('base64'));
const M = mod.default;
const P = fx.primitives, N = fx.months.length;

// 与页面 JS_CHECK 同一套实现
const derived = M.deriveAll(P);
const dv = derived.dv, spread = derived.spread;
const sc = M.computeScalars(P);

let checks = 0, fails = 0;
const note = (m) => console.log('  ✗ ' + m);
const same = (a, b, tol) => b === null ? !Number.isFinite(a) : Number.isFinite(a) && Math.abs(a - b) <= tol;
const relOk = (a, b) => {
  if (a === null && b === null) return true;
  if (typeof a === 'number' && typeof b === 'number') return Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(b));
  return false;
};
for (const col of fx.derived_order) for (let i = 0; i < N; i++) {
  checks++;
  if (!relOk(dv[col][i], fx.derived[col][i])) { fails++; if (fails < 6) note('derived ' + col + ' @' + fx.months[i]); }
}
for (const s of fx.stats) {
  const got = M.statPair(M.pick(dv, P, s.a), M.pick(dv, P, s.b));
  checks += 4;
  if (!same(got.r, s.r, 1e-9)) { fails++; note('r  ' + s.a + '~' + s.b + ' js=' + got.r + ' exp=' + s.r); }
  if (!same(got.p, s.p, 1e-12)) { fails++; note('p  ' + s.a + '~' + s.b + ' js=' + got.p + ' exp=' + s.p); }
  if (!same(got.rho, s.rs, 1e-9)) { fails++; note('ρ  ' + s.a + '~' + s.b + ' js=' + got.rho + ' exp=' + s.rs); }
  if (got.n !== s.n) { fails++; note('n  ' + s.a + '~' + s.b + ' js=' + got.n + ' exp=' + s.n); }
}
const scal = [['spread_min', sc.spread_min, fx.scalars.spread_min],
              ['spread_max', sc.spread_max, fx.scalars.spread_max],
              ['std_cpi', sc.std_cpi, fx.scalars.std_cpi],
              ['std_ppi', sc.std_ppi, fx.scalars.std_ppi],
              ['r2', sc.r2, fx.scalars.r2],
              ['idx_norm_last', dv.idx_norm[N - 1], fx.scalars.idx_norm_last],
              ['sec_norm_last', dv.sec_norm[N - 1], fx.scalars.sec_norm_last]];
for (const [name, got, exp] of scal) {
  checks++;
  if (!same(got, exp, 1e-9 * Math.max(1, Math.abs(exp)))) { fails++; note('scalar ' + name + ' js=' + got + ' exp=' + exp); }
}
checks += 2;
if ((fx.months[sc.spread_min_idx] ?? null) !== fx.scalars.spread_min_month) { fails++; note('spread_min 所在月'); }
if ((fx.months[sc.spread_max_idx] ?? null) !== fx.scalars.spread_max_month) { fails++; note('spread_max 所在月'); }

console.log(JSON.stringify({ checks, fails }));
"""


def selftest(months, P, d, exp) -> int:
    """把内嵌的 JS_MATH 抽出来喂给 node，与 pandas+scipy 期望值逐项对账。

    注意：驱动脚本调用的是页面同一套 deriveAll/statPair/computeScalars，
    因此这条自检覆盖的是页面真正执行的代码路径，而不是它的平行复刻。
    """
    tmp = Path(tempfile.mkdtemp(prefix="cpippi_selftest_"))
    try:
        (tmp / "math.mjs").write_text(
            JS_MATH + "\nexport default {pairs, pearson, spearman, pFromR, std, rankArr,"
                      " ibeta, gammaln, deriveAll, pick, statOf, statPair, computeScalars};\n",
            encoding="utf-8")
        (tmp / "driver.mjs").write_text(SELFTEST_DRIVER, encoding="utf-8")
        (tmp / "fixture.json").write_text(json.dumps({
            "months": months,
            "primitives": {k: [_clean(v) for v in P[k]] for k in PRIM},
            "derived": exp["derived"], "derived_order": exp["derived_order"],
            "stats": exp["stats"], "scalars": exp["scalars"]},
            ensure_ascii=False), encoding="utf-8")
        print("[selftest] 用内嵌 JS 复算，与 pandas+scipy 对账…")
        r = subprocess.run(["node", str(tmp / "driver.mjs"), str(tmp / "math.mjs"),
                            str(tmp / "fixture.json")],
                           capture_output=True, text=True, encoding="utf-8", timeout=180)
        if r.returncode != 0:
            print(r.stdout or "", r.stderr or "")
            print(f"[selftest] 失败：node 退出码 {r.returncode}")
            return 1
        print(r.stdout.strip())
        last = [ln for ln in r.stdout.strip().splitlines() if ln.startswith("{")][-1]
        res = json.loads(last)
        ok = res["fails"] == 0
        print(f"[selftest] {'PASS' if ok else 'FAIL'}：{res['checks']} 项检查，失败 {res['fails']} 项")
        return 0 if ok else 1
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================ main
def main():
    global OUT, SERIES, IDX_SYM, IDX_NAME, SEC_SYM, SEC_NAME
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true",
                    help="仅用内嵌 JS 重验对齐 pandas/scipy（需 node），不写报告")
    ap.add_argument("--indir", default=str(OUT),
                    help="分析产出目录（含 meta.json / CSV / PNG），默认 outputs/cpi_ppi")
    ap.add_argument("-o", "--output", default=None,
                    help="输出 HTML 路径，默认 <indir>/report.html")
    ap.add_argument("--compare", default=None,
                    help="另一版本目录（含 corr_*.csv），用于追加 §10 主指数对比，如 outputs/cpi_ppi")
    args = ap.parse_args()

    OUT = Path(args.indir)
    SERIES = OUT / "series_monthly.csv"
    meta_p = OUT / "meta.json"
    meta = {}
    if meta_p.exists():
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        IDX_SYM = meta.get("index_symbol", IDX_SYM)
        IDX_NAME = meta.get("index_name", IDX_NAME)
        SEC_SYM = meta.get("secondary_symbol", SEC_SYM)
        SEC_NAME = meta.get("secondary_name", SEC_NAME)
    else:
        print(f"[提示] 未找到 {meta_p}，沿用默认名称 {IDX_NAME} / {SEC_NAME}"
              "（先跑 analyze_cpi_ppi.py 会写出 meta.json）")
    out = Path(args.output) if args.output else OUT / "report.html"
    print(f"主指数：{IDX_NAME}({IDX_SYM})　次指数：{SEC_NAME}({SEC_SYM})")

    if not SERIES.exists():
        sys.exit(f"缺少 {SERIES}，请先运行 python tools/analyze_cpi_ppi.py")
    months, P, d = build_panel()
    exp = expected_payload(months, P, d)
    data = data_payload(months, P)

    if args.selftest:
        sys.exit(selftest(months, P, d, exp))

    missing = [n for n, _ in FIGS if not (OUT / n).exists()]
    if missing:
        sys.exit(f"缺少图片 {missing}，请先运行 python tools/analyze_cpi_ppi.py")
    imgs = {n: png_data_uri(OUT / n) for n, _ in FIGS}
    other = compare_payload(Path(args.compare)) if args.compare else None

    html = build_html(months, P, d, exp, data, imgs, other, monthly_schema=meta.get("monthly_schema"))
    out.write_text(html, encoding="utf-8")
    print(f"报告已生成：{out}")
    print(f"  体积 {out.stat().st_size / 1024 / 1024:.2f} MB"
          f"（其中内嵌图片 {sum(len(v) for v in imgs.values()) / 1024 / 1024:.2f} MB）")
    print(f"  内嵌原始列 6 列 × {len(months)} 行；校验项 {len(exp['stats']) + 8} 条（{len(exp['stats'])} 相关 + 派生链 + 6 标量 + R²）")
    print(f"  自检：python tools/build_cpi_ppi_report.py --selftest")


if __name__ == "__main__":
    main()
