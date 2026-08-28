# GOLD-C-001 指标口径确认评审（role C: industry）

## 0. 评审信息

- 评审人：role C（industry）
- 日期：2026-08-28
- 分支：`role-c-industry`
- 评审对象：Gold 标准草稿中 10 个 required 指标的口径定义、单位、证据类型/要求、直接/派生属性，以及与 `evaluation/metrics.py`、`evaluation/gold.py` 评分语义的兼容性
- 评审基准：`origin/role-a-core@235ffe2` 的 Gold 草稿内容（与 `origin/role-a-adapt-008` 同版本，两分支该文件 diff 为空）。该版本 `status=pending_signoff`（尚未人工复核签收），items 与 `c3aa4ad` 引入的真实草稿一致
- 评审范围约束（遵守计划全局约束）：
  - C 不修改任何 Gold JSON 文件（含 `fixtures/evaluation/*.json`）
  - 引用原文一律逐字（quote 不得改写）
  - 计算型指标必须记录分子/分母公式
  - `evidence_requirement=multiple` 必须为两个独立来源
  - 未签收（`status != "signed"`）的 Gold 不得用于评分
- 依赖说明：config 文件（`configs/*.yaml`）无 `definition` 字段，本评审的 definition 列依据计划文档明确给出的公式、YAML `keywords` 与草稿 `expected_text` 所体现的口径确认一致性；涉及年报原文表述的核对项移交 role B 交叉核对（B 未交付，状态见第 6 节）

## 1. 结论摘要

1. 10 个 required 指标的口径本身全部确认，与 `configs/food_beverage.yaml`、`configs/banking.yaml` 中 `required: true` 的指标集合精确一致（草稿 `required_metric_ids` 与 config 完全吻合，见第 7 节实证 A）。
2. 存在 2 个评分语义阻塞（不降低匹配标准的前提下无法通过当前评分器）：
   - BLOCKER-1：`GOLD-FOOD-005` 的 `expected_text` 为斜杠缩写短语，结构性不可能在任何来源原文中逐字出现
   - BLOCKER-2：`GOLD-FOOD-003` 的计算值 `expected_text` 与评分器对 quote/fact_text 的双重逐字校验矛盾
3. 签收门禁行为正确：`pending_signoff` 状态的 Gold 在加载时被拒绝，`signed` 草稿可正常加载（第 7 节实证 A）。
4. 待 B 交叉核对清单见第 6 节（B_source_verification.md 尚未交付，本评审相关核对项均为 pending）。

## 2. 指标口径评审表

字段依据：`industry_metric_id`/`display_name`/`evidence_types`/`evidence_requirement` 来自 `configs/*.yaml`；`unit` 来自 Gold 草稿各 item 的 `unit` 字段；`direct_or_derived` 依据草稿 `fixture_notice` 与取值性质。

### 2.1 食品饮料（food_beverage）

| industry_metric_id | display_name | definition | unit | evidence_types | evidence_requirement | direct_or_derived | review_result | note |
|---|---|---|---|---|---|---|---|---|
| revenue_growth | 收入增速 | 营业收入同比增速；草稿取值形态"营业收入同比增长 -1.21%" | % | financial | single | direct | 确认 | GOLD-FOOD-001，DOC-FOOD-001 p6；负值逐字含"-1.21%"即可通过数值校验 |
| gross_margin | 毛利率 | 毛利占收入百分比；草稿取分产品口径（"茅台酒毛利率 93.53%"） | % | financial | single | direct | 确认（口径待 B 核对） | GOLD-FOOD-002，DOC-FOOD-001 p18；分子分母口径与逐字文本需 B 核对原文 |
| sales_expense_rate | 销售费用率 | 销售费用/营业收入×100%（计划 Step 2 明确，草稿 fixture_notice 同） | % | financial | single | derived | 口径确认；评分匹配存在 BLOCKER-2 | GOLD-FOOD-003，DOC-FOOD-001 p9；详见第 3 节 |
| inventory | 财务存货 | 资产负债表存货项目账面价值（财务口径，非实物量；docs/CONTRACTS.md 约定 inventory 仅财务存货，inventory_volume 为实物量 optional 指标） | 亿元（原值为元） | financial | single | direct | 确认（附换算括号核对项） | GOLD-FOOD-004，DOC-FOOD-001 p57；expected_text 含"元→亿元"换算括号，需 B 核对逐字（见 5.4） |
| food_safety | 食品安全 | 来源级食品安全/质量管理事实（news/policy/company_release 各自可独立验证） | 无 | news + policy + company_release | multiple | direct | 口径确认；草稿形态存在 BLOCKER-1 | GOLD-FOOD-005，independent_sources = DOC-FOOD-004 p16（海天）+ DOC-FOOD-001 p9（茅台）；详见第 4 节 |

### 2.2 银行（banking）

| industry_metric_id | display_name | definition | unit | evidence_types | evidence_requirement | direct_or_derived | review_result | note |
|---|---|---|---|---|---|---|---|---|
| net_interest_margin | 净息差 | 净利息收入/平均生息资产×100%；草稿取年报披露口径（"净利息收益率 1.28%"），以年报披露值为准 | % | financial | single | direct | 确认（待 B 核对逐字） | GOLD-BANK-001，DOC-BANK-001 p16；config keywords 同时含"净息差/净利息收益率"，expected_text 用后者，需 B 确认 p16 原文用词与空格 |
| loan_growth | 贷款增长 | 客户贷款及垫款总额同比增速 | % | financial | single | direct | 确认（待 B 核对逐字） | GOLD-BANK-002，DOC-BANK-001 p34；expected_text 为"客户贷款及垫款总额同比增长 7.5%"，需 B 确认原文逐字形态 |
| non_performing_loan_ratio | 不良贷款率 | 不良贷款余额/贷款总额×100%（监管口径），以年报披露值为准 | % | financial | single | direct | 确认（待 B 核对逐字） | GOLD-BANK-003，DOC-BANK-001 p16 |
| provision_coverage | 拨备覆盖率 | 贷款损失准备/不良贷款余额×100%（监管口径），以年报披露值为准 | % | financial | single | direct | 确认（待 B 核对逐字） | GOLD-BANK-004，DOC-BANK-001 p16；"213.60%"尾零可被评分器接受（实证 D） |
| capital_adequacy | 资本充足率 | 资本净额/风险加权资产×100%（监管口径），以年报披露值为准；config risk_rules 明确"必须保留原始口径，不同监管口径不能混用" | % | financial + policy | single | direct | 确认（待 B 核对口径与逐字） | GOLD-BANK-005，DOC-BANK-001 p102；需 B 确认为集团并表口径，且非核心一级/一级资本充足率 |

### 2.3 required_metric_ids 一致性

草稿 `required_metric_ids` 与 config `required: true` 指标集合精确一致（`required_metric_ids_source` 分别为 `configs/food_beverage.yaml@a55f757` 与 `configs/banking.yaml@a55f757`），实证输出见第 7 节 A 组。

## 3. 销售费用率计算式专项（计划 Step 2）

- **公式确认**：销售费用率 = 销售费用 / 营业收入 × 100%。分子（销售费用）与分母（营业收入）均为同一年报、同一报告期、同一币种的金额（单位：元），单位一致性成立。
- **四舍五入核对**：`GOLD-FOOD-003` 取 `expected_value=4.30`、`unit=%`。验证 4.30% 需要用 p9 原文的销售费用与营业收入原值复算（保留两位小数四舍五入）。原值不在 C 可见范围内，**移交 B 复算确认**（第 6 节第 1 项）。
- **BLOCKER-2（评分匹配矛盾）**：`expected_text = "销售费用率（销售费用/营业收入）约 4.30%"`。评分器语义（`evaluation/metrics.py`）：
  - `_evidence_supports_item` 要求 quote **与** fact_text **双双**通过 `_text_supports_item`，后者要求文本逐字包含 expected_text 且含"数值+单位"紧邻匹配；
  - 若证据原文只含分子分母原值（如"销售费用 …… 元""营业收入 …… 元"），不含该计算值短语，则逐字包含失败（实证 C：`got=False`）；
  - 若仅 quote 含计算值短语而 fact_text 只含原值，双重校验仍然失败（实证 C：`got=False`）;
  - 仅当 quote 与 fact_text 都逐字含"销售费用率（销售费用/营业收入）约 4.30%"时才通过——而年报原文一般不会有该合并表述。
  - 该矛盾需 role A 决策（例如调整 expected_text 为原文可逐字出现的形态，或将计算关系放入 claim 计算说明），**C 不降低匹配标准，也不修改 Gold JSON**。

## 4. food_safety 专项（计划 Step 3）

- **口径确认**：food_safety 证据类型为 news + policy + company_release，`evidence_requirement=multiple`，草稿给出 DOC-FOOD-004 p16（佛山市海天调味食品股份有限公司，content_hash `2c7fba45…`）与 DOC-FOOD-001 p9（贵州茅台酒股份有限公司，content_hash `474905de…`）两个独立来源，满足"multiple 须双独立来源"约束（publisher 与 content_hash 均不同，实证 E 位置匹配通过）。
- **BLOCKER-1（斜杠缩写不可逐字出现）**：`expected_text = "公司坚持做好食品安全/质量管理"` 为含斜杠的缩写合并短语。评分器要求证据 quote 与 fact_text **逐字包含**该短语：
  - 海天年报的质量管理表述与茅台年报的食品安全表述各自使用自己的原文措辞（如顿号"、"或"和"连接），不可能逐字含有斜杠串"食品安全/质量管理"；
  - 实证 B：用两家公司原文措辞的模拟 quote/fact_text 调用 `_evidence_supports_item` 与 `_claim_matches_item`，均返回 False；仅当文本逐字含"食品安全/质量管理"时才返回 True——即在真实原文约束下该 item 结构性恒不通过；
  - 若通过拼接 quote 来满足匹配，则违反 CONTRACTS.md"quote 不得由模型改写/拼接"的约束，且不构成来源级可验证事实。
- **与计划 Step 3 的一致性结论**：food_safety 应表达为**来源级各自可验证事实**（每条证据的 expected_text/quote 取该来源原文逐字片段），而不是合并为一个不存在于任何原文的短语。草稿当前的 expected_text 形态与此原则冲突，需 role A 决策修订（C 不改 Gold JSON）。

## 5. 评分器兼容性核对（计划 Step 4）

以下核对基于 `evaluation/metrics.py` 与 `evaluation/gold.py` 的实际代码语义（逐行复核）与第 7 节实证结果。**本评审未降低任何匹配标准，全部阻塞点为草稿形态与现有标准的冲突，交由 A/B 决策处理。**

### 5.1 评分器语义要点（事实摘录）

- `_claim_matches_item`：claim 的 `industry_metric_ids` 含 item 的 `industry_metric_id`，且 `expected_text.casefold() in claim.text.casefold()`。
- `_text_supports_item`：文本逐字包含 expected_text **且** 通过数值-单位校验（正则 `(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?\s*{unit}`，IGNORECASE；数值用 Decimal 相等比较）。
- `_evidence_supports_item`：quote 与 fact_text **双双**通过 `_text_supports_item`。
- `_location_matches`：证据 `doc_id` 等于来源 `doc_id`，且来源 `page` 非 None 时 page 相等。
- `multiple` 判定：≥2 条引用证据且各自通过 location 校验，归一化 publisher 与 content_hash 各自 ≥2 个不同值。
- `load_gold_standard`：`status != "signed"` 直接拒绝（"Gold Standard is not signed for scoring"）；`required_metric_ids` 与 config `required: true` 集合精确匹配；每个 item 的 `industry_metric_id` 必须存在于 config。

### 5.2 阻塞点清单

| 编号 | 对象 | 阻塞描述 | 实证 |
|---|---|---|---|
| BLOCKER-1 | GOLD-FOOD-005 | 斜杠缩写 expected_text 结构性不可能逐字出现于任何来源原文 → quote/fact_text/claim 三层校验恒 False | B 组 |
| BLOCKER-2 | GOLD-FOOD-003 | 计算值 expected_text 与 quote+fact_text 双重逐字校验矛盾：原文只有分子分母原值时恒 False | C 组 |
| 待核-1 | GOLD-FOOD-004 | expected_text 含换算括号"（约 614.27 亿元）"，需 B 确认 p57 原文是否逐字含该括号形态；若原文只有"61,427,421,796.18 元"则逐字包含失败 | D 组 |
| 待核-2 | 全部数值 item | 空格逐字敏感：expected_text 中"净利息收益率 1.28%"的空格必须与 PDF 提取文本一致；"1.28 %"可匹配（`\s*`）但"1.28个百分点"不能匹配"%"；需 B 按 PDF 提取形态逐字核对 10 项 expected_text | D 组 |
| 待核-3 | GOLD-BANK-001~005 | 银行 5 项 expected_text 的逐字原文、页码；资本充足率需确认集团并表口径且非核心一级/一级口径（config risk_rules：必须保留原始口径） | 第 6 节 |
| 待核-4 | GOLD-FOOD-002/003 | 毛利率分产品口径（茅台酒）与销售费用率 4.30% 复算需 B 用原值确认 | 第 6 节 |

### 5.3 门禁与结构确认（无阻塞）

- 签收门禁：`pending_signoff` 的 Gold 加载被拒绝、`signed` 草稿正常加载（A 组）——当前草稿 `status=pending_signoff`，按全局约束"A 人工复核签收后方可评分"，门禁行为与流程约束一致。
- `multiple` 独立来源结构：GOLD-FOOD-005 的两个来源 publisher/content_hash 均不同，位置匹配通过（E 组）；阻塞仅在 expected_text 形态（BLOCKER-1）。

## 6. 待 B 交叉核对清单（依赖项）

`docs/gold_review/B_source_verification.md` 尚未交付（`docs/gold_review/` 目录在当前分支不存在），以下核对项状态均为 **pending**：

1. GOLD-FOOD-003：用 p9 原文的销售费用与营业收入原值复算销售费用率，确认 4.30%（保留两位小数）。
2. GOLD-FOOD-004：确认 p57 原文是否逐字含"存货 61,427,421,796.18 元（约 614.27 亿元）"（含括号换算）。
3. 10 项 expected_text 与 PDF 提取文本的逐字一致性（空格、标点、全角/半角）。
4. 银行 5 项：p16/p34/p102 的逐字原文与页码；资本充足率确认为集团并表口径。
5. GOLD-FOOD-002：茅台酒毛利率 93.53% 的分产品口径与原文逐字核对。

## 7. 实证记录

使用仓库真实代码（`evaluation/metrics.py`、`evaluation/gold.py`、`app/schemas/*`）编写只读实证脚本，在 `role-c-industry@19f0819` 工作副本上运行，共 20 项断言全部 PASS：

- **A. 签收门禁与加载**：main 空模板（`items: []`，pending_signoff）被拒绝："Gold Standard is not signed for scoring: status='pending_signoff'…"；235ffe2 pending_signoff 草稿同样被拒；signed 草稿加载成功，`required_metric_ids = ['food_safety', 'gross_margin', 'inventory', 'revenue_growth', 'sales_expense_rate']`，与 `configs/food_beverage.yaml` required:true 集合精确一致。
- **B. 斜杠缩写（GOLD-FOOD-005）**：海天原文措辞（顿号）与茅台原文措辞（"和"）的 quote/fact_text 支撑斜杠缩写 expected_text 均为 False；含海天原文的 Claim 匹配为 False；仅逐字含"食品安全/质量管理"时为 True。
- **C. 计算型双重校验（GOLD-FOOD-003）**：仅含分子分母原值的证据支撑计算值 expected_text 为 False；quote 含计算值而 fact_text 仅含原值为 False；quote 与 fact_text 都逐字含"销售费用率（销售费用/营业收入）约 4.30%"时为 True。
- **D. 数值/单位/空格敏感性**：逐字含"净利息收益率 1.28%"（含空格）为 True；原文无空格时 expected_text 包含为 False；"1.28 %"（数值与单位间空格）可匹配；"1.28个百分点"不能匹配单位"%"；"213.60%" 与 Decimal('213.6') 相等（尾零不影响）；GOLD-FOOD-004 括号齐全为 True、缺失括号为 False；换算值须逐字出现"614.27 亿元"。
- **E. multiple 结构（GOLD-FOOD-005）**：两来源 location 匹配均为 True；仅当 quote 逐字含斜杠串（即伪造拼接文本）时 multiple 才可能满足——真实原文无法满足，与 BLOCKER-1 互证。

## 8. 测试记录（计划 Step 5）

- 命令：`pytest tests/industry -q`
- 结果：**115 passed**（0.86s）
- 环境：Python 3.12.10（便携版，仓库依赖按 `requirements-dev.txt` 安装）

## 9. 后续动作

1. 本评审随 `role-c-industry` 分支提交（提交说明：`docs(gold): confirm metric definitions and scoring semantics`），不触碰 main。
2. BLOCKER-1/BLOCKER-2 及第 6 节核对清单移交 role A（Gold 形态决策）与 role B（原文交叉核对）；C 不修改 Gold JSON、不降低匹配标准。
3. Gold 草稿在 A 人工复核并签收（`status=signed`）之前不得用于评分（门禁已在实证 A 中验证）。
