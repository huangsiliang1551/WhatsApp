import { useCallback, useEffect, useRef, useState } from "react";
import { t } from "./i18n";

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useAsync<T>(
  fn: () => Promise<T>,
  deps: unknown[] = [],
): AsyncState<T> & { refetch: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: null });
  const mountedRef = useRef(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const execute = useCallback(() => {
    setState({ data: null, loading: true, error: null });
    fnRef.current()
      .then((data) => {
        if (mountedRef.current) setState({ data, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (mountedRef.current) {
          setState({ data: null, loading: false, error: err instanceof Error ? err.message : t("common.error") });
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    mountedRef.current = true;
    execute();
    return () => { mountedRef.current = false; };
  }, [execute]);

  return { ...state, refetch: execute };
}
