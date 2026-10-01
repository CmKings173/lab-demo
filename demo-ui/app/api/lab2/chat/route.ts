import { runLab2Chat } from "@/lib/server/openclaw-lab2";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  const result = await runLab2Chat(request);
  if (!result.ok) {
    return Response.json(
      { error: { code: result.failure.code, message: result.failure.message } },
      { status: result.failure.status, headers: { "Cache-Control": "no-store" } },
    );
  }
  return Response.json(result.value, { headers: { "Cache-Control": "no-store" } });
}
