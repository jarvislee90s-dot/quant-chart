# 任务：执行 quant-chart 二期实施计划（批次1+2）

## 你是谁、做什么
你是执行工程师，逐任务实施一份已定稿的 TDD 实施计划。文档：
- 实施计划（唯一依据，逐任务含全部代码与测试）：E:\LLMproject\Github\quant-chart\docs\superpowers\plans\2026-08-28-phase2.md
- 设计 spec（背景，先通读）：E:\LLMproject\Github\quant-chart\docs\superpowers\specs\2026-08-28-phase2-design.md
- 仓库：E:\LLMproject\Github\quant-chart，**起点 HEAD = `2d24205`**（干净工作树）

## 环境事实（已验证，不要重复探测）
- Windows + Git Bash；bash 内路径 /e/LLMproject/Github/quant-chart
- `python` = Python 3.14（D:\Program Files\Python314），pandas/plotly/kaleido/click/PyYAML/pytest 已装；Chrome 已装（kaleido 出图可用）
- quant-chart 已 `pip install -e`（命令 `chartflow` 可用）
- 真实数据（Task 10 e2e 用）：E:\LLMproject\PersonalAffairs\Backset\{IM2612.CFE原始.xlsx, 000852.SH.xlsx}
- local-datasource **本机已可 import**（E:\LLMproject\Github\local-datasource，基线 98cd3bd）——Task 10 的 `integration_localds` 测试会连网真实跑（深度约 8 个交易日，测试区间取近 3 天）；网络失败属环境问题：记录 DEVIATIONS 不阻塞
- 全部 10 个任务**不需要**安装/升级任何包；Task 8/9 的 local-datasource 交互全部用计划里的 fake 包注入 stub

## 执行规则
1. Task 1→10 顺序执行，每任务严格五步：写失败测试→跑确认失败→最小实现→跑通过→git commit（信息照计划）
2. 计划步骤带 `- [ ]` 复选框，完成一项改 `- [x]` 随任务提交
3. **计划内嵌代码未经运行验证前不得视为正确**：TDD 红灯不得止步于 ModuleNotFoundError——计划代码里的每个防御分支（KeyError/ValueError/except/轴重映射）都必须有测试驱动到它；计划代码与计划测试矛盾时，保留实现修测试（或反之），一律记 DEVIATIONS
4. 计划与设计文档矛盾时（如设计承诺的断言缺失），补齐设计意图，**不得保留死代码/死常量/永久 skip**
5. 注意计划内标注的次序依赖：Task 4 有一个 `@pytest.mark.skip(reason="待 Task 6 多面板")` 测试，Task 6 完成后必须解除并让它通过；`api_sina.py` 本期保留不动（批次3 才删）
6. **回归红线**：既有 34 个测试必须全绿；单面板输出视觉等价（Task 6 的 `test_single_panel_unchanged` 就是这条红线）
7. 代码、提交信息、文档注释全部中文（与计划一致）；不做计划之外的"顺手重构"
8. 偏差记录：仓库根 DEVIATIONS.md 追加新节「二期执行记录（2026-08-28）」，格式沿用既有「任务号/计划原文/实际做法/原因」

## 完成后验收包（按此格式输出，主 Agent 要 review）
1. `git log --oneline` 全量输出
2. 最终 HEAD 上重跑的 `pytest -q` 末尾摘要（应含 integration_localds 的通过或跳过状态）
3. 验收产物：`chartflow run configs/basis_zones_position.yaml -o outputs/basis_zones_position.png --html outputs/basis_zones_position.html` 的产物路径、字节数、**文件 mtime 与生成时刻的 HEAD SHA**（产物必须由最终 commit 的代码生成——最后一次 commit 之后重跑本命令，验收包以该次为准）
4. 附带跑一次 `chartflow run configs/basis_zones.yaml -o outputs/basis_zones_regress.png`，同样给 mtime+SHA（单面板回归对照图）
5. DEVIATIONS.md 新节全文（若无偏差写"无偏差"）
6. 计划复选框完成统计（x/总数）
7. 一句话备注：验收图目测结果（上面板 3 个买卖点标记买▲买▲平×、下面板仓位阶梯 0→1→2→0 是否都在位）与任何遗留问题
