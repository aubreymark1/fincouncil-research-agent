# mini_bank 机制消融实验结果

> 本结果来自受控合成资料集，仅用于验证时间锁和 Critic 的机制作用，不代表真实市场泛化效果。

## 实验条件

- 资料集：`fixtures/experiments/mini_bank/`
- 截止日期：`2026-08-20`
- 模型：`deepseek-v4-flash`
- LLM 输出：`minimal_synthesis` narrative-only 协议
- 三组实验使用同一 request、manifest、Gold、模型和提示词。
- request hash：`sha256:5a2e8bda24ad8863624d27965a665540993e681e8073e065b106b050489bfefb`
- manifest hash：`sha256:d9c7a147f0408f2601f134b2583c61f94e2f5c4df97d1b96f20dba135bafba89`

## 实验组

| 实验组 | 变化 |
|---|---|
| E3-F 完整系统 | 时间锁、行业配置、证据验证、LLM 和 Narrative Critic 全部开启 |
| E3-T 无时间锁 | 关闭时间锁，其他能力保持不变 |
| E3-C 无 Critic | 关闭确定性 Critic 和 Narrative Critic，其他能力保持不变 |

## 结果

| 实验组 | 状态 | 用时（秒） | 正文段落 | 正文字符 | Gold 覆盖率 | 证据有效率 | 定位准确率 | 截止日期违规 | Narrative Critic 问题 | 全部校验问题 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E3-F 完整系统 | success | 49.3 | 4 | 549 | 100% | 100% | 37.5% | 0 | 1 | 10 |
| E3-T 无时间锁 | success | 30.6 | 4 | 638 | 100% | 85.7% | 42.9% | 1 | 2 | 11 |
| E3-C 无 Critic | success | 24.2 | 4 | 573 | 100% | 100% | 42.9% | 0 | 0 | 5 |

## 可直接写入报告的结论

在相同的受控资料、模型和截止日期下，完整系统 E3-F 未产生截止日期违规，所有被引用证据均有效；关闭时间锁后，系统引用了 1 条截止日期后的资料，证据有效率下降至 85.7%，说明时间锁能够阻断未来资料进入正式证据链。关闭 Critic 后，Narrative Critic 的问题发现数从 1–2 条降为 0，说明 Critic 能够暴露正文中的风险冲突和引用问题。

三组 Gold 覆盖率均为 100%，说明本组实验主要验证的是安全边界和审查机制，不足以证明各机制对事实覆盖率的提升。该实验只有一个受控案例，不能据此推断统计显著性、真实市场泛化准确率或投资收益。

## 结果文件

- `outputs/experiments/mini_bank/ablation_results.json`
- `outputs/experiments/mini_bank/ablation_results.csv`
- 每组目录下的 `report.json`、`report.md` 和 `run_metadata.json`
