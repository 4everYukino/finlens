# FinLens

跟踪国证成长 100 指数成分股，采用[统一方法论](FinAnalysis.md)。

财报原文存放在标的的 `report/`。

分析按 `analyses/26Q3/` 归档，包含 `report.md`、`input.json`、`fpeg.json`、`dcf.json` 和 `rdcf.json`。

每次分析完成后，使用 [md-to-pdf](https://github.com/simonhaenisch/md-to-pdf) 在对应季度目录原地导出 `report.pdf`，样式使用 `report.css`。

导出时显式指定 `--document-title`，采用「公司（代码）｜报告期分析」格式，例如 `松发股份（603268）｜2026 年三季报分析`。

估值计算见 [scripts](scripts/README.md)。
