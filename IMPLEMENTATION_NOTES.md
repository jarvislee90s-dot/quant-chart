# IMPLEMENTATION_NOTES —— Task2：日线多面板 + 成交量子图

> 分支：`task2/gazelle`（基线 9fd55e1）。本文记录设计决策、理由、新旧行为对照证据与验收输出留档。
> 偏差与裁决记录另见 `DEVIATIONS.md`「Task2 偏差记录」；接口约定另见设计文档
> `docs/superpowers/specs/2026-08-28-daily-candle-charting-design.md` §9 增补。

## 一、设计决策与理由

### 决策 1：日线多面板「接入统一」日内 extra_panels 体系，不另立机制

- **备选**：(a) 接入统一（`panels`/`extra_panels`/`row_heights` 同一机制）；(b) 日线另立 `subplots` 键并存。
- **选择 (a)**。`merge_panels` 本就是两条产品线共用，单面板红线只存在于
  `build_daily_figure` 的一处 `len(panels) != 1 → raise`。拆除后日线获得与日内同构的
  `_build_daily_multi`（`make_subplots(shared_xaxes=True)`：主图保留预测区、时间刻度只画
  最底面板、逐面板纵轴按 `range_cols` 或层内 line/volume 列自适应）。日线无贴水 overlay，
  轴重映射 `_remap_daily_axes` 比日内少一层（只做"缺省轴/字面 y → 本面板主轴"）。
- **理由**：(b) 会让"多面板"在两条产品线有两套语义，用户每配一图都要先问模式；统一后
  三个配置键跨产品线同效，学习成本归零，且 `merge_panels` 优先级语义（panels >
  extra_panels > 插件默认）原样复用。
- **取舍**：日线暂不支持 overlay 双右轴（贴水是日内概念）；日线面板内 `axis: "y2"/"y3"`
  按字面绑定对应行主轴，不做 overlay 重定向。

### 决策 2：成交量子图 = `volume` 原语 + `params.volume_panel` 一键声明

- **数据口径**：适配器既有 `volume` 列（CSV `成交量`/`volume`，中英表头已映射；
  无量品种如伦敦金现货，适配器丢列且脚注"无量"提示）。不新增数据通道、不改适配器契约。
- **配色**：红涨青跌，缺省直接引用 `theme.DARK["up"]/["down"]`——与 K 线同色语义
  （通达信/同花顺惯例），主题保持单一校准源；`up/down/opacity/width` 可在层配置覆盖。
- **轴对齐**：量柱 x=pos 数值轴，多面板 `shared_xaxes=True` 与主图逐柱同位；量轴纵域
  `[0, max×1.16]`（下限锁 0，不做下留白）；时间刻度只画底轴。
- **一键声明**：`params.volume_panel: true` 由插件追加预置面板
  （`title/y_title/range_cols/layers` 齐备），与手写 `extra_panels` 等价二选一；
  无量时插件不追加空面板，不静默画空图。
- **理由**：成交量是多面板的"canonical 第一副图"，一键声明覆盖 90% 场景；原语化
  （`type: volume`）保留把量柱放进任意面板、或与其他副图组合的自由度。

### 决策 3：P2#3 `_hline` 修复——线体与标注共用 xref

- **问题**：else 分支 `xref = "paper"` 是死赋值（随后被无条件覆盖）；"只给 to 不给 from"
  时标注 `xref` 退化为 paper、x 取数据 pos（如 242），锚点错位到纸面外。
- **方案**：`has_from/has_to` 双布尔先行，数据段统一 `xref = ctx.xaxis`、缺省端取数据
  首/末 pos；纸面段（无 from/to）才 `xref = "paper"` 且保留副轴拒绝；线体与标注共用同一
  xref 变量，结构上消灭错位可能。
- **行为面**：from+to 与纸面全宽两形态逐字节不变（快照证明）；仅 to-only 形态的标注
  xref 由 paper 修正为数据坐标（修复目标）。

### 决策 4：P2#4 贴水副轴刻度——包络内零变化，包络外数据自适应

- **问题**：`tickvals=[0]+arange(240,400,20)` 与下限 -15 为硬编码量级假设；贴水 >400 无刻度、
  < -15 被裁切。
- **方案**：`_basis_axis(b0,b1)` / `_basis_rate_ticks(bylo,byhi,rate)`——
  - 包络（b0≥-15、b1≤400、byhi/rate≤5.55）内：范围 `[-15, b1+42%span]` 与历史刻度
    `[0,240..380]`/`[0..5.5]` **原样保留**（既有图零变化的硬保证）；
  - 包络外：下限 `min(-15, b0-10%span)` 随数据下扩；刻度按 `_nice_step`
    （5/10/20/25/50/100/200/500，目标 ≤12 个）整齐生成覆盖全范围；率轴同法
    （0.25/0.5/1/2/5 档）。
- **理由**：包络门控把"修复 bug"与"改变既有图"严格隔离——既有三张复刻图与全部存量
  配置落在包络内，渲染逐字节不变；只有真正越界的数据才启用新行为。

### 决策 5（连带）：`qa/verify._by_color` 跳过无 `.line` 的 trace

- 量柱 `go.Bar` 无 `.line` 属性，入图后按色取线 AttributeError；改 `getattr` 守卫，
  线图行为零变化。多面板世界里验收器必须容忍异质 trace。

### 决策 6（预存缺陷）：`test_api_success` 补 `integration_localds` 标记

- 该测试 monkeypatch `local_datasource.providers`，未装包环境必 ModuleNotFoundError；
  按 pyproject 注册标记归类后，未装环境 deselect 而非失败（基线 1 failed → 0 failed），
  已装环境照常跑（fake_query 不打真网）。

### 裁决：两处「单面板拒绝」既有测试改写（涉及「既有断言零改动」）

- `test_build_daily_figure_rejects_multi_panel` / `test_extra_panels_rejected` 钉死的正是
  本任务明文要求解除的红线（设计文档 §2.3 自述为"分期实施的边界，不是产品决策"），
  保留 == 不做任务。裁决：1:1 改写为支持测试（数量不减），其余既有断言全部零改动。
  详见 DEVIATIONS.md「Task2 偏差记录 · 裁决 1」。

## 二、新旧行为对照证据

### 对比工具（已入仓，任何人可复跑）：`tools/fig_compare.py`

14 个场景（11 个 legacy/既有 config + 3 个 probe 修复探针），数据路径替换为
确定性种子的同构合成文件、params 原样 → fig JSON 快照；`--dump` 落盘 / `--diff`
语义对比。复跑步骤（基线 9fd55e1）：

```bash
git archive 9fd55e1 | tar -x -C /tmp/qc_base            # 基线代码（不碰工作区）
PYTHONPATH=/tmp/qc_base/src python tools/fig_compare.py --dump /tmp/before
python tools/fig_compare.py --dump /tmp/after           # 当前 HEAD
python tools/fig_compare.py --diff /tmp/before /tmp/after
```

### 结果分类（2026-09-01 自查实跑，探针化重构后）

**意外 diff（回归）：0 处** —— 11 个 legacy/既有 config 场景全部 0 diff：

| 场景 | 结果 |
|---|---|
| `cfg_basis_review` / `cfg_basis_zones` / `cfg_basis_zones_position` | **0 diff**（Wind 同构 xlsx 覆盖 zones/trades 日期，params 原样） |
| `cfg_daily_candle`（15 分钟样板配置） | **0 diff**（同构 15 分钟 CSV 覆盖配置区间与全部时刻引用） |
| `cfg_chart_01_xau` / `cfg_chart_02_cu0` / `cfg_chart_03_tl0` | **0 diff**（同构日线 CSV 覆盖配置区间；三份验收清单字节零改动） |
| `daily_single` / `daily_e2e` | **0 diff**（单面板抽函数后逐字节不变） |
| `intraday_single` / `intraday_multi` | **0 diff** |

**预期 diff（修复目标）：31 处，全部落在修复面（xref/tickvals/range）**：

| 探针场景 | diff 数 | 内容 |
|---|---|---|
| `probe_p2_3_to_only`（只给 to 的 hline 标注） | 1 | 标注 xref：paper→x（数据坐标，修复锚点错位） |
| `probe_p2_4_beyond_400`（贴水 530–650） | 19 | y2 刻度 [-100..700] 覆盖数据（原 240–380 无刻度）、率轴 [-1..9]（原 0..5.5） |
| `probe_p2_4_negative_floor`（贴水 -50..-38） | 11 | 下限 -15→-51.2 不再裁切、刻度延伸到 -55 |

### 合成数据等价性论证（防"碰巧全 PASS"质疑）

对比是 **diff-based**（同一份代码跑两侧），不是 pass/fail-based——合成数据只需
与真实数据走**同一条渲染路径**，路径等价性由以下四点保证：

1. **xlsx 双表头同构**：3 份 basis 配置的合成 Excel 由仓库自带的
   `tests/make_fixtures.py` 生成——与 Wind 导出同构（10 列中文表头含"（元）"后缀、
   脚注行"数据来源：Wind"），且该生成器就是本仓测试套件自己在用的夹具源
   （conftest autouse），excel_wind 适配器的每一条解析分支都由它驱动。
2. **basis 量级双覆盖**：合成 basis=300→275.9 落在遗留包络内（刻度按历史值钉死，
   `test_basis_axis_legacy_envelope_identical` 字面断言）；越界量级（530–650、
   -50..-38）由探针场景专门驱动自适应分支——两侧代码的包络门控取值相同，
   真实 config 的贴水率验收值（≤5.55）落在包络内是清单锁定的事实。
3. **日期锚点逐字解析**：configs 里的标注/通道锚点是日期字符串，经 `_xof` 对载入
   的 df 逐字匹配（缺席即 KeyError，两侧同错）；合成 CSV 的日期网格覆盖配置区间
   全部日期，日内配置覆盖 09:30–11:30/13:00–15:00 全部 15 分钟时刻（含 09:45/15:00
   等被引用时刻），锚点解析行为与真实数据逐字一致。
4. **数值驱动分支全覆盖**：合成行情单调+1 步进与随机游走分别驱动
   vwap 零成交填充、basis 正负面积拆分、ffill 缺口、多面板轴重映射等全部分支——
   这些分支由本仓既有测试套件在同一夹具上断言，非"碰巧"路径。

无法逐字复现的部分（原始 `E:/`/`data/`/local-datasource 数据缺席）已在
`test_regression.py`（`QUANT_CHART_TEST_DATA` 缺席 skip）与 `test_acceptance_charts.py`
（CSV 缺席 skip）中按同一既有约定处理；有数据的环境直接跑既有清单即可。

### 测试口径

- 命令：`pytest -q -m "not integration_localds"`
- 基线（任务起点）：`1 failed, 138 passed, 9 skipped, 1 deselected`
- 终态：**`160 passed, 9 skipped, 2 deselected, 0 failed`**（+22 新测试；138 不减；
  预存失败 test_api_success 修复为 deselect）
- 既有三层验收清单（chart_01/02/03）零改动；新增 `daily_volume` 清单登记为第 4 图。

## 三、验收输出留档

```
$ pytest -q -m "not integration_localds"
160 passed, 9 skipped, 2 deselected in 15.5s

$ python tools/verify_chart.py configs/daily_volume_demo.yaml \
    out/projects/daily_volume_demo/chart.png --checks tests/acceptance_checks/daily_volume.py
验收通过: out/projects/daily_volume_demo/chart.png（0 违规）

$ chartflow run configs/daily_volume_demo.yaml
PNG  -> out/projects/daily_volume_demo/chart.png
HTML -> out/projects/daily_volume_demo/chart.html
项目 -> out/projects/daily_volume_demo（config 快照已归档）
数据来源:条形CSV(daily_volume_demo.csv)；交易日60天。
```

### Fresh clone 复现（换台机器开箱验证，2026-09-01 自查实跑）

```
$ git clone -b task2/gazelle <repo> /tmp/fresh_qc && cd /tmp/fresh_qc
$ python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
$ .venv/bin/chartflow run configs/daily_volume_demo.yaml
PNG  -> out/projects/daily_volume_demo/chart.png
HTML -> out/projects/daily_volume_demo/chart.html
项目 -> out/projects/daily_volume_demo（config 快照已归档）
数据来源:条形CSV(daily_volume_demo.csv)；交易日60天。

$ .venv/bin/python -m pytest -q -m "not integration_localds"
160 passed, 9 skipped, 2 deselected in 12.34s

$ .venv/bin/python -m pytest tests/test_acceptance_charts.py -v
tests/test_acceptance_charts.py::test_acceptance_chart[daily_volume_demo-examples/daily_volume_demo.csv] PASSED
1 passed, 3 skipped in 1.25s        # 三张参考图按既有约定 skip（data/ 缺席）

$ .venv/bin/python tools/verify_chart.py configs/daily_volume_demo.yaml \
    out/projects/daily_volume_demo/chart.png --checks tests/acceptance_checks/daily_volume.py
验收通过: out/projects/daily_volume_demo/chart.png（0 违规）
```

fresh clone 成品与工作区成品 md5 逐字节一致（`7318e11cd427422b04ead41684db56b4`）。
注：系统自带 python3（pip 21）不支持 PEP 660 editable 安装，需 Python ≥3.12
（`requires-python = ">=3.12"`）。

## 四、交付物索引

| 交付物 | 路径 |
|---|---|
| 示例 config | `configs/daily_volume_demo.yaml` |
| 示例数据（合成，种子 20260831 可复现） | `examples/daily_volume_demo.csv`（生成器 `tools/make_demo_daily.py`） |
| 成品图 | `out/projects/daily_volume_demo/chart.png`（+ chart.html、config 快照） |
| 验收清单 | `tests/acceptance_checks/daily_volume.py`（登记于 `test_acceptance_charts.py` 第 4 图） |
| 设计决策（本文） | `IMPLEMENTATION_NOTES.md` |
| 偏差与裁决 | `DEVIATIONS.md`「Task2 偏差记录」 |
| 接口约定 | 设计文档 §9 增补（`docs/superpowers/specs/2026-08-28-daily-candle-charting-design.md`） |

## 五、提交序列（语义化小步，工具/文档分离提交）

1. `fix(render)` P2#3 `_hline` 死赋值与 to-only 标注错位（+3 回归测试）
2. `fix(render)` P2#4 贴水副轴刻度数据自适应（+3 回归测试）
3. `feat(render/core)` 日线多面板——解除单面板红线，接入 extra_panels 体系
4. `feat(plugins/render)` 成交量子图——volume 原语 + volume_panel 一键声明
5. `fix(tests)` test_api_success 补 integration_localds 标记（预存缺陷）
6. `fix(qa)` _by_color 跳过无 .line 的 trace（+1 回归测试）
7. `feat(tests/configs)` 验收清单+示例配置（17 项新测试；两处拒绝测试 1:1 改写为支持测试）
8. `test(pipeline)` YAML row_heights 日内同效回归
9. `docs` README/DEVIATIONS/设计文档/本 NOTES（第一轮文档）
10. `chore(tools/docs)` fig_compare 对比工具入仓+自查证据留档
11. `fix(render)` 自审薄弱点——_panel_range 空值守卫/纵轴取数列泛化/zero_floor 面板键
12. `fix(render)` _panel_range 守卫补洞——cols 非空但列全缺时不崩
13. `test(render)` 多面板/量柱边界自查+存疑项收尾
14. `chore(tools)` fig_compare 探针化——P2#3/#4 修复目标拆独立探针场景
15. `docs` 自审轮文档（§7 薄弱点/边界/存疑收尾、§9.5 扩展契约、合成数据等价性论证）
16. `feat(plugins)` MA 窗口超数据长度不画+脚注回显（backlog #23）
17. `test(plugins)` MA 窗口四类回归+日内换算+e2e
18. `docs` 追加轮文档（§八 决策与证据、DEVIATIONS、设计文档 FR-5、README、backlog 核销）

## 六、未做与后续

- overlay 双右轴（贴水率）不进日线（无贴水概念）；
- `Ctx.y2axis` 字段仍未使用（P2#5，非本轮范围）；
- 量柱目前单色阶（红/青二色），未来如需"量能均线/地量地价"等要素，按原语扩展而非新面板类型。

## 七、自审轮记录（2026-09-01，对照验收标准自查）

### 7.1 薄弱点修复（修前→修后）

| # | 薄弱点 | 修前 | 修后 | 测试 |
|---|---|---|---|---|
| 1 | `_panel_range` 遇列缺失/全 NaN 崩溃 | `np.concatenate([df[c].dropna()...])` 空列表抛 ValueError；cols 非空但列全缺同样崩 | 先收 arrays 再判空，退化为 `[0,1]`，空面板仍成行 | `test_volume_all_nan_explicit_panel_no_crash` / `test_volume_column_absent_explicit_panel_no_crash`（修前复现崩溃，修后钉住） |
| 2 | 纵轴取数列硬编码 `("line","volume")` 元组 | 未来同构原语（带 `col`）漏网、纵轴退回 close | 收所有带 `"col"` 的图层（标注类原语无 `col` 天然排除） | `test_zero_floor_panel_key`（line 层 + `zero_floor: true` 锁 0 基线） |
| 3 | `zero_floor` 只能按 volume 类型自动识别 | 新原语无法表达 0 基线 | 面板显式 `zero_floor: true` 或含量柱层自动 | 同上 |

另：`_volume` 缺 open/close 列由裸 KeyError 改为中文报错（`test_volume_requires_ohlc_columns`）。

### 7.2 边界行为表（新面板逐条，测试证据）

| 边界 | 行为 | 测试 |
|---|---|---|
| 空数据（0 行） | 槽位引擎先行报"日线数据为空"，多面板路径不绕过该守卫 | `test_empty_df_rejected_before_layout` |
| 成交量全 NaN | 原语省略无量柱；面板纵轴退化 [0,1]，不崩 | `test_volume_all_nan_explicit_panel_no_crash` |
| 无量（列缺失） | 插件不追加空面板；手写面板原语省略、纵轴退化 [0,1] | `test_volume_panel_skipped_without_volume_column` / `test_volume_column_absent_explicit_panel_no_crash` |
| 单根 K 线 | 槽位/量柱/面板均不崩 | `test_volume_panel_single_candle` |
| 成交量全零 | 量柱零高度成图，量轴退化 [0,0.16] | `test_volume_all_zero_renders_flat` |
| 日期段不连续（跳日） | pos 逐行连续压缩，量柱与 K 线逐柱同位 | `test_date_gap_bars_align_with_candles` |
| n≥3 面板 | 中间面板刻度隐藏、底轴画刻度、row_heights 三行生效 | `test_three_panel_layout_ticks_and_heights` |

### 7.3 上轮存疑项收尾对照

| 存疑点 | 处理 | 证据 |
|---|---|---|
| 1. chart_01/02/03 真实数据未本机复现 | 论证：`data/*.csv` 按 gitignore 设计缺席，验收按既有约定 skip（同 `test_regression.py` 的 `QUANT_CHART_TEST_DATA` 先例）；替代证据=同管线合成渲染 0 diff + 清单字节零改动（§二） | 环境限制，补验路径：有 `data/` 时跑 `pytest tests/test_acceptance_charts.py -v` |
| 2. test_api_success 未在装包环境实跑 | **补上机器证据**：`test_api_success_with_injected_fake` 向 sys.modules 注入假 local_datasource，成功路径本机可跑（与标记版同逻辑） | 新测试通过（口径内） |
| 3. PNG 跨 OS 像素一致性 | 论证：机器验收口径是 fig 断言（三层清单），PNG 为交付物；同机两 checkout md5 一致已证；字体回退是 plotly/OS 层 | 无需测试（文档已注字体要求） |
| 4. n≥3 布局未测 | **补上**：`test_three_panel_layout_ticks_and_heights` | 新测试通过 |
| 5. .DS_Store 工作区噪声 | `git status` 干净（.DS_Store 已 checkout 恢复，不入库） | 每轮收尾核验 |

### 7.4 探针分类（对比工具反证，详见 §二）

预期 diff（修复目标）31 处 = P2#3 探针 1 处 + P2#4 探针 19+11 处，全部落在
xref/tickvals/range 修复面；意外 diff（回归）0 处。

## 八、追加轮：MA 窗口超数据长度（backlog #23）

### 决策（三选一论证）

- **现状实测**：12 行数据 + `ma=[20,60]`——`rolling(20/60)` 全 NaN，图层仍进图
  （scatter 全 NaN 图上不可见），脚注静默、图例仍显示 MA20/MA60（误导）。
- **选择**：窗口 ≤ 数据长 → 画 partial 末段（现有 rolling 语义，保留真实 MA 含义，
  与 backlog #23「语义保留、不静默截断」一致）；窗口 > 数据长 → **不画**（图层移除、
  图例同步消失）+ 脚注回显「MA 窗口超出数据长度（N根），未绘制: MA20（20根）、…」。
- **不画 vs 画可用部分 vs 报错**：
  - 「画可用部分」须 `min_periods=1`，会把 MA20 算成 5 根均值——篡改 MA 语义，排除；
  - 「报错」会阻断整张图：多窗口混合时一个超长窗口毁掉全图，且行情软件从不因指标
    窗口不足拒绝出图，排除；
  - 「不画+回显」与 TradingView（`ta.sma` 窗口不足返回 na 不画线不报错）、
    通达信/同花顺（窗口不足不画）一致，且符合本仓「不静默」哲学（P0 守卫同族）。
- **配色稳定性**：颜色按 MA 原序号取 palette，缺失窗口不挤压其余 MA 配色
  （`test_ma_windows_mixed_keeps_shorter_with_note` 钉住）。

### 证据

- 回归测试 6 项（`test_daily_plugin.py` 5 + `test_daily_pipeline.py` 1）：
  窗口内 / 恰等于 / 超出 / 多窗口混合 / 日内换算路径（ma5→80 根 > 64 根）/ e2e 脚注；
- 兼容：fig_compare 既有 11 场景全 0 diff（既有 config 窗口均在数据长内），
  pytest 176 passed / 0 failed。

## 九、合并后修复轮（2026-09-01，PR #1 合并评审 + 三笔加固）

PR #1 评审发现三处问题：一处自述不变式破损（合并前修上 PR 分支）、两处 P3
边角（合并后直接 master）。全部 TDD（修前 RED → 修后 GREEN）+ gate 验证。

### 9.1 P2#4 包络内下限 leak（commit 9d52c2e，合并前修入 PR）

- **问题**：`_basis_axis` 包络分支返回 `min(-15, b0-10%span)`——当 `0.1*span > b0+15`
  （如贴水 -10..100，包络内）下限突破 -15，违背 PR 自述"包络内逐值不变"。
  钉死测试与 gate 合成数据的贴水都在 300 附近，恰好不在 leak 区——守护未覆盖
  其声称的不变式。
- **修法**：包络分支直接返回 `-15.0`（历史值）；数据下扩只属超包络分支（行为不变，
  `test_basis_axis_beyond_envelope_not_clipped`/`negative_floor_extends` 原测全过）。
- **证据**：leak 区 5 例参数化回归 `test_basis_axis_envelope_floor_pinned_at_minus15`
  （4 leak 区 + 1 对照；修前 4 败/修后全过，断言含贴水率轴联动）；全量 188P/0F；
  gate 14 场景 PASS（场景数据均不在 leak 区，修复对既有渲染零影响）。

### 9.2 日线手写面板缺省轴解析（commit dcf92a6）

- **根因**：轴缺省解析责任放错层——原语层硬编码 `y2`（日内贴水 overlay 语义），
  日内 `_remap_axes` 对 panel[0] 缺省解析到 `overlay_y2`（语义正确），日线版拷贝时
  把 panel[0] 的解析整个丢掉（`default_axis=None` 原样返回），单面板路径不经 remap。
  `panels:` 整体替换插件面板（merge_panels 最高优先级）绕过插件
  `setdefault(axis="y")` 注入 → 缺省漏到硬编码 `y2`。
- **症状矩阵**（比评审初判更广）：多面板+数据段 hline/area → 静默画到第 2 行量轴；
  纸面全宽 hline → `_hline` 守卫误报"副轴请给 from/to"（用户并未要求副轴）；
  单面板+数据段 → 幽灵轴线不可见。
- **修法**：`_remap_daily_axes` 覆盖所有面板（panel[0] 目标 `"y"`）+ 单面板路径接入；
  显式 `axis: "y2"` 仍视为字面轴引用不改写。插件自产层已有 `axis="y"`，remap 是
  no-op——gate 0 diff 证实既有渲染零影响。
- **证据**：3 回归（多面板静默路径 / 单面板误报路径 / `panels:` 整体替换 e2e），
  修前全败修后全过；全量 194P/0F；gate PASS。偏离"与日内同构"注记已登记 DEVIATIONS。

### 9.3 日内 row_heights 长度校验（commit 723ba67）

- **问题**：长度与面板数不符时——多面板落到 plotly 英文报错
  （`must be a list of numbers of length 2`），**单面板被 `_build_single` 静默丢弃**
  （配置写错无迹可寻，比评审初判的"英文报错"更糟）。
- **修法**：`run_pipeline` 面板数定稿后、`build_figure` 前校验，文案与日线一字不差。
- **证据**：双路径回归（3≠2 多面板 / 2≠1 单面板静默路径），修前 plotly 英文错 +
  DID NOT RAISE，修后中文报错；全量 195P/0F；gate PASS。

### 9.4 文档同步

- README「多面板与成交量子图」：row_heights 长度规则、缺省轴解析范围（所有面板
  含手写主图/单面板）两处补句；
- DEVIATIONS 登记 9.2 的"与日内同构"偏离（见「合并后修复轮」条目）。
