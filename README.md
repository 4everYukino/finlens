## FinLens

跟踪国证成长 100 指数成分股，采用 [统一方法论](FinAnalysis.md)。

成分股、行业分类及优先研究方向见 [ConstituentStock.md](ConstituentStock.md)。

标的统一存放在 `stocks/<code>.<exchange>/`，目录名采用六位证券代码和交易所后缀，例如 `stocks/603268.SH/`。

* `SH`: 上交所
* `SZ`: 深交所
* `BJ`: 北交所

公司更名或调出指数时保留目录及历史分析。

财报原文存放在标的目录下的 `report/`，按报告期存放。

> 只能在官方平台，如「巨潮资讯网」去获得财报、投资者活动记录等资料。
>
> 若分析时需要用到副本、补查资料及公告、调研记录等辅助资料，仅临时查阅，不入库。

分析按 `stocks/<code>.<exchange>/analyses/26Q3/` 归档，包含 `report.md`、`input.json`、`fpeg.json`、`dcf.json` 和 `rdcf.json`。

估值与价格口径：

* 价值基准日取最近一期资产负债表日，三阶段 DCF 与内在价值均以此为准。
* 行情基准日取财报发布日，即首个反映该财报信息的交易日不复权收盘价。FPEG、反向 DCF 与 WACC 市值权重只使用这一次价格，构成报告内的「发布日快照」。
* 报告不跟踪实时股价。持续的价格判断由独立的「每日价格判断」机制完成，只重算 FPEG、反向 DCF 与相对条件价值的折让，不重算 DCF 与 WACC。

> 26Q3 及更早的报告使用当时的盘中价，与上述口径不同，保留原样作为历史快照。按现行口径改造旧报告时，见 [报告重构指南](RefactorGuide.md)。

每次分析完成后，使用 [md-to-pdf](https://github.com/simonhaenisch/md-to-pdf) 在对应季度目录原地导出 `report.pdf`，样式使用 `report.css`：

```bash
node_modules/.bin/md-to-pdf report.md \
  --stylesheet ../../../../report.css \
  --document-title "松发股份(603268) | 2026 Q3"
```

* 输出与输入同名，不再传 `--output`。
* `--css` 接收的是 CSS 字符串，不是文件路径。
* `--document-title` 采用「公司(代码) | 报告期」格式。

估值计算见 [scripts](scripts/README.md)。

## 依赖

* Node.js 20+
* Python 3.11+
* pip 22.3+

执行：

```bash
npm ci --cache .cache/npm
python3 -m venv --without-pip .venv
python3 -m pip --python .venv install --cache-dir .cache/pip -r requirements.txt
```

然后请使用 `.venv/bin/python` 和 `node_modules/.bin/md-to-pdf`，避免每次重新安装。
