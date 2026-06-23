import { useEffect, useRef, useState } from "react";

interface NetworkStatus {
  isOnline: boolean;
  isWeakNetwork: boolean;
}

export function useNetworkStatus(): NetworkStatus {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [isWeakNetwork, setIsWeakNetwork] = useState(false);
  const lastCheckRef = useRef(0);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    const checkWeakNetwork = () => {
      const now = Date.now();
      if (now - lastCheckRef.current < 30000) return;
      lastCheckRef.current = now;

      const img = new Image();
      const start = Date.now();
      img.onload = () => {
        const rtt = Date.now() - start;
        setIsWeakNetwork(rtt > 3000);
      };
      img.onerror = () => {};
      img.src = "/favicon.ico?" + start;
    };

    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        checkWeakNetwork();
      }
    };

    document.addEventListener("visibilitychange", handleVisibility);
    checkWeakNetwork();

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, []);

  return { isOnline, isWeakNetwork };
}
