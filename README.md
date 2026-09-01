# quant-chart

**YAML 驱动的行情图工作流**：准备好数据两表、改几行配置，一条命令产出研报级行情图（PNG）和可缩放交互图（HTML）。内置中证1000股指期货贴水监控两套预设，贴水、击球区、买卖观察窗等要素开箱即用；另含**深色策略蜡烛图产品线**（日线/日内，`daily_candle` 预设：红涨青跌 K 线 + 工作日均线 + 自动拟合通道 + 8 类声明式标注），见「五之二」。

![basis_zones 效果图](docs/images/basis_zones_example.png)

---

## 一、架构介绍

### 1.1 四段流水线

```mermaid
flowchart LR
    FE["Wind 导出 · 期货分钟表"] --> AD
    IE["Wind 导出 · 指数分钟表"] --> AD
    LDS["local-datasource<br/>api/auto 通道 · 分钟+日线<br/>（库直调，近期窗口）"] --> AD
    AD["① 数据适配器 adapters/<br/>excel_wind · local_ds · common 对齐层<br/>缺失分钟前值填充 · 质量报告"]
    AD --> CAN["规范宽表<br/>datetime + fut_* + idx_*"]
    CAN --> SE["② 槽位引擎 session.py<br/>242格/日 · 交易时段压缩X轴 · 跨日断线"]
    SE --> IND["③ 指标注册表 indicators.py<br/>basis 贴水 / vwap 均价 / basis_rate 贴水率"]
    IND --> SIG["信号层 signals.py<br/>每日最低 · 窗口最低事件"]
    SIG --> PLG["策略插件 plugins/<br/>basis_review / basis_zones<br/>（只算不画）"]
    PLG --> RD["④ Plotly 渲染 render/<br/>面板 · 双右轴 · 通用注释原语"]
    RD --> OUT1["PNG 1600×900 研报图"]
    RD --> OUT2["HTML 交互图 · 缩放悬停"]
```

以上为**分钟级贴水管线**；深色策略蜡烛图（日线/日内条形）走 `daily_*` 旁路管线（条形 CSV / 期货主连日线 → 条形槽位 → `daily_candle` 插件 → 深色主题组装，含通道自动拟合与出图自检），数据流与用法见「五之二」。

### 1.2 三层配置理念：改需求只动对应的层

| 你想改什么 | 动哪里 | 举例 |
|---|---|---|
| 数据（换合约、换区间） | `input` | 换两个 Excel 路径、改 `range` |
| 计算（策略参数、击球区、触发线） | `strategy` + `params` | 改 `trigger: 250`、增删 `zones` |
| 外观（画什么线、什么颜色） | `panels.layers` | 一般不用动，插件已给默认图层 |

90% 的日常需求只动前两层，不用碰任何代码。

### 1.3 目录结构

```
quant-chart/
├── configs/               # 配置模板（复制一份改成你的）
├── src/quantchart/
│   ├── adapters/          # ① 数据适配（Wind Excel / local-datasource）
│   ├── core/              # ②③ 槽位引擎 / 指标 / 信号 / 插件注册 / 流水线
│   ├── render/            # ④ Plotly 原语翻译与面板组装
│   └── plugins/           # 策略插件（basis_review / basis_zones）
├── tests/                 # 单测 + 真实数据回归 + 三图三层验收（acceptance_checks/）
├── tools/                 # fetch_daily 取数 · verify_chart 出图自检 CLI
└── docs/                  # 设计文档 / 实施计划 / 待办 backlog/ / 图片
```

---

## 二、操作手册（从零到出图）

### 操作流程总览

```mermaid
flowchart TD
    S0["Step 0 准备环境"] --> S1["Step 1 Wind 导出两张分钟表<br/>（只想看最近几天？改 mode: api 可免 Excel）"]
    S1 --> S2["Step 2 复制模板，改 YAML 字段"]
    S2 --> S3["Step 3 chartflow run 出图"]
    S3 --> OK{"出图成功？"}
    OK -- "否" --> ERR["对照「六、常见报错排查」修复"] --> S2
    OK -- "是" --> S4["Step 4 检查质量脚注，查看 PNG / HTML"]
```

### Step 0：准备环境

- Python ≥ 3.12
- 本机装有 **Chrome 浏览器**（kaleido 静态出图依赖它）
- 安装本包（在仓库根目录）：

```bash
pip install -e ".[dev]"
```

验证：`chartflow --help` 能打印帮助即安装成功。

### Step 1：准备数据（两张 Excel）

从 Wind 导出**两张分钟级 Excel**，一张期货、一张现货指数（只想看最近几天、手头没有 Excel？见速查表 `mode: api` 行）。要求：

| 要求 | 说明 |
|---|---|
| 列名（10 列，顺序不限） | `代码, 名称, 日期, 开盘价(元), 最高价(元), 最低价(元), 收盘价(元), 涨跌幅, 成交额(百万), 成交量(股)` |
| 粒度 | 每行一个分钟；交易时段内的分钟（午休、周末本来就没有） |
| 时间覆盖 | 两张表都覆盖你要分析的日期区间 |
| 脚注行 | 末尾的“数据来源：Wind”行**允许存在**，程序自动剔除 |
| 缺失分钟 | 个别分钟缺失没关系，程序自动**前值填充**，并在图脚注报告填充数量 |

> 示例数据即 `E:/LLMproject/PersonalAffairs/Backset/` 下的 `IM2612.CFE原始.xlsx`（期货）与 `000852.SH.xlsx`（指数），可参照其格式。

### Step 2：复制模板，改 YAML

```bash
mkdir my
cp configs/basis_zones.yaml my/first.yaml
```

打开 `my/first.yaml`，按下表逐字段修改（模板里的路径是示例，务必替换成你自己的）：

| 字段 | 必填 | 含义 | 示例值 |
|---|---|---|---|
| `input.mode` | 是 | 数据模式：`excel`=Wind 两表（任意历史深度）；`api`=local-datasource（期货分钟约 4 个交易日、指数约 8 个，需已安装）；`auto`=API 优先、覆盖不足自动整体改用 Excel（需同时配 `input.api` 与 `input.excel`，脚注标注降级） | `excel` |
| `input.excel.future` | mode=excel/auto | 期货分钟表路径。Windows 路径请用正斜杠 `/` | `E:/data/IM2612.CFE原始.xlsx` |
| `input.excel.index` | mode=excel/auto | 指数（现货）分钟表路径 | `E:/data/000852.SH.xlsx` |
| `input.api.future` / `input.api.index` | mode=api/auto | 期货与指数代码（经 local-datasource 取数） | `IM2612` / `000852` |
| `input.range` | 是 | 分析区间 `[起始日, 结束日]`，闭区间；api/auto 模式还用它做分钟深度校验 | `[2026-08-17, 2026-08-27]` |
| `strategy` | 是 | 策略预设：`basis_review`=纯行情+贴水+每日最低；`basis_zones`=再加击球区/触发线/低点价差标注 | `basis_zones` |
| `title` | 否 | 图表标题（也可用命令行 `--title` 覆盖） | `"IM2612 行情与贴水"` |
| `params.trigger` | zones 用 | 贴水触发线数值（点），画在击球区内 | `250` |
| `params.zones[].from / to` | zones 用 | 击球区起止时间 `"YYYY-MM-DD HH:MM"`，**必须落在数据区间内的交易时段** | `"2026-08-19 11:30"` |
| `params.zones[].price` | zones 用 | 击球区价格带 `[下沿, 上沿]`（点） | `[7200, 7300]` |
| `params.zones[].label` | zones 用 | 击球区标签文字，显示在框内底部 | `"击球区Ⅰ"` |
| `trades` / `trades_csv` | 否 | 手填交易明细列表（或 CSV 路径，二选一）。每条 `{time, action, lots, price?}`，action ∈ buy/sell/close，close 的 lots 写 `all`；缺 price 用该分钟收盘价。配置后自动在主图标注买卖点（买▲红/卖▼绿/平×灰）并在数据中生成仓位 | `[{time: "2026-08-21 09:39", action: buy, lots: 1}]` |
| `contract_mult` | 否 | 合约乘数，用于 `position_value`（手数×乘数×价） | `200` |
| `extra_panels` | 否 | 在默认面板后**追加**面板（`panels` 是整体替换，两者可并用）。可选键 `y_title`（轴标题）、`range_cols`（按哪些列定 Y 轴范围） | 见 `configs/basis_zones_position.yaml` 仓位面板 |

### Step 3：一条命令出图

```bash
chartflow run my/first.yaml -o out.png --html out.html
```

| 选项 | 说明 |
|---|---|
| `-o, --output` | 输出 PNG 路径（默认 `out.png`，固定 1600×900；目录不存在会自动创建） |
| `--html` | 同时输出交互 HTML 的路径（不给则不出 HTML） |
| `--title` | 覆盖 YAML 里的 `title` |

成功时控制台输出（最后一行是数据质量脚注，也会印在图的底部）：

```
PNG  -> out.png
HTML -> out.html
数据来源:Wind Excel；交易日9天/分钟槽位2178个，期货前值填充6分钟，指数前值填充18分钟。
```

### Step 4：查看结果

- **PNG**：白底研报风格，直接插入报告/聊天工具。
- **HTML**：双击用浏览器打开，可**拖框缩放**看分钟细节、**悬停**查任意分钟的数值。注意 HTML 依赖 Plotly CDN，**需联网**首次加载。

---

## 三、图例说明

![图例标注](docs/images/basis_zones_annotated.png)

| 编号 | 要素 | 含义 | 来自哪里 |
|---|---|---|---|
| ① | 分钟收盘价线（深蓝实线） | 期货每分钟收盘价，左轴 | 插件默认图层 |
| ② | 日内均价线（橙色虚线） | 当日累计成交额÷累计成交量，每日重置 | 插件默认图层 |
| ③ | 贴水面积（红/绿，右轴） | 贴水=现货−期货；红=贴水、绿=升水；右侧外轴为贴水率% | 插件默认图层 |
| ④ | 每日贴水最低倒三角 | 每个交易日的贴水最低点数值；**黑色**=当日曾触及触发线 | 插件默认图层 |
| ⑤ | 击球区矩形 | 买入观察窗（时间×价格带） | `params.zones` |
| ⑥ | 区内触发线（墨绿虚线） | 贴水=trigger 的参考线，只画在击球区内 | `params.trigger` |
| ⑦ | 现价基准线（灰虚线） | 区间最后一分钟收盘价，横贯全图 | 插件默认图层 |
| ⑧ | 低点连线+价差标注（紫） | 击球区窗口内各交易日最低价，虚线连到现价线，标注“距末日收盘价 +价差（+涨幅%）” | `params.zones` |
| ⑨ | 日期行 | 每个交易日的日期，置于时间刻度下方独立一行 | 引擎自动 |
| ⑩ | 右侧双轴 | 贴水（点）与贴水率（%） | 引擎自动 |
| ⑪ | 仓位阶梯线（下面板）与买卖点标记 | 下面板净持仓阶梯（0→1→2→0，hv 阶梯）；主图买▲红/卖▼绿/平×灰标在成交分钟 | 顶层 `trades` + `extra_panels`（示例 `configs/basis_zones_position.yaml`） |

X 轴只含实际交易时段（09:30–11:30、13:00–15:00），午休与跨日间隙自动压缩、跨日不连线。

---

## 四、数据来源

### 4.1 两条数据通道

| 通道 | 深度 | 适用 |
|---|---|---|
| **Excel（Wind 导出）** | 任意历史 | 主通道：任意区间分析、离线可用 |
| **local-datasource** | 期货分钟约 4 个交易日（新浪源）、指数分钟约 8 个（腾讯源），按实际数据动态判定 | 近期窗口快速看图；`auto` 模式下覆盖不足自动整体改用 Excel |

背景实测（2026-08，直连免费接口的分钟深度天花板，local-datasource 封装后同理）：新浪期货分钟约 4 个交易日、腾讯指数分钟约 8 个、东财 push2his 当时整域拒绝、通达信 pytdx 不可用（乱码/停服）。**分钟级长历史免费源无解，深度靠 Excel 补。**

### 4.2 local-datasource 接入（已交付）

分钟与日线统一经 [local-datasource](https://github.com/jarvislee90s-dot/local-datasource)（本机数据服务仓，库直调、CSV 读回，消费契约 v1.1），`mode: api` / `mode: auto` 均可用：

- `api`：只走 local-datasource；请求区间早于源覆盖（期货分钟约 4 个交易日、指数约 8 个，深度按实际数据动态判定）时明确报错并给补数指引，绝不静默降级
- `auto`：API 优先；覆盖不足时自动整体改用已配置的 Excel，脚注标注「API自X日始，已整体改用Excel」
- Excel 通道职责：补 API 覆盖不到的历史区间（任意深度）
- 版本锁定：联调基线 commit `d106144`（建议 `pip install -e` 于固定提交）

---

## 五、常见改法速查

| 想做什么 | 改哪里 |
|---|---|
| 换分析区间 | `input.range` 两行日期 + `title` 里的日期 |
| 换合约 / 换指数 | `input.excel.future` 与 `input.excel.index` 两个路径 |
| 调整击球区窗口或价格带 | `params.zones` 的 `from`/`to`/`price` |
| 增删击球区 | `params.zones` 列表增删条目（每个区自动带触发线与低点标注） |
| 不要击球区，只看行情+贴水 | `strategy: basis_review`，删掉 `params` 段 |
| 改贴水触发线 | `params.trigger` |
| 只看最近几天（手头没有 Excel） | `mode: api` + `input.api` 两行代码 |
| 只改标题 | `title` 或命令行 `--title` |
| 想看自己的仓位 | 顶层写 `trades` + `extra_panels` 仓位面板（完整示例 `configs/basis_zones_position.yaml`） |
| 主图下加成交量子图 | 日线 `params` 下写 `volume_panel: true`（示例 `configs/daily_volume_demo.yaml`） |
| 自定义副图 / 调面板高度 | 顶层 `extra_panels` + 可选 `row_heights`（如 `[0.6, 0.25, 0.15]`） |

## 五之二、深色策略图（日线/日内）

`strategy: daily_candle` 产出深色研报蜡烛图：红涨青跌 K 线 + 均线 + 通道与声明式标注，槽位引擎按「每交易日根数」自适应日线与日内。数据输入有两条通道：

| 通道 | `input.mode` | 必填 | 适用 |
|---|---|---|---|
| 通用条形 CSV | `daily_csv` | `input.csv` | 日线 / 15分钟 / 30分钟 / 60分钟均可；列名中英兼容，按 datetime 排序去重 |
| local-datasource | `daily_api` | `input.api.symbol`（如 `IM0`/`CU0`/`TL0`） | 库直调取条形数据，免手工导出 |

两者都必填 `input.range: [起始日, 结束日]` 闭区间。出图命令与一期相同：`chartflow run configs/daily_candle.yaml -o out/daily.png --html out/daily.html`。

### 周期三参数

| 参数 | 默认 | 作用 |
|---|---|---|
| `input.granularity` | `auto` | 周期：`auto` 按数据推断每交易日根数并回显在脚注；也可显式指定 `day`/`week`/`month`/`15min`/`30min`/`60min`，与推断值偏差超 ±15% 直接报错（周期错了整张图就错，不允许静默） |
| `input.tick_anchor` | `"10:30"` | 日内图每日刻度锚定时刻：锚定该日此时刻那根 bar 标日期；该时刻缺失退回日首根只标日期 |
| `input.strict_range` | `false` | `true` 时数据覆盖不足（请求起点早于实际覆盖）直接报错；默认只在脚注提示「数据自X日始，请求起点Y早于覆盖」 |

### 通道与标注：只声明，不算数

- **`params.channels` 自动拟合**：每条通道只写 `{start, end, color, dash}`（窗口+样式），上下两轨由 `fit_channel` 自动拟合——中枢主导三步法：中枢LSQ定角度位置→小角度倾斜→张合压摆动极值。
- **`params.channels` / `params.annotations` 都在 `params` 段下**。`annotations` 共 8 类，定位一律写「x + 价」：x 可以是日期字符串（须在数据中，否则报错）或 pos 数值（bar 槽位序号，预演区可超出数据末根）。

| type | 关键参数 | 示例 |
|---|---|---|
| `hline` | `value`、color、width、dash | `{type: hline, value: 6999.8, color: "#e47b7c", width: 1.0, dash: solid}` |
| `zone` | `from`/`to`、`price`（[下沿, 上沿]）、edgecolor、fillcolor、dash、opacity、label | `{type: zone, from: "2026-08-05 09:45", to: "2026-08-12 15:00", price: [7300, 7430], edgecolor: "#ff0000", fillcolor: "rgba(0,0,0,0)", opacity: .85}` |
| `circle` | `at`（[x, 价]）、size、color、label（序号文字） | `{type: circle, at: ["2026-08-11 13:45", 7560], color: "#eeef4e", size: 20, label: "1"}` |
| `arrow` | `from`/`to`（[x, 价]，箭头指向 to）、color、width、text | `{type: arrow, from: [514.0, 6999.8], to: [514.0, 7560.0], color: "#f21010", width: 3.2}` |
| `trendline` | `from`/`to`（[x, 价]）、color、width、dash、label | `{type: trendline, from: [1022.0, 7456.8], to: [1038.0, 7380.0], color: "#f04a4a", width: 2.2}` |
| `text` | `at`（[x, 价]）、`text`、size、color、bgcolor | `{type: text, at: [470.0, 7240], text: "区间宽度560点", size: 12, color: "#f21010"}` |
| `tag` | `value`（价）、`text`、color（底色）、text_color（字色）；固定挂在图右缘 | `{type: tag, value: 7560.0, text: "7560", color: "#8c4210", text_color: "#f0e0c0"}` |
| `channel` | `from`/`to`（中枢端点 [x, 价]）、lower/upper（下探/上张，可不对称；或 `width` 等宽）、color、dash、line_width、label | `{type: channel, from: ["2026-07-22", 7000], to: ["2026-08-26", 7500], lower: 80, upper: 120, color: "#39d353", dash: dash}` |

非法 type / 缺参数会以中文报错定位到条目序号。

### 元素类型目录（16 原语 / 20+ 语义要素）

绘图原语一共 **16 个**（`render/primitives.py`，分钟线继承 8 个 + 深色产品线新增 7 个 + 成交量子图 1 个）。同一原语按用法拆成语义要素——比如 `hline` 一个原语，按语义就是支撑线 / 压力线 / 多空分界线三种要素：

| 原语(type) | 语义要素（按用法拆） | 说明 |
|---|---|---|
| `candle` | 蜡烛图 | 红涨青跌，每图 1 个 |
| `line` | 均线 | 工作日语义（见下"均线与预测区"），每图 4–5 条 |
| `channel` | **上升通道 / 下降通道**（一声明 = 上下双轨） | `fit_channel` 自动拟合（中枢主导三步法），支持事件式锚定与 label |
| `hline` + `tag` | **支撑线 / 压力线 / 多空分界线 / 历史高点线 / 前低线** + 右缘价格药丸 | 线与药丸成对声明，同高呼应 |
| `zone` | **击球区 / 筹码密集区 / 集合区间 / 箱体** | 时间 × 价格矩形（观察区语义） |
| `trendline` | 手绘趋势线 / 杯柄线 / 点状上升支撑 | 两点线段，可 dash |
| `arrow` | **区间宽度箭头 / 价差箭头 / 走势预演箭头（BULL/BEAR）/ 多空分界小箭头 / 颈线箭头 / 分段下边缘箭头** | 用量最大的标注（四图合计 34 支） |
| `circle` | **关键点圆圈**（假突破/重要K线标记，可带序号） | ①②③④ 式圈注 |
| `text` | **品种大字 / 高低点价签 / 形态说明 / 多空分界文字 / 通道标签** | 自由彩字 |
| `tag` | **右缘价格药丸**（价格数字 / BULL / BEAR） | 固定挂在图右缘 |
| `volume` | **成交量子图**（多面板） | 红涨青跌柱与 K 线同色语义，逐柱对齐；无量自动省略 |

四张已交付图（15 分样板 / 伦敦金 / 沪铜 / 国债TL）的绘制层分布：40 / 26 / 49 / 35 层（合计 150）——其中 `arrow` 34、`text` 40 是标注主力，行情层（candle+MA）每图仅 5–6 层。

### AI 作图标准工作流（含校验回路）

让 AI 依照本库画一张图时，实际执行的是下面这个带**三个回路**的流程（不是线性流水线）——回路①校准标注、回路②修要素缺失、回路③响应独立评审：

```mermaid
flowchart TD
    A["① 参数确认<br/>品种/数据源 · 周期 · 时间窗口 · 关键位阶 · 输出<br/>（未明确就问，不猜）"] --> B["② 取数<br/>fetch_daily：local-datasource / akshare / CSV"]
    B --> C{"③ 覆盖校验<br/>数据起点 ≥ 请求起点？粒度与指定一致？"}
    C -- "不足/不符" --> C2["调整窗口 / 补数 / 修正 granularity"] --> B
    C -- "通过" --> D["④ 读图三步（有样张时）<br/>zoom 逐个确认位阶 → 数据极值交叉验证 → 原文文字优先<br/>证据存 out/refs/"]
    D --> E["⑤ 写 YAML<br/>channels（支持 peak/trough/above/below 事件式锚定）<br/>+ annotations + ma + granularity + forecast_days"]
    E --> F["⑥ 出图 chartflow run --project<br/>一图一文件夹归档：config快照/PNG/HTML/refs/compare<br/>脚注回显：周期推断/每交易日根数/pos锚点/预测区换算/可见性警告"]
    F --> G["⑥b 三层机器验收 qa.verify<br/>L1要素 · L2相对位置 · L3数学 · R渲染保真"]
    G -- "违规（回路①校准）" --> E
    G -- "全过" --> H["⑦ 目检对照<br/>成品 vs 样张并排 zoom 走查"]
    H -- "要素缺失/错位（回路②）" --> E
    H -- "风格同款" --> I["⑧ 独立评审（可选）<br/>第三方视角判定差异幅度"]
    I -- "差异大（回路③）" --> J["分析原因：数据窗口/标定/遗漏/bug"] --> E
    I -- "可接受" --> K["⑨ 交付留档<br/>PNG/HTML + 并排对照图 + 提交"]
```

要点：

- **回路①（校准）**：三层机器验收任何一条违规都回到 YAML 校准——标注数值、坐标、颜色按读图证据修正，改完重出图重验收；
- **回路②（要素）**：目检发现样张有而成品没有的要素（或错位）回 YAML 补齐——窗口扩展后此前"窗外"的元素也要回归（如国债两年窗的 122.28/108.61）；
- **回路③（评审）**：独立第三方视角判定差异幅度，"差异大"须分析原因（数据窗口/标定/遗漏/bug）后回到 ⑤；
- **脚注回显**是每轮回路的自检信号：周期推断、每交易日根数、pos 锚点计数、预测区换算、可见性警告——错在脚注上第一眼可见；
- 无样张的全新图：跳过 ④⑦ 的样张对照，位阶由用户口述或读数提取后同样交叉验证；
- **一图一项目文件夹**（防覆盖）：YAML 顶层 `project: out/projects/<图名>`（或 CLI `--project`）——
  PNG/HTML 默认落 `<project>/chart.png|html`，**运行时自动归档 config 快照**（configs/ 仍为权威源），
  zoom 证据放 `<project>/refs/`、对照图 `compare.png`。每张图的一切产物自包含，后画的图永不覆盖前面的：
  ```text
  out/projects/chart_02_cu0/
  ├── config.yaml      # 运行时配置快照（权威源在 configs/）
  ├── chart.png / chart.html
  ├── compare.png      # 成品 vs 样张并排
  └── refs/            # 读图 zoom 证据
  ```

### 最小 YAML 示例（摘自 configs/daily_candle.yaml 头部）

### 出图自检 CLI（三层验收）

出图后可对「配置 + 成品图」跑机器断言的验收清单——L1 要素齐备 / L2 相对位置 / L3 数学+渲染保真，清单以 python 函数形式随测试交付：

```bash
.venv/bin/python tools/verify_chart.py configs/chart_01_xau.yaml out/projects/chart_01_xau/chart.png --checks tests/acceptance_checks/chart_01.py
```

通过时输出「验收通过: …（0 违规）」。三张样张复刻各配一份成品清单：`tests/acceptance_checks/chart_0{1,2,3}.py`（伦敦金 / 沪铜 / 国债）；多面板+成交量子图配 `tests/acceptance_checks/daily_volume.py`（合成演示数据随仓，任何环境可跑）。

**改动前后渲染对比**：`tools/fig_compare.py` 把 13 个场景（含 7 份既有 config 原样渲染）落成 fig JSON 快照并做语义 diff——`--dump` 落盘基线/当前两份，`--diff` 逐场景报差异（复跑步骤见工具 docstring）。

### 读图证据约定（`out/refs/`）

复刻样张定数值时，关键读数（药丸价格、高低点价签、通道走向等）一律放大截图留证于**项目文件夹** `refs/`（即 `out/projects/<图名>/refs/`），坐标标定依据与逐字确认结论写在对应配置文件头部注释——后续改数可追溯、可复核。

### 通道窗口事件式锚定：绑定业务事件，不绑定日历

`channels` 的 `start`/`end` 除日期字符串外，支持**事件式锚点**——数据刷新自动重锚，杜绝硬编码日期漂移：

| 锚点 | 含义 | 示例 |
|---|---|---|
| `{peak: true}` | 窗口内最高价那根 bar | `start: {peak: true}`（自峰值引出下降通道） |
| `{trough: true}` | 窗口内最低价那根 bar | `end: {trough: true}` |
| `{above: 价, after?: 日}` | 首次**收盘站上**该价位（可限定起始日） | `end: {above: 4384.642, after: "2026-06-30"}`（回升首破=通道终点） |
| `{below: 价, after?: 日}` | 首次**收盘跌破**该价位 | `end: {below: 108.61}` |

解析结果自动回显脚注（如「通道1锚点解析: 2025-02-07→2026-08-10」）；数据窗口内未发生该事件、或规则非法，中文报错定位。

### 均线工作日换算与预测区

- **均线默认按工作日**：日内周期下 `params.ma` 的 N = N 个**工作日**（15 分钟图 `ma: 5` = 16×5 = 80 根）；`ma_unit: "bar"` 特别约定按根数。窗口 ≤ 数据长度时画 partial 末段（不静默截断）；窗口 > 数据长度时该 MA 不画（图例同步消失）并在脚注回显「MA 窗口超出数据长度（N根），未绘制」——与 TradingView/通达信一致，不阻断整图。
- **右缘预测区**：`forecast_days`（顶层，单位**工作日**，默认 2）——为 BULL/BEAR 走势预演留出右侧空白作图区；日线策略图建议 10–15。脚注回显换算（"预测区: 15个工作日 ≈ 15根"）。
- **内置渲染可见性守卫**：任何元素超出 xaxis 范围（Plotly 会静默裁剪、图上不可见）都会在脚注追加"⚠ 渲染可见性警告"——写错坐标当场可见，不靠人眼发现。

### 多面板与成交量子图（日线/日内同一机制）

日线与日内共用同一套多面板机制：顶层 `panels`（整体替换）/ `extra_panels`（追加）+ 可选 `row_heights`（每行高度占比，默认主图 0.72、其余平分 0.28；**长度须等于面板数**，不符报中文错误，日线/日内同校验）。多面板共享 X 轴——主图与子图逐柱对齐，时间刻度只画在最底面板。

- **成交量子图（最常用）**：日线 `params` 下写 `volume_panel: true`，一键在主图下追加成交量子图（等价于手写 `extra_panels: [{title: 成交量, y_title: 成交量, range_cols: [volume], layers: [{type: volume, col: volume}]}]`）。数据取适配器 `volume` 列（CSV `成交量`/`volume`，中英表头兼容）；量柱红涨青跌与 K 线同色语义（色值取自主题，可配 `up/down/opacity/width` 覆盖）；量轴下限锁 0。无量品种（如伦敦金现货）自动省略，脚注提示"无量"。
- **自定义副图**：任意原语都能放进 `extra_panels` 的 `layers`（如把某条均线单独放大到副图：`{title: MA5, y_title: MA5, layers: [{type: line, col: ma5, name: MA5}]}`）；**所有面板（含手写主图 `panels:`/单面板）**的缺省轴与字面 `axis: "y"` 均自动解析为本面板主轴（日线无贴水 overlay，缺省即"本面板轴"；显式 `axis: "y2"` 视为字面轴引用不改写），`range_cols` 指定纵轴取数列（缺省收面板内所有带 `col` 的图层）；`zero_floor: true` 可对任意副图锁 0 基线（量柱面板自动）。
- **新增子图类型**：子图类型 = 绘图原语，约定式自动发现（`render/primitives.py` 加 `_<type>` 即可，无注册表）——接口约定见设计文档 §9.5。
- 空面板列表报错；单面板配置走原路径，渲染结果与多面板改造前逐字节一致（回归测试钉死）。

示例：`configs/daily_volume_demo.yaml`（合成数据 `examples/daily_volume_demo.csv` 随仓，可离线复现），成品 `out/projects/daily_volume_demo/chart.png`。

### 验收清单与待办

- 每幅样张复刻图配一份**三层验收清单**（`tests/acceptance_checks/<图>.py`，L1 要素 / L2 相对位置 / L3 数学关系 + 渲染保真），由 `tests/test_acceptance_charts.py` parametrize 装载，`chartflow` 出图后跑一遍即机器验收（含多面板+成交量子图的 `daily_volume_demo`，CSV 随仓不 skip）；
- 发现但暂不解决的问题登记在 [`docs/backlog/README.md`](docs/backlog/README.md)（如通道自动分段器——拟合主观性强，需人工先指定段边界）。

### 最小 YAML 示例（摘自 configs/daily_candle.yaml 头部）

```yaml
input:
  mode: daily_csv
  csv: data/IM2612_15min.csv
  range: [2026-06-01, 2026-08-28]
strategy: daily_candle
title: "IM2612 合约 · 15分钟策略同款复刻（样板）"
params:
  ma: [5, 10, 20, 30, 60]
  channels:
    - {start: "2026-07-27 09:45", end: "2026-08-18 15:00", color: "#fdfd52", dash: dash}
  annotations:
    - {type: hline, value: 6999.8, color: "#e47b7c", width: 1.0, dash: solid}
    - {type: zone, from: "2026-08-05 09:45", to: "2026-08-12 15:00", price: [7300, 7430], edgecolor: "#ff0000", fillcolor: "rgba(0,0,0,0)", opacity: .85}
    - {type: tag, value: 7560.0, text: "7560", color: "#8c4210", text_color: "#f0e0c0"}
```

## 六、常见报错排查

| 报错（节选） | 原因 | 解决 |
|---|---|---|
| `缺少必填字段: input` / `缺少必填字段: strategy` | YAML 顶层缺字段 | 按报错补上对应字段 |
| `input.mode=excel 需要 input.excel.future 与 input.excel.index 两表路径（缺失: input.excel.index）` | excel 段缺表路径 | 按括号里的字段路径补齐 |
| `未安装 local-datasource…或改用 mode: excel` | `mode=api/auto` 但本机未安装 local-datasource | `pip install -e <其仓库路径>` 或改 `excel` |
| `分钟数据自 X 日始…请从 Wind 导出 Excel 提供补数` | api 模式请求区间早于源覆盖（期货约 4 个交易日、指数约 8 个） | 更早历史改用 `mode: excel`；`auto` 模式会自动整体改用已配置的 Excel 并在脚注标注 |
| `FileNotFoundError: ...xlsx` | Excel 路径不对 | 检查路径，Windows 用正斜杠 `/` |
| `时间点不在数据中: 2026-08-22 13:00` | `zones` 的 from/to 写在非交易日、非交易时段或数据区间外 | 改成区间内实际存在的交易分钟 |
| kaleido / Chrome 相关报错 | 静态导出缺 Chrome | 安装 Chrome 后重试 |
| 脚注“前值填充N分钟” | 数据里个别分钟缺失，已自动用前值填充 | 无需处理；若 N 异常大，检查 Wind 导出是否断档 |
| `周期校验失败: 数据推断每交易日约 N 根…` | 日线模式下 `input.granularity` 与数据实际粒度不符 | 修正 `granularity` 或检查数据；不确定就用默认 `auto` |
| `通道X锚点无命中: …（数据窗口内未发生该事件）` | 事件式锚点（above/below）的价位在窗口内未发生 | 核对价位或放宽窗口；亦可用日期字符串直接锚定 |
| 脚注“⚠ 渲染可见性警告(超界元素成品中不可见)…” | 标注/元素坐标超出 xaxis 范围（图上被裁剪） | 按警告列出的元素修正坐标；pos 锚点注意不要超过交易日数 |

## 七、进阶：写一个新策略插件

`src/quantchart/plugins/` 下新建文件：

```python
from ..core.indicators import apply_indicators
from ..core.plugins import StrategyOutput, register_strategy

@register_strategy("my_strategy")
def run(df, slots, **params):
    df = apply_indicators(df, [{"name": "basis"}])   # 加指标列
    events = []                                       # 可选：产出事件点
    panels = [{"title": "主图", "layers": [...]}]     # 默认图层（YAML 可覆盖）
    return StrategyOutput(df=df, events=events, panels=panels)
```

铁律：**插件只算不画**——不 import plotly，视觉一律交给 `panels.layers` 里的通用原语（line/area/zone/hline/events/leader_tag/day_seps/day_labels）。详见[设计文档](docs/superpowers/specs/2026-08-27-quant-chart-design.md)。

## 八、开发与文档

```bash
pytest -q                          # 全部测试（夹具自动生成，克隆即跑）
pytest tests/test_regression.py -q # 真实数据回归（默认读 Backset 目录，可用 QUANT_CHART_TEST_DATA 改指）
```

- [设计文档](docs/superpowers/specs/2026-08-27-quant-chart-design.md) · [实施计划](docs/superpowers/plans/2026-08-27-quant-chart-mvp.md) · [偏差与已知问题 DEVIATIONS.md](DEVIATIONS.md)
- 深色蜡烛图产品线：[第一篇·通用作图能力](docs/superpowers/specs/2026-08-28-daily-candle-charting-design.md) · [第二批次·剩余三图复刻](docs/superpowers/specs/2026-08-29-three-reference-charts-design.md) · [实施计划](docs/superpowers/plans/2026-08-29-three-reference-charts-batch2.md) · [待办与暂缓事项](docs/backlog/README.md)
- 三期候选（DEVIATIONS 在案）：规则生成器（条件→仓位模拟） · API+Excel 区间拼接 · 期权/ETF 品类 · 回测联动
- 效果图更新：改图后运行 `python tools/annotate_readme_fig.py` 重新生成图例标注版
