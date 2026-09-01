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
3. ~~`_hline` 存在死赋值（else 分支 `xref = "paper"` 随后被覆盖）；"只给 to 不给
   from"时标注 x 锚点取 x0 会错位。~~——已修（task2，commit 8d78b75）：线体与标注
   共用 xref，回归测试 3 形态（见下「Task2 偏差记录」）。
4. ~~`figure.py` 副轴刻度 240–400 与 -15 下限为硬编码量级假设（贴水超出该范围
   会被裁切），应在注释/文档标明或改为自适应。~~——已修（task2，commit 456d896）：
   遗留包络内零变化，包络外数据自适应（见下「Task2 偏差记录」）。
5. `Ctx.y2axis` 字段未被使用。
6. `signals.daily_min_events` 遇某日整段 NaN 时 `idxmin` 崩溃。
7. `run_pipeline` 标题回退对单元素 `range` 会 IndexError（`[0]–[1]` 取值）。
8. 设计 §5 "插件接口启动校验（签名校验、错误定位到插件文件）"未实现。
9. ~~`_days_needed` 把节假日当交易日~~——已随 P1-4 移除该函数而消解。
10. `_wire_events` 的 `trade_exec` 前缀聚合用 `startswith`：若未来出现
    `trade_exec_xxx` 等撞名 kind 会被误聚合（现库无此 kind，潜伏）。改为精确匹配需同时
    保留 `ref="trade_exec"` 的前缀聚合语义，联调批再定。
11. spec §3.1 承诺的"中文列名容错"未实现（对方按契约 v1.1/基线 98cd3bd 返回英文列名，（批次3 改判：不做——契约基线 d106144 锁定英文列名，联调实测通过）
    现网不可达）：中文列表会 KeyError 而非映射。属批次3 联调项，届时按对方实际列名清单补。

## 二期执行记录（2026-08-28）

执行范围：docs/superpowers/plans/2026-08-28-phase2.md（Task 1→10，批次1+2）。
起点 HEAD=2d24205，既有 34 测试全绿；终点 60 测试全绿（含 integration_localds 真库连网通过）。

### Task 3 —— 缺 lots 报错文案与计划测试断言矛盾

- **计划原文**：实现 `raise ConfigError(f"trades[{k}] 缺少 lots")`；测试 `assert "trades[0].lots" in str(e.value)`
- **实际做法**：文案改为 `trades[{k}].lots 缺失（close 动作可省略）`，保留测试断言不动
- **原因**：计划实现与计划测试自相矛盾；设计 spec §四明确错误格式示例为
  `trades[2].lots`（定位到条目下标与字段），按设计意图修实现文案。

### Task 4/6 —— pipeline 先于 figure 传入 row_heights 导致 4 个既有测试崩

- **计划原文**：Task 4 的 run_pipeline 调 `build_figure(..., row_heights=row_heights)`，
  而 `row_heights` 参数要到 Task 6 才加入 build_figure 签名
- **实际做法**：Task 4 提交时让 build_figure 先接受该参数（N==1 路径不使用），Task 6 再实现多面板逻辑
- **原因**：计划任务次序矛盾——Task 4 的 Step 4 要求"全量回归除待 Task 6 测试外全绿"，
  不补参数则 4 个既有测试 TypeError。最小前向兼容修复。

### Task 5 —— events style_map 的 plan 版实现把 symbol 归一成元组

- **计划原文**：`_events` 收集 `syms/cols` 列表后单个 trace 传出 `marker=dict(symbol=syms, color=cols)`
- **实际做法**：按（符号,颜色）样式分组出多个 trace；单一样式时 symbol 仍为标量
- **原因**：plotly 会把列表形式的 symbol 规范化为元组 `('triangle-up','x')`，
  与计划测试断言 `== "triangle-up"` 矛盾，且 MVP 既有测试（单事件、symbol 标量）同样被破坏。
  分组出 trace 后视觉等价、断言形态与 MVP 一致。

### Task 5 —— line 阶梯测试夹具缺 position_lots 列

- **计划原文**：`test_line_hv_shape` 直接对夹具 ctx 画 `{"col": "position_lots", "shape": "hv"}`
- **实际做法**：测试内补 `ctx.df["position_lots"] = 1.0` 常量列
- **原因**：夹具 df 无该列，测试在断言 shape 前就 KeyError；补列后红灯落在目标断言上。

### Task 6 —— plotly 轴行为与计划代码/测试三处矛盾

- **计划原文**：① `fig.update_layout(**{"y3": ...})` 传裸轴号；② 测试断言
  `fig.layout.xaxis2.matches == "x"`；③ 测试断言 `fig.layout.xaxis2 is None`
- **实际做法**：① 布局键改 `yaxis3`/`yaxis4`（plotly 布局属性树只认 yaxisN，
  裸 y3 是 trace 级引用名）；② 共享X断言改为 `fig.layout.xaxis.matches == "x2"`
  （plotly 7 的 make_subplots 用主轴 matches 指向副轴实现 shared_xaxes，xaxis2.matches 为 None）；
  ③ 未生成断言改为 `"xaxis2" not in fig.layout`（plotly 对未设轴属性访问抛 AttributeError 而非返回 None）
- **原因**：三者均为计划与 plotly 7.0 实际行为的矛盾，测试意图（共享X/未生成第二面板轴）不变。

### Task 6 —— _wire_events 按完整 kind 分桶导致 trade_exec 层 KeyError

- **计划原文**：`_wire_events` 以 `e.kind`（如 `trade_exec:buy`）为键建桶；
  pipeline 自动挂载的交易层 `ref="trade_exec"`（无后缀）
- **实际做法**：`_wire_events` 对 `trade_exec` 前缀事件额外聚合出 `trade_exec` 桶（ref 前缀引用）
- **原因**：两处键不一致，解禁的多面板 e2e 测试在 `_events` 处 KeyError: 'trade_exec'。
  设计意图是"有 trades 必有买卖点标记"，前缀聚合后 buy/sell/close 三种 kind 全部入图。

### Task 10 —— 多面板下 axis:"y"/主轴引用名失效

- **计划原文**：`_build_multi` 给面板 i 生成 Ctx(yaxis=f"y{i}")；`_remap_axes` 不处理字面 "y"
- **实际做法**：面板1 的轴引用用 plotly 约定名 x/y（无编号，y1/x1 不是合法轴引用）；
  `_remap_axes` 对非面板0 的 `axis: "y"`（意为"本面板主轴"，如仓位面板 0 基准线）
  注入本面板实际主轴名
- **原因**：plotly 主轴引用固定为 "y"；计划写法让面板0 的 hline/area 落到不存在的 y1，
  且仓位面板 `hline(axis: y)` 被判为"纸面全宽副轴"而报错。示例配置 e2e 因此跑不通。

### Task 10 —— test_not_installed 在真库已装环境下失效

- **计划原文**：`monkeypatch.setitem(sys.modules, "local_datasource", None)` 模拟未安装
- **实际做法**：级联对全部 `local_datasource*` 已缓存子模块置 None 哨兵
- **原因**：全量回归时 `test_integration_localds.py`（字母序在前）真装真库并 import 成功，
  子模块留存 sys.modules；`import_module("local_datasource.providers.futures")` 命中子模块缓存，
  绕过顶层哨兵不抛 ImportError。生产"未安装"场景无此问题，属测试装置缺口。

### Task 10 —— 多面板下 _line 不绑定面板轴，仓位阶梯线落空

- **计划原文**：`_line` 原语不设置 `yaxis`（单面板 MVP 依赖 plotly 默认主轴，从未显式绑定）
- **实际做法**：`_line` 显式绑定 `yaxis=ctx.yaxis`（主轴 "y" 时传 None 等价，副轴必传）；
  并给 `test_multi_panel_axes_and_rows` 补断言 `position_lots` trace 的 `yaxis == "y2"`
- **原因**：验收图目测发现下面板仓位阶梯空白——多面板下 line trace 无轴引用时
  plotly 一律画在主图 y 轴（0–2 的仓位线压在主图底部不可见）。单面板默认轴恰好等于
  ctx 轴故 MVP 无影响；计划的多面板章节未覆盖此差异，属设计承诺
  （spec §2.1"非面板0 各一主轴"）的落地缺口，以验收图目测驱动补齐。

### 二期评审 I-1 —— 多面板时间刻度全部丢失（代码评审后修复）

- **计划原文**：Task 6 `_build_multi` 给顶轴配 tickvals/ticktext，又给底轴
  `showticklabels=False`；`shared_xaxes` 本身隐藏顶轴刻度 → 双面板零时间刻度
- **实际做法**：刻度配置（range/tickvals/ticktext/tickangle/tickfont/linecolor）
  移到最底面板轴且 `showticklabels=True`，中间轴 `showticklabels=False`，
  顶轴维持 shared_xaxes 的隐藏；`test_multi_panel_axes_and_rows` 补刻度归属断言
  （底轴可见且 tickvals>5、顶轴仍隐藏）
- **原因**：违反 spec §2.1"X 轴刻度与日期行只画在最底面板"。测试盲区根源：
  既有断言只测 trace 存在性与 matches，未测刻度可见性；验收目测当时聚焦
  买卖点/阶梯，漏看刻度。修复由代码评审指出后 TDD 补齐。

### 二期评审修复（2026-08-28，同日第二阶段）

- **I-1**（Important）：多面板时间刻度全部丢失——shared_xaxes 隐藏顶轴刻度、
  代码又显式关掉底轴刻度，违反 spec §2.1"刻度画在最底面板"。TDD 修复：刻度配置
  （range/tickvals/ticktext/tickfont）移至最底面板轴且可见，中间轴隐藏；
  `test_multi_panel_axes_and_rows` 补刻度归属断言。commit 26e552b。
- **Minor 1**：`_leader_tag` 的 trace/标注未绑面板轴（放 extra_panels 会落主图）→
  绑定 `yaxis=ctx.yaxis`，补 `test_multi_panel_leader_tag_on_own_panel`。commit 3665178。
- **Minor 2**：`_remap_axes` 不处理面板0 原语缺省 axis（用户 panels 整体替换时缺省 y2
  会落到面板1 主轴）→ 面板0 缺省注入 overlay 重映射轴；补
  `test_multi_panel_panel0_default_axis_remap`。commit 3665178。
- **Minor 3**（不修）：`_wire_events` 前缀聚合 `startswith("trade_exec")` 的撞名边角——
  现库仅 `trade_exec:{action}` 一种前缀 kind，无现实触发面；改精确匹配反而破坏
  ref 前缀聚合语义。记 P2 已知问题第 10 条。
- **Minor 4**（不修）：spec §3.1"中文列名容错"未实现——契约基线 98cd3bd 返回英文列名，
  属批次3 联调项；已复现 KeyError 并记 P2 已知问题第 11 条。
- **Minor 5**：非覆盖类 ValueError 原样上报但缺"可改用 mode: excel"提示（spec §四）→
  auto.py 补提示包装（保留原异常消息），补 `test_non_coverage_error_keeps_excel_hint`。commit c409194。
- **Minor 6**：`contract_mult: true`（bool 是 int 子类）可过校验 → 校验排除 bool，
  补 `test_contract_mult_bool_rejected`。commit c409194。
- **Minor 7**：契约测试排序断言缺负向驱动 → `_install_fake` 加 `descending` 参数，
  补 `test_descending_input_normalized` 负向回归（实为日网格 reindex 天然归一，
  注释已注明，非专门排序逻辑）。commit c409194。
- **连带发现并修复**：`test_not_installed` 单跑时仍漏气——本机真装 local_datasource，
  哨兵只对已缓存键生效，未缓存时 import_module 会重新加载真包；顶层键须显式放入。
  该修复在 c409194 同批提交。教训：全量跑的测试顺序恰好掩盖了单跑缺陷，修复后
  已验证（单跑/组合跑/integration 先行）三种序列全绿。

### 无其他偏差

- Task 1/2/7/8/9 与计划一致；计划内 fake 注入装置、CoverageGap 转译、auto/api 语义均按计划落地。
- `api_sina.py` 按计划保留未动（批次3 删）。
- `pytest.mark.integration_localds` 联调测试在本机真实通过（未跳过）：local-datasource 已安装且连网。

## 批次3 联调收官（2026-08-28，同日第三阶段）

local-datasource 终版 `d106144`（基线 98cd3bd 之后仅文档变更，代码零漂移）。真库实测四路全通：
快乐路径（3 交易日 726 槽位、fut_hold/idx_amount 附加列保留）、覆盖缺口转译
（真 CoverageError → CoverageGap，起始日 2026-08-24 提取正确）、mode:api 端到端出图、
mode:auto 覆盖不足整体回退 Excel（source 标注降级）。

收官动作：
- 删除 `src/quantchart/adapters/api_sina.py`（零引用，批次3 计划项）
- `config.py` 补 api/auto 模式校验（input.api.future/index 与 input.range，与 excel 模式对齐）
- README 更新：mode 三态说明、4.2 节改写为"已交付"、报错表与速查表同步、目录树注释
- 测试琐碎清理：setitem 注释纠正、死变量清除、leader_tag annotation 轴绑定补断言
- P2 #11（中文列名容错）改判**不做**：契约基线锁定英文列名，风险归零（见下）

## 日线阶段（2026-08-28，feat/daily-candle 分支）偏差记录

> 控制方裁决：「既有测试零改动」约束指分支前既有测试；本分支新增的
> tests/test_daily_primitives.py 两处断言（`#e0524d`/`#2fc4c4` 字面量）随本裁决
> 同步改为对齐 `theme.DARK["up"]/["down"]` 常量。

### 日线 1 —— _arrow 把 textposition 传给了 add_annotation

- **计划原文**：plan 代码把 Scatter 的 textposition 参数传给 add_annotation
- **实际做法**：改为 9 项 xanchor/yanchor 等价映射；text_position 配置键与
  "middle right" 缺省保留
- **原因**：Plotly 7.0 注解无 textposition 属性，逐次 ValueError。
  九宫格锚点映射与 Scatter textposition 语义等价。

### 日线 2 —— figure_daily 的 Ctx 用 slots.df 而非 df

- **计划原文**：brief 代码 `Ctx(df=df)`（原始规范宽表）
- **实际做法**：改为 `Ctx(df=slots.df)`
- **原因**：build_daily_slots 在副本上加 pos 列，蜡烛原语读 `ctx.df["pos"]`，
  传原始 df 会 KeyError: 'pos'；管线保证 out.df 与 slots.df 为同一对象。

### 日线 3 —— _zone 增加 dash/opacity 透传键

- **计划原文**：_zone 边线线型与填充透明度为写死的既有限制，无配置键
- **实际做法**：增加 dash/opacity 透传键，缺省 "dash"/0.32 与原行为逐像素不变
- **原因**：参考图"红实线框"需要实线+淡填充，YAML 无法从既有限制下表达。

### 日线 4 —— _normalize 表头 strip 重命名方向写反

- **计划原文**：dict 推导做 stripped→original 的重命名映射
- **实际做法**：改为 `rename(columns=lambda c: str(c).strip())`，并补空白表头回归测试
- **原因**：计划推导方向写反（stripped→original 永不命中），带空白表头不会被清洗。

## Task2 —— 日线多面板+成交量子图（2026-08-31，task2/gazelle 分支）偏差记录

### 裁决 1 —— 两处「单面板拒绝」既有测试随红线解除而改写（涉及「既有断言零改动」约束）

- **约束原文**：新增功能必须带测试，既有断言零改动。
- **冲突**：`tests/test_daily_pipeline.py::test_build_daily_figure_rejects_multi_panel`
  与 `test_extra_panels_rejected` 两条既有断言，钉死的正是本任务明文要求解除的
  「日线单面板限制」（设计文档 §2.3 自述为"分期实施的边界，不是产品决策"）。
  保留它们 == 不做任务，无第三种状态。
- **裁决**：按任务优先，两条拒绝测试**改写为支持测试**（1:1 替换，数量不减）：
  - `test_build_daily_figure_rejects_multi_panel` → `test_build_daily_figure_multi_panel_layout`
    （双面板成行/量柱落 y2/刻度只在底轴）+ `test_build_daily_figure_empty_panels_rejected`
    （空面板仍报错）；
  - `test_extra_panels_rejected` → `test_extra_panels_supported`（副图 MA5 落 y2）。
- **为何不算"放水"**：被改的只有"拒绝多面板"这一被任务否决的契约；其余既有断言
  （三层验收清单、回归值、快照对比）全部零改动且全绿。同类裁决有先例：日线阶段
  「既有测试零改动」约束经控制方裁决限定为"分支前既有测试"（见上节卷首）。

### 决策 1 —— 日线多面板与日内 extra_panels 的关系：接入统一，不另立体系

- **备选**：(a) 接入统一（panels/extra_panels 同一机制）；(b) 日线另立 `subplots` 键并存。
- **实际做法**：(a)。`merge_panels` 本就是两条产品线共用，本轮只拆除
  `build_daily_figure` 里最后一处 `len(panels) != 1 → raise`，日线获得与日内同构的
  `_build_daily_multi`（make_subplots 共享X、轴号重映射、底轴画刻度）。
- **原因**：(b) 会让"多面板"在两条产品线有两套语义，用户每配一图都要先问模式；
  接入统一后 `extra_panels`/`panels`/`row_heights` 三个键跨产品线同效，学习成本归零。
  日线无贴水 overlay 轴，轴重映射比日内少一层（无 y2→overlay 重定向），
  `_remap_daily_axes` 只做"缺省轴/字面 y → 本面板主轴"。

### 决策 2 —— 成交量子图的数据口径与配色

- **数据来源**：适配器 `volume` 列（CSV `成交量`/`volume`，中英表头已映射；
  无量品种如伦敦金现货，适配器丢列且脚注"无量"提示）。不新增数据通道、不改适配器契约。
- **配色**：红涨青跌，色值缺省直接引用 `theme.DARK["up"]/["down"]`——与 K 线同色语义
  （通达信/同花顺惯例），主题单一校准源；`up/down/opacity/width` 可在层配置覆盖。
- **轴对齐**：量柱 x=pos 数值轴，多面板 `shared_xaxes=True` 与主图逐柱同位；
  量轴纵域 `[0, max×1.16]`（下限锁 0，不做下留白）；时间刻度只画底轴。
- **一键声明**：`params.volume_panel: true` 由插件追加预置面板
  （title/y_title/range_cols/layers 齐备），与手写 `extra_panels` 等价二选一；
  无量时插件不追加空面板（适配器脚注已提示），不静默画空图。

### P2#3 修复（commit 8d78b75）

- 线体与标注共用同一 `xref`（数据段 `ctx.xaxis` / 纸面 `paper`），消除 else 分支
  死赋值；"只给 to 不给 from"时标注不再退化为 paper 坐标（原实现 x=数据 pos 配
  paper 坐标 → 锚点错位到纸面外）。回归测试 3 形态：to-only / from-only / 纸面全宽。
- 既有行为不变面：from+to、纸面全宽两形态快照逐字节一致（见下证据节）。

### P2#4 修复（commit 456d896）

- 包络（b0≥-15、b1≤400、byhi/rate≤5.55）内：范围 [-15, b1+42%] 与历史刻度
  [0,240..380]/[0..5.5] 原样保留——既有图零变化；
- 包络外：下限 `min(-15, b0-10%span)` 随数据下扩，刻度按 `_nice_step`
  （5/10/20/25/50/100/200/500，目标 ≤12 个）整齐生成覆盖全范围，点/率两轴同法。
- 回归测试：包络内钉死历史值；超包络刻度覆盖数据范围、下限不裁切。

### 连带修复 —— qa/verify `_by_color` 遇 Bar 崩溃（commit 39f327d）

- 量柱（go.Bar 无 `.line`）入图后按色取线 AttributeError；改 `getattr` 守卫，
  线图行为零变化，补回归。

### 预存缺陷 —— test_api_success 缺标记（commit 1ec49a8）

- 补 `@pytest.mark.integration_localds`：未装 local-datasource 环境由 fail 变
  deselect（基线 1 failed → 0 failed），已装环境照常跑（fake_query 不打真网）。

### 新旧行为对照证据（验收输出留档）

- 快照对比（入仓工具 `tools/fig_compare.py`，13 场景 fig.to_dict 语义 diff，
  含 7 份既有 config 原样渲染；复跑步骤见工具 docstring 与 IMPLEMENTATION_NOTES §二）：
  7 份 config + `daily_single`/`daily_e2e`/`intraday_multi` 全部 **0 diff**；
  `intraday_single` 1 diff——仅 P2#3 修复的 to-only 标注 xref（paper→x 数据坐标）；
  `intraday_basis_beyond`/`_negative` 仅 P2#4 的刻度/下限变化（设计目标）。
- pytest 口径 `pytest -q -m "not integration_localds"`：
  基线 138 passed / 1 failed / 9 skipped / 1 deselected
  → 终态 **160 passed / 0 failed / 9 skipped / 2 deselected**
  （+22 新测试；两条拒绝测试 1:1 改写为支持测试，数量不减）。
- fresh clone（`git clone -b task2/gazelle` + 独立 venv `pip install -e ".[dev]"`）：
  全套 160 passed、验收清单 PASSED、验收 CLI 0 违规，成品 PNG 与工作区 md5 一致。
- 验收 CLI：`python tools/verify_chart.py configs/daily_volume_demo.yaml
  out/projects/daily_volume_demo/chart.png --checks tests/acceptance_checks/daily_volume.py`
  → 验收通过（0 违规）。

### 自审轮（2026-09-01）新增偏差与收尾

- **薄弱点 1（实现缺陷，自审发现）**：`_panel_range` 对列缺失/全 NaN 崩溃——
  `range_cols: [volume]` 指定缺失列（无量品种手写量面板）时
  `np.concatenate([])` 抛 ValueError。修：先收 arrays 再判空，退化 [0,1]，
  空面板仍成行。边界测试钉住（`test_volume_all_nan_explicit_panel_no_crash` /
  `test_volume_column_absent_explicit_panel_no_crash`，修前复现崩溃、修后通过）。
- **薄弱点 2（设计妥协）**：纵轴取数列原硬编码 `("line","volume")` 类型元组，
  未来带 `col` 的同构原语会漏网。修：收所有带 `"col"` 的图层（标注类原语无
  `col` 键天然排除），零特例。
- **薄弱点 3（接口缺口）**：`zero_floor` 原仅按 volume 类型自动识别，新原语无法
  表达 0 基线。修：面板显式 `zero_floor: true`（量柱层仍自动），
  `test_zero_floor_panel_key` 钉住。
- **探针化**：fig_compare 拆出 `probe_p2_3_to_only`/`probe_p2_4_*` 独立探针场景，
  对比结果按「预期 diff（修复目标）31 处 / 意外 diff（回归）0 处」分类
  （工具与 NOTES §7.4 留档）。
- **存疑项收尾**：n≥3 布局补测；test_api_success 补注入式机器证据
  （sys.modules 假包，不依赖真 local-datasource）。

### 追加轮（2026-09-01）—— MA 窗口超数据长度（backlog #23）

- **现状实测**：12 行数据 + `ma=[20,60]` → `rolling` 全 NaN、图层仍进图（图上不可见）、
  脚注静默、图例仍显示 MA20/MA60（误导）。
- **决策**：窗口 > 数据长度时该 MA 不画（图层移除/图例消失）+ 脚注回显；
  窗口 ≤ 数据长度维持 partial 末段（语义不变）。不画可用部分（篡改语义）、
  不报错（阻断整图）——与 TradingView/通达信惯例一致。
- **证据**：fig_compare 既有 11 场景 0 意外 diff（既有 config 窗口均在数据长内）；
  pytest 176 passed / 0 failed（+6 回归测试）。
