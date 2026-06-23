import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button, Result } from "antd";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("[ErrorBoundary] Caught an error:", error, errorInfo);

    // Optional: report client-side errors to the server
    // Wrapped in try/catch to prevent cascading failures
    try {
      fetch("/api/client-errors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: error.message,
          stack: error.stack,
          componentStack: errorInfo.componentStack,
        }),
      }).catch(() => {
        // Silently ignore network errors
      });
    } catch {
      // Silently ignore any unexpected errors during reporting
    }
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Result
          status="error"
          title="页面出现异常"
          subTitle={this.state.error?.message || "未知错误"}
          extra={
            <Button type="primary" onClick={this.handleRetry}>
              重试
            </Button>
          }
        />
      );
    }

    return this.props.children;
  }
}
