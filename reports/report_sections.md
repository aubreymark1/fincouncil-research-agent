# D-007 报告章节说明

最终报告由 `reports/template.md.j2` 渲染，实验数字必须来自 `results.csv` 或 `metrics.json`，不得手工填写。

## 章节

1. **运行概览**：公司、行业、cutoff、run_id、状态。
2. **指标结果**：来自 `metrics.json` / `results.csv` 的确定性指标。
3. **成功结果**：可复现的正面结果。
4. **失败案例**：失败的实验、错误信息和保留的日志。
5. **需人工确认内容**：进入 `review` / `pending` 的结论和证据。
6. **被拒绝资料**：cutoff 后、无关、无日期等被拒绝或未采用的资料。
7. **银行迁移复用**：银行 case 对核心编排、配置和评测的复用情况。
8. **行业配置实际改变**：行业配置对检索、风险规则和报告输出的具体影响。
9. **项目局限**：未覆盖场景、数据限制、人工依赖和已知风险。

## 数据来源规则

- 指标：`metrics.json`、`results.json`、`results.csv`
- 报告内容：`report.json`、`run_metadata.json`
- 图表：`evaluation/charts.py` 生成的 SVG
- 禁止：手工填写实验数字、只保留最好结果、删除失败记录
