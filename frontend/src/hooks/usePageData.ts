import { useCallback, useEffect, useRef, useState } from "react";

export interface PageDataOptions<T> {
  fetcher: () => Promise<T>;
  deps?: unknown[];
  immediate?: boolean;
  onSuccess?: (data: T) => void;
  onError?: (error: string) => void;
}

export interface PageDataResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  setData: (updater: (prev: T | null) => T | null) => void;
}

export function usePageData<T>(options: PageDataOptions<T>): PageDataResult<T> {
  const { fetcher, deps = [], immediate = true, onSuccess, onError } = options;
  const [data, setDataRaw] = useState<T | null>(null);
  const [loading, setLoading] = useState(immediate);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  // Use refs to keep load() stable across re-renders
  // This prevents `reload` reference changes when fetcher/accountId changes,
  // avoiding potential cascading re-render loops after auth state changes.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  const setData = useCallback((updater: (prev: T | null) => T | null) => {
    setDataRaw((prev) => updater(prev));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetcherRef.current();
      if (mountedRef.current) {
        setDataRaw(result);
        onSuccessRef.current?.(result);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "请求失败";
      if (mountedRef.current) {
        setError(msg);
        onErrorRef.current?.(msg);
      }
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    if (immediate) void load();
    return () => { mountedRef.current = false; };
  }, deps);

  return { data, loading, error, reload: load, setData };
}
