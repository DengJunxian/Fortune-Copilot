export type ActorRole = "client" | "advisor" | "compliance" | "admin";

export interface DemoActor {
  id: string;
  role: ActorRole;
  label: string;
}

const actorLabels: Record<ActorRole, string> = {
  client: "客户 · 李先生",
  advisor: "客户经理 · 王顾问",
  compliance: "合规审核员 · 陈审核",
  admin: "演示管理员",
};

export function demoActor(role: ActorRole): DemoActor {
  return {
    id: `demo-${role}`,
    role,
    label: actorLabels[role],
  };
}

export function actorHeaders(actor: DemoActor): Record<string, string> {
  return {
    "X-Actor-ID": actor.id,
    "X-Actor-Role": actor.role,
  };
}

export function portalDefaultRole(path: string): ActorRole {
  if (path === "/demo") return "admin";
  if (path === "/advisor") return "advisor";
  if (path === "/risk") return "compliance";
  return "client";
}
