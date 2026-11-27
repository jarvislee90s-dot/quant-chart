"""CPI-PPI 剪刀差 与 股债相关性分析（2020-01 起，月度）。

口径：
  剪刀差 spread = CPI同比(%) - PPI同比(%)         单位：百分点
  股：主指数（默认 000300 沪深300；--index/--index-name 可换成上证指数等）+ 中证500(000905)
      月末收盘，另算月度收益率
  债：10年国债到期收益率(%) 月末最后有效值，另算月度变化(百分点)

用法:
  python tools/analyze_cpi_ppi.py              # 用缓存，缺则联网取
  python tools/analyze_cpi_ppi.py --refresh    # 强制重新取数

依赖：pandas、numpy、scipy、matplotlib。缓存不足或刷新时还需要 akshare、local-datasource 和网络。

产出（outputs/cpi_ppi/）:
  raw/*.csv            原始序列（日频/月频，未对齐）
  series_monthly.csv   对齐后的月度面板
  corr_level.csv       水平值相关（全样本 + 子区间）
  corr_change.csv      月度变化相关（全样本 + 子区间）
  corr_change12.csv    12个月变化相关（去趋势鲁棒性检验）
  corr_decompose.csv   成分分解（CPI腿 / PPI腿 / 剪刀差 各自与市场的相关）
  corr_lag.csv         领先/滞后互相关（-3..+3 月）
  rolling_corr.csv     24 个月滚动相关
  fig01_trend.png      走势图（三面板）
  fig02_correlation.png 相关性分析（四面板）
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats as _st

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cpi_ppi"
RAW = OUT / "raw"

START_DATE = "2020-01-01"
INDEX_END = "2026-12-31"
Y10_FROM = "20200101"

# 指数槽位：V1 = 沪深300，V2 = 上证指数（由 CLI 覆盖；名称参与 CSV 标签与图例）
IDX_SYM, IDX_NAME = "000300", "沪深300"
SEC_SYM, SEC_NAME = "000905", "中证500"
_DEFAULT_NAMES = {"000300": "沪深300", "000905": "中证500", "000001": "上证指数",
                  "399001": "深证成指", "399006": "创业板指", "000852": "中证1000",
                  "000016": "上证50", "000688": "科创50"}


def idn(suffix: str = "") -> str:
    """主指数显示名：idn("(点位)") -> "沪深300(点位)"。"""
    return f"{IDX_NAME}{suffix}"


def sdn(suffix: str = "") -> str:
    """次指数（中证500）显示名。"""
    return f"{SEC_NAME}{suffix}"

# 子区间：按宏观 regime 划分
SUB_PERIODS = [
    ("2020-21 疫情放水/再通胀", "2020-01", "2021-12"),
    ("2022-23 通缩压力", "2022-01", "2023-12"),
    ("2024-26 最新regime", "2024-01", "2026-12"),
]

# 浅色研报风格配色
BG = "#ffffff"
FG = "#16191d"
GRID = "#dde2e8"
C_CPI = "#d9480f"
C_PPI = "#1971c2"
C_SPREAD = "#6d28d9"
C_IDX = "#c92a2a"      # 主指数（V1 沪深300 / V2 上证指数）
C_SEC = "#2f9e44"      # 次指数（中证500）
C_BOND = "#0b7285"
C_NEG_FILL = "#e03131"      # 剪刀差负值填充（浅色调）
# 变化口径柱色（浅一号，用于图二分区间对比）
C_IDX_L = "#f0a3a3"
C_SEC_L = "#8ccf95"
C_BOND_L = "#6fb3bf"

matplotlib.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DengXian", "sans-serif"],
    "axes.unicode_minus": False,
    "figure.facecolor": BG,
    "axes.facecolor": BG,
    "savefig.facecolor": BG,
    "text.color": FG,
    "axes.labelcolor": FG,
    "xtick.color": FG,
    "ytick.color": FG,
    "axes.edgecolor": GRID,
    "grid.color": GRID,
    "font.size": 10,
})



# ---------------------------------------------------------------- 取数
def _fetch_cpi_ppi() -> tuple[pd.DataFrame, pd.DataFrame]:
    import akshare as ak
    cpi = ak.macro_china_cpi()[["月份", "全国-同比增长"]].copy()
    ppi = ak.macro_china_ppi()[["月份", "当月同比增长"]].copy()
    cpi.to_csv(RAW / "cpi_raw.csv", index=False, encoding="utf-8-sig")
    ppi.to_csv(RAW / "ppi_raw.csv", index=False, encoding="utf-8-sig")
    return cpi, ppi


def _fetch_y10() -> pd.DataFrame:
    import akshare as ak
    df = ak.bond_zh_us_rate(start_date=Y10_FROM)
    df = df[["日期", "中国国债收益率10年"]].copy()
    df.to_csv(RAW / "y10_raw.csv", index=False, encoding="utf-8-sig")
    return df


def _fetch_index(symbol: str) -> pd.DataFrame:
    from local_datasource.providers.index import query_index
    path, _ = query_index(symbol=symbol, period="daily",
                          start_date=START_DATE, end_date=INDEX_END,
                          file_path=str(RAW / f"idx_{symbol}_raw.csv"))
    return pd.read_csv(path, encoding="utf-8-sig")


def fetch_all(refresh: bool) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    need = lambda n: refresh or not (RAW / n).exists()
    if need("cpi_raw.csv") or need("ppi_raw.csv"):
        print("[fetch] CPI/PPI (akshare macro_china_cpi / macro_china_ppi)")
        _fetch_cpi_ppi()
    if need("y10_raw.csv"):
        print("[fetch] 10年国债收益率 (akshare bond_zh_us_rate)")
        _fetch_y10()
    for sym in (IDX_SYM, SEC_SYM):
        if need(f"idx_{sym}_raw.csv"):
            print(f"[fetch] 指数 {sym} (local_datasource query_index)")
            _fetch_index(sym)


# ---------------------------------------------------------------- 月度对齐
def _parse_cn_month(s: pd.Series) -> pd.PeriodIndex:
    """'2026年09月份' -> PeriodIndex('M')"""
    return pd.PeriodIndex(
        pd.to_datetime(s.str.replace("年", "-").str.replace("月份", "", regex=False),
                       format="%Y-%m"),
        freq="M")


def build_monthly() -> pd.DataFrame:
    cpi = pd.read_csv(RAW / "cpi_raw.csv", encoding="utf-8-sig")
    ppi = pd.read_csv(RAW / "ppi_raw.csv", encoding="utf-8-sig")
    y10 = pd.read_csv(RAW / "y10_raw.csv", encoding="utf-8-sig")

    m = pd.DataFrame(index=pd.period_range("2020-01", "2026-12", freq="M"))
    m.index.name = "month"

    c = pd.DataFrame({"cpi_yoy": cpi["全国-同比增长"].to_numpy()},
                     index=_parse_cn_month(cpi["月份"]))
    p = pd.DataFrame({"ppi_yoy": ppi["当月同比增长"].to_numpy()},
                     index=_parse_cn_month(ppi["月份"]))
    m = m.join(c).join(p)

    y10["日期"] = pd.to_datetime(y10["日期"])
    y = y10.dropna(subset=["中国国债收益率10年"]).set_index("日期")["中国国债收益率10年"]
    m["y10"] = y.resample("ME").last().to_period("M")

    for sym, col in ((IDX_SYM, "idx"), (SEC_SYM, "sec")):
        df = pd.read_csv(RAW / f"idx_{sym}_raw.csv", encoding="utf-8-sig")
        df["date"] = pd.to_datetime(df["date"])
        m[col] = df.set_index("date")["close"].resample("ME").last().to_period("M")

    # 样本止于最后一个 CPI、PPI 都可用的月份。保留内部缺月，确保位移是日历月。
    m["spread"] = m["cpi_yoy"] - m["ppi_yoy"]
    first, last = m["spread"].first_valid_index(), m["spread"].last_valid_index()
    if first is None:
        raise ValueError("没有 CPI 与 PPI 均可用的月份")
    m = m.loc[first:last].copy()

    # 变化量口径（月度）
    m["d_spread"] = m["spread"].diff()
    m["d_cpi"] = m["cpi_yoy"].diff()
    m["d_ppi"] = m["ppi_yoy"].diff()
    m["idx_ret"] = m["idx"].pct_change(fill_method=None) * 100
    m["sec_ret"] = m["sec"].pct_change(fill_method=None) * 100
    m["d_y10"] = m["y10"].diff()                        # 百分点

    # 变化量口径（12个月）：去掉长期趋势、保留中期结构，作鲁棒性检验
    m["d12_spread"] = m["spread"].diff(12)
    m["d12_cpi"] = m["cpi_yoy"].diff(12)
    m["d12_ppi"] = m["ppi_yoy"].diff(12)
    m["idx_ret12"] = m["idx"].pct_change(12, fill_method=None) * 100
    m["sec_ret12"] = m["sec"].pct_change(12, fill_method=None) * 100
    m["d12_y10"] = m["y10"].diff(12)

    # 归一化（首月=100）
    for col in ("idx", "sec"):
        base = m[col].dropna().iloc[0]
        m[f"{col}_norm"] = m[col] / base * 100

    m.to_csv(OUT / "series_monthly.csv", encoding="utf-8-sig")
    return m


# ---------------------------------------------------------------- 统计
def _corr(a: pd.Series, b: pd.Series, method: str = "pearson") -> tuple[float, float, int]:
    """返回 (r, p, n)。n<4 或零方差时 p 记 nan。"""
    both = pd.concat([a, b], axis=1).dropna()
    n = len(both)
    if n < 4 or both.iloc[:, 0].nunique() < 2 or both.iloc[:, 1].nunique() < 2:
        return np.nan, np.nan, n
    r = both.iloc[:, 0].corr(both.iloc[:, 1], method=method)
    if method == "pearson":
        p = _st.pearsonr(both.iloc[:, 0], both.iloc[:, 1])[1]
    else:
        p = _st.spearmanr(both.iloc[:, 0], both.iloc[:, 1])[1]
    return r, p, n


def sig_mark(p: float) -> str:
    if pd.isna(p):
        return "  -"
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "n.s."


# 三个口径：(标签, 剪刀差列, 市场列[名称,列], 输出文件)
# 注意：必须是函数而非模块级常量——显示名依赖 IDX_NAME，模块级会在 main() 覆盖前就冻结。
def _specs():
    return [
        ("level", "spread",
         [(idn("(点位)"), "idx"), (sdn("(点位)"), "sec"), ("10年国债收益率(%)", "y10")],
         "corr_level.csv"),
        ("change", "d_spread",
         [(idn("(月收益率%)"), "idx_ret"), (sdn("(月收益率%)"), "sec_ret"),
          ("10年国债(月变化pp)", "d_y10")],
         "corr_change.csv"),
        ("change12", "d12_spread",
         [(idn("(12月收益率%)"), "idx_ret12"), (sdn("(12月收益率%)"), "sec_ret12"),
          ("10年国债(12月变化pp)", "d12_y10")],
         "corr_change12.csv"),
    ]


def corr_tables(m: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """三个口径的相关（全样本 + 子区间），Pearson/Spearman 与 p 值并列。

    level   : 剪刀差水平 vs 市场水平       —— 会被共同趋势放大
    change  : Δ剪刀差 vs 市场月度变化      —— 增量信息，噪音大
    change12: 12个月变化 vs 12个月变化     —— 去掉长期趋势但保留中期结构（鲁棒性检验）
    """
    tables: dict[str, pd.DataFrame] = {}
    period_defs = [("全样本", None, None)] + SUB_PERIODS
    for tag, xcol, targets, fname in _specs():
        rows = []
        for label, lo, hi in period_defs:
            sub = m if lo is None else m[(m.index >= pd.Period(lo, "M")) &
                                        (m.index <= pd.Period(hi, "M"))]
            for name, col in targets:
                r_p, p_p, n = _corr(sub[xcol], sub[col], "pearson")
                r_s, _, _ = _corr(sub[xcol], sub[col], "spearman")
                rows.append({"区间": label, "市场变量": name, "n": n,
                             "Pearson": r_p, "p值": p_p, "显著性": sig_mark(p_p),
                             "Spearman": r_s})
        t = pd.DataFrame(rows)
        t.to_csv(OUT / fname, index=False, encoding="utf-8-sig")
        tables[tag] = t
    return tables



def lag_table(m: pd.DataFrame, max_lag: int = 3) -> pd.DataFrame:
    """领先/滞后互相关。

    lag = k 表示：剪刀差[t] 与 市场[t+k] 的相关。
      k > 0 → 剪刀差**领先**市场 k 个月
      k < 0 → 剪刀差**滞后**市场 |k| 个月
    """
    rows = []
    series = [(idn("(点位)"), "idx", "level"), (sdn("(点位)"), "sec", "level"),
              ("10年国债收益率(%)", "y10", "level"),
              (idn("(月收益率%)"), "idx_ret", "change"),
              (sdn("(月收益率%)"), "sec_ret", "change"),
              ("10年国债(月变化pp)", "d_y10", "change")]
    for name, col, kind in series:
        x = m["spread"] if kind == "level" else m["d_spread"]
        for k in range(-max_lag, max_lag + 1):
            r, _p, n = _corr(x, m[col].shift(-k))
            rows.append({"市场变量": name, "口径": kind, "lag": k, "n": n, "corr": r})
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "corr_lag.csv", index=False, encoding="utf-8-sig")
    return t


def rolling_table(m: pd.DataFrame, window: int = 24) -> pd.DataFrame:
    """滚动 window 个月相关（水平值与变化值）。"""
    r = pd.DataFrame(index=m.index)
    for name, col in ((IDX_NAME, "idx"), (SEC_NAME, "sec"), ("10年国债", "y10")):
        r[f"{name}_level"] = m["spread"].rolling(window).corr(m[col])
    for name, col in ((IDX_NAME, "idx_ret"), (SEC_NAME, "sec_ret"),
                      ("10年国债", "d_y10")):
        r[f"{name}_change"] = m["d_spread"].rolling(window).corr(m[col])
    r.to_csv(OUT / "rolling_corr.csv", encoding="utf-8-sig")
    return r


def decompose(m: pd.DataFrame) -> pd.DataFrame:
    """成分分解：把「剪刀差 vs 市场」拆成 CPI 腿 / PPI 腿 / 剪刀差 三条相关。

    动机：spread = CPI - PPI，若 CPI 本身没有波动，剪刀差就只是 PPI 的镜像，
    此时「剪刀差与股市相关」实际是「PPI 与股市相关」——不拆开就会误判机制。
    """
    specs = [
        ("水平", "cpi_yoy", "ppi_yoy", "spread",
         [(idn("(点位)"), "idx"), (sdn("(点位)"), "sec"), ("10年国债收益率(%)", "y10")]),
        ("月度变化", "d_cpi", "d_ppi", "d_spread",
         [(idn("(月收益率%)"), "idx_ret"), (sdn("(月收益率%)"), "sec_ret"),
          ("10年国债(月变化pp)", "d_y10")]),
        ("12个月变化", "d12_cpi", "d12_ppi", "d12_spread",
         [(idn("(12月收益率%)"), "idx_ret12"), (sdn("(12月收益率%)"), "sec_ret12"),
          ("10年国债(12月变化pp)", "d12_y10")]),
    ]
    rows = []
    for tag, ccol, pcol, scol, targets in specs:
        for name, mcol in targets:
            r_c, p_c, n = _corr(m[ccol], m[mcol])
            r_p, p_p, _ = _corr(m[pcol], m[mcol])
            r_s, p_s, _ = _corr(m[scol], m[mcol])
            rows.append({"口径": tag, "市场变量": name, "n": n,
                         "CPI腿": r_c, "CPI_p": p_c, "CPI显著性": sig_mark(p_c),
                         "PPI腿": r_p, "PPI_p": p_p, "PPI显著性": sig_mark(p_p),
                         "剪刀差": r_s, "剪刀差_p": p_s, "剪刀差显著性": sig_mark(p_s)})
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "corr_decompose.csv", index=False, encoding="utf-8-sig")
    return t


# ---------------------------------------------------------------- 绘图
def _style(ax, title: str | None = None):
    ax.grid(True, alpha=0.9, linewidth=0.6)
    ax.set_axisbelow(True)
    if title:
        ax.set_title(title, color=FG, fontsize=11, pad=8, loc="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def _ordinals(idx: pd.PeriodIndex) -> np.ndarray:
    """PeriodIndex -> 单调整数轴（Period.ordinal，可直接当 matplotlib x 用）。"""
    return np.array([p.ordinal for p in idx], dtype=float)


def _xaxis_months(ax, m: pd.DataFrame, step: int = 6):
    o = _ordinals(m.index)
    ax.set_xlim(o[0] - 1, o[-1] + 1)
    ticks = [p.ordinal for p in m.index if p.month % step == 1]
    ax.set_xticks(ticks)
    ax.set_xticklabels([p.strftime("%Y") if p.month == 1 else p.strftime("%Y-%m")
                        for p in m.index if p.month % step == 1], fontsize=8)


def plot_trend(m: pd.DataFrame, roll: pd.DataFrame, path: Path):
    x = _ordinals(m.index)
    fig, axes = plt.subplots(3, 1, figsize=(15, 12), sharex=True,
                             gridspec_kw={"height_ratios": [1.15, 1.15, 1.0], "hspace": 0.16})

    ax = axes[0]
    ax.axhline(0, color=FG, linewidth=0.8, alpha=0.45)
    ax.plot(x, m["spread"], color=C_SPREAD, linewidth=2.6, marker="o", markersize=3,
            label="CPI-PPI 剪刀差（百分点）", zorder=5)
    ax.plot(x, m["cpi_yoy"], color=C_CPI, linewidth=1.6, alpha=0.9, label="CPI 同比 %")
    ax.plot(x, m["ppi_yoy"], color=C_PPI, linewidth=1.6, alpha=0.9, label="PPI 同比 %")
    ax.fill_between(x, 0, m["spread"], where=m["spread"] >= 0, color=C_SPREAD, alpha=0.12)
    ax.fill_between(x, 0, m["spread"], where=m["spread"] < 0, color=C_NEG_FILL, alpha=0.12)
    _style(ax, "① 物价：CPI / PPI 同比 与 CPI-PPI 剪刀差")
    ax.set_ylabel("% / 百分点")
    ax.legend(loc="upper right", framealpha=0.9, fontsize=9)

    ax = axes[1]
    ax.plot(x, m["idx_norm"], color=C_IDX, linewidth=1.8, label=f"{IDX_NAME}（2020-01=100）")
    ax.plot(x, m["sec_norm"], color=C_SEC, linewidth=1.8, label=f"{SEC_NAME}（2020-01=100）")
    ax.set_ylabel("归一化指数")
    _style(ax, f"② 股债：{IDX_NAME} / {SEC_NAME} 归一化走势 与 10年国债收益率")
    ax2 = ax.twinx()
    ax2.plot(x, m["y10"], color=C_BOND, linewidth=1.7, linestyle="--", alpha=0.9,
             label="10年国债收益率 %（右轴，上行=债价下跌）")
    ax2.set_ylabel("10年国债收益率 %", color=C_BOND)
    ax2.tick_params(axis="y", colors=C_BOND)
    for s in ("top", "left"):
        ax2.spines[s].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", framealpha=0.9, fontsize=9)


    ax = axes[2]
    ax.axhline(0, color=FG, linewidth=0.8, alpha=0.45)
    for col, c, lab in ((f"{IDX_NAME}_level", C_IDX, f"剪刀差 vs {IDX_NAME}（水平）"),
                        (f"{SEC_NAME}_level", C_SEC, f"剪刀差 vs {SEC_NAME}（水平）"),
                        ("10年国债_level", C_BOND, "剪刀差 vs 10年国债（水平）"),
                        (f"{IDX_NAME}_change", C_IDX, f"Δ剪刀差 vs {IDX_NAME}月收益率"),
                        (f"{SEC_NAME}_change", C_SEC, f"Δ剪刀差 vs {SEC_NAME}月收益率"),
                        ("10年国债_change", C_BOND, "Δ剪刀差 vs Δ10年国债")):
        ls = "-" if col.endswith("level") else ":"
        ax.plot(x, roll[col], color=c, linewidth=1.9 if ls == "-" else 1.3,
                linestyle=ls, alpha=0.95 if ls == "-" else 0.8, label=lab)
    for y in (0.5, -0.5):
        ax.axhline(y, color=FG, linewidth=0.7, alpha=0.3, linestyle="--")
    _style(ax, "③ 24个月滚动相关系数（实线=水平口径，点线=变化口径）")
    ax.set_ylabel("滚动相关系数")
    ax.set_ylim(-1.05, 1.05)
    ax.legend(loc="lower left", framealpha=0.9, fontsize=8, ncol=3)

    _xaxis_months(ax, m, step=6)
    fig.suptitle("CPI-PPI 剪刀差 与 股债相关性（2020-01 起，月度）",
                 color=FG, fontsize=14, y=0.955)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def plot_corr(m: pd.DataFrame, tables: dict[str, pd.DataFrame],
              lag: pd.DataFrame, roll: pd.DataFrame, path: Path):
    lv, ch, t12 = tables["level"], tables["change"], tables["change12"]
    fig = plt.figure(figsize=(15, 11))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 0.95], hspace=0.28, wspace=0.22)

    # (a) 全样本相关矩阵（水平 + 变化）
    ax = fig.add_subplot(gs[0, 0])
    cols = {"spread": "剪刀差", "cpi_yoy": "CPI同比", "ppi_yoy": "PPI同比",
            "idx": IDX_NAME, "sec": SEC_NAME, "y10": "10年国债",
            "idx_ret": f"{IDX_NAME}月收益", "sec_ret": f"{SEC_NAME}月收益",
            "d_y10": "Δ10年国债"}
    cm = m[list(cols)].rename(columns=cols).corr("pearson")
    cmap = plt.get_cmap("RdBu_r")
    im = ax.imshow(cm.to_numpy(), cmap=cmap, vmin=-1, vmax=1)
    ax.set_xticks(range(len(cm)), cm.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(cm)), cm.index, fontsize=8)
    for i in range(len(cm)):
        for j in range(len(cm)):
            v = cm.iloc[i, j]
            rgba = cmap((v + 1) / 2)
            lum = 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7.5,
                    color="#111111" if lum > 0.5 else "#ffffff")

    ax.set_title("(a) 全样本 Pearson 相关矩阵（水平值 + 变化值同框）",
                 color=FG, fontsize=11, pad=8, loc="left")
    ax.grid(False)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)

    # (b) lag 互相关
    ax = fig.add_subplot(gs[0, 1])
    lags = sorted(lag["lag"].unique())
    width = 0.13
    for i, (name, c) in enumerate(((idn("(点位)"), C_IDX), (sdn("(点位)"), C_SEC),
                                   ("10年国债收益率(%)", C_BOND),
                                   (idn("(月收益率%)"), C_IDX_L),
                                   (sdn("(月收益率%)"), C_SEC_L),
                                   ("10年国债(月变化pp)", C_BOND_L))):
        sub = lag[lag["市场变量"] == name].set_index("lag").reindex(lags)
        ax.bar(np.arange(len(lags)) + (i - 2.5) * width, sub["corr"], width=width,
               color=c, label=name, alpha=0.92)
    ax.set_xticks(range(len(lags)), [f"{k:+d}" if k else "0" for k in lags])
    ax.axhline(0, color=FG, linewidth=0.8, alpha=0.5)
    _style(ax, "(b) 领先/滞后互相关：lag>0 = 剪刀差领先市场（月）")
    ax.set_xlabel("lag（月）")
    ax.set_ylabel("相关系数")
    ax.set_ylim(-0.85, 0.42)          # 给顶部图例留白，避免压住最高柱
    ax.legend(fontsize=7.5, framealpha=0.9, ncol=2)


    # (c) 子区间对比（柱=月度变化口径，圆点=12个月变化口径）
    ax = fig.add_subplot(gs[1, 0])
    order = ["全样本"] + [s[0] for s in SUB_PERIODS]
    groups = [(idn("(点位)"), idn("(月收益率%)"), idn("(12月收益率%)"), lv, ch, t12, C_IDX),
              (sdn("(点位)"), sdn("(月收益率%)"), sdn("(12月收益率%)"), lv, ch, t12, C_SEC),
              ("10年国债收益率(%)", "10年国债(月变化pp)", "10年国债(12月变化pp)", lv, ch, t12, C_BOND)]
    xpos = np.arange(len(order))
    w = 0.26
    for i, (nl, nc, n12, tl, tc, t12_, c) in enumerate(groups):
        vals = [tc[(tc["区间"] == o) & (tc["市场变量"] == nc)]["Pearson"].iloc[0] for o in order]
        ax.bar(xpos + (i - 1) * w, vals, width=w * 0.92, color=c,
               label=f"{nc}（月，柱）", alpha=0.9)
        v12 = [t12_[(t12_["区间"] == o) & (t12_["市场变量"] == n12)]["Pearson"].iloc[0]
               for o in order]
        ax.scatter(xpos + (i - 1) * w, v12, s=34, color=c, marker="D",
                   edgecolors="#ffffff", linewidths=1.0, zorder=6,
                   label=f"{n12}（12月，菱形）")
    ax.set_xticks(xpos, [o.replace(" ", "\n") for o in order], fontsize=8)
    ax.axhline(0, color=FG, linewidth=0.8, alpha=0.5)
    for y in (0.5, -0.5):
        ax.axhline(y, color=FG, linewidth=0.7, alpha=0.3, linestyle="--")
    _style(ax, "(c) 分区间 Pearson：变化口径（柱=月度，菱形=12个月）")
    ax.set_ylabel("相关系数")
    ax.set_ylim(-1.05, 1.05)
    ax.legend(fontsize=7, framealpha=0.9, ncol=2, loc="upper left")


    # (d) 散点：Δ剪刀差 vs 月度收益率
    ax = fig.add_subplot(gs[1, 1])
    for col, c, lab in (("idx_ret", C_IDX, IDX_NAME), ("sec_ret", C_SEC, SEC_NAME)):
        sub = m[["d_spread", col]].replace([np.inf, -np.inf], np.nan).dropna()
        x, y = sub["d_spread"], sub[col]
        r, _, n = _corr(x, y)
        display = f"r={r:.2f}" if pd.notna(r) else f"n={n}，相关不可用"
        ax.scatter(x, y, s=26, color=c, alpha=0.75, edgecolors="none", label=f"{lab}（{display}）")
        if len(x) >= 2 and x.nunique() >= 2:
            k, b = np.polyfit(x, y, 1)
            xs = np.linspace(x.min(), x.max(), 50)
            ax.plot(xs, k * xs + b, color=c, linewidth=1.4, linestyle="--", alpha=0.8)
    ax.axhline(0, color=FG, linewidth=0.7, alpha=0.4)
    ax.axvline(0, color=FG, linewidth=0.7, alpha=0.4)
    _style(ax, "(d) 散点：Δ剪刀差（百分点） vs 指数月度收益率（%）")
    ax.set_xlabel("Δ剪刀差（百分点）")
    ax.set_ylabel("月度收益率 %")
    ax.legend(fontsize=8.5, framealpha=0.9)

    fig.suptitle("CPI-PPI 剪刀差 与 股债相关性分析（2020-01 起，月度）",
                 color=FG, fontsize=14, y=0.94)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def plot_decompose(m: pd.DataFrame, dc: pd.DataFrame, path: Path):
    """成分分解图：CPI 腿 / PPI 腿 / 剪刀差 三条相关并列。"""
    tags = ["水平", "月度变化", "12个月变化"]
    cols = [("CPI腿", "CPI_p", C_CPI, "CPI 腿"),
            ("PPI腿", "PPI_p", C_PPI, "PPI 腿"),
            ("剪刀差", "剪刀差_p", C_SPREAD, "剪刀差（组合）")]
    r2 = m["spread"].corr(m["ppi_yoy"]) ** 2

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.6))
    for ax, tag in zip(axes, tags):
        sub = dc[dc["口径"] == tag]
        names = list(dict.fromkeys(sub["市场变量"]))
        xpos = np.arange(len(names))
        w = 0.26
        for i, (col, pcol, c, lab) in enumerate(cols):
            rows = [sub[sub["市场变量"] == nm].iloc[0] for nm in names]
            vals = [r[col] for r in rows]
            ax.bar(xpos + (i - 1) * w, vals, width=w * 0.9, color=c, label=lab, alpha=0.92)
            for x, r in zip(xpos + (i - 1) * w, rows):
                if pd.notna(r[col]) and pd.notna(r[pcol]) and r[pcol] < 0.05:
                    ax.text(x, r[col] + (0.05 if r[col] >= 0 else -0.05), "*",
                            ha="center", va="bottom" if r[col] >= 0 else "top",
                            color=FG, fontsize=14)
        ax.set_xticks(xpos, [n.replace("(", "\n(") for n in names], fontsize=7.5)
        ax.axhline(0, color=FG, linewidth=0.8, alpha=0.5)
        for y in (0.5, -0.5):
            ax.axhline(y, color=FG, linewidth=0.7, alpha=0.3, linestyle="--")
        _style(ax, f"{tag}口径")
        ax.set_ylim(-0.95, 0.95)
        ax.set_ylabel("相关系数（* = p<0.05）")
        ax.legend(fontsize=8, framealpha=0.9)
    fig.suptitle("成分分解：剪刀差与市场的相关，究竟来自 CPI 腿还是 PPI 腿？"
                 f"（本样本 PPI 解释剪刀差方差 {100 * r2:.0f}%）",
                 color=FG, fontsize=13, y=1.005)
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- 报告
def star(r: float) -> str:
    a = abs(r) if pd.notna(r) else 0
    return "强" if a >= 0.7 else ("中" if a >= 0.4 else ("弱" if a >= 0.2 else "极弱"))


def report(m: pd.DataFrame, tables: dict[str, pd.DataFrame], dc: pd.DataFrame,
           lag: pd.DataFrame, roll: pd.DataFrame, window: int = 24):
    lv, ch, t12 = tables["level"], tables["change"], tables["change12"]
    W = 90
    print("\n" + "=" * W)
    print("CPI-PPI 剪刀差 与 股债相关性分析")
    print("=" * W)
    print(f"样本：{m.index[0]} → {m.index[-1]}，共 {len(m)} 个月")
    print(f"剪刀差 = CPI同比 - PPI同比（百分点）。区间 {m['spread'].min():.2f} ~ {m['spread'].max():.2f}，"
          f"均值 {m['spread'].mean():.2f}")
    print(f"最新一期 {m.index[-1]}：CPI {m['cpi_yoy'].iloc[-1]:.1f}% / PPI {m['ppi_yoy'].iloc[-1]:.1f}% "
          f"/ 剪刀差 {m['spread'].iloc[-1]:.2f}pp / {IDX_NAME} {m['idx'].iloc[-1]:.0f} "
          f"/ {SEC_NAME} {m['sec'].iloc[-1]:.0f} / 10年国债 {m['y10'].iloc[-1]:.2f}%")

    def dump(title, table):
        print("\n" + "-" * W)
        print(title)
        print("-" * W)
        print(f"{'区间':<22}{'市场变量':<20}{'n':>4}{'Pearson':>10}{'p值':>9}{'':>3}"
              f"{'显著性':>7}{'Spearman':>10}  强度")
        for _, row in table.iterrows():
            r, p = row["Pearson"], row["p值"]
            print(f"{row['区间']:<22}{row['市场变量']:<20}{row['n']:>4}"
                  f"{r:>10.3f}{p:>9.4f}{'':>3}{row['显著性']:>7}"
                  f"{row['Spearman']:>10.3f}  {star(r)}")

    dump("【水平口径】剪刀差(水平) vs 市场(水平) —— 注意：含共同趋势，易虚高", lv)
    dump("【月度变化口径】Δ剪刀差 vs 市场月度变化 —— 增量信息", ch)
    dump("【12个月变化口径】12月Δ剪刀差 vs 市场12月变化 —— 去趋势鲁棒性检验", t12)

    r2 = m["spread"].corr(m["ppi_yoy"]) ** 2
    print("\n" + "-" * W)
    print("【成分分解】spread = CPI - PPI，两条腿各自与市场的相关（* = p<0.05）")
    print("-" * W)
    print(f"本样本波动幅度：CPI {m['cpi_yoy'].std():.2f}pp vs PPI {m['ppi_yoy'].std():.2f}pp  "
          f"；剪刀差与 PPI 的样本相关平方为 {100 * r2:.1f}%")
    print(f"{'口径':<12}{'市场变量':<20}{'CPI腿':>9}{'':>2}{'PPI腿':>9}{'':>2}"
          f"{'剪刀差':>9}{'':>2}")
    for _, row in dc.iterrows():
        def cell(v, p):
            return f"{v:>7.3f}{'*' if pd.notna(p) and p < 0.05 else ' '}"
        print(f"{row['口径']:<12}{row['市场变量']:<20}"
              f"{cell(row['CPI腿'], row['CPI_p']):>9}  "
              f"{cell(row['PPI腿'], row['PPI_p']):>9}  "
              f"{cell(row['剪刀差'], row['剪刀差_p']):>9}")

    print("\n" + "-" * W)
    print("【领先/滞后】全样本互相关（lag>0 = 剪刀差领先市场，不标显著性）")
    print("-" * W)
    print(f"{'市场变量':<20}{'口径':<8}" + "".join(f"{k:>9}" for k in range(-3, 4)))
    for name in lag["市场变量"].unique():
        sub = lag[lag["市场变量"] == name]
        kind = sub["口径"].iloc[0]
        vals = sub.set_index("lag")["corr"].reindex(range(-3, 4))
        cells = (f"{v:>9.3f}" if pd.notna(v) else f"{'—':>9}" for v in vals)
        print(f"{name:<20}{kind:<8}" + "".join(cells))

    print("\n" + "-" * W)
    print(f"\n【滚动{window}个月相关】水平口径 与 变化口径 的区间统计")
    print("-" * W)
    for c in (f"{IDX_NAME}_level", f"{SEC_NAME}_level", "10年国债_level",
              f"{IDX_NAME}_change", f"{SEC_NAME}_change", "10年国债_change"):
        s = roll[c].dropna()
        if s.empty:
            continue
        print(f"{c:<22}min {s.min():+.2f}  max {s.max():+.2f}  "
              f"均值 {s.mean():+.2f}  末值 {s.iloc[-1]:+.2f}  "
              f"正相关占比 {(s > 0).mean() * 100:.0f}%（n={len(s)}）")

    print("\n" + "-" * W)
    print("【自动判读】")
    print("-" * W)
    for tag, label in (("level", "水平口径"), ("change", "月度变化"), ("change12", "12个月变化")):
        t = tables[tag]
        base = t[t["区间"] == "全样本"]
        n_sig = base["p值"].lt(0.05).sum()
        n_valid = base["p值"].notna().sum()
        maxabs = base["Pearson"].abs().max()
        max_label = f"{maxabs:.3f}" if pd.notna(maxabs) else "不可用"
        print(f"{label:<10}全样本最大 |r| = {max_label}；"
              f"有效 p 值 {n_valid} 个，其中 p<0.05 共 {n_sig} 个（未经时序校正）")
    print("\n注意：CPI/PPI 为次月 9 日左右公布（M 月数据在 M+1 月可得），")
    print("      故 lag 分析中的「剪刀差领先市场」在信息可得性上需再打一个月折扣。")
    print("      水平口径的 p 值因序列自相关而偏乐观，应以变化口径与滚动稳定性为准。")
    print(f"产出目录：{OUT}")
    print("=" * W + "\n")



def main():
    global OUT, RAW, IDX_SYM, IDX_NAME
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="强制重新取数（忽略缓存）")
    ap.add_argument("--window", type=int, default=24, help="滚动相关窗口（月），默认 24")
    ap.add_argument("--index", default=IDX_SYM, help=f"主指数代码，默认 {IDX_SYM}（沪深300）")
    ap.add_argument("--index-name", default=None, help="主指数显示名，默认按代码查表")
    ap.add_argument("--outdir", default=str(OUT), help="产出目录，默认 outputs/cpi_ppi")
    args = ap.parse_args()

    OUT = Path(args.outdir)
    RAW = OUT / "raw"
    IDX_SYM = args.index
    IDX_NAME = args.index_name or _DEFAULT_NAMES.get(args.index, args.index)

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"主指数：{IDX_NAME}({IDX_SYM})　次指数：{SEC_NAME}({SEC_SYM})　产出：{OUT}")
    fetch_all(args.refresh)
    m = build_monthly()
    tables = corr_tables(m)
    dc = decompose(m)
    lag = lag_table(m)
    roll = rolling_table(m, args.window)

    plot_trend(m, roll, OUT / "fig01_trend.png")
    plot_corr(m, tables, lag, roll, OUT / "fig02_correlation.png")
    plot_decompose(m, dc, OUT / "fig03_decomposition.png")
    report(m, tables, dc, lag, roll, args.window)

    # 供报告生成器读取（指数名称/样本区间），避免两处硬编码
    (OUT / "meta.json").write_text(json.dumps({
        "index_symbol": IDX_SYM, "index_name": IDX_NAME,
        "secondary_symbol": SEC_SYM, "secondary_name": SEC_NAME,
        "months": len(m), "start": str(m.index[0]), "end": str(m.index[-1]),
        "window": args.window, "monthly_schema": "calendar-v1",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"meta.json 已写出（{IDX_NAME} / {SEC_NAME}）")


if __name__ == "__main__":
    main()

