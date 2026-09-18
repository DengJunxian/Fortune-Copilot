import type { ReactNode } from "react";

interface DashboardCardProps {
  children: ReactNode;
  className?: string;
  eyebrow: string;
  title: string;
  action?: ReactNode;
}

export function DashboardCard({
  action,
  children,
  className = "",
  eyebrow,
  title,
}: DashboardCardProps) {
  return (
    <section className={`wealth-dashboard-card ${className}`.trim()}>
      <header>
        <div><span>{eyebrow}</span><h2>{title}</h2></div>
        {action}
      </header>
      {children}
    </section>
  );
}

export function DashboardUnavailable({ children }: { children: ReactNode }) {
  return <p className="dashboard-unavailable">{children}</p>;
}
