# FinLens

跟踪国证成长 100 指数成分股，采用[统一方法论](FinAnalysis.md)。

成分股、行业分类及优先研究方向见 [ConstituentStock.md](ConstituentStock.md)。

财报原文存放在标的的 `report/`，按报告期存放。

> 若分析时需要用到副本、补查资料及公告、调研记录等辅助资料，仅临时查阅，不入库。

分析按 `analyses/26Q3/` 归档，包含 `report.md`、`input.json`、`fpeg.json`、`dcf.json` 和 `rdcf.json`。

每次分析完成后，使用 [md-to-pdf](https://github.com/simonhaenisch/md-to-pdf) 在对应季度目录原地导出 `report.pdf`，样式使用 `report.css`。

导出时显式指定 `--document-title`，采用「公司(代码) | 报告期」格式，例如 `松发股份(603268) | 2026 Q3`。

估值计算见 [scripts](scripts/README.md)。
