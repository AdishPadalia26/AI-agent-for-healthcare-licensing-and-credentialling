import { SignJWT } from "jose";
import { getToken } from "next-auth/jwt";
import type { NextRequest } from "next/server";

export const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:5000";

export interface SessionUser {
  email: string;
  name?: string;
}

export async function sessionUser(req: NextRequest): Promise<SessionUser | null> {
  const token = await getToken({ req, secret: process.env.NEXTAUTH_SECRET });
  if (!token?.email) return null;
  return { email: token.email, name: token.name ?? undefined };
}

/** Mints a two-minute token that lets Flask trust the signed-in user. */
export async function backendAuthHeader(user: SessionUser): Promise<string> {
  const secret = process.env.BACKEND_JWT_SECRET ?? process.env.NEXTAUTH_SECRET;
  if (!secret) throw new Error("BACKEND_JWT_SECRET or NEXTAUTH_SECRET must be set");
  const token = await new SignJWT({ name: user.name })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(user.email)
    .setIssuer("credentialing-web")
    .setAudience("credentialing-api")
    .setExpirationTime("2m")
    .sign(new TextEncoder().encode(secret));
  return `Bearer ${token}`;
}
