import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL, backendAuthHeader, sessionUser } from "@/lib/backend";

type Context = { params: Promise<{ path: string[] }> };

const FORWARDED_RESPONSE_HEADERS = ["content-type", "content-disposition", "cache-control"];

async function proxy(req: NextRequest, { params }: Context) {
  const user = await sessionUser(req);
  if (!user) return NextResponse.json({ error: "Authentication required" }, { status: 401 });

  const { path } = await params;
  const target = `${BACKEND_URL}/api/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers = new Headers({ Authorization: await backendAuthHeader(user) });
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);

  const hasBody = !["GET", "HEAD"].includes(req.method);
  const upstream = await fetch(target, {
    method: req.method,
    headers,
    body: hasBody ? await req.arrayBuffer() : undefined,
    cache: "no-store",
  }).catch(() => null);
  if (!upstream) return NextResponse.json({ error: "Processing service is unavailable" }, { status: 502 });

  const responseHeaders = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  return new Response(upstream.status === 204 ? null : upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
