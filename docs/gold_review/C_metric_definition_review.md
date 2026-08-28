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
- 依赖说明（v2 修订）：config 文件（`configs/*.yaml`）无 `definition` 字段，本评审的 definition 列依据计划文档明确给出的公式、YAML `keywords` 与草稿 `expected_text` 所体现的口径确认一致性。年报 PDF 原文位于仓库 `data/raw/`（git 跟踪）；v1 撰写时未读取原文、将涉原文核对项全部移交 role B，v2 已由 C 直接读取三份相关年报（茅台 143 页、海天 215 页、工商银行 408 页）完成核对（第 7 节 F 组），B 交叉核对仍有独立价值（替代工具复核与口径确认，见第 6 节）。
- 修订记录：
  - v1（2026-08-28）：初稿。基于口径一致性、评分器语义逐行复核与只读实证脚本完成；**撰写时未读年报 PDF 原文**，涉原文表述为推断或模拟构造。
  - v2（2026-08-28）：勘误 8 处（v1 将模拟措辞误述为"原文措辞"、对 `docs/CONTRACTS.md` 的引文不准确、实证断言计数 20 实为 21、"原值不在 C 可见范围内"不实、银行 definition 通识公式未标注来源等）；新增第 7 节 F 组 PDF 原文核对（哈希匹配、9 项 expected_text 逐字核对、销售费用率复算、FOOD-005 真实原文提取）；新增 BLOCKER-3/BLOCKER-4；更新第 1/2/3/4/5/6/9 节相应内容。

## 1. 结论摘要

1. 10 个 required 指标的口径本身全部确认，与 `configs/food_beverage.yaml`、`configs/banking.yaml` 中 `required: true` 的指标集合精确一致（草稿 `required_metric_ids` 与 config 完全吻合，见第 7 节实证 A）。
2. 存在 4 个评分语义/原文形态阻塞（不降低匹配标准的前提下无法通过当前评分器）：
   - BLOCKER-1：`GOLD-FOOD-005` 的 `expected_text` 为斜杠缩写短语，v2 经真实原文核实：该短语在两份来源 PDF 提取全文（严格+去空格）均无命中，且茅台全文不含"食品安全"、海天全文不含"质量管理"（F.4）
   - BLOCKER-2：`GOLD-FOOD-003` 的计算值 `expected_text` 与评分器对 quote/fact_text 的双重逐字校验矛盾（v2 复算确认数值 4.30 正确，但短语形态在原文全文 0 命中，F.2/F.3）
   - BLOCKER-3（v2 新增）：6 项 expected_text（FOOD-001/002/003/004、BANK-001/002）在对应 PDF 提取全文严格+去空格均无逐字命中（F.2）
   - BLOCKER-4（v2 新增）：BANK-004/005 草稿页码与实际命中页不符（p16→p87、p102→p101），location 校验将失败（F.6）
3. 签收门禁行为正确：`pending_signoff` 状态的 Gold 在加载时被拒绝，`signed` 草稿可正常加载（第 7 节实证 A）。
4. 待 B 交叉核对清单见第 6 节（B_source_verification.md 尚未交付；v2 后清单第 1/2 项已由 C 完成，第 3/4 项部分完成，其余 pending）。

## 2. 指标口径评审表

字段依据：`industry_metric_id`/`display_name`/`evidence_types`/`evidence_requirement` 来自 `configs/*.yaml`；`unit` 来自 Gold 草稿各 item 的 `unit` 字段；`direct_or_derived` 依据草稿 `fixture_notice` 与取值性质。
v2 注：2.2 definition 列的分子/分母公式为通识公式（行业常识表述，非引自 config 或年报原文），v1 未标注来源，v2 补充声明；年报披露值以 note 中 v2 核对的原文为准。

### 2.1 食品饮料（food_beverage）

| industry_metric_id | display_name | definition | unit | evidence_types | evidence_requirement | direct_or_derived | review_result | note |
|---|---|---|---|---|---|---|---|---|
| revenue_growth | 收入增速 | 营业收入同比增速；草稿取值形态"营业收入同比增长 -1.21%" | % | financial | single | direct | 口径确认；expected_text 无逐字命中（BLOCKER-3） | GOLD-FOOD-001，DOC-FOOD-001 p6；v2 核对：全文严格+去空格 0 命中；p9 有"营业收入168,838,102,514.79170,899,152,276.34-1.21"（数值 -1.21 存在，整句形态不存在，F.2） |
| gross_margin | 毛利率 | 毛利占收入百分比；草稿取分产品口径（"茅台酒毛利率 93.53%"） | % | financial | single | direct | 口径待 B 核对；expected_text 无逐字命中（BLOCKER-3） | GOLD-FOOD-002，DOC-FOOD-001 p18；v2 核对：草稿页 p18 与全文均 0 命中（F.2） |
| sales_expense_rate | 销售费用率 | 销售费用/营业收入×100%（计划 Step 2 明确，草稿 fixture_notice 同） | % | financial | single | derived | 口径确认；数值复算一致（F.3）；文本形态 BLOCKER-2/3 | GOLD-FOOD-003，DOC-FOOD-001 p9；详见第 3 节 |
| inventory | 财务存货 | 资产负债表存货项目账面价值（财务口径，非实物量；docs/CONTRACTS.md 约定 inventory 仅财务存货，inventory_volume 为实物量 optional 指标） | 亿元（原值为元） | financial | single | direct | 口径确认；换算括号经核不存在于原文（BLOCKER-3） | GOLD-FOOD-004，DOC-FOOD-001 p57；v2 核对：p57 含精确数字"61,427,421,796.18"，但"614.27"全文 0 页，expected_text 整体 0 命中（F.5） |
| food_safety | 食品安全 | 来源级食品安全/质量管理事实（news/policy/company_release 各自可独立验证） | 无 | news + policy + company_release | multiple | direct | 口径确认；BLOCKER-1 经真实原文证实 | GOLD-FOOD-005，independent_sources = DOC-FOOD-004 p16（海天）+ DOC-FOOD-001 p9（茅台）；真实原文见 F.4，详见第 4 节 |

### 2.2 银行（banking）

| industry_metric_id | display_name | definition | unit | evidence_types | evidence_requirement | direct_or_derived | review_result | note |
|---|---|---|---|---|---|---|---|---|
| net_interest_margin | 净息差 | 净利息收入/平均生息资产×100%（通识公式）；草稿取年报披露口径（"净利息收益率 1.28%"），以年报披露值为准 | % | financial | single | direct | 口径确认；expected_text 无逐字命中（BLOCKER-3） | GOLD-BANK-001，DOC-BANK-001 p16；v2 核对：p16 为"净利息收益率（4）1.281.421.61"多期并列形态，全文 0 命中（F.6）；config keywords 同含"净息差/净利息收益率" |
| loan_growth | 贷款增长 | 客户贷款及垫款总额同比增速（通识公式） | % | financial | single | direct | 口径确认；expected_text 无逐字命中（BLOCKER-3） | GOLD-BANK-002，DOC-BANK-001 p34；v2 核对：p34 原文"客户贷款及垫款总额（简称"各项贷款"）305,061.14亿元，增加21,338.85亿元，增长7.5%"——原文为"增长7.5%"而非"同比增长 7.5%"，全文 0 命中（F.6） |
| non_performing_loan_ratio | 不良贷款率 | 不良贷款余额/贷款总额×100%（监管口径，通识公式），以年报披露值为准 | % | financial | single | direct | 口径确认；草稿页 p16 无逐字形态 | GOLD-BANK-003，DOC-BANK-001 p16；v2 核对：p16 为"不良贷款率（7）1.311.341.36"；严格 0 命中，去空格命中 p22/85（紧邻形态仅空白差异，F.6） |
| provision_coverage | 拨备覆盖率 | 贷款损失准备/不良贷款余额×100%（监管口径，通识公式），以年报披露值为准 | % | financial | single | direct | 口径确认；页码不符（BLOCKER-4） | GOLD-BANK-004，DOC-BANK-001；v2 核对：草稿 p16 为"拨备覆盖率（8）213.60214.91213.97"（无"213.60%"紧邻形态）；"拨备覆盖率 213.60%"严格命中 p87（F.6）；"213.60%"尾零可被评分器接受（实证 D） |
| capital_adequacy | 资本充足率 | 资本净额/风险加权资产×100%（监管口径，通识公式），以年报披露值为准；config risk_rules 明确"必须保留原始口径，不同监管口径不能混用" | % | financial + policy | single | direct | 口径确认（并表口径待 B）；页码不符（BLOCKER-4） | GOLD-BANK-005，DOC-BANK-001；v2 核对：草稿 p102 为"资本充足率（%）18.7619.3…"（无"18.76%"紧邻形态）；"资本充足率 18.76%"严格命中 p101（F.6）；需 B 确认为集团并表口径，且非核心一级/一级资本充足率 |

### 2.3 required_metric_ids 一致性

草稿 `required_metric_ids` 与 config `required: true` 指标集合精确一致（`required_metric_ids_source` 分别为 `configs/food_beverage.yaml@a55f757` 与 `configs/banking.yaml@a55f757`），实证输出见第 7 节 A 组。

## 3. 销售费用率计算式专项（计划 Step 2）

- **公式确认**：销售费用率 = 销售费用 / 营业收入 × 100%。分子（销售费用）与分母（营业收入）均为同一年报、同一报告期、同一币种的金额（单位：元），单位一致性成立。v2 核实：两原值同现于茅台年报 p9 提取文本（F.3），同一报告期成立。
- **四舍五入核对（v2 已完成）**：`GOLD-FOOD-003` 取 `expected_value=4.30`、`unit=%`。C 已用 p9 原值复算（F.3）：7,253,499,600.68 ÷ 168,838,102,514.79 × 100 = 4.296127% → 保留两位 4.30，**与草稿一致**。v1 称"原值不在 C 可见范围内、移交 B 复算"不实——年报 PDF 位于仓库 `data/raw/` 下，v1 撰写时未读取（已在修订记录勘误）。
- **BLOCKER-2（评分匹配矛盾）**：`expected_text = "销售费用率（销售费用/营业收入）约 4.30%"`。评分器语义（`evaluation/metrics.py`）：
  - `_evidence_supports_item` 要求 quote **与** fact_text **双双**通过 `_text_supports_item`，后者要求文本逐字包含 expected_text 且含"数值+单位"紧邻匹配；
  - 若证据原文只含分子分母原值（如"销售费用 …… 元""营业收入 …… 元"），不含该计算值短语，则逐字包含失败（实证 C：`got=False`）；
  - 若仅 quote 含计算值短语而 fact_text 只含原值，双重校验仍然失败（实证 C：`got=False`）;
  - 仅当 quote 与 fact_text 都逐字含"销售费用率（销售费用/营业收入）约 4.30%"时才通过——v2 实证：该短语在茅台 PDF 提取全文严格+去空格均 0 命中（F.2），即从原文取证不可能满足。
  - 该矛盾需 role A 决策（例如调整 expected_text 为原文可逐字出现的形态，或将计算关系放入 claim 计算说明），**C 不降低匹配标准，也不修改 Gold JSON**。

## 4. food_safety 专项（计划 Step 3）

- **口径确认**：food_safety 证据类型为 news + policy + company_release，`evidence_requirement=multiple`，草稿给出 DOC-FOOD-004 p16（佛山市海天调味食品股份有限公司，content_hash `2c7fba45…`）与 DOC-FOOD-001 p9（贵州茅台酒股份有限公司，content_hash `474905de…`）两个独立来源，满足"multiple 须双独立来源"约束（publisher 与 content_hash 均不同，实证 E 位置匹配通过；v2 哈希与 `data/raw/` 下 PDF 文件精确匹配，F.1）。
- **BLOCKER-1（斜杠缩写不可逐字出现，v2 经真实原文证实）**：`expected_text = "公司坚持做好食品安全/质量管理"` 为含斜杠的缩写合并短语。评分器要求证据 quote 与 fact_text **逐字包含**该短语：
  - v2 真实原文（逐字，F.4）：海天 p16 为"坚持做好食品安全、稳定供应、可持续发展"；茅台 p9 相关表述为"恪守"质量是生命之魂"信仰……构建覆盖全产业链的质量管理体系"。两处均不含斜杠串"食品安全/质量管理"；
  - v2 全文扫描（F.4）：斜杠串在两份提取全文中均无命中（茅台严格+去空格、海天去空格均 0 页）；**茅台全文（143 页）任何页均不含"食品安全"四字，海天全文（215 页）任何页均不含"质量管理"四字**——即无论用什么连接符（斜杠/顿号/"和"），该合并短语在任一单一来源原文中都不可能出现，quote/fact_text/claim 三层校验恒 False；
  - 实证 B（v1）：用**模拟构造**的 quote/fact_text 调用 `_evidence_supports_item` 与 `_claim_matches_item`，均返回 False；仅当文本逐字含"食品安全/质量管理"时才返回 True。该实证验证的是评分器行为（结论有效），但 v1 将其表述为"用两家公司原文措辞"不实——v1 撰写时未读原文，quote/fact_text 为模拟文本（已在修订记录勘误）；
  - 若通过拼接 quote 来满足匹配，则违反 `docs/CONTRACTS.md`"quote 不得由模型改写"的约束，且不构成来源级可验证事实。v1 引文"quote 不得由模型改写/拼接"不准确：CONTRACTS.md 原文仅"quote 不得由模型改写；"，无"拼接"表述（已在修订记录勘误；不得改写引文的约束依然支撑本节结论）。
- **与计划 Step 3 的一致性结论**：food_safety 应表达为**来源级各自可验证事实**（每条证据的 expected_text/quote 取该来源原文逐字片段，如海天"坚持做好食品安全、稳定供应、可持续发展"），而不是合并为一个不存在于任何原文的短语。草稿当前的 expected_text 形态与此原则冲突，需 role A 决策修订（C 不改 Gold JSON）。v2 真实原文（F.4）进一步支持该结论。

## 5. 评分器兼容性核对（计划 Step 4）

以下核对基于 `evaluation/metrics.py` 与 `evaluation/gold.py` 的实际代码语义（逐行复核）与第 7 节实证结果。**本评审未降低任何匹配标准，全部阻塞点为草稿形态与现有标准的冲突，交由 A/B 决策处理。**

### 5.1 评分器语义要点（事实摘录）

- `_claim_matches_item`：claim 的 `industry_metric_ids` 含 item 的 `industry_metric_id`，且 `expected_text.casefold() in claim.text.casefold()`。
- `_text_supports_item`：文本逐字包含 expected_text **且** 通过数值-单位校验（正则 `(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?\s*{unit}`，IGNORECASE；数值用 Decimal 相等比较）。
- `_evidence_supports_item`：quote 与 fact_text **双双**通过 `_text_supports_item`。
- `_location_matches`：证据 `doc_id` 等于来源 `doc_id`，且来源 `page` 非 None 时 page 相等。
- `multiple` 判定：每条引用证据须通过 evidence 支撑校验（quote 与 fact_text 双重逐字+数值单位）与 location 校验；满足条件的证据 ≥2 条，且归一化 publisher 与 content_hash 各 ≥2 个不同值。（v1 摘录遗漏前置的支撑校验条件，v2 补全。）
- `load_gold_standard`：`status != "signed"` 直接拒绝（"Gold Standard is not signed for scoring"）；`required_metric_ids` 与 config `required: true` 集合精确匹配；每个 item 的 `industry_metric_id` 必须存在于 config。

### 5.2 阻塞点清单

| 编号 | 对象 | 阻塞描述 | 实证 |
|---|---|---|---|
| BLOCKER-1 | GOLD-FOOD-005 | 斜杠缩写 expected_text 在两份来源 PDF 提取全文（严格+去空格）均无命中；且茅台全文无"食品安全"、海天全文无"质量管理"，任何连接符形态的合并短语在单一来源原文中都不可能出现 → quote/fact_text/claim 三层校验恒 False | B 组 + F.4 |
| BLOCKER-2 | GOLD-FOOD-003 | 计算值 expected_text 与 quote+fact_text 双重逐字校验矛盾；v2 复算确认数值 4.30 正确，但短语形态全文 0 命中 | C 组 + F.2/F.3 |
| BLOCKER-3（v2 新增） | FOOD-001/002/004、BANK-001/002（5 项；FOOD-003 见 BLOCKER-2） | expected_text 在对应 PDF 提取全文严格+去空格均无逐字命中：原文为表格多期并列形态（BANK-001/003 相关）或措辞不同（p34 为"增长7.5%"非"同比增长 7.5%"）；FOOD-004 的换算括号"（约 614.27 亿元）"全文不存在 | F.2/F.5/F.6 |
| BLOCKER-4（v2 新增） | BANK-004/005 | 草稿页码与实际命中页不符："拨备覆盖率 213.60%"严格命中 p87（草稿 p16）、"资本充足率 18.76%"严格命中 p101（草稿 p102）；`_location_matches` 在 page 非 None 时须相等，按草稿页码构造的证据无法通过 location 校验 | F.6 |
| 待核-1 | GOLD-FOOD-004 | v2 已核实：p57 含精确数字"61,427,421,796.18"，但换算括号"（约 614.27 亿元）"全文 0 页，expected_text 整体不可逐字匹配（并入 BLOCKER-3 描述）；仅余 B 以替代工具交叉复核 | F.5 |
| 待核-2 | 全部数值 item | 空格逐字敏感仍成立（"1.28 %"可匹配、"1.28个百分点"不能匹配"%"）；v2 已按 pypdf 完成 9 项 expected_text 初核（F.2）；"无命中"结论以 pypdf 提取为限，建议 B 以替代提取工具（pdfplumber/PyMuPDF 等）交叉复核 | D 组 + F.2 |
| 待核-3 | GOLD-BANK-001~005 | 页码已核（BLOCKER-4：BANK-004→p87、BANK-005→p101）；资本充足率集团并表口径确认仍 pending B | F.6 + 第 6 节 |
| 待核-4 | GOLD-FOOD-002/003 | 4.30% 复算已完成且一致（F.3）；93.53% 分产品口径待 B（v2 初核：p18 草稿页与全文均无逐字命中，F.2） | F.2/F.3 |

### 5.3 门禁与结构确认（无阻塞）

- 签收门禁：`pending_signoff` 的 Gold 加载被拒绝、`signed` 草稿正常加载（A 组）——当前草稿 `status=pending_signoff`，按全局约束"A 人工复核签收后方可评分"，门禁行为与流程约束一致。
- `multiple` 独立来源结构：GOLD-FOOD-005 的两个来源 publisher/content_hash 均不同，位置匹配通过（E 组；v2 哈希与 PDF 文件精确匹配，F.1）；阻塞仅在 expected_text 形态（BLOCKER-1）。

## 6. 待 B 交叉核对清单（依赖项，v2 状态更新）

`docs/gold_review/B_source_verification.md` 尚未交付（`docs/gold_review/` 目录在本分支的交付物即本文件），各核对项状态如下：

1. GOLD-FOOD-003 复算：**C 已完成（v2，F.3）**——4.296127% → 4.30 与草稿一致；B 可复核。
2. GOLD-FOOD-004 换算括号：**C 已完成（v2，F.5）**——p57 含精确数字"61,427,421,796.18"；"614.27"全文 0 页，换算括号不存在于原文；B 可用替代工具复核。
3. 10 项 expected_text 与 PDF 提取文本的逐字一致性：**C 已完成 pypdf 初核 9 项（F.2，FOOD-005 见 F.4）**——6 项严格+去空格均 0 命中、BANK-003 仅去空格命中 p22/85、BANK-004/005 命中页与草稿页码不符；建议 B 以替代提取工具交叉复核（pypdf 对空格/换行的处理可能影响结果）。
4. 银行 5 项原文与页码：**页码部分 C 已完成（F.6）**——BANK-004 实际 p87（草稿 p16）、BANK-005 实际 p101（草稿 p102）；资本充足率集团并表口径确认仍 **pending**。
5. GOLD-FOOD-002 茅台酒毛利率 93.53%：**pending**（v2 初核：p18 草稿页与全文均无逐字命中，F.2；分产品口径需 B 结合原文表格确认）。

## 7. 实证记录

使用仓库真实代码（`evaluation/metrics.py`、`evaluation/gold.py`、`app/schemas/*`）编写只读实证脚本，在 `role-c-industry@19f0819` 工作副本上运行，共 21 项断言全部 PASS（v1 误记为 20 项，v2 更正）：

- **A. 签收门禁与加载**：main 空模板（`items: []`，pending_signoff）被拒绝："Gold Standard is not signed for scoring: status='pending_signoff'…"；235ffe2 pending_signoff 草稿同样被拒；signed 草稿加载成功，`required_metric_ids = ['food_safety', 'gross_margin', 'inventory', 'revenue_growth', 'sales_expense_rate']`，与 `configs/food_beverage.yaml` required:true 集合精确一致。
- **B. 斜杠缩写（GOLD-FOOD-005）**：**模拟构造**的海天风格（顿号连接）与茅台风格 quote/fact_text 支撑斜杠缩写 expected_text 均为 False；含海天风格文本的 Claim 匹配为 False；仅逐字含"食品安全/质量管理"时为 True。（v1 称"海天原文措辞（顿号）与茅台原文措辞（'和'）"不实——撰写时未读原文，为模拟文本；v2 真实原文见 F.4：海天顿号连接恰与模拟一致，茅台"和"连接的食品安全表述未获原文支持。）
- **C. 计算型双重校验（GOLD-FOOD-003）**：仅含分子分母原值的证据支撑计算值 expected_text 为 False；quote 含计算值而 fact_text 仅含原值为 False；quote 与 fact_text 都逐字含"销售费用率（销售费用/营业收入）约 4.30%"时为 True。
- **D. 数值/单位/空格敏感性**：逐字含"净利息收益率 1.28%"（含空格）为 True；原文无空格时 expected_text 包含为 False；"1.28 %"（数值与单位间空格）可匹配；"1.28个百分点"不能匹配单位"%"；"213.60%" 与 Decimal('213.6') 相等（尾零不影响）；GOLD-FOOD-004 括号齐全为 True、缺失括号为 False；换算值须逐字出现"614.27 亿元"。
- **E. multiple 结构（GOLD-FOOD-005）**：两来源 location 匹配均为 True；仅当 quote 逐字含斜杠串（即伪造拼接文本）时 multiple 才可能满足——真实原文无法满足（F.4 实证），与 BLOCKER-1 互证。
- **F. PDF 原文核对（v2 新增，只读脚本：sha256 + pypdf 逐页提取 + 严格/去空格子串匹配 + 数值复算）**：

#### F.1 文件身份（sha256 密码学匹配）

- `data/raw/food_beverage/600519_贵州茅台_贵州茅台2025年年度报告_1225114741.pdf`（143 页）的 sha256 = `474905deeaf0f875fc0a1b097a626c0c7852c427faadc5d7fc7816cbf45ea288`，与草稿 DOC-FOOD-001 `content_hash` **精确一致**；
- `data/raw/food_beverage/603288_海天味业_海天味业2025年年度报告_1225038237.pdf`（215 页）的 sha256 = `2c7fba45257decc8edc4a0d8462c51accf146593f8c6097b26ed5ad52cf4115e`，与草稿 DOC-FOOD-004 `content_hash` **精确一致**；
- `data/raw/banking/601398_工商银行_工商银行2025年度报告_1225047240.pdf`（408 页）的 sha256 = `e2edab73032f143aad881f612382bc613c8b96b424bb197b125d64a0ef23c78b`；银行草稿 DOC-BANK-001 未提供 content_hash 字段，无法比对。
- 结论：草稿 sources 的 doc_id ↔ PDF 文件身份经哈希确认（DOC-FOOD-001=茅台、DOC-FOOD-004=海天）。

#### F.2 expected_text 逐字核对（9 项；方法限定见 F.7）

| item | 草稿 expected_text | 草稿页 | 严格命中页 | 去空格命中页 |
|---|---|---|---|---|
| FOOD-001 | 营业收入同比增长 -1.21% | p6 | 无 | 无 |
| FOOD-002 | 茅台酒毛利率 93.53% | p18 | 无 | 无 |
| FOOD-003 | 销售费用率（销售费用/营业收入）约 4.30% | p9 | 无 | 无 |
| FOOD-004 | 存货 61,427,421,796.18 元（约 614.27 亿元） | p57 | 无 | 无 |
| BANK-001 | 净利息收益率 1.28% | p16 | 无 | 无 |
| BANK-002 | 客户贷款及垫款总额同比增长 7.5% | p34 | 无 | 无 |
| BANK-003 | 不良贷款率 1.31% | p16 | 无 | [22, 85] |
| BANK-004 | 拨备覆盖率 213.60% | p16 | [87] | [22, 87] |
| BANK-005 | 资本充足率 18.76% | p102 | [101] | [22, 101, 385] |

#### F.3 销售费用率复算（数值层面与草稿一致）

- 茅台 p9 提取文本含（逐字）："销售费用7,253,499,600.685,639,300,059.4928.62管理费用"（本期 7,253,499,600.68 / 上期 5,639,300,059.49）与"营业收入168,838,102,514.79170,899,152,276.34-1.21"（本期 168,838,102,514.79 / 上期 170,899,152,276.34 / 变动 -1.21）；
- 复算：7,253,499,600.68 ÷ 168,838,102,514.79 × 100 = 4.296127% → 保留两位 4.30，与草稿 `expected_value=4.30` **一致**；
- 结论：数值正确；但 expected_text 短语形态全文 0 命中（BLOCKER-2 维持、BLOCKER-3 适用）。

#### F.4 GOLD-FOOD-005 真实原文与全文扫描

- 海天 p16（逐字）："坚持做好食品安全、稳定供应、可持续发展"；
- 茅台 p9（逐字摘引）："恪守"质量是生命之魂"信仰""构建覆盖全产业链的质量管理体系"；
- 斜杠串"食品安全/质量管理"出现页：茅台 0 页（严格与去空格均无）、海天 0 页（去空格；严格命中被去空格 0 命中逻辑蕴含）；
- 茅台全文（143 页）含"食品安全"的页：**无**；海天全文（215 页）含"质量管理"的页：**无**。

#### F.5 GOLD-FOOD-004 换算括号

- p57 提取文本含"61,427,421,796.18"：True（上下文逐字："…存货1061,427,421,796.1854,343,285,157.47…"）；
- p57 含"614.27"：False；全文含"614.27"的页：无 → 换算括号"（约 614.27 亿元）"不可能逐字出现。

#### F.6 银行各项原文上下文（逐字摘引）

- p16："净利息收益率（4）1.281.421.61""不良贷款率（7）1.311.341.36""拨备覆盖率（8）213.60214.91213.97"——多期并列表格形态，数值后无"%"紧邻；
- p34："客户贷款及垫款总额（简称"各项贷款"）305,061.14亿元，增加21,338.85亿元，增长7.5%"——措辞为"增长7.5%"；
- p102："核心一级资本充足率（%）13.5714.10一级资本充足率（%）14.9415.36资本充足率（%）18.7619.3…"——p102 为"资本充足率（%）18.76…"形态；
- 严格命中页：BANK-004 → p87、BANK-005 → p101（均与草稿页码不符，BLOCKER-4）；"18.76"全文出现页：[16, 22, 40, 101, 102, 385]。

#### F.7 方法与限定

- 提取工具：pypdf 逐页提取（茅台 143 页、海天 215 页、工行 408 页）；匹配口径：**严格** = 提取原文中的逐字子串；**去空格** = 移除全部空白字符后匹配（可覆盖空格/换行差异，不能覆盖字符或措辞差异）；
- **限定**：本组"无命中"结论以 pypdf 提取文本为限；pypdf 对复杂版面的空格插入/缺失、换行位置可能影响结果，建议 role B 以替代提取工具（pdfplumber/PyMuPDF 等）交叉复核后再作最终判定；
- 脚本只读（哈希、文本提取、子串匹配、数值复算），未修改仓库任何文件。

## 8. 测试记录（计划 Step 5）

- 命令：`pytest tests/industry -q`
- 结果：**115 passed**（0.86s）
- 环境：Python 3.12.10（便携版，仓库依赖按 `requirements-dev.txt` 安装）

## 9. 后续动作

1. v1 已随 `465b223` 提交至 `role-c-industry`；本 v2 勘误以单独提交（提交说明：`docs(gold): correct errata and add PDF source verification`）推送至同分支，不触碰 main。
2. BLOCKER-1/2/3/4 及第 6 节核对清单移交 role A（Gold 形态决策）与 role B（替代工具交叉复核、口径确认）；C 不修改 Gold JSON、不降低匹配标准。
3. Gold 草稿在 A 人工复核并签收（`status=signed`）之前不得用于评分（门禁已在实证 A 中验证）。

## 10. A 最终裁决记录（2026-08-28）

- `food_gold.json` 与 `bank_gold.json` 已基于本评审和 B/D 交叉核验结果完成填充并标记 `signed`。
- FOOD-002 采用 DOC-FOOD-001 第 18 页的“茅台酒 93.53%”，与 B 记录的“酒类 91.23%”区分产品口径。
- FOOD-005 改为两个来源均可直接核验的“食品安全”短语，来源为 DOC-FOOD-004 第 16 页和 DOC-FOOD-012 第 1 页。
- BANK-002 采用原文第 34 页的贷款增长 7.5%；BANK-003～005 采用第 16 页主要指标表，避免把目录/附注命中页误当成 Gold locator。
- FOOD-003 的 4.30% 是经原始分子分母复算的派生答案，Gold 保留计算结果；评分器的逐字 quote 限制留作 EXP-001 的已知评测限制，不通过伪造 quote 绕过。
