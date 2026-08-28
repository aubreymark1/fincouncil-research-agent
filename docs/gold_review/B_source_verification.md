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
| food_case | food_safety | DOC-FOOD-012 | 1 | 国家市场监督管理总局 | 为规范食品安全抽样检验工作，加强食品安全监督管理，保障公众身体健康和生命安全，根据《中华人民共和国食品安全法》等法律法规，制定本办法。 | 《食品安全抽样检验管理办法》第一条（policy） | sha256:218a1d43c097350775fd20e03824984b8aa46395223396b3947ef9a773ce8957 | policy | 通过 | multiple 来源 1/2 |
| food_case | food_safety | DOC-FOOD-013 | 3 | 国家卫生健康委员会 | 国家卫生健康委员会公告 2025年 第2号 根据《中华人民共和国食品安全法》规定，经食品安全国家标准审评委员会审查通过，现发布《食品安全国家标准 预包装食品标签通则》（GB 7718-2025）等50项食品安全国家标准和9项修改单。 | 50 项食品安全国家标准发布公告（policy） | sha256:7b997236bd5ccbacbd0c7192ce16983265e035d43b0303f94eaeba9445b26db5 | policy | 通过 | multiple 来源 2/2 |

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

**核验结果：已补充 2 个 policy 来源，multiple 要求满足。**

两个来源均为真实监管政策文件，逐字原文如下：

| 来源 | 页码 | 原文（逐字） | 类型判定 |
|---|---|---|---|
| 国家市场监督管理总局《食品安全抽样检验管理办法》（2025 年修正，总局令第 101 号） | 1 | 为规范食品安全抽样检验工作，加强食品安全监督管理，保障公众身体健康和生命安全，根据《中华人民共和国食品安全法》等法律法规，制定本办法。 | policy，匹配 |
| 国家卫生健康委员会公告 2025 年第 2 号（发布 50 项食品安全国家标准） | 3 | 国家卫生健康委员会公告 2025年 第2号 根据《中华人民共和国食品安全法》规定，经食品安全国家标准审评委员会审查通过，现发布《食品安全国家标准 预包装食品标签通则》（GB 7718-2025）等50项食品安全国家标准和9项修改单。 | policy，匹配 |

**独立性核对**：两个来源 publisher 不同（国家市场监督管理总局 vs 国家卫生健康委员会）、content_hash 不同（`sha256:218a1d43...` vs `sha256:7b997236...`），**满足 multiple 的独立来源要求**。

> 说明：此前资料包仅含财报（financial 类型），food_safety 无法满足 news/policy/company_release 要求。本次按路线 A 补充 2 份真实监管政策文件（`DOC-FOOD-012`、`DOC-FOOD-013`）归档至 `data/raw/food_beverage/`，并在 `food_case.csv` 新增对应 formal 记录。原文逐字来自下载的 PDF，未改写。

## 四、来源独立性核对

- 本任务中 `multiple` 指标仅 `food_safety` 一项。
- food_safety 的两个来源 publisher 不同（市场监管总局 vs 卫健委）、content_hash 不同，**独立性满足**（详见 3.2）。
- 其余 9 个指标均为 `single`，不涉及独立性要求。

## 五、结论

| 维度 | 结果 |
|---|---|
| 必查指标总数 | 10（食品 5 + 银行 5） |
| 已找到逐字 quote 并可追溯 | 10（食品 5 + 银行 5，全部通过） |
| 未找到（阻塞） | 0 |
| 计算型指标（sales_expense_rate） | 分子/分母/公式/结果已记录，可复现 |
| multiple 指标（food_safety） | 2 个独立 policy 来源，publisher 与 content_hash 均不同 |
| 编造 quote | 0（所有 quote 均逐字来自 PDF 提取文本） |

**交接给 C 的要点**：food_safety 已补充 2 个真实 policy 来源（市场监管总局令第 101 号办法 + 卫健委 2025 年第 2 号公告），满足 multiple 的 news/policy/company_release 类型与独立来源要求。C 在 GOLD-C-001 中确认 policy 类证据的 Gold 表达方式即可。
