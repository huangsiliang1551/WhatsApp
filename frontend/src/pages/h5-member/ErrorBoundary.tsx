import { Component, type ErrorInfo, type ReactNode } from "react";
import { t } from "./i18n";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
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
    console.error("[H5 ErrorBoundary]", error, errorInfo);
    this.reportError(error, errorInfo).catch(() => {});
    this.props.onError?.(error, errorInfo);
  }

  async reportError(error: Error, errorInfo: ErrorInfo): Promise<void> {
    try {
      const { api } = await import("../../services/api");
      await api.post("/api/h5/client-errors", {
        message: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
        url: window.location.href,
        userAgent: navigator.userAgent,
      });
    } catch {
      // Silently fail
    }
  }

  handleRefresh = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <section className="h5-card-stack h5-member-auth-shell h5-error-boundary-shell">
          <div className="h5-empty-state">
            <div className="h5-empty-icon">!</div>
            <strong className="h5-empty-title">{t("errorBoundary.title")}</strong>
            <p className="h5-empty-desc">{t("errorBoundary.description")}</p>
            <button
              className="h5-primary-button h5-error-boundary-refresh"
              onClick={this.handleRefresh}
            >
              {t("errorBoundary.refresh")}
            </button>
          </div>
        </section>
      );
    }
    return this.props.children;
  }
}
