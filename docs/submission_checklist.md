# D-007 最终提交清单

> 维护人：D  
> 用途：最终交付前逐项核对，所有实验数字必须来自可复现文件。

## 代码与测试

- [ ] `evaluation/metrics.py` 指标计算已合并
- [ ] `evaluation/experiment_runner.py` 与 `scripts/evaluate.py` 已合并
- [ ] `evaluation/red_team.py` 红蓝测试已合并
- [x] `evaluation/gold.py` Gold Standard 格式校验已合并
- [x] `evaluation/charts.py` 图表生成已合并
- [x] `app/ui/` Streamlit 页面已合并并支持 report.md、失败/disabled 状态和只读导出
- [ ] `reports/template.md.j2` 报告模板已合并
- [x] `pytest tests/evaluation -q` 通过
- [ ] `python scripts/evaluate.py --case food_main --all` 可运行（或明确 disabled 原因）

## 实验与数据

- [ ] `evaluation/experiment_definitions.yaml` 已冻结
- [ ] E0—E3 输入条件一致
- [ ] 每组结果有 input hash
- [ ] 失败实验保留 `error.txt` 和原始目录
- [x] 合成 fixture 未冒充真实实验结果
- [x] 真实食品饮料/银行 Gold Standard 已由 A 基于 B/C/D 核验材料签收并接入评分定义

## 页面与交付

- [x] Streamlit 能读取 `report.json` / `report.md` / `run_metadata.json` / `metrics.json`
- [x] 页面不调用模型、不修改报告内容
- [x] 图表只读取 `results.csv` / `results.json`，缺失/失败/disabled 不转为 0
- [x] 报告模板中的数字来自 `results.csv` / `metrics.json`
- [ ] 银行迁移结果有独立章节
- [ ] 局限与未覆盖场景已写明

## 最终门禁

- [ ] 全量测试通过
- [ ] 任务看板状态已同步
- [ ] PR 已创建且指向 `main`
- [ ] 没有未合并且影响交付的 D 任务

## FINAL-001 验收记录（2026-08-27）

- 分支：`final-001-report-ui-results`，基于 `origin/main`。
- `python scripts/run_case.py --request fixtures/shared/research_request.json` 已在独立 worktree 重现 RUN-DEMO 三件套；报告 1,580 条 Evidence，运行状态为 `success`。
- RUN-DEMO 当前没有 `metrics.json` 或 `results.*`；本次未加载 Gold、未生成或发布正式实验分数。
- `python -m streamlit run app/ui/app.py` 已启动并由浏览器加载验证；页面可展示报告元信息、摘要、结论、风险、待确认项、Evidence、ValidationIssue 和 report JSON/Markdown 下载。
- 页面与图表的自动化验证使用 `fixtures/evaluation/report_sample.json`、`fixtures/evaluation/metrics_gold_sample.json` 和临时合成 results 文件；这些 fixture 仅用于测试。
