# Gold Standard Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于项目真实食品饮料和银行资料，制作可追溯、可复核、可评分的 Gold Standard，并把交付结果留在仓库中。

**Architecture:** B 只负责从原始资料确认事实、页码和原文；C 只负责确认指标口径、单位、公式和证据要求；D 把 B/C 已确认内容整理成 Gold JSON 并补充评测测试。Gold 在 A 最终签收前保持不可用于正式评分的状态。

**Tech Stack:** Markdown、JSON、Python、pytest、pypdf、现有 `evaluation.gold` 和 `evaluation.metrics`。

**Spec:** `docs/task_board.md` 中的 GOLD-B-001、GOLD-C-001、GOLD-D-001。

**Deadline:** 2026-08-28 12:00（Asia/Shanghai）；B 在 09:00 前、C 在 10:00 前、D 在 11:30 前分别提交交付物，A 在 12:00 前完成最终签收判断。

## Global Constraints

- 不修改 `data/raw/` 下的原始 PDF。
- 不修改 `data/manifests/` 来掩盖资料问题。
- 原文引用必须逐字来自对应资料；不能用模型改写代替 quote。
- 每个指标必须记录 `source_doc_id`、页码和原文；计算型指标必须记录分子、分母和公式。
- `multiple` 指标必须有至少两个不同 publisher 且 content_hash 不同的来源。
- B/C 不修改 Gold JSON；D 不修改 `app/schemas/`、`app/orchestrator/` 或 `app/agents/`。
- A 未最终签收前，Gold 不得标记为正式 `signed`，也不得接入正式 E0—E3 评分。
- 所有交付必须通过仓库现有校验和相关测试。

---

### Task 1: B source verification

**Owner:** B  
**Task ID:** GOLD-B-001

**Files:**
- Read: `data/manifests/food_case.csv`
- Read: `data/manifests/bank_case.csv`
- Read: `data/raw/food_beverage/`
- Read: `data/raw/banking/`
- Read: `configs/food_beverage.yaml`
- Read: `configs/banking.yaml`
- Create: `docs/gold_review/B_source_verification.md`

**Consumes:** 两个 manifest、正式 PDF、两个行业配置中的 `required: true` 指标。

**Produces:** 一份逐项证据核验表，覆盖食品饮料 5 项和银行 5 项必查指标。

- [ ] **Step 1: 读取指标清单和资料清单**

记录以下 10 个指标，不处理 `required: false` 的可选指标：

```text
food_beverage: revenue_growth, gross_margin, sales_expense_rate, inventory, food_safety
banking: net_interest_margin, loan_growth, non_performing_loan_ratio, provision_coverage, capital_adequacy
```

- [ ] **Step 2: 为每个指标找到原始证据**

在 `B_source_verification.md` 使用以下字段记录：

```text
case_id | industry_metric_id | source_doc_id | source_page | publisher
quote | raw_value_or_text | content_hash | evidence_type | review_result | note
```

`quote` 必须逐字抄录；找不到时填写“未找到”，并说明查过的资料和页码范围。

- [ ] **Step 3: 单独处理两个高风险指标**

1. `sales_expense_rate`：记录销售费用原值、营业收入原值、单位、公式和计算结果，不要只写 4.30%。
2. `food_safety`：每个来源分别记录其原文，不把海天和茅台两段话拼成一个来源都不存在的句子。

- [ ] **Step 4: 核对来源独立性**

对于 `multiple` 指标，确认来源的 publisher 和 content_hash 均不同；如果只是不同页或同一公司同一报告，标记为不满足独立来源。

- [ ] **Step 5: 验证并提交**

运行：

```powershell
python scripts/validate_manifest.py data/manifests/food_case.csv
python scripts/validate_manifest.py data/manifests/bank_case.csv
```

然后只提交 `docs/gold_review/B_source_verification.md`，提交说明使用：

```text
docs(gold): verify source pages for food and bank metrics
```

验收：10 个必查指标都有来源、页码、原文或明确的缺失记录；不存在编造 quote。

---

### Task 2: C metric definition review

**Owner:** C  
**Task ID:** GOLD-C-001

**Files:**
- Read: `configs/food_beverage.yaml`
- Read: `configs/banking.yaml`
- Read: `docs/CONTRACTS.md`
- Read: `docs/manual_review_checklist.md`
- Read: `docs/gold_review/B_source_verification.md`
- Create: `docs/gold_review/C_metric_definition_review.md`

**Consumes:** B 的来源核验表、行业 YAML、公共契约。

**Produces:** 一份指标口径确认表和 Gold 表达建议。

- [ ] **Step 1: 逐项确认指标定义**

在 `C_metric_definition_review.md` 使用以下字段：

```text
industry_metric_id | display_name | definition | unit
evidence_types | evidence_requirement | direct_or_derived | review_result | note
```

- [ ] **Step 2: 确认计算型指标**

明确 `sales_expense_rate` 的计算式：

```text
销售费用率 = 销售费用 / 营业收入 × 100%
```

同时核对分子、分母的单位是否一致，以及四舍五入规则。

- [ ] **Step 3: 确认多来源指标**

确认 `food_safety` 的 Gold 应表达为两个来源各自可验证的事实，而不是把两个公司的不同表述合并成一条不存在于原文的 quote。

- [ ] **Step 4: 检查 Gold 与评分器的兼容性**

重点核对 `evaluation/metrics.py` 对 `expected_text`、数值、quote 和 fact_text 的匹配要求。若现有结构无法表达计算型或来源级文本，必须在表中写出具体阻塞点，不得降低匹配标准。

- [ ] **Step 5: 验证并提交**

运行：

```powershell
pytest tests/industry -q
```

提交说明使用：

```text
docs(gold): confirm metric definitions and scoring semantics
```

验收：食品饮料和银行各 5 个必查指标均有明确口径；所有不确定项都有记录。

---

### Task 3: D Gold assembly and validation

**Owner:** D  
**Task ID:** GOLD-D-001

**Files:**
- Read: `docs/gold_review/B_source_verification.md`
- Read: `docs/gold_review/C_metric_definition_review.md`
- Read: `evaluation/gold.py`
- Read: `evaluation/metrics.py`
- Modify: `fixtures/evaluation/food_gold.json`
- Modify: `fixtures/evaluation/bank_gold.json`
- Modify: `tests/evaluation/test_gold_schema.py`
- Create: `docs/gold_review/D_gold_assembly_log.md`

**Consumes:** B 的原文证据和 C 的指标口径确认；现有 Gold loader/scorer 的实际行为。

**Produces:** 两份结构合法、来源可追溯、能被当前评分逻辑正确处理的 Gold 文件，以及对应测试和组装记录。

- [ ] **Step 1: 先保持未签收状态**

在 B/C 交付并由 A 确认前，Gold 使用 `pending_signoff` 或仓库现有的不可评分状态；不要仅因为 JSON 能加载就标记为 `signed`。

- [ ] **Step 2: 按核验结果组装 Gold**

每项至少包含：

```text
item_id | item_type | expected_text | expected_value | unit
required | source_doc_id/source_page | industry_metric_id | evidence_requirement
```

计算型指标必须保留计算所需的原始数值和公式；多来源指标必须保留来源级 publisher、content_hash、页码和来源级事实。

- [ ] **Step 3: 补充真实内容校验测试**

测试至少验证：

1. 两个 Gold 覆盖配置中的全部必查指标；
2. source_doc_id 存在于对应 manifest；
3. source_page 为正整数且不超出对应 PDF 页数；
4. 计算结果按记录的公式可复现；
5. multiple 来源的 publisher 和 content_hash 独立；
6. 未签收 Gold 不会被正式评分。

- [ ] **Step 4: 记录无法表达的内容**

如果现有 `evaluation.gold` 或 `evaluation.metrics` 无法正确表达某个已核验指标，先在 `D_gold_assembly_log.md` 记录具体例子和影响，不通过修改 expected_text 或删除证据要求来绕过问题。

- [ ] **Step 5: 运行评测测试并提交**

运行：

```powershell
pytest tests/evaluation/test_gold_schema.py -q
pytest tests/evaluation/test_metrics.py -q
```

提交说明使用：

```text
feat(evaluation): assemble verified food and bank gold standards
```

验收：D 的 JSON、测试和组装记录都在仓库中；A 明确签收前不得接入 `evaluation/experiment_definitions.yaml`。

---

### Task 4: A final sign-off gate

**Owner:** A

**Files:**
- Read: `docs/gold_review/B_source_verification.md`
- Read: `docs/gold_review/C_metric_definition_review.md`
- Read: `docs/gold_review/D_gold_assembly_log.md`
- Modify after sign-off: `evaluation/experiment_definitions.yaml`
- Modify after sign-off: `docs/task_board.md`

- [ ] **Step 1: Review B/C/D deliverables**
- [ ] **Step 2: Confirm all required metrics, formulas, pages and sources**
- [ ] **Step 3: Only after confirmation, change Gold status to `signed`**
- [ ] **Step 4: Set the signed Gold paths in experiment definitions**
- [ ] **Step 5: Run the first scored experiment and record the result**
