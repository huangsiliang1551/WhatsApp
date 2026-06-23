import { useCallback, useRef } from "react";

import { Modal } from "antd";
import type { ModalFuncProps } from "antd";

interface ConfirmActionOptions {
  title: string;
  content: string;
  danger?: boolean;
  onConfirm: () => void | Promise<void>;
  okText?: string;
  cancelText?: string;
}

interface UseConfirmActionReturn {
  confirmAction: (options: ConfirmActionOptions) => void;
  /**
   * Execute an action with loading/disabled state tracking.
   * Returns the wrapped function and loading state setter.
   */
  withLock: <T extends (...args: unknown[]) => Promise<void>>(fn: T) => T;
}

/**
 * Hook that provides:
 * 1. confirmAction - Show a confirmation modal before executing dangerous operations
 * 2. withLock - Wrap an async function to prevent double-click/duplicate submission
 */
export function useConfirmAction(): UseConfirmActionReturn {
  const lockRef = useRef(false);

  const confirmAction = useCallback((options: ConfirmActionOptions): void => {
    const config: ModalFuncProps = {
      title: options.title,
      content: options.content,
      okText: options.okText ?? "确定",
      cancelText: options.cancelText ?? "取消",
      okButtonProps: options.danger ? { danger: true } : undefined,
      onOk: async () => {
        try {
          await options.onConfirm();
        } catch (err) {
          console.error("[useConfirmAction] action failed:", err);
        }
      },
    };
    Modal.confirm(config);
  }, []);

  const withLock = useCallback(<T extends (...args: unknown[]) => Promise<void>>(fn: T): T => {
    const wrapped = (async (...args: unknown[]) => {
      if (lockRef.current) return;
      lockRef.current = true;
      try {
        await fn(...args);
      } finally {
        lockRef.current = false;
      }
    }) as T;
    return wrapped;
  }, []);

  return { confirmAction, withLock };
}
