# DEVIATIONS —— 偏差记录

> 规则：计划某处跑不通或有错误时，做最小偏差修复并在此记录「任务号/计划原文/实际做法/原因」。

## Task 3 —— 测试夹具路径在 Windows 下解析错误

- **计划原文**：`tests/test_excel_wind.py` 中 `FIX = __file__.rsplit("/", 1)[0] + "/fixtures"`
- **实际做法**：`FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")`
- **原因**：Windows 下 `__file__` 为反斜杠路径，`rsplit("/", 1)` 切不开，
  得到 `…\tests\test_excel_wind.py/fixtures`（把测试文件当目录），3 个测试全部
  `FileNotFoundError`。改用 `os.path` 后语义与计划一致（指向 tests/fixtures）。

## Task 3 —— ffill 断言比较错了相邻两行

- **计划原文**：`assert abs(df["idx_close"].iloc[-1] - df["idx_close"].iloc[-2]) < 1e-9  # ffill 生效`
- **实际做法**：`assert abs(df["idx_close"].iloc[-2] - df["idx_close"].iloc[-3]) < 1e-9  # ffill 生效（填充的14:59==14:58）`
- **原因**：夹具每天删 14:59 后，最后一行是真实 15:00、倒数第 2 行是被填充的 14:59
  （等于 14:58 的值）。价格每分钟递增 0.1，故 `iloc[-1]-iloc[-2]=0.2` 是正常现象，
  该断言永远不成立；校验 ffill 应比较"填充行==其前一行"，即 `iloc[-2]` 与 `iloc[-3]`。
  `rep.filled_index == 2` 断言已独立验证填充计数，实现本身无偏差。

## Task 5 —— 信号函数测试传入了缺 pos 列的原始 df

- **计划原文**：`evs = daily_min_events(df, slots, col="basis")` /
  `evs = window_min_events(df, [...], col="fut_low")`（df 为 `_df()` 原始表）
- **实际做法**：改传 `slots.df`（`daily_min_events(slots.df, slots, …)`、
  `window_min_events(slots.df, …)`）
- **原因**：两个信号函数内部都要读 `df.at[i, "pos"]`（Event.pos 字段），输入契约是
  "含 pos 列的槽位表"。计划 Task 8 的用法 `daily_min_events(slots.df, slots, "basis")`
  及流水线向插件传 `slots.df` 均符合该契约，仅 Task 5 测试传错了原始 df，
  KeyError: 'pos'。断言数值不变（同一份数据），实现无偏差。
