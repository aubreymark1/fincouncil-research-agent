import type { Claim, NarrativeBlock, NarrativeSegment, ResearchReport, ValidationIssue } from "./types";

export interface ReadableSection {
  section: string;
  segments: ReadableSegment[];
}

export interface ReadableSegment {
  segment_id: string;
  text: string;
  evidence_ids: string[];
  claim_type: NarrativeSegment["claim_type"];
  status: NarrativeSegment["status"];
}

export interface PresentedValidationIssue {
  title: string;
  detail: string;
  action: string;
}

function claimToSection(claim: Claim, section: string): ReadableSection {
  return {
    section,
    segments: [{
      segment_id: `SEG-${claim.claim_id.replace(/^CL-/, "")}`,
      text: claim.text,
      evidence_ids: claim.evidence_ids,
      claim_type: claim.claim_type,
      status: claim.status === "pass" ? "pass" : "review",
    }],
  };
}

function normalizeBlock(block: NarrativeBlock, blockIndex: number): ReadableSection | null {
  const segments = block.segments?.length
    ? block.segments.map((segment) => ({
        segment_id: segment.segment_id,
        text: segment.text,
        evidence_ids: segment.evidence_ids ?? [],
        claim_type: segment.claim_type,
        status: segment.status,
      }))
    : block.text
      ? [{
          segment_id: `SEG-LEGACY-${blockIndex + 1}`,
          text: block.text,
          evidence_ids: block.evidence_ids ?? [],
          claim_type: "analysis" as const,
          status: "pass" as const,
        }]
      : [];
  return segments.length > 0 ? { section: block.section, segments } : null;
}

export function getReadableSections(
  report: Pick<ResearchReport, "narrative" | "claims" | "risks">,
): ReadableSection[] {
  const narrative = report.narrative ?? [];
  if (narrative.length > 0) {
    return narrative.map(normalizeBlock).filter((item): item is ReadableSection => Boolean(item));
  }

  return [
    ...report.claims
      .filter((claim) => claim.status === "pass")
      .map((claim) => claimToSection(claim, "正式结论")),
    ...report.risks
      .filter((claim) => claim.status === "pass")
      .map((claim) => claimToSection(claim, "正式风险")),
  ];
}

export function citationIdsForSegment(segment: Pick<ReadableSegment, "evidence_ids">): string[] {
  return segment.evidence_ids;
}

export function presentValidationIssue(
  issue: Pick<ValidationIssue, "issue_type" | "message" | "severity">,
): PresentedValidationIssue {
  switch (issue.issue_type) {
    case "required_metric_missing":
      return {
        title: "核心指标缺失",
        detail: issue.message,
        action: "回到证据索引，补充该指标的可核验来源。",
      };
    case "missing_published_at":
      return {
        title: "时间锁待核验",
        detail: issue.message,
        action: "确认原始资料发布日期，必要时重新运行。",
      };
    case "npl_provision_joint_incomplete":
    case "nim_missing_period":
      return {
        title: "指标口径待确认",
        detail: issue.message,
        action: "补充比较期间或联合口径后，再将结论纳入正式研究。",
      };
    case "evidence_verification":
      return {
        title: "证据状态提示",
        detail: issue.message,
        action: "查看证据索引，确认来源状态与适用范围。",
      };
    default:
      return {
        title: issue.severity === "error" || issue.severity === "critical" ? "需要处理" : "校验提示",
        detail: issue.message,
        action: "打开对应证据或重新运行，确认这条校验项。",
      };
  }
}
