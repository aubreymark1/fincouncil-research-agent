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
  category: "已自动处理" | "需要人工确认" | "尚未覆盖";
  title: string;
  detail: string;
  technical_detail: string;
  action: string | null;
  tone: "success" | "info" | "warning" | "error";
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
      {
        const metric = issue.message.match(/\(([^)]+)\)/)?.[1] ?? "核心指标";
        return {
        category: "尚未覆盖",
        title: "核心指标缺失",
        detail: `本次运行没有形成“${metric}”的正式结论，证据不足或口径不完整。`,
        technical_detail: issue.message,
        action: "回到证据索引，补充该指标的可核验来源。",
        tone: "warning",
        };
      }
    case "missing_published_at":
      return {
        category: "需要人工确认",
        title: "资料日期待确认",
        detail: "资料清单中有一份资料缺少发布日期，时间锁无法自动确认。",
        technical_detail: issue.message,
        action: "确认原始资料发布日期，必要时重新运行。",
        tone: "warning",
      };
    case "published_after_cutoff":
      return {
        category: "已自动处理",
        title: "截止日后的资料已排除",
        detail: "这份资料晚于研究截止日，时间锁已自动将它排除。",
        technical_detail: issue.message,
        action: null,
        tone: "success",
      };
    case "npl_provision_joint_incomplete":
    case "nim_missing_period":
      return {
        category: "需要人工确认",
        title: "指标口径待确认",
        detail: "这条指标证据的比较期间或联合口径不完整，暂不进入正式结论。",
        technical_detail: issue.message,
        action: "补充比较期间或联合口径后，再将结论纳入正式研究。",
        tone: "warning",
      };
    case "evidence_verification":
      {
        const hasUnverified = /\d+\s+remain unverified/i.test(issue.message);
        return {
          category: hasUnverified ? "需要人工确认" : "已自动处理",
          title: hasUnverified ? "部分证据待复核" : "证据已完成校验",
          detail: hasUnverified ? "部分证据尚未完成来源状态核验。" : "证据来源已按当前策略完成自动校验。",
          technical_detail: issue.message,
          action: hasUnverified ? "查看证据索引，确认来源状态与适用范围。" : null,
          tone: hasUnverified ? "warning" : "success",
        };
      }
    default:
      return {
        category: issue.severity === "error" || issue.severity === "critical" ? "需要人工确认" : "已自动处理",
        title: issue.severity === "error" || issue.severity === "critical" ? "需要处理" : "校验提示",
        detail: "这条校验项需要结合来源和研究口径进一步确认。",
        technical_detail: issue.message,
        action: issue.severity === "error" || issue.severity === "critical" ? "打开对应证据或重新运行，确认这条校验项。" : null,
        tone: issue.severity === "error" || issue.severity === "critical" ? "error" : "info",
      };
  }
}
