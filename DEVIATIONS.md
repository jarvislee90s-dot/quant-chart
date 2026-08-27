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

## Task 6 —— auto 测试配置缺 input.api 段

- **计划原文**：`auto_load({"mode": "auto", "range": ["2026-08-19", "2026-08-26"]})`
- **实际做法**：补上 `"api": {"future": "IM2612"}`，即
  `auto_load({"mode": "auto", "api": {"future": "IM2612"}, "range": [...]})`
- **原因**：实现按设计文档 YAML 模板读取 `input.api.future`（设计文档第 4 节：
  `api: {future: IM2612, index: "000852"}`），测试配置漏掉该段导致
  KeyError: 'api'。补齐后与设计一致，实现无偏差（auto 模式必须有 api.future）。

## Task 6 —— NeedsExcelError 文案无大写"Excel"

- **计划原文**：报错文案 `……请改用 mode=excel 提供两表。`；测试断言 `"Excel" in str(e)`
- **实际做法**：文案改为 `……请改用 mode=excel 提供两份 Excel 表。`
- **原因**：计划文案只有小写 `excel`，与同计划内测试断言（大写 `Excel`）及设计文档
  第 6 节『明确报"需 Excel 补至 X 日"』不符。修实现文案而非放宽测试断言，
  保持用户可见错误信息包含明确的"Excel"字样。

## Task 7 —— area 原语测试断言与计划自身实现矛盾

- **计划原文**：测试 `assert len(fig.data) == 2 and all(t.fill == "tozeroy" for t in fig.data)`；
  而同任务实现 `_area` 添加 3 个 trace（正填充、负填充、贴水轮廓线）
- **实际做法**：断言改为 `len(fig.data) == 3 and all(t.fill == "tozeroy" for t in fig.data[:2])`
- **原因**：计划内实现与测试自相矛盾。保留实现（第 3 个 trace 是轮廓线，
  对应已验证样张的贴水描边视觉要素），修正测试断言以匹配"两个填充+一条轮廓"
  的实际结构。

## Task 8 —— leader_tag 连线载体与 day_seps 单日夹具两处测试矛盾

- **计划原文**：
  ① `assert any(sh.type == "line" for sh in fig.layout.shapes)  # 连线到基准线`；
  ② `test_day_seps_and_labels` 用单日夹具断言存在日分隔 shape
- **实际做法**：
  ① 改为 `assert any(t.mode == "lines" for t in fig.data)`（连线是 Scatter 点线 trace）；
  ② 测试内自建两日夹具再断言分隔线
- **原因**：①计划实现的连线（低点→基准线）是 `add_trace(go.Scatter(mode="lines"))`
  而非 layout shape，测试断言查错了容器；②单日数据 `sep_center` 为空、
  本来就没有日分隔线，断言恒假。两处均为测试侧修复，实现无偏差。
