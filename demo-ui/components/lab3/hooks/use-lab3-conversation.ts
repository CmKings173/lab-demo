"use client";

import { useCallback, useRef, useState, type FormEvent } from "react";

import { submitConversation } from "@/lib/api/lab3";
import type { RunStatus } from "@/lib/contracts";
import type { ConversationMessage } from "@/lib/lab3-contracts";

type RunCoordinator = {
  isRunActive: boolean;
  beginRunCreation: () => boolean;
  finishRunCreation: () => void;
  attachRun: (runId: string, status: RunStatus) => boolean;
};

export function useLab3Conversation() {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);

  const appendAssistantMessage = useCallback((content: string) => {
    setMessages((current) => [...current, { role: "assistant", content }]);
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>, coordinator: RunCoordinator) => {
    event.preventDefault();
    const content = draft.trim();
    if (!content || busy || coordinator.isRunActive) return;
    if (content.length > 4000 || messages.length >= 20 ||
        messages.reduce((sum, item) => sum + item.content.length, content.length) > 20_000) {
      setError("Cuộc trò chuyện đã đạt giới hạn nội dung. Hãy bắt đầu phiên mới để tiếp tục.");
      return;
    }
    if (!coordinator.beginRunCreation()) return;

    const requestGeneration = ++generation.current;
    const userMessage: ConversationMessage = { role: "user", content };
    const conversation = [...messages, userMessage];
    setMessages(conversation);
    setDraft("");
    setError(null);
    setBusy(true);
    try {
      const response = await submitConversation(conversation);
      if (requestGeneration !== generation.current) return;
      if (response.status === "needs_information") {
        appendAssistantMessage(response.question);
        return;
      }
      if (!coordinator.attachRun(response.run_id, response.run_status)) {
        setError("A workflow run is already active. Wait for it to finish before starting another.");
      }
    } catch (reason) {
      if (requestGeneration === generation.current) {
        setError(reason instanceof Error ? reason.message : "Không gửi được yêu cầu đến conversation API.");
      }
    } finally {
      if (requestGeneration === generation.current) setBusy(false);
      coordinator.finishRunCreation();
    }
  };

  const startNewConversation = useCallback(() => {
    if (busy) return;
    generation.current += 1;
    setMessages([]);
    setDraft("");
    setError(null);
  }, [busy]);

  return { messages, draft, setDraft, busy, error, submit, startNewConversation, appendAssistantMessage };
}
