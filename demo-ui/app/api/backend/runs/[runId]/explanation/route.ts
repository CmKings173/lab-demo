import { proxyLab3Explanation } from "@/lib/server/lab3-explanation";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 90;

export async function POST(request: Request, context: {
  params: Promise<{ runId: string }>;
}): Promise<Response> {
  const { runId } = await context.params;
  return proxyLab3Explanation(request, runId);
}
