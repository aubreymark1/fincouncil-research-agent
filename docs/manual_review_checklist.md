# 行业人工复核清单

> 维护人：C  
> 用途：报告进入正式发布前，由人工逐项核对行业口径与证据。  
> 本清单不替代自动校验（`checklist.py`、`risk_rules.py`、`metric_rules.py`、Critic），而是覆盖自动规则无法判断的语义问题。

## 一、通用复核项（两个行业都适用）

- [ ] 每条结论的精确数字都能在 `quote` 原文中找到，或由 `calculation` 明确推导。
- [ ] 每处引用都能通过 `locator` 人工定位到原始资料；locator 兼容两种来源：
  - PDF：`page`（页码）+ `section`（章节）+ `chunk`；
  - HTML：`section` + `chunk`（`page` 可为 `None`，**不要求页码**）。

  HTML 证据复核示例：`locator = "section 政策背景 chunk CHUNK-html-001"` 合法，不得因缺少页码而拒绝。
- [ ] `published_at` 不晚于 `cutoff_date`；日期不明或晚于截止的资料未进入正文。
- [ ] `quote` 未被改写、拼接或断章取义。
- [ ] 需多来源的结论（`evidence_requirement=multiple`）确实来自至少两个不同发布主体，且内容哈希不同，而非同一来源重复引用。
- [ ] 管理层表述（"计划/预计/目标/拟"）未被写成已完成事实。

## 二、食品饮料专项复核

### 2.1 收入、销量、价格是否混淆

- [ ] 收入（`revenue_growth`）与销量（`volume`）未互相替代：收入=销量×价格，缺一项时不得用另一项反推。
- [ ] 销量与价格未在无证据时相互替代（见 `metric_rules.py` 的 `volume_price_substitution`）。
- [ ] "量价齐升/量价背离"类表述同时有销量证据与价格证据支撑。

### 2.2 库存和动销是否有公司证据

- [ ] 财务存货（`inventory`，financial）、实物库存量（`inventory_volume`，operating，如"期末库存量/产成品库存量"）、渠道库存与动销（`channel`，operating/company_release/news）三个口径未被混用。
- [ ] 未用裸词"库存/动销"同时覆盖多个口径。
- [ ] 动销、经销商库存、渠道库存的结论有渠道层面证据，而非仅凭财务存货科目推断。
- [ ] 存货增速与收入增速的比较有对应证据（见 `inventory_growth_vs_revenue` 规则）。

### 2.3 管理层计划是否被写成事实

- [ ] "计划/预计/目标/力争/拟"等表述对应的结论是 change/analysis 或待人工确认，而非 fact。
- [ ] 未把产能规划、扩产计划、渠道目标写成已实现的事实。

### 2.4 毛利率和费用率口径是否一致

- [ ] 毛利率（`gross_margin`）变化说明了比较期间（同比/环比/较上年）。
- [ ] 毛利率与销售费用率（`sales_expense_rate`）使用同一期间的分子分母，未跨期混用。
- [ ] 毛利率变化区分了价格、成本、产品结构三个驱动，而非笼统归因。

### 2.5 食品安全信息是否适用于目标公司

- [ ] 食品安全/抽检/召回信息的主体是目标公司或其产品，而非泛行业结果。
- [ ] 行业抽检不合格未直接写成目标公司风险。
- [ ] `food_safety` 需 `multiple` 独立来源（不同发布主体 + 不同内容哈希）。

## 三、银行专项复核

### 3.1 净息差期间是否一致

- [ ] 净息差（`net_interest_margin`，含"净利息收益率/息差"等同义）变化说明了比较期间。
- [ ] 未把单季净息差与全年净息差直接比较。
- [ ] 净息差变动区分了资产端与负债端驱动因素。

### 3.2 不良率和拨备是否联合解释

- [ ] 不良率（`non_performing_loan_ratio`）、关注类贷款、拨备覆盖率（`provision_coverage`）三者联合呈现，未只看单一指标。
- [ ] 拨备覆盖率结论的证据类型为 financial（新闻/政策的拨备信息不满足 `provision_coverage` 的证据类型要求，见 `metric_rules.py` 的 `npl_provision_joint_check`）。
- [ ] 不良率上升/下降的方向与拨备覆盖率变动方向未被割裂解读。

### 3.3 资本充足率口径是否准确

- [ ] 资本充足率（`capital_adequacy`）保留了原始口径：核心一级/一级/资本充足率未混用。
- [ ] 未把不同监管口径（如并表与非并表、新规与旧规）直接对比。
- [ ] 风险加权资产变化有对应证据支撑。

### 3.4 房地产或地方债风险是否过度推断

- [ ] 房地产/地方债行业新闻未直接推导到目标银行；目标银行自身敞口（`real_estate_exposure`）证据缺失时结论应为 unresolved。
- [ ] 房地产贷款不良、开发贷、按揭贷款等敞口数据有目标银行财务证据（financial），而非仅行业新闻。
- [ ] 未把区域性风险直接等同于目标银行的资产质量恶化。

### 3.5 行业政策是否直接套到目标银行

- [ ] 监管政策（资本、拨备、流动性、房地产）区分了"行业普遍要求"与"目标银行受影响"两层。
- [ ] 未把监管红线直接写成目标银行已违规或必然受损。
- [ ] 流动性（`liquidity`）、存款结构（`deposit_structure`）等指标的口径与监管口径一致。

## 四、复核结论

- 复核通过：所有对应项打勾，且未发现需修改的结论。
- 需修改：标记出错的 `claim_id` / `evidence_id` 及原因，退回对应节点重跑。
- 记录方式：复核结果写入报告的"待人工确认"章节或 `ValidationIssue`（`human_confirmation_required=True`）。

## 五、银行迁移检查记录（MIG-001，2026-08-27）

> 执行人：C；任务边界：允许修改 `configs`、`outputs`；验收标准："不改核心编排生成银行报告"（见 task_board）。
> 本次检查**零修改核心编排与其他角色代码**：迁移脚本置于仓库外（`<工作区>/.tools/bank_migration_check.py`），只读调用 main 已合并的公共模块（ingestion/industry/schemas），全部写入落在 `outputs/bank_migration/`。

### 5.1 产出物

| 文件 | 内容 |
| --- | --- |
| `outputs/bank_migration/config_switch.json` | food_beverage ↔ banking 双配置档案及差异字段，作为"配置切换"证明 |
| `outputs/bank_migration/bank_minimal_result.json` | 最小化运行明细：资料哈希、分页统计、逐指标检索命中、双口径清单/风险检查结果 |
| `outputs/bank_migration/bank_minimal_report.md` | 六节中文简报（配置切换、资料处理、命中、必查指标、风险 Claims、局限与待办） |

### 5.2 复现方式

```powershell
# 工作区根目录下（依赖 pypdf/fpdf2 已随 requirements-dev 安装）
$env:PYTHONPATH = "<仓库根目录>"
python "<工作区>/.tools/bank_migration_check.py"
```

固定参数：manifest=`data/manifests/bank_case.csv`，chunk 上限 2000 字符，时间锁 cutoff=`2026-08-26`。两次独立运行结果完全一致（可复现）。

### 5.3 关键结论

- 资料处理：`data/raw/banking` 四份正式年报（DOC-BANK-001~004，共 1483 个 chunk，单份 289~427 页）解析成功；DOC-BANK-101（日期不明新闻稿）按契约被时间锁扣留，未进入证据池。
- 契约口径：检索得 496 条关键词命中证据，均携带 `review_status="pending"`；C 清单按契约将其判为未核验，报出 **5 条必查指标缺证据** 问题；4 条风险规则全部 unresolved（仅显示缺失的证据类型）。
- 模拟复核（仅内存中把副本标记为 verified，输出中明确标注 `simulated_verified`，不影响任何落盘证据状态）：5 条清单问题清零；`nim_pressure` 触发 1 条确定性风险 Claim，绑定 6 条净息差证据；其余 3 条因缺少 policy/news 类证据类型保持 unresolved（符合规则设计）。
- 本次复核无需新增清单条目：第一节（locator 兼容 HTML 无页码）与第三节（3.1 净息差期间一致等）已覆盖银行专项语义。

### 5.4 遗留缺口（跨角色）

1. **P0**：B 的 `locate_evidence` 固定产出 `review_status="pending"`，而 C 规则只消费 `verified`——二者之间的复核机制尚未实现，正式链路需要 A/B/C 三方约定闭环方案。
2. 真实端到端接线归 **A-008**：编排层注入 `industry_loader=load_industry_config` 后即可完成银行迁移，行业侧代码无需再改。
