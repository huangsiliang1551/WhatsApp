import { useCallback, useEffect, useState } from "react";
import * as api from "../../../services/api";
import { useAppStore } from "../../../stores/appStore";
import type { ConversationNote } from "../../../services/api";

export interface UseConversationNotesReturn {
  notes: ConversationNote[];
  loading: boolean;
  error: string | null;
  addNote: (content: string) => Promise<void>;
  updateNote: (noteId: string, content: string) => Promise<void>;
  removeNote: (noteId: string) => Promise<void>;
  refresh: () => Promise<void>;
}

export function useConversationNotes(
  accountId: string,
  conversationId: string
): UseConversationNotesReturn {
  const [notes, setNotes] = useState<ConversationNote[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const consoleAgentName = useAppStore((s) => s.consoleAgentName);

  const load = useCallback(async () => {
    if (!accountId || !conversationId) {
      setNotes([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await api.listConversationNotes(accountId, conversationId);
      setNotes(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载备注失败");
    } finally {
      setLoading(false);
    }
  }, [accountId, conversationId]);

  useEffect(() => {
    void load();
  }, [load]);

  const addNote = useCallback(
    async (content: string) => {
      if (!accountId || !conversationId || !content.trim()) return;
      setError(null);
      try {
        const note = await api.createConversationNote(
          accountId,
          conversationId,
          content.trim(),
          consoleAgentName
        );
        setNotes((prev) => [note, ...prev]);
      } catch (err) {
        setError(err instanceof Error ? err.message : "添加备注失败");
      }
    },
    [accountId, conversationId, consoleAgentName]
  );

  const removeNote = useCallback(
    async (noteId: string) => {
      if (!accountId || !conversationId) return;
      setError(null);
      try {
        await api.deleteConversationNote(accountId, conversationId, noteId);
        setNotes((prev) => prev.filter((n) => n.id !== noteId));
      } catch (err) {
        setError(err instanceof Error ? err.message : "删除备注失败");
      }
    },
    [accountId, conversationId]
  );

  const updateNote = useCallback(
    async (noteId: string, content: string) => {
      if (!accountId || !conversationId || !content.trim()) return;
      setError(null);
      try {
        const updated = await api.updateConversationNote(
          accountId,
          conversationId,
          noteId,
          content.trim()
        );
        setNotes((prev) => prev.map((n) => (n.id === noteId ? updated : n)));
      } catch (err) {
        setError(err instanceof Error ? err.message : "修改备注失败");
      }
    },
    [accountId, conversationId]
  );

  return { notes, loading, error, addNote, updateNote, removeNote, refresh: load };
}
