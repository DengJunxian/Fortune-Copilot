import { AppLink } from "../router/Link";

export function NotFoundPage() {
  return (
    <main className="page-shell not-found" id="main-content">
      <p className="page-kicker">页面不存在</p>
      <h1>没有找到这个入口</h1>
      <p>请返回三端入口，或检查地址是否完整。</p>
      <AppLink to="/">返回首页</AppLink>
    </main>
  );
}
