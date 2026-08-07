import type { ReactNode } from "react";

interface StatusBadgeProps {
  children: ReactNode;
  tone: "success" | "warning" | "info" | "danger";
}

export function StatusBadge({ children, tone }: StatusBadgeProps) {
  return (
    <span className="status-badge" data-tone={tone}>
      {children}
    </span>
  );
}

