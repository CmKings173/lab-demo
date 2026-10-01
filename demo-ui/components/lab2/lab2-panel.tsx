"use client";

import { Lab2Chat } from "./lab2-chat";
import { useLab2Chat } from "./hooks/use-lab2-chat";
import { Lab2RuntimePanel } from "./lab2-runtime-panel";
import styles from "./lab2-panel.module.css";

export function Lab2Panel() {
  const chat = useLab2Chat();

  return <section className={styles.root} id="lab2-chat" aria-labelledby="lab2-title">
    <header className={styles.pageHeader}>
      <div className={styles.titleBlock}>
        <p className={styles.eyebrow}><span>LAB 02</span><i aria-hidden="true">/</i> AGENT + RAG</p>
        <h1 id="lab2-title">CNTTShop AI Advisor</h1>
        <p className={styles.subtitle}>Find products, explore AI deployment requirements, and check grounded product documents.</p>
      </div>
    </header>

    <div className={styles.columns}>
      <Lab2Chat
        messages={chat.messages}
        draft={chat.draft}
        requestState={chat.requestState}
        error={chat.error}
        onDraftChange={chat.setDraft}
        onSubmit={chat.submit}
        onNewConversation={chat.startNewConversation}
      />
      <Lab2RuntimePanel requestState={chat.requestState} traceReason={chat.traceReason} />
    </div>
  </section>;
}
