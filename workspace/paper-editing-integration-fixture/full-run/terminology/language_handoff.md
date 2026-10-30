# 语言审校术语交接

- 原稿 `paper-language-v0.1-fixture/manuscript.md`，SHA-256 `fa05039c73ebacae4d9f1d76d901521e00d78603ddf703ce91974bf2d45a4501`；全文；未应用结构建议。
- 增量表 `paper-editing-integration-fixture/full-run/terminology/terminology_glossary.yaml`，SHA-256 `e4e90df841c312e0ede2c1adf79f27c2f248af41b450bfcbb0582b1df2f9dcb0`。
- 旧表模拟 approved 约束：multi-agent system / MAS、Horizon Mapper、mean absolute error / MAE、x_t；按原有允许变体保留。此状态为测试数据，没有真人审批，不授权改稿。
- 未经作者确认不得将 forecast horizon 与 forecast_horizon、input 与 observations 或 x_t 互换；不要重命名 controller、monitor、Horizon Mapper 或改写公式。
- MAS 在摘要第7行定义，MAE 在方法第17行定义；摘要和正文是否分别引入取决于未知期刊规则，不删除或补加定义而假设政策。
- 保留 $\hat{y}_{t+1} = f(x_t)$、x_t 的原定义、四时间步与代码值。单步公式与四步范围、f 的含义及输入与观测的关系待作者核实；符号或公式更改需专项审批。
- 其他新增候选均为 proposed、unverified，未获批准；请勿视为已确立定义。保留合成声明、引用、数字、限定语与科学含义。本交接不授权修改或启动语言代理。
