"""新浪期货分钟接口（约4个交易日窗口）。"""
import json
import re

import pandas as pd
import requests

URL = ("https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20t=/"
       "InnerFuturesNewService.getFewMinLine")


def _http_get(symbol: str) -> str:
    r = requests.get(URL, params={"symbol": symbol, "type": "1"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    return r.text


def parse_sina_payload(text: str) -> pd.DataFrame:
    m = re.search(r"\((\[.*\])\)", text, re.S)
    data = json.loads(m.group(1)) if m else []
    rows = []
    for item in data:                       # 元素兼容 dict(d/o/h/l/c/v) 与逗号串
        if isinstance(item, str):
            rows.append(item.split(",")[:6])
        else:
            rows.append([item.get(k) for k in ("d", "o", "h", "l", "c", "v")])
    df = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["hold"] = 0
    return df[["datetime", "open", "high", "low", "close", "volume", "hold"]]


def fetch_sina_minute(symbol: str) -> pd.DataFrame:
    raw = parse_sina_payload(_http_get(symbol))
    return raw.rename(columns={c: f"fut_{c}" for c in
                               ["open", "high", "low", "close", "volume"]})[
        ["datetime", "fut_open", "fut_high", "fut_low", "fut_close", "fut_volume"]]
