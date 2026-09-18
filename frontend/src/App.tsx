import { lazy, Suspense } from "react";
import { AppShell } from "./components/layout/AppShell";
import { clientProfileFeatureEnabled } from "./api/clientProfile";
import { cfsFeatureEnabled } from "./api/cfs";
import { familyEnterpriseFeatureEnabled } from "./api/familyEnterprise";
import { liabilityFeatureEnabled } from "./api/liability";
import { persistentTwinFeatureEnabled } from "./api/persistentTwin";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { RouterProvider } from "./router/RouterProvider";
import { useRouter } from "./router/context";

const AdvisorPage = lazy(() =>
  import("./pages/AdvisorPage").then((module) => ({ default: module.AdvisorPage })),
);
const AdvisorActionCenterPage = lazy(() =>
  import("./pages/AdvisorActionCenterPage").then((module) => ({
    default: module.AdvisorActionCenterPage,
  })),
);
const ClientPage = lazy(() =>
  import("./pages/ClientPage").then((module) => ({ default: module.ClientPage })),
);
const PlanningPage = lazy(() =>
  import("./pages/PlanningPage").then((module) => ({ default: module.PlanningPage })),
);
const DemoPage = lazy(() =>
  import("./pages/DemoPage").then((module) => ({ default: module.DemoPage })),
);
const CompetitionPage = lazy(() =>
  import("./pages/CompetitionPage").then((module) => ({ default: module.CompetitionPage })),
);
const RiskPage = lazy(() =>
  import("./pages/RiskPage").then((module) => ({ default: module.RiskPage })),
);
const WealthProfilePage = lazy(() =>
  import("./pages/WealthProfilePage").then((module) => ({
    default: module.WealthProfilePage,
  })),
);
const WealthDashboardPage = lazy(() =>
  import("./pages/WealthDashboardPage").then((module) => ({
    default: module.WealthDashboardPage,
  })),
);
const WealthGoalsPage = lazy(() =>
  import("./pages/WealthGoalsPage").then((module) => ({
    default: module.WealthGoalsPage,
  })),
);
const WealthTwinPage = lazy(() =>
  import("./pages/WealthTwinPage").then((module) => ({
    default: module.WealthTwinPage,
  })),
);
const FamilyEnterprisePage = lazy(() =>
  import("./pages/FamilyEnterprisePage").then((module) => ({
    default: module.FamilyEnterprisePage,
  })),
);
const WealthCFSPage = lazy(() =>
  import("./pages/WealthCFSPage").then((module) => ({
    default: module.WealthCFSPage,
  })),
);
const RetirementPlanPage = lazy(() =>
  import("./pages/RetirementPlanPage").then((module) => ({
    default: module.RetirementPlanPage,
  })),
);
const GlobalExposurePage = lazy(() =>
  import("./pages/GlobalExposurePage").then((module) => ({
    default: module.GlobalExposurePage,
  })),
);
const FamilyNeedsPage = lazy(() =>
  import("./pages/FamilyNeedsPage").then((module) => ({
    default: module.FamilyNeedsPage,
  })),
);
const WealthHistoryPage = lazy(() =>
  import("./pages/WealthHistoryPage").then((module) => ({
    default: module.WealthHistoryPage,
  })),
);

interface RouteDefinition {
  paths: readonly string[];
  render: () => React.ReactNode;
}

const routeRegistry: readonly RouteDefinition[] = [
  { paths: ["/"], render: () => <HomePage /> },
  { paths: ["/client", "/planning"], render: () => <PlanningPage /> },
  { paths: ["/client/advanced"], render: () => <ClientPage /> },
  { paths: ["/wealth"], render: () => <WealthDashboardPage /> },
  { paths: ["/wealth/profile"], render: () => clientProfileFeatureEnabled ? <WealthProfilePage /> : <NotFoundPage /> },
  { paths: ["/wealth/goals"], render: () => liabilityFeatureEnabled ? <WealthGoalsPage /> : <NotFoundPage /> },
  { paths: ["/wealth/twin"], render: () => persistentTwinFeatureEnabled ? <WealthTwinPage /> : <NotFoundPage /> },
  { paths: ["/wealth/family-enterprise"], render: () => familyEnterpriseFeatureEnabled ? <FamilyEnterprisePage /> : <NotFoundPage /> },
  { paths: ["/wealth/cfs"], render: () => cfsFeatureEnabled ? <WealthCFSPage /> : <NotFoundPage /> },
  { paths: ["/wealth/retirement"], render: () => cfsFeatureEnabled ? <RetirementPlanPage /> : <NotFoundPage /> },
  { paths: ["/wealth/global"], render: () => cfsFeatureEnabled ? <GlobalExposurePage /> : <NotFoundPage /> },
  { paths: ["/wealth/family"], render: () => cfsFeatureEnabled ? <FamilyNeedsPage /> : <NotFoundPage /> },
  { paths: ["/wealth/history"], render: () => persistentTwinFeatureEnabled ? <WealthHistoryPage /> : <NotFoundPage /> },
  { paths: ["/demo"], render: () => <DemoPage /> },
  { paths: ["/competition"], render: () => <CompetitionPage /> },
  { paths: ["/advisor"], render: () => <AdvisorPage /> },
  { paths: ["/advisor/actions"], render: () => <AdvisorActionCenterPage /> },
  { paths: ["/risk"], render: () => <RiskPage /> },
];

function RouteView() {
  const { path } = useRouter();
  const route = routeRegistry.find((candidate) => candidate.paths.includes(path));
  const page = route?.render() ?? <NotFoundPage />;

  return (
    <AppShell>
      <Suspense
        fallback={(
          <main className="page-shell" id="main-content">
            <div className="analysis-state" role="status" aria-live="polite">
              <span className="loading-mark" aria-hidden="true" />
              <div>
                <h1>正在打开家庭财富规划</h1>
                <p>请稍候，客户资料与财务报表正在准备。</p>
              </div>
            </div>
          </main>
        )}
      >
        {page}
      </Suspense>
    </AppShell>
  );
}

export function AppRoutes({ initialPath }: { initialPath?: string }) {
  return (
    <RouterProvider initialPath={initialPath}>
      <RouteView />
    </RouterProvider>
  );
}

export default function App() {
  return <AppRoutes />;
}
