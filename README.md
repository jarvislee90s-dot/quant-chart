# quant-chart

YAML 驱动的行情图工作流：Wind Excel / API → 指标 → 信号 → Plotly（PNG + 交互HTML）。

## 快速开始

    pip install -e ".[dev]"
    chartflow run configs/basis_zones.yaml -o out.png --html out.html

## 配置三层

- `input`：数据（excel 两表 / auto API优先降级；range 为分析区间）
- `strategy` + `params`：计算插件（basis_review / basis_zones）
- `panels.layers`：视觉原语（line/area/zone/hline/events/leader_tag/day_seps/day_labels），
  覆盖插件默认面板；zone/hline 等注释原语任何策略可用

## 新增策略

`src/quantchart/plugins/` 下新建文件，`@register_strategy("名字")`，
`run(df, slots, **params) -> StrategyOutput(df, events, panels)`。只算不画。

## 测试

    pytest -q            # 单测（夹具为合成数据）
    pytest tests/test_regression.py -q   # 真实数据回归（需 QUANT_CHART_TEST_DATA）
