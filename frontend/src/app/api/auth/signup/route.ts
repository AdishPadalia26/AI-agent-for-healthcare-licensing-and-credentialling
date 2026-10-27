import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const body = await req.json();
  // TODO create user
  return NextResponse.json({ ok: true, user: { email: body.email } });
}
