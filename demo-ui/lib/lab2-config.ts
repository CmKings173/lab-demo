import { LAB2_AGENT_ID, LAB2_DOMAIN_TOOL_NAMES, LAB2_MODEL_TARGET } from "./lab2-contracts";

export { LAB2_AGENT_ID, LAB2_DOMAIN_TOOL_NAMES, LAB2_MODEL_TARGET };

export const LAB2_ROUTE_STEPS = [
  { label: "USER REQUEST", value: "Natural language" },
  { label: "OPENCLAW AGENT", value: LAB2_AGENT_ID },
  { label: "MODEL TARGET", value: LAB2_MODEL_TARGET },
  { label: "DOMAIN TOOLS", value: `${LAB2_DOMAIN_TOOL_NAMES.length} allowlisted tools` },
  { label: "TOOL API", value: "Private Lab2 boundary" },
  { label: "DATA SOURCES", value: "PostgreSQL + WeKnora" },
] as const;

const toolDescriptions = [
  "Filter and search the structured product catalog.",
  "Retrieve one exact product record by its ID.",
  "Search mapped product documents through WeKnora.",
  "Compare exact catalog records for selected products.",
  "Compare configuration IDs when that repository is configured.",
  "Run the deterministic Lab2 sizing estimate.",
] as const;

export const LAB2_DOMAIN_TOOL_DETAILS = LAB2_DOMAIN_TOOL_NAMES.map((name, index) => ({
  name,
  detail: toolDescriptions[index],
}));

export const LAB2_MAX_CONVERSATION_MESSAGES = 20;
export const LAB2_MAX_CONVERSATION_CHARS = 20_000;
