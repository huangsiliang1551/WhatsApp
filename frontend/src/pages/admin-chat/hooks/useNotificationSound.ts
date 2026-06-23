import { useCallback, useState } from "react";

const STORAGE_KEY = "fx_sound_enabled";

export function useNotificationSound() {
  const [enabled, setEnabled] = useState<boolean>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) !== "false";
    } catch {
      return true;
    }
  });

  const play = useCallback(() => {
    if (!enabled) return;
    try {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioCtx();
      const oscillator = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();
      oscillator.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      oscillator.frequency.value = 880;
      oscillator.type = "sine";
      gainNode.gain.setValueAtTime(0.25, audioCtx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.12);
      oscillator.start(audioCtx.currentTime);
      oscillator.stop(audioCtx.currentTime + 0.12);
    } catch {
      // Audio API not available
    }
  }, [enabled]);

  const toggleEnabled = useCallback((v: boolean) => {
    setEnabled(v);
    try {
      localStorage.setItem(STORAGE_KEY, String(v));
    } catch { /* ignore */ }
  }, []);

  return { play, enabled, setEnabled: toggleEnabled };
}
