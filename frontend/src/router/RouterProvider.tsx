import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { RouterContext } from "./context";

interface RouterProviderProps {
  children: ReactNode;
  initialPath?: string;
}

function normalizePath(path: string): string {
  const normalized = path.split(/[?#]/, 1)[0] || "/";
  return normalized.length > 1 ? normalized.replace(/\/$/, "") : normalized;
}

export function RouterProvider({ children, initialPath }: RouterProviderProps) {
  const [path, setPath] = useState(() => normalizePath(initialPath ?? window.location.pathname));

  useEffect(() => {
    if (initialPath !== undefined) {
      return undefined;
    }
    const handlePopState = () => setPath(normalizePath(window.location.pathname));
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [initialPath]);

  const navigate = useCallback(
    (to: string) => {
      const nextPath = normalizePath(to);
      if (initialPath === undefined) {
        window.history.pushState({}, "", to);
      }
      if (nextPath !== path) setPath(nextPath);
      window.scrollTo({ top: 0, behavior: "auto" });
    },
    [initialPath, path],
  );

  const value = useMemo(() => ({ path, navigate }), [navigate, path]);
  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}
