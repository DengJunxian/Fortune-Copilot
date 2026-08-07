import { type ReactNode, useEffect, useMemo, useState } from "react";
import { ArrowLeftIcon, ArrowRightIcon, ShieldCheckIcon } from "@phosphor-icons/react";
import {
  fetchCapabilities,
  offlineCapabilities,
  type CapabilitySource,
} from "../../api/capabilities";
import { demoActor, portalDefaultRole } from "../../api/actor";
import { PortalContext } from "../../contexts/PortalContext";
import {
  DisplayPreferencesProvider,
} from "../../contexts/DisplayPreferencesProvider";
import { useDisplayPreferences } from "../../contexts/displayPreferences";
import { AppLink, NavLink } from "../../router/Link";
import { useRouter } from "../../router/context";

const portalDensity: Record<string, string> = {
  "/demo": "risk",
  "/client": "client",
  "/planning": "client",
  "/client/advanced": "client",
  "/advisor": "advisor",
  "/risk": "risk",
};

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <DisplayPreferencesProvider>
      <AppShellContent>{children}</AppShellContent>
    </DisplayPreferencesProvider>
  );
}

function AppShellContent({ children }: { children: ReactNode }) {
  const { path } = useRouter();
  const { theme, largeText, plainLanguage } = useDisplayPreferences();
  const [capabilities, setCapabilities] = useState(offlineCapabilities);
  const [source, setSource] = useState<CapabilitySource>("offline-fallback");
  const [actor, setActor] = useState(() => demoActor(portalDefaultRole(path)));

  useEffect(() => {
    setActor(demoActor(portalDefaultRole(path)));
  }, [path]);

  useEffect(() => {
    const controller = new AbortController();
    fetchCapabilities(controller.signal)
      .then((payload) => {
        setCapabilities(payload);
        setSource(payload.runtime_mode.startsWith("offline") ? "offline-fallback" : "api");
      })
      .catch(() => {
        setCapabilities(offlineCapabilities);
        setSource("offline-fallback");
      });
    return () => controller.abort();
  }, []);

  const density = useMemo(() => portalDensity[path] ?? "client", [path]);
  const internalWorkspace = ["/advisor", "/risk", "/demo", "/client/advanced"].includes(path);

  return (
    <div
      data-density={density}
      data-theme={theme}
      data-text-scale={largeText ? "large" : "default"}
      data-language-mode={plainLanguage ? "plain" : "standard"}
    >
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <header className="app-header">
        <div className="header-inner">
          <AppLink className="brand-link" to="/" aria-label="智运财富首页">
            <span className="brand-mark" aria-hidden="true">
              运
            </span>
            <span className="brand-copy">
              <strong>智运财富</strong>
              <span>普慧金融 · Fortune Copilot</span>
            </span>
          </AppLink>
          <nav className="primary-nav" aria-label="主导航">
            {internalWorkspace ? (
              <>
                <NavItem to="/planning">客户规划</NavItem>
                <NavItem to="/advisor">客户经理工作台</NavItem>
                <NavItem to="/risk">合规管理</NavItem>
              </>
            ) : (
              <>
                <NavItem to="/">首页</NavItem>
                <NavItem to="/planning">开始规划</NavItem>
              </>
            )}
          </nav>
          {internalWorkspace ? (
            <div className="staff-context"><ShieldCheckIcon size={18} weight="duotone" aria-hidden="true" /><span>内部工作区</span></div>
          ) : path === "/planning" || path === "/client" ? (
            <AppLink className="header-exit" to="/"><ArrowLeftIcon size={17} aria-hidden="true" /> 保存并返回</AppLink>
          ) : (
            <AppLink className="header-cta" to="/planning">建立我的规划 <ArrowRightIcon size={17} aria-hidden="true" /></AppLink>
          )}
        </div>
      </header>
      <PortalContext.Provider
        value={{
          capabilities,
          source,
          actor,
          setActorRole: (role) => setActor(demoActor(role)),
        }}
      >
        {children}
        <footer className="product-footer">
          <div><strong>智运财富</strong><span>普慧金融，让家庭财务现状、目标和行动安排更清楚。</span></div>
          <p>规划结果仅供财务规划参考，不构成任何金融产品的收益或本金保证。</p>
        </footer>
      </PortalContext.Provider>
    </div>
  );
}

function NavItem({ to, children }: { to: string; children: string }) {
  return (
    <NavLink className="nav-link" to={to}>
      {children}
    </NavLink>
  );
}
