"use client";

import { useState } from "react";

import { Lab1Panel } from "@/components/lab1/lab1-panel";
import { Lab2Panel } from "@/components/lab2/lab2-panel";
import { WorkflowConsole } from "@/components/lab3/workflow-console";
import { NavRail, type LabKey } from "@/components/nav-rail";

const labNames: Record<LabKey, string> = {
  lab1: "MODEL DEVELOPMENT",
  lab2: "GROUNDED AGENT",
  lab3: "DETERMINISTIC WORKFLOW",
};

export function DemoShell() {
  const [activeLab, setActiveLab] = useState<LabKey>("lab3");
  return <div className="app-shell">
    <NavRail activeLab={activeLab} onSelect={setActiveLab} />
    <header className="app-topbar">
      <div className="app-breadcrumb"><span>AI ENGINEERING CONSOLE</span><span aria-hidden="true">/</span><strong>{labNames[activeLab]}</strong></div>
      <div className="app-top-meta"><span className="workspace-indicator"><i aria-hidden="true" />LOCAL WORKSPACE</span><span className="mono">LAB DEMO</span></div>
    </header>
    <main className="app-content" id="main-content" tabIndex={-1}>
      <div className="lab-screen" hidden={activeLab !== "lab1"}><Lab1Panel /></div>
      <div className="lab-screen" hidden={activeLab !== "lab2"}><Lab2Panel /></div>
      <div className="lab-screen" hidden={activeLab !== "lab3"}><WorkflowConsole /></div>
    </main>
  </div>;
}
