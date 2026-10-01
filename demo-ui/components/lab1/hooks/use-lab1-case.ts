"use client";

import { useEffect, useRef, useState } from "react";

import { fetchLab1Case } from "@/lib/api/lab1";
import type { Lab1CaseDetail } from "@/lib/lab1-contracts";

type CaseRequest =
  | { caseId: string; status: "loaded"; detail: Lab1CaseDetail }
  | { caseId: string; status: "failed"; message: string };

export function useLab1Case(caseId: string) {
  const [request, setRequest] = useState<CaseRequest | null>(null);
  const generation = useRef(0);
  const currentRequest = request?.caseId === caseId ? request : null;

  useEffect(() => {
    if (!caseId) return undefined;

    const requestGeneration = ++generation.current;
    const controller = new AbortController();
    fetchLab1Case(caseId, controller.signal)
      .then((detail) => {
        if (requestGeneration === generation.current) setRequest({ caseId, status: "loaded", detail });
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted || requestGeneration !== generation.current) return;
        setRequest({
          caseId,
          status: "failed",
          message: reason instanceof Error ? reason.message : "The selected Lab 1 case could not be loaded.",
        });
      });

    return () => {
      controller.abort();
      if (generation.current === requestGeneration) generation.current += 1;
    };
  }, [caseId]);

  if (!caseId) return { status: "idle" as const, detail: null, error: null };
  if (!currentRequest) return { status: "loading" as const, detail: null, error: null };
  if (currentRequest.status === "failed") {
    return { status: "failed" as const, detail: null, error: currentRequest.message };
  }
  return { status: "loaded" as const, detail: currentRequest.detail, error: null };
}
