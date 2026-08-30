import assert from "node:assert/strict";
import { citationIdsForSegment, getReadableSections, presentValidationIssue } from "../src/reportUtils.ts";

const report = {
  narrative: [
    {
      section: "核心判断",
      text: "净息差仍承压。",
      evidence_ids: ["EV-001"],
    },
    {
      section: "风险与待确认",
      text: "房地产敞口需要进一步核验。",
      evidence_ids: ["EV-002"],
    },
  ],
  claims: [],
  risks: [],
  unresolved_items: [],
};

assert.deepEqual(getReadableSections(report)[0].segments[0].evidence_ids, ["EV-001"]);
assert.equal(getReadableSections(report)[1].segments[0].text, "房地产敞口需要进一步核验。");

assert.deepEqual(
  presentValidationIssue({
    severity: "error",
    issue_type: "required_metric_missing",
    message: "E202 required metric net_interest_margin (净息差) has no Claim.",
  }),
  {
    category: "尚未覆盖",
    title: "核心指标缺失",
    detail: "本次运行没有形成“净息差”的正式结论，证据不足或口径不完整。",
    technical_detail: "E202 required metric net_interest_margin (净息差) has no Claim.",
    action: "回到证据索引，补充该指标的可核验来源。",
    tone: "warning",
  },
);

assert.deepEqual(
  presentValidationIssue({
    severity: "critical",
    issue_type: "published_after_cutoff",
    message: "E103 DOC-FOOD-104 was published after cutoff and was rejected by the time lock.",
  }),
  {
    category: "已自动处理",
    title: "截止日后的资料已排除",
    detail: "这份资料晚于研究截止日，时间锁已自动将它排除。",
    technical_detail: "E103 DOC-FOOD-104 was published after cutoff and was rejected by the time lock.",
    action: null,
    tone: "success",
  },
);

console.log("reportUtils behavior tests passed");

const segmented = {
  narrative: [{
    section: "核心判断",
    segments: [
      { segment_id: "SEG-1", text: "句子 A。", evidence_ids: ["EV-001"], claim_type: "fact", status: "pass" },
      { segment_id: "SEG-2", text: "句子 B。", evidence_ids: ["EV-002", "EV-003"], claim_type: "analysis", status: "pass" },
    ],
  }],
  claims: [],
  risks: [],
};
const sections = getReadableSections(segmented);
assert.deepEqual(citationIdsForSegment(sections[0].segments[0]), ["EV-001"]);
assert.deepEqual(citationIdsForSegment(sections[0].segments[1]), ["EV-002", "EV-003"]);
