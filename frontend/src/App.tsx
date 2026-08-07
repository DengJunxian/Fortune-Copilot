import { lazy, Suspense } from "react";
import { AppShell } from "./components/layout/AppShell";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { RouterProvider } from "./router/RouterProvider";
import { useRouter } from "./router/context";

const AdvisorPage = lazy(() =>
  import("./pages/AdvisorPage").then((module) => ({ default: module.AdvisorPage })),
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
const RiskPage = lazy(() =>
  import("./pages/RiskPage").then((module) => ({ default: module.RiskPage })),
);

function RouteView() {
  const { path } = useRouter();
  let page;
  switch (path) {
    case "/":
      page = <HomePage />;
      break;
    case "/client":
    case "/planning":
      page = <PlanningPage />;
      break;
    case "/client/advanced":
      page = <ClientPage />;
      break;
    case "/demo":
      page = <DemoPage />;
      break;
    case "/advisor":
      page = <AdvisorPage />;
      break;
    case "/risk":
      page = <RiskPage />;
      break;
    default:
      page = <NotFoundPage />;
  }

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
