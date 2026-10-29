## 序

本仓库用于持续追踪财报，并通过 `Claude Code` 或者 `Codex` 来完成财报分析。

> 根目录下的 `FinAnalysis.md` 决定了财报分析的方法论。

## 项目规范

文件夹命名规范为 `$股票代码-$股票名`。

在 `report` 内存放财报，按年份 + 报告期来命名。

在 `analyses` 内存放财报分析，也是按年份 + 报告期来命名。

这里，由 agent 产出的财报分析为 Markdown 格式，再经由 `md-to-pdf` 渲染为 PDF 格式，便于阅读。

可在仓库根目录运行:

```bash
npx md-to-pdf --basedir . --stylesheet report.css "300308-中际旭创/analyses/26Q3.md"
```

格式控制由 `report.css` 完成。

为避免体积浪费，PDF 格式的财报分析不上传到 git，仅做本地浏览使用。
