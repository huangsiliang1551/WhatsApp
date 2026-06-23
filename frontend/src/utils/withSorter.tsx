type LooseColumn = {
  dataIndex?: string | string[];
  sorter?: unknown;
  children?: unknown;
  [key: string]: unknown;
};

export function withSorter<T = any>(columns: any): any {
  const safeColumns = (columns ?? []) as LooseColumn[];

  return safeColumns.map((column) => {
    if (!column.dataIndex || column.sorter || column.children) {
      return column;
    }

    const key = Array.isArray(column.dataIndex) ? column.dataIndex.join(".") : column.dataIndex;

    return {
      ...column,
      sorter: (left: any, right: any): number => {
        const leftValue = getNestedValue(left, key);
        const rightValue = getNestedValue(right, key);

        if (leftValue == null && rightValue == null) return 0;
        if (leftValue == null) return 1;
        if (rightValue == null) return -1;
        if (typeof leftValue === "string" && typeof rightValue === "string") {
          return leftValue.localeCompare(rightValue);
        }
        if (typeof leftValue === "number" && typeof rightValue === "number") {
          return leftValue - rightValue;
        }
        if (typeof leftValue === "boolean" && typeof rightValue === "boolean") {
          return Number(leftValue) - Number(rightValue);
        }
        return 0;
      },
      sortDirections: ["ascend", "descend"] as const,
    };
  });
}

function getNestedValue(obj: unknown, key: string): unknown {
  if (obj == null) return undefined;
  if (!key.includes(".")) {
    return (obj as Record<string, unknown>)[key];
  }
  return key.split(".").reduce<unknown>((current, part) => {
    if (current == null) return undefined;
    return (current as Record<string, unknown>)[part];
  }, obj);
}
