import { createContext, useContext } from "react";
import type { CapabilitiesResponse, CapabilitySource } from "../api/capabilities";
import type { ActorRole, DemoActor } from "../api/actor";

export interface PortalContextValue {
  capabilities: CapabilitiesResponse;
  source: CapabilitySource;
  actor: DemoActor;
  setActorRole: (role: ActorRole) => void;
}

export const PortalContext = createContext<PortalContextValue | undefined>(undefined);

export function usePortalContext(): PortalContextValue {
  const value = useContext(PortalContext);
  if (!value) {
    throw new Error("Portal context is missing");
  }
  return value;
}
