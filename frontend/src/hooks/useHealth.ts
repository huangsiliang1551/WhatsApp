import { useEffect, useState } from "react";

import { api } from "../services/api";

export function useHealth() {
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    api
      .get("/health")
      .then(() => setStatus("ok"))
      .catch(() => setStatus("unreachable"));
  }, []);

  return status;
}
