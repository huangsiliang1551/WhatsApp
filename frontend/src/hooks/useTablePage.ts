import { useCallback, useState } from "react";
import { usePageData } from "./usePageData";

export interface TablePageOptions<T, F extends Record<string, unknown>> {
  fetcher: (params: {
    page: number;
    size: number;
    filters: F;
    sort?: string;
  }) => Promise<{ items: T[]; total: number }>;
  defaultFilters: F;
  defaultPageSize?: number;
}

export interface TablePageResult<T, F> {
  items: T[];
  total: number;
  loading: boolean;
  error: string | null;
  filters: F;
  page: number;
  pageSize: number;
  selectedKeys: string[];
  setFilters: (f: Partial<F>) => void;
  setPage: (p: number) => void;
  setPageSize: (s: number) => void;
  setSelectedKeys: (keys: string[]) => void;
  reload: () => Promise<void>;
  clearSelection: () => void;
}

export function useTablePage<T, F extends Record<string, unknown>>(
  options: TablePageOptions<T, F>
): TablePageResult<T, F> {
  const { fetcher, defaultFilters, defaultPageSize = 20 } = options;
  const [page, setPage] = useState(1);
  const [pageSize, setPageSizeState] = useState(defaultPageSize);
  const [filters, setFiltersRaw] = useState<F>(defaultFilters);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [sort, setSort] = useState<string | undefined>(undefined);

  const { data, loading, error, reload } = usePageData({
    fetcher: () => fetcher({ page, size: pageSize, filters, sort }),
    deps: [page, pageSize, filters, sort],
  });

  const setFilters = useCallback((f: Partial<F>) => {
    setFiltersRaw((prev) => ({ ...prev, ...f }));
    setPage(1);
  }, []);

  const setPageSize = useCallback((s: number) => {
    setPageSizeState(s);
    setPage(1);
  }, []);

  const clearSelection = useCallback(() => setSelectedKeys([]), []);

  return {
    items: data?.items ?? [],
    total: data?.total ?? 0,
    loading,
    error,
    filters,
    page,
    pageSize,
    selectedKeys,
    setFilters,
    setPage,
    setPageSize,
    setSelectedKeys,
    reload,
    clearSelection,
  };
}
