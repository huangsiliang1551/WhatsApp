let activeAudio: HTMLAudioElement | null = null;

const ALERT_TONE_DATA_URI =
  "data:audio/wav;base64,UklGRlQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YTAAAAABf39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/";

export function playTaskMonitorAlertSound(): void {
  try {
    if (activeAudio) {
      activeAudio.pause();
      activeAudio.currentTime = 0;
    }
    activeAudio = new Audio(ALERT_TONE_DATA_URI);
    void activeAudio.play().catch(() => undefined);
  } catch {
    // Ignore browsers/environments without audio playback support.
  }
}
