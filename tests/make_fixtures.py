# tests/make_fixtures.py —— 生成与 Wind 导出同构的小样本两表
import datetime as dtm
import pandas as pd
from quantchart.core.session import day_grid

COLS = ["代码", "名称", "日期", "开盘价(元)", "最高价(元)", "最低价(元)",
        "收盘价(元)", "涨跌幅", "成交额(百万)", "成交量(股)"]

def make(path: str, code: str, days, base: float, drop_minutes: int = 0):
    rows = []
    for i, t in enumerate([ts for d in days for ts in day_grid(d)]):
        px = base + i * 0.1
        rows.append([code, code, t, px, px + .5, px - .5, px, 0.0, 100.0 + i, 10 + i])
    df = pd.DataFrame(rows, columns=COLS)
    if drop_minutes:                       # 模拟指数端缺 14:59
        df = df[~df["日期"].dt.strftime("%H:%M").isin(["14:59"])]
    df.loc[len(df)] = ["数据来源：Wind"] + [None] * 9   # Wind 脚注行
    df.to_excel(path, index=False)

if __name__ == "__main__":
    import pathlib
    out = pathlib.Path(__file__).parent / "fixtures"
    out.mkdir(exist_ok=True)
    days = [dtm.date(2026, 8, 19), dtm.date(2026, 8, 20)]
    make(out / "fut.xlsx", "IM2612.CFE", days, 7000.0)
    make(out / "idx.xlsx", "000852.SH", days, 7300.0, drop_minutes=2)
    print("fixtures written:", out)
