# 银行迁移检查简版报告（MIG-001）

- 生成时间（UTC）：2026-08-27T10:48:09+00:00
- cutoff_date：2026-08-26
- 资料包：`data/manifests/bank_case.csv`
- 核心编排改动：无（全部为对已合并公共模块的只读调用）

## 一、配置切换证明

| 维度 | food_beverage | banking |
|---|---|---|
| 必查指标 | 5 个 | 5 个 |
| 风险规则 | 4 条 | 4 条 |
| 报告章节 | summary/fundamentals/channel_inventory… | summary/fundamentals/credit_risk… |

- 食品饮料必查：revenue_growth, gross_margin, sales_expense_rate, inventory, food_safety
- 银行必查：net_interest_margin, loan_growth, non_performing_loan_ratio, provision_coverage, capital_adequacy
- 银行风险规则：credit_risk_deterioration, nim_pressure, capital_adequacy_concern, real_estate_concentration_risk

## 二、银行资料处理结果

- 时间锁后可用文档：4 个（DOC-BANK-001, DOC-BANK-002, DOC-BANK-003, DOC-BANK-004）
- 切分块数：1483
- 抽取失败：0 个文档

### 检索命中（复核前诊断）

| 指标 | 命中数 | 覆盖文档 |
|---|---|---|
| net_interest_margin | 45 | 4 |
| loan_growth | 71 | 4 |
| deposit_structure | 35 | 4 |
| non_performing_loan_ratio | 50 | 4 |
| provision_coverage | 70 | 4 |
| capital_adequacy | 96 | 4 |
| liquidity | 117 | 4 |
| real_estate_exposure | 12 | 3 |

## 三、必查指标检查（pending 证据输入）

- 问题条数：5
- 说明：B 定位器产出均为 `review_status=pending`，C 清单只认 `verified`，因此正式结果按契约如实报缺。

## 四、风险 Claims（pending 证据输入）

- `CL-RISK-CREDIT-RISK-DETERIORATION-53E6879A50` type=unresolved severity=high
- `CL-RISK-NIM-PRESSURE-20231F7B41` type=unresolved severity=medium
- `CL-RISK-CAPITAL-ADEQUACY-CONCERN-19DDF93AB3` type=unresolved severity=high
- `CL-RISK-REAL-ESTATE-CONCENTRATION-RISK-B7157342CC` type=unresolved severity=medium

## 五、复核机制落地后的预期（内存模拟，未写入共享数据）

- 模拟 verified 证据：496 条
- 清单剩余问题：0 条
- 触发的确定性风险 Claim：1 条

## 六、局限与待办

- 跨角色缺口：pending→verified 复核机制尚未实现（见 ABC 冲突汇总 P0-2），需 A/B 明确归属。
- 真实端到端接线归 A-008：当前 `run_pipeline` 默认 stub 加载器不支持 banking，A 通过注入`industry_loader=load_industry_config` 即可完成迁移，无需改行业代码。
- 四家银行 2025 年报为通用资料包，目标公司分析需在正式运行时指定 company_name 过滤。
