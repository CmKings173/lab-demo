import type { FormEvent } from "react";

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
  return <aside className="lab3-chat" aria-label="Conversation with Lab 3 advisor">
    <header className="lab3-chat-header"><div><strong>QWEN ADVISOR</strong><span>Lab 3 · direct conversation API</span></div><button type="button" onClick={onNewConversation} disabled={composerLocked} aria-label="Start a new conversation">NEW CHAT</button></header>
    <div className="lab3-chat-messages" aria-live="polite" aria-relevant="additions">
      {messages.length === 0 ? <div className="lab3-chat-empty"><strong>Start a conversation</strong><p>Describe the server configuration you need. The backend will ask for missing requirements before creating a workflow.</p></div> : messages.map((message, index) => <article key={`${index}-${message.role}`} className={`lab3-message ${message.role}`}><span>{message.role === "user" ? "YOU" : "QWEN ADVISOR"}</span><p>{message.content}</p></article>)}
      {busy ? <p className="lab3-chat-pending" role="status">Waiting for the conversation service.</p> : null}
    </div>
    {error ? <p className="stitch-alert" role="alert">{error}</p> : null}
    <form className="lab3-composer" onSubmit={onSubmit}><label htmlFor="lab3-message">MESSAGE</label><div><textarea id="lab3-message" rows={3} maxLength={4000} value={draft} onChange={(event) => onDraftChange(event.currentTarget.value)} placeholder="Describe your model, usage, budget." disabled={composerLocked} /><button type="submit" aria-label="Send message" disabled={composerLocked || !draft.trim()}>SEND</button></div><small>{runActive ? "Wait for the active workflow to finish before starting another conversation." : "Messages are sent to the Lab 3 conversation API."}</small></form>
  </aside>;
}
