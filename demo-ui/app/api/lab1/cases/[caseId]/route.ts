import { NextResponse } from "next/server";

import { getLab1Case, Lab1ArtifactError } from "@/lib/server/lab1-artifacts";

export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  context: { params: Promise<{ caseId: string }> },
) {
  const { caseId } = await context.params;
  if (!/^eval-\d{4}$/.test(caseId)) {
    return NextResponse.json({ error: { message: "Lab 1 case was not found." } }, {
      status: 404,
      headers: { "Cache-Control": "no-store" },
    });
  }

  try {
    return NextResponse.json(await getLab1Case(caseId), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    const message = error instanceof Lab1ArtifactError
      ? error.message
      : "Lab 1 case data could not be loaded.";
    const status = error instanceof Lab1ArtifactError ? error.status : 503;
    return NextResponse.json({ error: { message } }, {
      status,
      headers: { "Cache-Control": "no-store" },
    });
  }
}
