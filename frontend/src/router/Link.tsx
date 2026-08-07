import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from "react";
import { useRouter } from "./context";

interface AppLinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  children: ReactNode;
  to: string;
}

export function AppLink({ children, onClick, target, to, ...props }: AppLinkProps) {
  const { navigate } = useRouter();

  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event);
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey ||
      target === "_blank"
    ) {
      return;
    }
    event.preventDefault();
    navigate(to);
  }

  return (
    <a href={to} target={target} onClick={handleClick} {...props}>
      {children}
    </a>
  );
}

export function NavLink(props: AppLinkProps) {
  const { path } = useRouter();
  const isActive = path === props.to;
  return <AppLink {...props} aria-current={isActive ? "page" : undefined} />;
}

