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

## Task 10 —— 插件调用方式测试与注册机制矛盾

- **计划原文**：`out = strat.run(slots.df, slots, trigger=250.0)`；
  而 `register_strategy` 注册的就是函数本体，且 Task 12 流水线为
  `get_strategy(cfg["strategy"])(slots.df, slots, **params)` 直接调用
- **实际做法**：测试改为 `out = strat(slots.df, slots, trigger=250.0)`
- **原因**：计划内注册机制（REGISTRY[name]=fn）、流水线调用、测试三处中
  测试一处写成了 `.run` 方法调用，与其余两处矛盾。按流水线的调用约定
  （注册值为可调用对象）修测试，实现无偏差。Task 11 测试存在同一问题
  （`get_strategy("basis_zones").run(...)`），按同口径修正。

## Task 13 —— 回归测试复算时在无 pos 列的表上算指标

- **计划原文**：`df = apply_indicators(df, [{"name": "basis"}])` 后
  `daily_min_events(df, slots, "basis")`（df 为 auto_load 原始宽表）
- **实际做法**：改为 `df = apply_indicators(slots.df, [{"name": "basis"}])`
- **原因**：与 Task 5 记录的同一契约问题——信号函数要求输入含 pos 列。
  auto_load 返回的规范宽表无 pos 列，须基于 `slots.df` 加指标列。
  断言数值不变，实现无偏差。另：计划的 `WINDOW_DIFF` 常量在测试代码中
  仅作核对值列出、无对应断言，按计划原文保留。

## Task 13 —— CLI 不自建输出目录

- **计划原文**：CLI 直接 `fig.write_image(output, ...)`；验收命令
  `chartflow run ... -o outputs/basis_zones.png`（outputs/ 不存在时 FileNotFoundError）
- **实际做法**：CLI 写 PNG/HTML 前调用 `_ensure_parent()` 确保父目录存在
- **原因**：单测用 pytest `tmp_path` 掩盖了该问题；验收命令按计划原文
  首次执行即失败。输出目录自建属于命令行工具的常规行为，属最小修复，
  不改变任何设计接口。

---

# 评审修复记录（2026-08-28，主 Agent 评审后）

上文 10 条偏差经评审全部裁定合理。以下为评审要求修复项的实施记录。

## P0-1 vwap 零成交分钟崩溃（已修）

- `indicators.py` 原 `vol.replace(0, pd.NA)` 将 float64 升为 object，
  `cumsum` 抛 `TypeError`（已用失败测试复现）。改为 `vol.where(vol > 0)`
  产生 NaN 并保持 float64，除后 `ffill` 即零成交分钟沿用前值。
- `make_fixtures.py` 新增 `zero_vol_minute` 参数，fut 夹具含 10:00 零成交分钟，
  流水线端到端测试随即覆盖该分支。

## P0-2 WINDOW_DIFF 死常量（已修）

- `test_regression.py` 新增 `test_window_diff_series`：以现价（末日收盘）减各窗口
  最低 `fut_low`，`len` 前置断言 + 逐值 `abs(a-b)<=1` 断言。真实数据上
  [+250, +198, +263, +375, +384] 验证吻合。

## P0-3 验收产物以 HEAD 重出（已执行）

- 评审所提"陈旧 PNG"与实际有出入：`outputs/` 现存 PNG 为 CLI 修复后
  （01:50）重新生成，标题与"现价（8.27收盘）"标签此前目测均在。
  但按"产物必须由最终提交代码生成"的流程要求，评审修复提交后已在 HEAD
  重跑 `pytest -q` 与 `chartflow run` 并重新出图核验。

## P1-4 auto 模式降级（已修，评审-directed 设计变更）

- 原 `auto` 抓取新浪数据仅用于数天数、最终仍全量走 Excel，且覆盖不足时会
  阻断一次本可成功的 Excel 运行。现 `auto`/`api` 模式直接抛 `NeedsExcelError`
  （提示属二期、本期用 `mode=excel`），不再发起网络请求；"新浪期货分钟 + Excel
  指数"拼装划入二期。`_days_needed` 一并移除（其"节假日当交易日"问题随之消解）。
- 测试改为断言 auto 不发起网络请求（`_http_get` 被替换为爆炸函数仍须抛
  `NeedsExcelError`）。README 同步更新。

## P1-5 config 校验下沉（已修）

- `excel` 段存在但缺 `future`/`index` 键时原先绕过校验、在 auto 层裸 KeyError。
  现校验下沉到 `input.excel.future/index`，错误信息带缺失字段路径；`open` 改
  `with` 管理。

## P1-6 夹具自举（已修）

- 新增 `tests/conftest.py` 会话级 autouse fixture：夹具 xlsx 缺失时自动运行
  `make_fixtures.py`（已实测删除 `tests/fixtures/` 后 pytest 自愈）。

# P2 已知问题（评审记录在案，随迭代处理）

1. 适配器跨日 ffill 会把上日 15:00 值填进次日 09:30（建议按日分组填充）。
2. `test_daily_min_basis_series` 的 `zip(got, DAILY_MIN)` 无长度前置断言
   （P0-2 已给窗口价差补了同类断言，此处待同样处理）。
3. `_hline` 存在死赋值（else 分支 `xref = "paper"` 随后被覆盖）；"只给 to 不给
   from"时标注 x 锚点取 x0 会错位。
4. `figure.py` 副轴刻度 240–400 与 -15 下限为硬编码量级假设（贴水超出该范围
   会被裁切），应在注释/文档标明或改为自适应。
5. `Ctx.y2axis` 字段未被使用。
6. `signals.daily_min_events` 遇某日整段 NaN 时 `idxmin` 崩溃。
7. `run_pipeline` 标题回退对单元素 `range` 会 IndexError（`[0]–[1]` 取值）。
8. 设计 §5 "插件接口启动校验（签名校验、错误定位到插件文件）"未实现。
9. ~~`_days_needed` 把节假日当交易日~~——已随 P1-4 移除该函数而消解。
