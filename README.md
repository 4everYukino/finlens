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

每次分析完成后，使用 [md-to-pdf](https://github.com/simonhaenisch/md-to-pdf) 在对应季度目录原地导出 `report.pdf`，样式使用 `report.css`。

导出时显式指定 `--document-title`，采用「公司(代码) | 报告期」格式，例如 `松发股份(603268) | 2026 Q3`。

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

## 阅读站

[线上阅读站](https://4everyukino.github.io/finlens/)由[部署工作流](.github/workflows/reading-pages.yml)在 `master` 更新后自动构建和发布，也可从 `master` 手动运行。首次发布前，在仓库的 **Settings → Pages** 中将 **Source** 设为 **GitHub Actions**。

- 新增研究时在 `stocks/<代码>/analyses/<报告期>/report.md` 开头填写 `title`、`tracks` 和 `valuations`。研究线索可多选，估值判断沿用该期报告结论并使用列表填写一个值。估值基准日从同目录的 `input.json` 读取。可参考 [麦格米特 26Q3](stocks/002851.SZ/analyses/26Q3/report.md)。
- 成分股变更时，在 `data/constituents/` 新增以样本日期命名的 YAML 快照。若生效与样本日期不同，填写 `effective_date`。首页按最新已生效快照更新。
- 开启下一研究期时，在 `content/reviews/` 新增季度页面，填入 `period`、`period_end` 和当期采用的 `snapshot`，再更新 `data/research.yaml` 的 `active_period`。已经归档的季度页面继续使用各自的样本快照。
