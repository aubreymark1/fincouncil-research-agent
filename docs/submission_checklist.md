# D-007 最终提交清单

> 维护人：D  
> 用途：最终交付前逐项核对，所有实验数字必须来自可复现文件。

## 代码与测试

- [ ] `evaluation/metrics.py` 指标计算已合并
- [ ] `evaluation/experiment_runner.py` 与 `scripts/evaluate.py` 已合并
- [ ] `evaluation/red_team.py` 红蓝测试已合并
- [ ] `evaluation/gold.py` Gold Standard 格式校验已合并
- [ ] `evaluation/charts.py` 图表生成已合并
- [ ] `app/ui/` Streamlit 页面已合并
- [ ] `reports/template.md.j2` 报告模板已合并
- [ ] `pytest tests/evaluation -q` 通过
- [ ] `python scripts/evaluate.py --case food_main --all` 可运行（或明确 disabled 原因）

## 实验与数据

- [ ] `evaluation/experiment_definitions.yaml` 已冻结
- [ ] E0—E3 输入条件一致
- [ ] 每组结果有 input hash
- [ ] 失败实验保留 `error.txt` 和原始目录
- [ ] 合成 fixture 未冒充真实实验结果
- [ ] 真实食品饮料/银行 Gold Standard 已由 B/C 签收（或明确标注待签收）

## 页面与交付

- [ ] Streamlit 能读取 `report.json` / `run_metadata.json` / `metrics.json`
- [ ] 页面不调用模型、不修改报告内容
- [ ] 图表只读取 `results.csv` / `results.json`
- [ ] 报告模板中的数字来自 `results.csv` / `metrics.json`
- [ ] 银行迁移结果有独立章节
- [ ] 局限与未覆盖场景已写明

## 最终门禁

- [ ] 全量测试通过
- [ ] 任务看板状态已同步
- [ ] PR 已创建且指向 `main`
- [ ] 没有未合并且影响交付的 D 任务
