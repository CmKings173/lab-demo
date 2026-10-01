"use client";

import { LAB2_AGENT_ID, LAB2_DOMAIN_TOOL_NAMES, LAB2_MODEL_TARGET } from "@/lib/lab2-config";
import { Lab2Chat } from "./lab2-chat";
import { useLab2Chat } from "./hooks/use-lab2-chat";
import { Lab2RuntimePath } from "./lab2-runtime-path";
import { Lab2ToolContract } from "./lab2-tool-contract";
import { Lab2TraceStatus } from "./lab2-trace-status";
import styles from "./lab2-panel.module.css";

export function Lab2Panel() {
  const chat = useLab2Chat();

  return <section className={styles.root} id="lab2-chat" aria-labelledby="lab2-title">
    <header className={styles.pageHeader}>
      <div className={styles.titleBlock}>
        <p className={styles.eyebrow}><span>LAB 02</span><i aria-hidden="true">/</i> AGENT + RAG</p>
        <h1 id="lab2-title">Agent &amp; RAG Intelligence Pipeline</h1>
        <p className={styles.subtitle}>Ask the configured Lab2 agent about products, requirements, and grounded product documents.</p>
      </div>
      <div className={styles.headerFacts} aria-label="Configured Lab2 targets">
        <div className={styles.fact}><span>AGENT</span><strong>{LAB2_AGENT_ID}</strong></div>
        <div className={styles.fact}><span>MODEL TARGET</span><strong>{LAB2_MODEL_TARGET}</strong></div>
        <div className={styles.fact}><span>DOMAIN TOOLS</span><strong>{String(LAB2_DOMAIN_TOOL_NAMES.length).padStart(2, "0")}</strong></div>
      </div>
    </header>

    <div className={styles.columns}>
      <div className={styles.leftColumn}>
        <Lab2RuntimePath />
        <Lab2ToolContract />
        <Lab2TraceStatus reason={chat.traceReason} />
      </div>
      <Lab2Chat
        messages={chat.messages}
        draft={chat.draft}
        requestState={chat.requestState}
        error={chat.error}
        onDraftChange={chat.setDraft}
        onSubmit={chat.submit}
        onNewConversation={chat.startNewConversation}
      />
    </div>
  </section>;
}
