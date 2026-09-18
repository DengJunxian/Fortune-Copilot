import { AdvisorActionCenter } from "../components/advisor/AdvisorActionCenter";
import { AppLink } from "../router/Link";

export function AdvisorActionCenterPage() {
  return (
    <main className="page-shell advisor-actions-page" id="main-content">
      <header className="page-intro advisor-actions-intro">
        <p className="page-kicker">顾问端 · 持续服务</p>
        <h1>客户行动中心</h1>
        <p>把家庭变化、到期责任、行为信号和专业转介排进同一队列，并保留每一步证据。</p>
        <AppLink to="/advisor">返回完整客户经理工作台</AppLink>
      </header>
      <AdvisorActionCenter />
    </main>
  );
}
