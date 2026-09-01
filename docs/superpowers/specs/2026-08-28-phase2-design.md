# quant-chart 二期设计：作图通用性 + local-datasource 接入

- 日期：2026-08-28
- 状态：待评审
- 前置：MVP（[一期设计](2026-08-27-quant-chart-design.md)、[实施计划](../plans/2026-08-27-quant-chart-mvp.md)）已交付并通过两轮代码审查
- 关联：local-datasource [issue #1](https://github.com/jarvislee90s-dot/local-datasource/issues/1) 与其二期设计（品种覆盖扩展）；消费契约《quant-chart × local-datasource 数据消费契约》（2026-08-28 版，存于用户桌面，联调批引用）

## 一、目标与范围

**目标**：把作图能力铺成通用底座——core 只认数据（时间索引上的列 + 事件列表），不关心数据怎么生成；数据输入新增 local-datasource 单一来源。

**本期（两批次）**：

- 批次1 作图通用性：多面板框架、仓位/买卖点作为纯数据输入、面板追加机制
- 批次2 数据接入：local-datasource 适配器（契约先行，stub 开发）

**明确不做（三期候选）**：规则生成器（条件→仓位模拟；经评审从本期移出——它是特定策略深度的东西，不该进 core）、API 与 Excel 的区间拼接、期权/ETF 品类图、回测语义（止盈止损/滑点/手续费统计）。

**批次3（联调，另行立项）**：local-datasource 真实接口端到端联调、删除 `api_sina.py` 雏形、README 数据来源章节改写。

## 二、批次1：作图通用性

### 2.1 多面板框架（改造 `render/figure.py`）

- `build_figure(df, slots, panels, rep, title)` 签名不变；内部从"单面板断言"放开为 **N 面板**：Plotly `make_subplots(rows=len(panels), shared_xaxes=True)`，`row_heights` 可由配置传入（默认主图 0.72 / 后续面板均分 0.28）。
- 面板归属：`panels` 列表位置即行号；`Ctx` 按面板实例化（axes 名 `x1/y1`、`x2/y2`…），`draw(fig, spec, ctx)` 原语接口不变。
- 仅面板0 保留贴水双右轴（`y2/y3` overlay）能力；其余面板各一个主 y 轴。
- X 轴刻度与日期行只画在**最底面板**；日分隔线以 paper 坐标画一次、跨全部面板高度。
- 兼容性：`len(panels)==1` 时输出与 MVP 视觉等价（关键布局属性一致；回归保障）。

### 2.2 仓位与买卖点：纯数据输入（新增 `core/position.py`）

- 顶层配置（与 `panels` 平级，定位是**数据**而非策略参数）：

```yaml
trades:                          # 或 trades_csv: <路径>，二选一
  - {time: "2026-08-21 09:39", action: buy, lots: 1, price: 7104.4}
  - {time: "2026-08-25 10:00", action: buy, lots: 1}     # 缺 price = 该分钟收盘价
  - {time: "2026-08-27 14:30", action: close, lots: all}
contract_mult: 200
```

- 核心函数（签名定性约定）：`expand_trades(df, trades, contract_mult) -> (df, events)`——在槽位表上展开为两列 `position_lots`（逐分钟净手数，前向填充，初始 0，允许负值）、`position_value`（手数 × contract_mult × 当分钟收盘）；并产出 `trade_exec` 事件（时间、成交价、标签"买1手@7104.4"）。
- 语义要点：`action ∈ {buy, sell, close}`，buy=+lots、sell=−lots、close（lots: all）=清零；`time` 必须是区间内实际存在的交易分钟（复用现有"时间点不在数据中"报错）；动作不加净仓约束——纪律由填表人负责。
- 买卖点标记不新增原语：`events` 原语增加可选 `style_map`（按事件动作映射 buy▲红 / sell▼绿 / close×灰），映射跟数据走、与策略无关；动作信息随事件产出（承载方式在实施计划中定）。
- 数据入口在流水线层（`pipeline.run_pipeline` 解析 `trades` 后调用 `expand_trades`），策略插件不感知。

### 2.3 面板追加机制（改造 `pipeline.merge_panels`）

- 现状：用户 `panels` 整体替换插件默认面板——想加一层就得抄全默认，体验差。
- 新增顶层 `extra_panels: [...]`：**追加**在插件默认面板之后；`panels` 仍为整体替换，两者可并用，优先级 panels > extra_panels > 默认。
- 不新增预设插件：`basis_zones + trades + extra_panels(仓位面板)` 即得"行情+仓位"双面板图；提供示例配置 `configs/basis_zones_position.yaml` 与 README 章节。

## 三、批次2：local-datasource 适配器

### 3.1 适配器（新增 `adapters/local_ds.py`）

- 核心函数：`load_via_local_ds(input_cfg) -> (df, QualityReport)`——**库直调**（契约§1 v1.1：CSV 读回形态）`local_datasource.providers` 的期货/指数分钟接口：`file_path` 由我方指定到临时目录，调用后 `pd.read_csv(path, encoding="utf-8-sig")` 读回，按契约§3 做列名映射（含中文列名容错；附加列如指数/个股的 `amount`、期货日线的 `settle` 直接忽略），产出与 excel_wind 同构的规范宽表。粒度映射：我方仅用 1 分钟 → 对方 `freq="1"`。
- 对齐逻辑下沉共用层 `adapters/common.py`（从 `excel_wind` 抽出日网格、reindex、前值填充、质量报告），两个适配器同源，保证规范宽表与质量脚注一致。
- `QualityReport.source = "local-datasource"`，脚注自动体现数据来源。

### 3.2 auto 语义（改造 `adapters/auto.py`）

- `mode: auto` = local-datasource 全区间优先；精确捕获 `local_datasource.providers.common.CoverageError`（`ValueError` 子类，message 含覆盖区间起止日与"补数"字样），正则提取**覆盖起始日**后**整体转 Excel** 并提示"API 数据自 X 日始，更早区间已改用 Excel"（补洞范围 = 起始日之前的区间）。
- `mode: api` = 只走 local-datasource，超覆盖直接报 Excel 补洞指引（不转译）。
- **v1 不做 API+Excel 区间拼接**（对齐与重复区间裁剪复杂度高，联调批按实际体验再议）。
- 未安装 local-datasource：auto/api 启动即报"未安装（pip install -e <本机路径>）或改用 mode: excel"，不静默。

### 3.3 stub 与契约测试

- 合成样本 DataFrame（按契约§3 构造：列名、datetime 格式、volume=0 语义）+ monkeypatch import，全程不连网、不依赖对方仓库。
- 契约测试逐条对照消费契约文件编号（§1 纯函数形态、§3 列名、§4 异常可捕获与 message 要素），测试注释引用§号，契约文件更新时测试同步。
- 联调专属测试打 marker `integration_localds`，未安装自动 skip。
- `api_sina.py` 本期保留不动，批次3 联调通过后删除。
- 联调基线：local-datasource commit `98cd3bd`（CoverageError 与列名清单在此交付）；按其建议锁 commit 安装（`pip install -e` 于固定提交）。

## 四、错误处理（定性）

- 配置错误：`trades` 条目缺字段/动作非法/时间不存在 → `ConfigError` 风格，错误信息定位到条目下标与字段（如 `trades[2].lots`）。
- 数据错误：local-datasource 异常分两类处理——覆盖不足（转译为补洞指引）、其他异常（原样上报，附"可改用 mode: excel"提示）。
- 渲染容错：无 trades 时一切照旧；trades 存在但某面板引用了不存在的列 → 启动时报错并列出可用列。

## 五、测试与验收（定性）

- 单测：`expand_trades`（累计/清零/负仓位/价格缺省/时间不存在）、`extra_panels` 合并顺序、多面板 axes 归属与共享X、`style_map` 映射、local_ds 列名映射与异常转译（stub）。
- 回归红线：MVP 的 34 个既有测试全绿；单面板输出视觉等价（关键布局属性断言一致）。
- 验收图：真实 IM2612 数据 + 手填 3–4 笔交易（8/21 09:39 买、8/25 买、8/27 平），产出"上面板击球区图+买卖点 / 下面板仓位阶梯"双面板 PNG+HTML；人工核对标记成交价与手填一致、仓位跳变发生在对应分钟。
- 批次2 验收另含一份 stub 数据的双面板冒烟图（证明数据来源切换不动渲染层）。

## 六、三期清单（记录在案）

规则生成器（条件→仓位模拟，普通插件形态）、API+Excel 区间拼接、期权/ETF 品类接入、更多面板子图类型（成交量子图等）、信号回测联动。

> 2026-08-31 task2 核销：**成交量子图 + 日线多面板**已交付（volume 原语 + `params.volume_panel`
> 一键声明，接入与日内同一 `panels/extra_panels/row_heights` 机制）。接口约定与验收见
> 《日线设计文档》§9 增补；其余三期项仍记录在案。
