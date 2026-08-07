import type { ButtonHTMLAttributes, ReactNode } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: "primary" | "secondary" | "danger";
  loading?: boolean;
}

export function Button({
  children,
  variant = "primary",
  loading = false,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className="button"
      data-variant={variant}
      disabled={disabled || loading}
      aria-busy={loading}
      {...props}
    >
      {loading ? "处理中" : children}
    </button>
  );
}
