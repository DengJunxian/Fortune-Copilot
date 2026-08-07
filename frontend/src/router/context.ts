import { createContext, useContext } from "react";

export interface RouterValue {
  path: string;
  navigate: (to: string) => void;
}

export const RouterContext = createContext<RouterValue | undefined>(undefined);

export function useRouter(): RouterValue {
  const value = useContext(RouterContext);
  if (!value) {
    throw new Error("Router context is missing");
  }
  return value;
}

