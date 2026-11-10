import { NextResponse } from "next/server";
import { BACKEND_URL } from "@/lib/backend";

export async function POST(req: Request) {
  const upstream = await fetch(`${BACKEND_URL}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await req.text(),
  });
  return NextResponse.json(await upstream.json(), { status: upstream.status });
}
