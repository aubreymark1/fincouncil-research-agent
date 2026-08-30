import assert from "node:assert/strict";
import { getReadableSections, presentValidationIssue } from "../src/reportUtils.ts";

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

assert.deepEqual(getReadableSections(report), report.narrative);

assert.deepEqual(
  presentValidationIssue({
    severity: "error",
    issue_type: "required_metric_missing",
    message: "E202 required metric net_interest_margin (净息差) has no Claim.",
  }),
  {
    title: "核心指标缺失",
    detail: "E202 required metric net_interest_margin (净息差) has no Claim.",
    action: "回到证据索引，补充该指标的可核验来源。",
  },
);

console.log("reportUtils behavior tests passed");
