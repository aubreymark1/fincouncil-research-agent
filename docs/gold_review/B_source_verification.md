# B 来源核验表（GOLD-B-001）

> 角色：B　|　任务：GOLD-B-001（来源核验）　|　核验日期：2026-08-28
> 覆盖：食品饮料 5 项 + 银行 5 项必查指标（`required: true`）
> 说明：`quote` 逐字抄录自对应 PDF 提取文本，未做任何改写；`content_hash` 为 PDF 文件字节的 sha256（与 `load_manifest` 计算方式一致）。

## 一、核验范围与方法

- **资料清单**：`data/manifests/food_case.csv`（11 份 formal）、`data/manifests/bank_case.csv`（4 份 formal）。
- **指标来源**：`configs/food_beverage.yaml`、`configs/banking.yaml` 中 `required: true` 的指标。
- **方法**：用 pypdf 逐页提取 PDF 文本，按指标关键词定位命中页，截取包含关键词与数值的原文片段作为 quote。
- **页码口径**：PDF 查看器物理页码（从 1 开始），与下游 `extract_pdf`/`TextChunk.page` 一致。

## 二、逐项核验表

### 食品饮料（food_beverage）

| case_id | industry_metric_id | source_doc_id | source_page | publisher | quote | raw_value_or_text | content_hash | evidence_type | review_result | note |
|---|---|---|---|---|---|---|---|---|---|---|
| food_case | revenue_growth | DOC-FOOD-001 | 6 | 贵州茅台酒股份有限公司 | 营业收入 168,838,102,514.79 170,899,152,276.34 -1.21 147,693,604,994.14 | 营业收入 2025 年 168,838,102,514.79 元，同比 -1.21% | sha256:474905deeaf0f875fc0a1b097a626c0c7852c427faadc5d7fc7816cbf45ea288 | financial | 通过 | 「主要会计数据」表；同比为负（-1.21%），2024 年为 170,899,152,276.34 元 |
| food_case | gross_margin | DOC-FOOD-001 | 10 | 贵州茅台酒股份有限公司 | 酒类 168,774,585,187.65 14,805,900,139.59 91.23 | 酒类毛利率 91.23%（2025 年） | sha256:474905deeaf0f875fc0a1b097a626c0c7852c427faadc5d7fc7816cbf45ea288 | financial | 通过 | 「主营业务分行业情况」表，酒类行；毛利率比上年减少 0.78 个百分点 |
| food_case | sales_expense_rate | DOC-FOOD-001 | 9 | 贵州茅台酒股份有限公司 | 销售费用 7,253,499,600.68 5,639,300,059.49 28.62；营业收入 168,838,102,514.79 170,899,152,276.34 -1.21 | 销售费用率 = 4.30%（计算型，见专项说明） | sha256:474905deeaf0f875fc0a1b097a626c0c7852c427faadc5d7fc7816cbf45ea288 | financial | 通过 | 分子分母同页（P9「主要会计数据」表），公式可复现，见 3.1 |
| food_case | inventory | DOC-FOOD-001 | 14 | 贵州茅台酒股份有限公司 | 存货 61,427,421,796.18 20.22 54,343,285,157.47 18.18 13.04 | 存货 61,427,421,796.18 元（2025 年末，占总资产 20.22%） | sha256:474905deeaf0f875fc0a1b097a626c0c7852c427faadc5d7fc7816cbf45ea288 | financial | 通过 | 资产负债表「存货」科目；同比 +13.04% |
| food_case | food_safety | 未找到 | — | — | 未找到 | 未找到符合 evidence_types 的来源 | — | — | 未找到（阻塞） | 详见 3.2：formal 资料无 news/policy/company_release 类型，multiple 要求无法满足 |

### 银行（banking）

| case_id | industry_metric_id | source_doc_id | source_page | publisher | quote | raw_value_or_text | content_hash | evidence_type | review_result | note |
|---|---|---|---|---|---|---|---|---|---|---|
| bank_case | net_interest_margin | DOC-BANK-001 | 16 | 中国工商银行股份有限公司 | 净利息差 （3） 1.15 1.23 1.41 净利息收益率 （4） 1.28 1.42 1.61 | 净利息差 1.15%、净利息收益率 1.28%（2025 年） | sha256:e2edab73032f143aad881f612382bc613c8b96b424bb197b125d64a0ef23c78b | financial | 通过 | 「主要财务指标」表；工行用「净利息差/净利息收益率」，未用「净息差」一词 |
| bank_case | loan_growth | DOC-BANK-001 | 21 | 中国工商银行股份有限公司 | 集团客户贷款及垫款总额达到 30.5 万亿元，增长 7.5% | 客户贷款及垫款总额 30.5 万亿元，增长 7.5%（2025 年末） | sha256:e2edab73032f143aad881f612382bc613c8b96b424bb197b125d64a0ef23c78b | financial | 通过 | 精确值另见 P14「客户贷款及垫款总额 30,506,114 28,372,229 26,086,482」（百万元） |
| bank_case | non_performing_loan_ratio | DOC-BANK-001 | 16 | 中国工商银行股份有限公司 | 不良贷款率 （7） 1.31 1.34 1.36 | 不良贷款率 1.31%（2025 年） | sha256:e2edab73032f143aad881f612382bc613c8b96b424bb197b125d64a0ef23c78b | financial | 通过 | 2024 年 1.34%、2023 年 1.36% |
| bank_case | provision_coverage | DOC-BANK-001 | 16 | 中国工商银行股份有限公司 | 拨备覆盖率 （8） 213.60 214.91 213.97 | 拨备覆盖率 213.60%（2025 年） | sha256:e2edab73032f143aad881f612382bc613c8b96b424bb197b125d64a0ef23c78b | financial | 通过 | 2024 年 214.91%、2023 年 213.97% |
| bank_case | capital_adequacy | DOC-BANK-001 | 16 | 中国工商银行股份有限公司 | 资本充足率 （10） 18.76 19.39 19.10 | 资本充足率 18.76%（2025 年） | sha256:e2edab73032f143aad881f612382bc613c8b96b424bb197b125d64a0ef23c78b | financial | 通过 | 核心一级 13.57%、一级 14.94%、资本充足率 18.76%（2025 年） |

## 三、高风险指标专项

### 3.1 sales_expense_rate（计算型指标）

- **公式**：销售费用率 = 销售费用 ÷ 营业收入 × 100%
- **分子（销售费用）**：7,253,499,600.68 元（P9「主要会计数据」表「销售费用」行）
- **分母（营业收入）**：168,838,102,514.79 元（P9 同表「营业收入」行）
- **单位一致性**：分子、分母均为人民币元，单位一致。
- **四舍五入规则**：保留两位小数。
- **计算结果**：7,253,499,600.68 ÷ 168,838,102,514.79 × 100% = **4.30%**
- **结论**：分子、分母同页可追溯，公式可复现，`review_result = 通过`。注意：年报原文未直接给出「销售费用率」数值，该值是 B 按公式计算，需 D 在 Gold 中保留分子/分母原始值供复现。

### 3.2 food_safety（multiple 指标，逐来源记录）

food_safety 的 `evidence_types = [news, policy, company_release]`、`evidence_requirement = multiple`（至少两个不同 publisher 且 content_hash 不同的来源）。

**核验结果：未找到符合要求的 formal 来源。**

逐来源排查（财报中出现的「食品安全」原文，均为 annual_report / interim_report 财务资料，非 news/policy/company_release）：

| 来源 | 页码 | 原文（逐字） | 类型判定 |
|---|---|---|---|
| 内蒙古伊利实业集团股份有限公司 2025 年年度报告 | 36 | 食品安全是食品企业最为关注的风险，对此，公司本着追求产品品质永无止境的信念，以国际标准和切实行动，持续改善、优化、升级企业的全球品质管理体系，确保产品质量与安全。 | annual_report → financial，不匹配 |
| 佛山市海天调味食品股份有限公司 2025 年年度报告 | 16 | 坚持做好食品安全、稳定供应、可持续发展等重点领域的严格管控 | annual_report → financial，不匹配 |
| 宜宾五粮液股份有限公司 2025 年年度报告 | 27 | 食品安全总监 | 职务名，非指标数据 |
| 泸州老窖股份有限公司 2025 年年度报告 | 35 | 食品安全总监 | 职务名，非指标数据 |
| 山西杏花村汾酒厂股份有限公司 2025 年年度报告 | 8 | 食品安全员 | 职务名，非指标数据 |
| 贵州茅台酒股份有限公司 2025 年年度报告 | — | 无「食品安全」字样 | 未出现 |

**阻塞点说明**：
1. 资料包中 formal 资料全部为 `annual_report` / `interim_report`（对应 evidence_type 为 financial），**不存在 news / policy / company_release 类型的 formal 来源**。
2. 红蓝材料（`DOC-FOOD-101~105`）含 announcement / news 类型，但 `review_status` 为 red_team / pending_date / rejected，**不得作为 formal 证据**。
3. 因此 food_safety 的 `multiple` 要求（两个不同 publisher + content_hash 的来源）在当前资料包内**无法满足**。

> 这是 B 无法自行解决的资料缺口，需交由 C（口径确认）和 A（签收判断）决定处理方式（补充 news/policy/company_release 真实资料，或调整 food_safety 的证据要求）。

## 四、来源独立性核对

- 本任务中 `multiple` 指标仅 `food_safety` 一项。
- 由于 food_safety 无符合 evidence_types 的 formal 来源，**独立性核对结论为「无法满足」**（详见 3.2）。
- 其余 9 个指标均为 `single`，不涉及独立性要求。

## 五、结论

| 维度 | 结果 |
|---|---|
| 必查指标总数 | 10（食品 5 + 银行 5） |
| 已找到逐字 quote 并可追溯 | 9（食品 4 + 银行 5） |
| 未找到（阻塞） | 1（food_safety） |
| 计算型指标（sales_expense_rate） | 分子/分母/公式/结果已记录，可复现 |
| 编造 quote | 0（所有 quote 均逐字来自 PDF 提取文本） |

**交接给 C 的要点**：food_safety 的 evidence_types（news/policy/company_release）与 multiple 要求，在当前资料包内无法满足，属于资料口径缺口，需 C 在 GOLD-C-001 中确认处理方案。
