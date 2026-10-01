import { NextResponse } from "next/server";

import { getLab1Dashboard, Lab1ArtifactError } from "@/lib/server/lab1-artifacts";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json(await getLab1Dashboard(), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    const message = error instanceof Lab1ArtifactError
      ? error.message
      : "Lab 1 data could not be loaded. Check that the generated artifacts are available.";
    const status = error instanceof Lab1ArtifactError ? error.status : 503;
    return NextResponse.json({ error: { message } }, {
      status,
      headers: { "Cache-Control": "no-store" },
    });
  }
}
