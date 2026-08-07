import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "../ui/Button";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Fortune Copilot UI error", { name: error.name, componentStack: info.componentStack });
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="error-fallback" id="main-content">
          <h1>页面暂时无法显示</h1>
          <p>本地数据不会因此上传。请刷新页面，或返回三端入口重新开始。</p>
          <Button type="button" onClick={() => window.location.assign("/")}>
            返回入口
          </Button>
        </main>
      );
    }

    return this.props.children;
  }
}

