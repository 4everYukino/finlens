# FinLens

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

每次分析完成后，使用 [md-to-pdf](https://github.com/simonhaenisch/md-to-pdf) 在对应季度目录原地导出 `report.pdf`，样式使用 `report.css`。

导出时显式指定 `--document-title`，采用「公司(代码) | 报告期」格式，例如 `松发股份(603268) | 2026 Q3`。

估值计算见 [scripts](scripts/README.md)。
