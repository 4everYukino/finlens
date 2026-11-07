# 估值计算脚本

使用 Python 3 标准库。

## 调用

在季度目录（例如 `stocks/603268.SH/analyses/26Q3/`）运行：

```bash
python3 -B ../../../../scripts/fpeg.py input.json --output fpeg.json
python3 -B ../../../../scripts/dcf.py input.json --output dcf.json
python3 -B ../../../../scripts/rdcf.py input.json --output rdcf.json
```

输入错误时非零退出，不覆盖输出；成功或明确不适用时返回 `0`。输入、输出不能指向同一文件。

## 共用输入

| 字段 | 约定 |
| --- | --- |
| `currency` | 固定为 `CNY` |
| `units` | 固定为 `{"money":"亿元","shares":"亿股","price":"元/股","eps":"元/股"}` |
| `valuation_date` | 估值基准日，格式为 `YYYY-MM-DD` |
| `market_price` | 基准日股价，元/股，FPEG 与反向 DCF 使用 |
| `balance_date` | 价值桥接起始日，不能晚于估值基准日，DCF 使用 |

比例使用小数。不适用原因填入相应模型或情景的 `not_applicable_reason`。

## FPEG

`fpeg` 包含 `base_year`、`end_year`、`base_eps`、`end_eps`。末年晚于基年，基年不早于估值年份；EPS 为归母口径。

$$
g_{\mathrm{EPS}} = \left(\frac{\mathrm{EPS}_{\mathrm{end}}}{\mathrm{EPS}_{\mathrm{base}}}\right)^{1/k}-1,
\qquad k = \mathrm{end\_year}-\mathrm{base\_year}
$$

$$
\mathrm{ForwardPE} = \frac{P_{\mathrm{mkt}}}{\mathrm{EPS}_{\mathrm{base}}},
\qquad \mathrm{FPEG} = \frac{\mathrm{ForwardPE}}{100\,g_{\mathrm{EPS}}}
$$

输出 `forward_pe`、`eps_cagr`、`fpeg`。EPS 或增速非正、预测缺失时返回 `not_applicable`。

## 三阶段 DCF

### 价值桥接

`bridge` 按 `balance_date` 填列：

| 字段 | 含义 |
| --- | --- |
| `cash_equivalents` | 经核实可用于估值的现金；受限资金另行判断 |
| `operating_cash` | 必要经营现金储备；超过现有现金时，差额体现为待补足的资金需求 |
| `nonoperating_financial_assets` | 未计入经营现金流的非经营资产价值 |
| `debt_components` | 融资性债务的名称与价值，不与营运资金重复 |
| `other_claims` | 与合并现金流对应的少数股东权益及其他索取权价值 |
| `shares` | 与权益价值口径一致的估值股数 |

`bridge_adjustments` 每项填 `amount` 和 `reason`；正值增加权益价值。

### 情景与逐期假设

`scenarios` 包含 `bear`、`base`、`bull`，各情景设置 `wacc`、`terminal_growth`、`terminal_roic`、`terminal_margin` 和 `terminal_tax_rate`。

- `base_annual_revenue`：估值所在年度的完整收入估计。
- `incremental_nwc_ratio`：收入增量对应的营运资金需求比例，可为负；逐年给定 `delta_nwc` 时可省略。
- `forecast`：从估值次年开始的连续年度预测，至少一年。

每个预测年度包含：

- `year`：年度；`stage`：`growth` 或 `transition`，按此顺序排列，期限自行确定。
- `revenue`、`ebit_margin`、`tax_rate`：收入、EBIT 利润率及经营税率。
- `da`、`capex`：折旧摊销与估值口径资本开支，均为非负金额。
- `delta_nwc`：可直接输入经营营运资金增加额；省略时按收入增量乘 `incremental_nwc_ratio` 计算。

资本开支包含增长所需的收购净支出；租赁与资本化研发须保持口径一致。

### 年中估值与日期衔接

12 月 31 日估值可省略 `stub`。其他日期需提供截至当年 12 月 31 日的尾段，包含与年度预测相同的经营字段及 `delta_nwc`，另加：

| 字段 | 可选值与规则 |
| --- | --- |
| `end` | 估值当年 12 月 31 日 |
| `allocation` | `remaining`：输入金额均为基准日之后的剩余金额；`uniform_days`：输入财报日至年末的整段金额，再按实际天数分摊 |
| `bridge_roll` | `explicit`：使用已列明的 `bridge_adjustments`；`uniform_fcff`：用已过去部分的 FCFF 减税后利息估计净金融头寸变化 |
| `after_tax_interest` | `uniform_fcff` 使用，整段税后利息金额 |

- `uniform_fcff` 只与 `uniform_days` 配合，且不能再叠加显式桥接调整。
- 使用 `explicit` 且财报日不同于基准日时，必须提供调整数组；空数组表示已确认无调整。
- 已过去期间只影响价值桥接，不再进入未来经营价值；基准日恰为尾段末日时，不重复计入尾段现金流。

### 计算规则

$$
\mathrm{NOPAT}_t = \mathrm{Revenue}_t\,m_t(1-\tau_t),\qquad
\mathrm{FCFF}_t = \mathrm{NOPAT}_t+\mathrm{DA}_t-\mathrm{CapEx}_t-\Delta\mathrm{NWC}_t
$$

$$
\mathrm{FCFF}_{n+1}=\mathrm{NOPAT}_{n+1}\left(1-\frac{g}{\mathrm{ROIC}_{\infty}}\right),\qquad
\mathrm{TV}_n=\frac{\mathrm{FCFF}_{n+1}}{w-g}
$$

$$
\mathrm{EV}_0=\sum_{t=1}^{n}\frac{\mathrm{FCFF}_t}{(1+w)^{u_t}}
+\frac{\mathrm{TV}_n}{(1+w)^{u_n}},\qquad
P_0=\frac{\mathrm{EV}_0+\mathrm{NetFinancial}_0}{N_0}
$$

- `m` 为 EBIT 利润率，`τ` 为经营税率；要求 `0 <= g < WACC` 且成熟期新增投入回报率 `ROIC > g`。
- 固定 WACC、期末折现，`ut` 为实际天数除以 `365`。
- 终值使用最后预测年度收入乘 `(1 + g)`，再按成熟期利润率、税率和再投资规则计算。
- 净金融头寸为符合条件的现金减经营储备，加非经营资产，减债务及其他索取权，再加桥接调整。
- 当前模型不支持永续收缩、非正稳定期回报或分阶段折现率。

### 敏感性与输出

`sensitivity` 支持：

- `wacc`、`growth`：计算交叉组合。
- `capex_multipliers`：测算未来显式期资本开支成本变化，例如 `[0.9, 1, 1.1]`；产能或长期效率变化另建情景。

输出包含三情景现金流、终值、价值桥接、每股价格及敏感性。其中：

- `terminal_share`：终值占经营价值的比例，经营价值为零时为 `null`。
- `full_stub_fcff`：分摊前的尾段 FCFF，无尾段时为 `null`。

## 反向 DCF

### 输入

`rdcf.py` 复用正向 DCF，配置放在 `reverse_dcf`：

- 必填：`variable`、`lower`、`upper`。
- 可选：`scenario`（默认 `base`）、`price_tolerance`（默认 `0.01` 元/股）。

| `variable` | 额外字段与联动规则 |
| --- | --- |
| `terminal_margin` | 仅改变永续期 EBIT 利润率；显式预测保持不变，永续再投资随 NOPAT 联动 |
| `operating_margin` | 指定 `stage`，将该阶段各年 EBIT 利润率设为待求值；其余阶段保持不变 |
| `revenue_growth` | 指定 `stage`，按待求年增速重建该阶段收入；后续阶段保留原逐年收入增长比例 |
| `growth_years` | 枚举高速增长期年数；缩短时截取原增长期，延长时须提供 `extension_growth`；过渡期保留原逐年相对增长与利润率路径，并整体移动日期 |

反推收入增速或年数时，配置 `reinvestment.capex` 和 `reinvestment.da`：

- `fixed`：保留原支出金额，须有现有产能等依据。
- `revenue_ratio`：保留原年度项目金额与收入的比例；延长期沿用最后增长年度模板。
- 营运资金始终按收入增量与 `incremental_nwc_ratio` 重算，替代原显式 `delta_nwc`。
- 反推年数时，`lower`、`upper` 为 `0` 至 `100` 的整数，至少保留一个显式预测年。
- 反推收入增速时，边界必须大于 `-1`；比例联动所用模板收入须为正。

### 求解与输出

$$
P_{\mathrm{DCF}}(x)=P_{\mathrm{mkt}},\qquad
\mathrm{EV}_{\mathrm{mkt}}=P_{\mathrm{mkt}}N_0-\mathrm{NetFinancial}_0
$$

- 连续变量先在边界内采样，再对异号区间二分；`search_steps` 默认 `32`，`max_iterations` 默认 `100`。
- 求解后代回完整 DCF，价差须在 `price_tolerance` 内。采样搜索不能保证发现所有非单调解。
- 离散年数逐一计算；未精确匹配时列出候选价格及相邻区间，不虚构小数年数。

| `status` | 含义 |
| --- | --- |
| `ok` | 隐含值 `implied_value`、回代价差 `price_error` 与完整 `valuation` |
| `not_applicable` | 缺少配置或基准情景不适用，附原因 |
| `outside_search_range` | 给定范围及采样下未找到支持现价的解 |
| `not_converged` | 已找到候选区间但未在迭代限制内收敛 |
| `multiple_solutions` | 找到多个可支持现价的候选，不能解释为唯一要求 |
| `bracketed` | 离散年限的相邻候选夹住现价，列出年数与价差 |

