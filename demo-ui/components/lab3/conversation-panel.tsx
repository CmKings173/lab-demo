import { useRef, type FormEvent, type KeyboardEvent } from "react";

import type { ConversationMessage } from "@/lib/lab3-contracts";

export function ConversationPanel({
  messages,
  draft,
  busy,
  runActive,
  creationBusy,
  error,
  onDraftChange,
  onSubmit,
  onNewConversation,
}: {
  messages: ConversationMessage[];
  draft: string;
  busy: boolean;
  runActive: boolean;
  creationBusy: boolean;
  error: string | null;
  onDraftChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onNewConversation: () => void;
}) {
  const composerLocked = busy || runActive || creationBusy;
  const formRef = useRef<HTMLFormElement>(null);
  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      formRef.current?.requestSubmit();
    }
  }
  return <aside className="lab3-chat" aria-label="Conversation with Lab 3 advisor">
    <header className="lab3-chat-header"><div><strong>CNTTShop Advisor</strong><span>Lab 3 · deterministic workflow</span></div><button type="button" onClick={onNewConversation} disabled={composerLocked} aria-label="Start a new conversation">NEW CHAT</button></header>
    <div className="lab3-chat-messages" aria-live="polite" aria-relevant="additions">
      {messages.length === 0 ? <div className="lab3-chat-empty"><strong>Start a conversation</strong><p>Say hello, ask about AI deployment, or describe your workload. The advisor collects your requirements; the workflow checks actual configurations.</p></div> : messages.map((message, index) => <article key={`${index}-${message.role}`} className={`lab3-message ${message.role}`}><span>{message.role === "user" ? "YOU" : "CNTTShop Advisor"}</span><p>{message.content}</p></article>)}
      {busy ? <p className="lab3-chat-pending" role="status">Waiting for the conversation service.</p> : null}
    </div>
    {error ? <p className="stitch-alert" role="alert">{error}</p> : null}
    <form ref={formRef} className="lab3-composer" onSubmit={onSubmit}><label htmlFor="lab3-message">MESSAGE</label><div><textarea id="lab3-message" rows={3} maxLength={4000} value={draft} onChange={(event) => onDraftChange(event.currentTarget.value)} onKeyDown={onKeyDown} placeholder="Describe your model, usage, budget." disabled={composerLocked} /><button type="submit" aria-label="Send message" disabled={composerLocked || !draft.trim()}>SEND</button></div><small>Enter to send | Shift+Enter for a new line{runActive ? " · Wait for the active workflow to finish before starting another conversation." : ""}</small></form>
  </aside>;
}
