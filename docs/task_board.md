# 任务看板

> 维护人：D  
> 更新频率：每次提交、PR、阻塞或验收后立即更新  
> 状态只使用：待开始、进行中、待审查、已完成、阻塞

## 一、当前里程碑

| 里程碑 | 截止时间 | 状态 | 验收人 |
|---|---|---|---|
| G0 公共接口和最小链路 | 8 月 24 日晚 | 待开始 | A |
| G1 四个角色模块可独立测试 | 8 月 25 日晚 | 待开始 | A/D |
| G2 食品饮料端到端 | 8 月 26 日晚 | 待开始 | A/B/C/D |
| G3 实验、迁移和红蓝测试 | 8 月 27 日晚 | 待开始 | D |
| G4 报告和演示可提交 | 8 月 29 日晚 | 待开始 | 全体 |
| G5 最终提交 | 8 月 30 日 18:00 | 待开始 | D |

## 二、任务表

| ID | 负责人 | 任务 | 允许修改 | 依赖 | 验收标准 | 截止 | 状态 | PR |
|---|---|---|---|---|---|---|---|---|
| A-001 | A | 建立公共 Schema | app/schemas、fixtures 公共示例 | 无 | 8 个结构可导入并通过测试 | 8/24 | 待开始 | |
| A-002 | A | 最小时间锁 | app/validators、tests/core | A-001 | 能拒绝 cutoff 后资料 | 8/24 | 待开始 | |
| A-003 | A | 最小编排和 CLI | app/orchestrator、app/main.py、scripts/run_case.py | A-001、B-001、C-001 | 能输出最小 report.json | 8/25 | 待开始 | |
| B-001 | B | manifest 读取和校验 | app/ingestion/manifest.py、tests/ingestion | A-001 | 缺字段和错误日期有明确问题 | 8/24 | 待开始 | |
| B-002 | B | PDF 页码提取 | app/ingestion/pdf_extractor.py、tests/ingestion | A-001 | fixture PDF 输出页码和文本 | 8/25 | 待开始 | |
| B-003 | B | 文本切分和证据定位 | app/ingestion/chunker.py、evidence_locator.py | B-002 | 输出符合 TextChunk/Evidence | 8/25 | 待开始 | |
| C-001 | C | 行业配置加载 | app/industry/loader.py、configs、tests/industry | A-001 | 两份 YAML 均通过校验 | 8/24 | 待开始 | |
| C-002 | C | 必查指标检查 | app/industry/checklist.py、tests/industry | C-001 | 缺失必查项返回问题 | 8/25 | 待开始 | |
| C-003 | C | 风险规则 | app/industry/risk_rules.py、tests/industry | C-001 | 两行业风险规则不同 | 8/25 | 待开始 | |
| D-001 | D | 评测指标 | evaluation/metrics.py、tests/evaluation | A-001 | 固定 fixture 可计算指标 | 8/24 | 待开始 | |
| D-002 | D | 红蓝测试运行器 | evaluation/red_team.py、tests/evaluation | A-002 | 覆盖四类错误输入 | 8/25 | 待开始 | |
| D-003 | D | Streamlit 页面 | app/ui、tests/evaluation | A-003 | 能读取 report.json 并展示证据 | 8/26 | 待开始 | |
| INT-001 | A | 第一次集成 B/C | integration tests | B-003、C-003 | ingestion、industry、core 全通过 | 8/25 | 待开始 | |
| INT-002 | A/D | 食品饮料完整运行 | outputs、integration tests | A-003、INT-001、D-003 | 生成 JSON、MD、日志和页面 | 8/26 | 待开始 | |
| EXP-001 | D | E0—E3 | evaluation、outputs/experiments | INT-002 | 相同输入下四组结果可复现 | 8/27 | 待开始 | |
| MIG-001 | C/A | 银行迁移 | configs、outputs | INT-002 | 不改核心编排生成银行报告 | 8/27 | 待开始 | |

## 三、阻塞记录

| 时间 | 任务 ID | 阻塞内容 | 需要谁处理 | 处理结果 |
|---|---|---|---|---|

## 四、接口变更记录

| 时间 | 发起人 | 变更字段 | 原因 | 受影响模块 | 是否重跑 |
|---|---|---|---|---|---|

## 五、每日汇报模板

~~~text
角色：
当前分支：
今天完成：
对应 commit：
测试命令与结果：
当前阻塞：
明天提交：
需要其他人提供：
~~~

## 六、验收记录

| 任务 ID | 验收人 | 测试命令 | 结果 | 备注 |
|---|---|---|---|---|


