"use client";

import { useCallback, useState, type FormEvent } from "react";

import { sendLab2Message } from "@/lib/api/lab2";
import { LAB2_MAX_CONVERSATION_CHARS, LAB2_MAX_CONVERSATION_MESSAGES } from "@/lib/lab2-config";
import type { Lab2ChatResponse } from "@/lib/lab2-contracts";

export type Lab2ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  model: string | null;
  usage: Lab2ChatResponse["usage"];
  truncated: boolean;
};

export type Lab2RequestState = "idle" | "sending" | "received" | "failed";

const initialTraceReason = "Tool-level events are not returned by the configured HTTP chat endpoint.";

export function useLab2Chat() {
  const [messages, setMessages] = useState<Lab2ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [requestState, setRequestState] = useState<Lab2RequestState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [traceReason, setTraceReason] = useState(initialTraceReason);

  const submit = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message || requestState === "sending") return;

    const conversationSize = messages.reduce((total, item) => total + item.text.length, message.length);
    if (messages.length >= LAB2_MAX_CONVERSATION_MESSAGES || conversationSize > LAB2_MAX_CONVERSATION_CHARS) {
      setError("This conversation has reached its limit. Start a new conversation to continue.");
      return;
    }

    const activeConversation = conversationId ?? crypto.randomUUID();
    setConversationId(activeConversation);
    setMessages((current) => [...current, {
      id: crypto.randomUUID(), role: "user", text: message, model: null, usage: null, truncated: false,
    }]);
    setDraft("");
    setError(null);
    setRequestState("sending");

    try {
      const result = await sendLab2Message({ message, conversationId: activeConversation });
      setConversationId(result.conversationId);
      setTraceReason(result.trace.reason);
      setMessages((current) => [...current, {
        id: crypto.randomUUID(),
        role: "assistant",
        text: result.message,
        model: result.model,
        usage: result.usage,
        truncated: result.truncated,
      }]);
      setRequestState("received");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The Lab2 agent could not complete this request.");
      setRequestState("failed");
    }
  }, [conversationId, draft, messages, requestState]);

  const startNewConversation = useCallback(() => {
    if (requestState === "sending") return;
    setMessages([]);
    setConversationId(null);
    setDraft("");
    setError(null);
    setRequestState("idle");
  }, [requestState]);

  return { messages, draft, setDraft, requestState, error, traceReason, submit, startNewConversation };
}
