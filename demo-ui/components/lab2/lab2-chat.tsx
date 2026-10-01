"use client";

import { useEffect, useRef, type FormEvent, type KeyboardEvent } from "react";

import type { Lab2ChatMessage, Lab2RequestState } from "./hooks/use-lab2-chat";
import styles from "./lab2-panel.module.css";

function turnLabel(state: Lab2RequestState): string {
  if (state === "sending") return "WAITING FOR AGENT";
  if (state === "received") return "RESPONSE RECEIVED";
  if (state === "failed") return "REQUEST FAILED";
  return "NO TURN SENT";
}

function usageLabel(usage: Lab2ChatMessage["usage"]): string | null {
  if (!usage) return null;
  const tokens = usage.totalTokens ?? (usage.promptTokens !== null && usage.completionTokens !== null
    ? usage.promptTokens + usage.completionTokens
    : null);
  return tokens === null ? null : `${tokens.toLocaleString()} tokens`;
}

function MessageItem({ message }: { message: Lab2ChatMessage }) {
  const tokenUsage = message.role === "assistant" ? usageLabel(message.usage) : null;
  return <article className={`${styles.message} ${message.role === "user" ? styles.userMessage : styles.assistantMessage}`}>
    <div className={styles.messageHeading}>
      <strong>{message.role === "user" ? "YOU" : "CNTTShop Advisor"}</strong>
      {message.role === "assistant" && message.model ? <span>{message.model}</span> : null}
    </div>
    <p>{message.text}</p>
    {message.role === "assistant" && message.truncated ? <small className={styles.truncated}>Reply shortened at the display limit.</small> : null}
    {tokenUsage ? <small className={styles.usage}>{tokenUsage}</small> : null}
  </article>;
}

export function Lab2Chat({
  messages,
  draft,
  requestState,
  error,
  onDraftChange,
  onSubmit,
  onNewConversation,
}: {
  messages: Lab2ChatMessage[];
  draft: string;
  requestState: Lab2RequestState;
  error: string | null;
  onDraftChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onNewConversation: () => void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const messagesRef = useRef<HTMLDivElement>(null);
  const sending = requestState === "sending";

  useEffect(() => {
    messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, requestState]);

  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      formRef.current?.requestSubmit();
    }
  };

  return <section className={styles.chatCard} aria-labelledby="chat-title">
    <div className={styles.chatHeader}>
      <div className={styles.chatTitle}>
        <span className={styles.agentMark} aria-hidden="true">AI</span>
        <div><p className={styles.chatOverline}>AI ADVISOR</p><h2 id="chat-title">CNTTShop Advisor</h2></div>
      </div>
      <span className={`${styles.turnStatus} ${styles[`turn_${requestState}`]}`}><i aria-hidden="true" />{turnLabel(requestState)}</span>
    </div>

    <div className={styles.messages} ref={messagesRef} aria-live="polite" aria-relevant="additions text">
      {messages.length === 0 ? (
        <div className={styles.emptyChat}>
          <span className={styles.emptyGlyph} aria-hidden="true">*</span>
          <h3>What would you like to find?</h3>
          <p>Ask for catalog products, a sizing estimate, or evidence from a product&apos;s mapped documents.</p>
          <span className={styles.noSeed}>NO SAMPLE CONVERSATION LOADED</span>
        </div>
      ) : messages.map((message) => <MessageItem key={message.id} message={message} />)}
      {sending ? <div className={styles.pending} role="status"><span className={styles.spinner} aria-hidden="true" />Waiting for the OpenClaw agent...</div> : null}
    </div>

    {error ? <p className={styles.error} role="alert">{error}</p> : null}

    <form className={styles.composer} onSubmit={onSubmit} ref={formRef}>
      <label htmlFor="lab2-message">MESSAGE THE ADVISOR</label>
      <textarea
        id="lab2-message"
        value={draft}
        maxLength={4_000}
        rows={3}
        onChange={(event) => onDraftChange(event.currentTarget.value)}
        onKeyDown={handleComposerKeyDown}
        placeholder="For example: Find a catalog server for Qwen inference."
        disabled={sending}
      />
      <div className={styles.composerFooter}>
        <span>Enter to send | Shift+Enter for a new line | {draft.length.toLocaleString()}/4,000</span>
        <button type="submit" disabled={!draft.trim() || sending} aria-label="Send message to CNTTShop advisor">
          {sending ? "SENDING..." : "SEND MESSAGE"}<span aria-hidden="true">&gt;</span>
        </button>
      </div>
    </form>
    <div className={styles.chatFooter}>
      <span>Only the final reply is shown; internal tool execution is not exposed here.</span>
      <button type="button" onClick={onNewConversation} disabled={sending}>NEW CONVERSATION</button>
    </div>
  </section>;
}
