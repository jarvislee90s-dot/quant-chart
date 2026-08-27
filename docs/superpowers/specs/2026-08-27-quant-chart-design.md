# quant-chart 设计文档

日期：2026-08-27
状态：已获用户认可（含 Plotly 内核样张验证通过）

## 1. 背景与目标

IM2612 贴水监控与击球区标注图（Backset 目录下 V1/V2 脚本）暴露了临时脚本模式的痛点：每次调整策略参数、更换标的、改变图型都要改代码。本项目把这些成果泛化为一个 **YAML 驱动的行情图工作流**：

- 数据输入：Wind 导出 Excel（分钟级主通道）+ 免费 API（自动降级）
- 换策略 = 改 YAML 参数或新增一个小插件文件，不改编译好的引擎代码
- 出图：静态研报 PNG + 交互 HTML 双形态

**非目标**（明确不做）：回测引擎、实时行情推送、Web 服务、仓位管理（二期再议）。

## 2. 通用规律：四段式流水线

所有"价格+指标+信号+注释"类分析图都可拆为同一条流水线：

```
① 数据适配   Excel(Wind模板)/API → 统一分钟表(datetime, OHLC, 量额, 多标的列)
② 指标计算   纯函数注册表：往表上加列（贴水、比值、均线…），指标可引用指标；不画图的列也在此层
③ 信号生成   在指标列上声明条件 → 事件点(时间+价格+标签) 与 时序序列(仓位等)
④ 图层渲染   面板=图层堆叠；图层只做"某列→几何形状"的映射，不含计算
```

关键洞察：买卖点、仓位、贴水在数据层面无本质区别——都是时间索引上的列。因此图型天然可组合，多面板（上：买卖点；下：持仓金额）共享同一压缩 X 轴。

## 3. 架构

```
quant-chart/                      # 独立 git 仓库，E:\LLMproject\Github\quant-chart
├── src/quantchart/
│   ├── adapters/
│   │   ├── excel_wind.py         # Wind 两表模板（期货表+指数表，含脚注行剔除）
│   │   ├── api_sina.py           # 新浪分钟（约4天窗口，短分析够用）
│   │   ├── api_daily.py          # 日线级（降级粗稿）
│   │   └── auto.py               # API优先→覆盖不足则明确提示Excel，绝不静默降级
│   ├── core/
│   │   ├── session.py            # 交易日历+242槽位网格+跨日NaN断点（压缩X轴数据结构）
│   │   ├── indicators.py         # 指标注册表：df→df加列，链式引用
│   │   └── signals.py            # 条件→事件点/序列
│   ├── render/
│   │   ├── figure.py             # Plotly figure 组装：面板、多轴、日期行、日分隔
│   │   └── primitives.py         # 通用绘图原语→Plotly shapes/annotations 翻译
│   ├── plugins/                  # 策略插件目录，自动发现注册
│   │   ├── basis_review.py       # 预设1 = V1图（价格+均价+贴水+每日最低标注）
│   │   └── basis_zones.py        # 预设2 = V2图（+击球区/触发线/低点连线/价差涨幅）
│   └── cli.py                    # chartflow run config.yaml -o out.png [--html]
├── configs/                      # 示例配置（两预设各一份，含注释说明）
├── tests/
└── docs/
```

渲染内核：**Plotly**（plotly.py ≥6，kaleido ≥1.3 导出静态图）。选型依据：shapes/annotations 声明式原语直接覆盖矩形区/平行通道/支撑压力线/事件标记/引导线标注；rangebreaks 或槽位法处理休市压缩；交互 HTML 免费副产品。已用样张验证：静态 PNG（中文、压缩X轴、全部注释要素）与交互缩放均达标。matplotlib 槽位法保留为逃生门（render 层接口不变时可替换实现）。

## 4. YAML 配置三层结构

视觉原语与策略解耦：zones 等注释任何策略都能用，不绑定某个策略。

```yaml
input:                            # 数据层
  mode: auto                      # auto | excel | api
  excel: {future: IM2612.CFE原始.xlsx, index: 000852.SH.xlsx}
  api:    {future: IM2612, index: "000852"}
  range: [2026-08-17, 2026-08-27]

strategy: basis_zones             # 计算层：插件名
params:                           # 插件参数（插件定义默认值，此处覆盖）
  trigger: 250

panels:                           # 表达层
  - title: 主图
    layers:                       # 数据驱动图层（引用列）
      - {type: line, col: im_close, color: "#1c4e9d", width: 2}
      - {type: line, col: im_vwap, dash: dash, color: "#ef8a1c"}
      - {type: area, col: basis, axis: y2, pos_color: "#d6404c", neg_color: "#2e9e63"}
    marks:                        # 事件标记（信号层产出）
      - {type: daily_min, col: basis, label: "{value:.0f}"}
    primitives:                   # 通用注释原语（任何策略可用）
      - {type: zone, from: "2026-08-19 11:30", to: "2026-08-21 11:00", price: [7200, 7300], label: "击球区Ⅰ"}
      - {type: hline_trigger, value: 250, axis: y2, scope: zone}
      - {type: hline_ref, col_last: im_close, label: "现价 {value}"}
      - {type: leader_tag, col: im_low, per_day_in: zone, text: "距期末 +{diff}（{pct}%）"}
```

## 5. 插件接口（唯一形状）

```python
@register_strategy("basis_zones")
def run(df: DataFrame, params: dict) -> StrategyOutput:
    ...
# StrategyOutput = DataFrame(新增指标列) + List[Event] + dict(默认panels配置)
```

- 插件只负责计算，不 import 任何渲染库
- 启动时校验接口签名，错误信息定位到插件文件与字段

## 6. 数据质量与错误处理

- 适配器输出质量报告：覆盖交易日数、缺失分钟、前值填充数、来源标记；自动写入图脚注
- API 覆盖不足时明确报"需 Excel 补至 X 日"，不静默用日线冒充分钟
- Excel 解析容错：Wind 脚注行、openpyxl 非法页设置（fallback calamine，V1 已验证）
- YAML 校验错误信息定位到字段路径

## 7. 测试与验收

- **回归基准**：新引擎跑两预设，断言关键数据与 V1/V2 已知结果一致——每日贴水最低序列（295/314/252/252/248/264/247/253/249）、2178 槽位、窗口低点价差（+250/+198/+263/+375/+384）
- 适配器小样本 Excel 单测；槽位网格性质测试（跨日断点、242/日）
- 样张目测验收：PNG 与现有 V2 视觉等价（元素齐全即可，不要求像素级一致）

## 8. 二期（接口预留，本期不实现）

- 仓位/持仓时序面板（数据模型已兼容：就是一列）
- 信号事件回测联动
- 多标的归一化对比图
- lightweight-charts 盘中实时监控页（如需要）

## 9. 样张与验证记录

- `plotly_sample_v2chart.py`（Backset 目录）：~200 行一次跑通 V2 全要素复刻
- 静态 PNG：kaleido 1.3 + 本机 Chrome，中文/三轴/注释全部正常
- 交互 HTML：浏览器实测缩放至区Ⅱ、分钟细节清晰、悬停可用
- 结论：渲染内核定 Plotly，方案 B（薄引擎+策略插件）定案
