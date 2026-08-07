import type { PlanWorkflowAction, PlanWorkflowState } from "../../api/reviewWorkflow";

export const workflowStateLabels: Record<PlanWorkflowState, string> = {
  draft: "草稿",
  calculated: "已计算",
  suitability_checked: "已做适当性检查",
  advisor_reviewed: "客户经理已复核",
  compliance_reviewed: "合规已复核",
  customer_confirmed: "客户已确认",
  active: "已生效",
  superseded: "已被替代",
};

export const workflowActionLabels: Record<PlanWorkflowAction, string> = {
  create: "创建草稿",
  calculate: "运行确定性计算",
  suitability_check: "执行三道闸门",
  advisor_review: "客户经理复核",
  revise_advice: "修改建议",
  edit_communication: "保存沟通稿",
  submit_compliance: "提交合规",
  compliance_approve: "合规通过",
  compliance_return: "合规退回",
  require_human_review: "要求人工复核",
  customer_confirm: "客户确认",
  activate: "激活方案",
  supersede: "替代旧方案",
};

export function workflowTone(state: PlanWorkflowState): "success" | "warning" | "info" | "danger" {
  if (state === "active") return "success";
  if (state === "superseded") return "warning";
  if (state === "draft") return "info";
  return "warning";
}
