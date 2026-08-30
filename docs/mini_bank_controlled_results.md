# mini_bank 受控实验结果

> 本结果来自受控合成资料集，仅用于验证 E0–E3 实验协议和系统机制，不代表真实市场泛化效果。

## 实验条件

- 资料集：`fixtures/experiments/mini_bank/`
- 截止日期：`2026-08-20`
- Gold：5 个必查银行指标，状态为 `signed`
- 模型：`deepseek-v4-flash`
- LLM 输出协议：`minimal_synthesis`，只输出带 Evidence ID 的 narrative 正文
- request hash：`sha256:5a2e8bda24ad8863624d27965a665540993e681e8073e065b106b050489bfefb`
- manifest hash：`sha256:d9c7a147f0408f2601f134b2583c61f94e2f5c4df97d1b96f20dba135bafba89`

## 结果

| 实验组 | 状态 | 正文段落 | 正文字符 | Gold 覆盖率 | 证据有效率 | 定位准确率 | 数字错误率 | 截止日期违规 | 校验问题 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| E0 人工基线 | success | 1 | 179 | 100% | 0% | 0% | 不可判定* | 0 | 0 |
| E1 通用 Agent | success | 4 | 729 | 100% | 0% | 0% | 不可判定* | 0 | 0 |
| E2 行业 Agent | success | 4 | 605 | 100% | 0% | 0% | 不可判定* | 0 | 0 |
| E3 完整 FinCouncil | success | 4 | 650 | 100% | 100% | 50% | 0% | 0 | 9 |

## 可引用结论

在相同的受控资料、截止日期和 Gold 指标下，四组实验均成功生成报告文件。E0 覆盖了全部 5 个指标，但人工报告没有机器可验证的来源字段；E1 和 E2 已能生成自然语言正文，但其原始证据仍处于未验证状态，因此证据有效率为 0。E3 同时启用了时间锁、行业配置、证据验证和 Critic，Gold 指标覆盖率为 100%，证据有效率为 100%，数字错误率为 0%，截止日期违规为 0。

compact/narrative 输出使 LLM 能够稳定完成正文组织；E3 的 9 条校验问题被保留为待确认信息，没有被静默删除。该实验支持系统机制有效，但样本为合成小数据集，不能据此推断真实市场环境下的泛化准确率或投资收益。

\* E0–E2 没有机器可验证的有效证据引用，评分器无法判断数字是否被证据支持，因此不应把旧评分器的 `1.0` 解释成真实数字错误率。

## 结果文件

- `outputs/experiments/mini_bank/results.json`
- `outputs/experiments/mini_bank/results.csv`
- 每组目录下的 `report.json`、`run_metadata.json` 和 `metrics.json`
