"""取数工具：期货主连/单合约/外盘现货 日线 → CSV（核心库保持无网络依赖）。

用法:
  .venv/bin/python tools/fetch_daily.py IM0 --start 2026-06-01 --end 2026-08-28 -o data/IM0_daily.csv
  .venv/bin/python tools/fetch_daily.py XAU --start 2025-09-01 --end 2026-08-28 -o data/XAU_daily.csv --foreign
"""
import argparse


def _foreign(symbol, start, end, out):
    import pandas as pd
    import akshare as ak
    df = ak.futures_foreign_hist(symbol=symbol)
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= start) & (df["date"] <= end + " 23:59:59")]
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return len(df)


def _domestic_fallback(symbol, start, end, out):
    import pandas as pd
    import akshare as ak
    df = ak.futures_zh_daily_sina(symbol=symbol.lower())
    df = df[(df["date"] >= start) & (df["date"] <= end)]
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return len(df)


def _minute(symbol, minutes, start, end, out):
    """日内 K 线（新浪源，15/30/60 分钟深度约数月）。"""
    import pandas as pd
    import akshare as ak
    df = ak.futures_zh_minute_sina(symbol=symbol, period=str(minutes))
    df = df.rename(columns={c: str(c).strip() for c in df.columns})
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime")
    df = df[(df["datetime"] >= start) & (df["datetime"] <= end + " 23:59:59")]
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return len(df)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("symbol", help="代码：IM0/CU0/TL0（主连）或 XAU（外盘，配 --foreign）")
    ap.add_argument("--start", required=True, help="起始日 YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="结束日 YYYY-MM-DD")
    ap.add_argument("-o", "--output", required=True, help="输出CSV路径")
    ap.add_argument("--foreign", action="store_true", help="外盘现货（akshare futures_foreign_hist）")
    ap.add_argument("--minute", type=int, default=None, choices=(15, 30, 60),
                    help="日内K线分钟数（新浪源；不配则取日线）")
    args = ap.parse_args()

    if args.minute:
        n = _minute(args.symbol, args.minute, args.start, args.end, args.output)
    elif args.foreign:
        n = _foreign(args.symbol, args.start, args.end, args.output)
    else:
        try:
            from local_datasource.providers.futures import query_futures
        except ImportError:
            n = _domestic_fallback(args.symbol, args.start, args.end, args.output)
        else:
            path, _summary = query_futures(symbol=args.symbol, period="daily",
                                           start_date=args.start, end_date=args.end,
                                           file_path=args.output)
            print(f"CSV -> {path}（local-datasource）")
            return
    print(f"CSV -> {args.output} rows={n}（akshare）")


if __name__ == "__main__":
    main()