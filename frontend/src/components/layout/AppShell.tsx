import { type ReactNode, useEffect, useMemo, useState } from "react";
import { ArrowLeftIcon, ArrowRightIcon, ShieldCheckIcon } from "@phosphor-icons/react";
import {
  fetchCapabilities,
  offlineCapabilities,
  type CapabilitySource,
} from "../../api/capabilities";
import { demoActor, portalDefaultRole } from "../../api/actor";
import { cfsFeatureEnabled } from "../../api/cfs";
import { liabilityFeatureEnabled } from "../../api/liability";
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
  "/wealth": "client",
  "/wealth/profile": "client",
  "/wealth/goals": "client",
  "/wealth/twin": "client",
  "/wealth/family-enterprise": "client",
  "/wealth/cfs": "client",
  "/wealth/retirement": "client",
  "/wealth/global": "client",
  "/wealth/family": "client",
  "/wealth/history": "client",
  "/advisor": "advisor",
  "/advisor/actions": "advisor",
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
  const internalWorkspace = ["/advisor", "/advisor/actions", "/risk", "/demo", "/client/advanced"].includes(path);

  return (
    <div
      className={path === "/" ? "app-root app-root-home" : "app-root"}
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
              <span>中国家庭财富管理系统</span>
            </span>
          </AppLink>
          <nav className="primary-nav" aria-label="主导航">
            {internalWorkspace ? (
              <>
                <NavItem to="/planning">家庭规划</NavItem>
                <NavItem to="/advisor/actions">顾问行动</NavItem>
                <NavItem to="/advisor">客户管理</NavItem>
                <NavItem to="/risk">合规审查</NavItem>
              </>
            ) : (
              <>
                <NavItem to="/">首页</NavItem>
                <NavItem to="/planning">家庭建档</NavItem>
                <NavItem to="/wealth">财富总览</NavItem>
                {liabilityFeatureEnabled ? (
                  <NavItem to="/wealth/goals">目标责任</NavItem>
                ) : null}
                {cfsFeatureEnabled ? <NavItem to="/wealth/cfs">综合方案</NavItem> : null}
              </>
            )}
          </nav>
          {internalWorkspace ? (
            <div className="staff-context"><ShieldCheckIcon size={18} weight="duotone" aria-hidden="true" /><span>内部工作区</span></div>
          ) : path === "/planning" || path === "/client" || path === "/wealth" || path.startsWith("/wealth/") ? (
            <AppLink className="header-exit" to="/"><ArrowLeftIcon size={17} aria-hidden="true" /> 保存并返回</AppLink>
          ) : (
            <AppLink className="header-cta" to="/planning">建立家庭规划 <ArrowRightIcon size={17} aria-hidden="true" /></AppLink>
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
          <div><strong>智运财富</strong><span>面向中国家庭的财富管理与规划服务。</span></div>
          <p>规划结果用于辅助家庭决策，不构成投资建议，也不承诺任何金融产品的本金或收益。</p>
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
