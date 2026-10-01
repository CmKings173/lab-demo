import { proxyLab3Conversation } from "@/lib/server/lab3-conversation";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 150;

// This filesystem route takes precedence over the existing afterFiles rewrite.
// The bounded conversation deadline does not apply to SSE or other backend routes.
export function POST(request: Request): Promise<Response> {
  return proxyLab3Conversation(request);
}
