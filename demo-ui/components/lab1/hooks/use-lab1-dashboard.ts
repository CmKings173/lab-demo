"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchLab1Dashboard } from "@/lib/api/lab1";
import type { Lab1Dashboard } from "@/lib/lab1-contracts";

export function useLab1Dashboard() {
  const [dashboard, setDashboard] = useState<Lab1Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const generation = useRef(0);

  useEffect(() => {
    const requestGeneration = ++generation.current;
    const controller = new AbortController();

    fetchLab1Dashboard(controller.signal)
      .then((nextDashboard) => {
        if (requestGeneration === generation.current) setDashboard(nextDashboard);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted || requestGeneration !== generation.current) return;
        setError(reason instanceof Error ? reason.message : "Lab 1 artifacts could not be loaded.");
      })
      .finally(() => {
        if (!controller.signal.aborted && requestGeneration === generation.current) setLoading(false);
      });

    return () => {
      controller.abort();
      if (generation.current === requestGeneration) generation.current += 1;
    };
  }, [reloadKey]);

  const reload = useCallback(() => {
    setError(null);
    setLoading(true);
    setReloadKey((key) => key + 1);
  }, []);

  return { dashboard, loading, error, reload };
}
