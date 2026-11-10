import { randomUUID } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { s3 } from "@/lib/s3";
import { PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { BACKEND_URL, backendAuthHeader, sessionUser } from "@/lib/backend";

const EXTENSIONS: Record<string, string> = {
  "application/pdf": "pdf",
  "image/jpeg": "jpg",
  "image/png": "png",
};
const ENCRYPTION_HEADER = "x-amz-server-side-encryption";

export async function GET(req: NextRequest) {
  const user = await sessionUser(req);
  if (!user) return NextResponse.json({ error: "Authentication required" }, { status: 401 });

  const { searchParams } = new URL(req.url);
  const fileName = searchParams.get("fileName");
  const fileType = searchParams.get("fileType");
  if (!fileName || !fileType) {
    return NextResponse.json({ error: "Missing fileName or fileType" }, { status: 400 });
  }
  const extension = EXTENSIONS[fileType];
  if (!extension) return NextResponse.json({ error: "Unsupported file type" }, { status: 400 });

  // Flask owns the per-user prefix and storage mode, so both sides always agree.
  const meResponse = await fetch(`${BACKEND_URL}/api/me`, {
    headers: { Authorization: await backendAuthHeader(user) },
    cache: "no-store",
  }).catch(() => null);
  if (!meResponse?.ok) {
    return NextResponse.json({ error: "Processing service is unavailable" }, { status: 502 });
  }
  const me = (await meResponse.json()) as { upload_prefix: string; storage_backend: string };
  const key = `${me.upload_prefix}${randomUUID()}/source.${extension}`;

  if (me.storage_backend !== "s3") {
    return NextResponse.json({
      key,
      uploadUrl: `/api/backend/uploads/local?key=${encodeURIComponent(key)}`,
      headers: { "Content-Type": fileType },
    });
  }

  const command = new PutObjectCommand({
    Bucket: process.env.AWS_S3_BUCKET_NAME!,
    Key: key,
    ContentType: fileType,
    ServerSideEncryption: "AES256",
  });
  const uploadUrl = await getSignedUrl(s3, command, {
    expiresIn: 900,
    unhoistableHeaders: new Set([ENCRYPTION_HEADER]),
  });
  return NextResponse.json({
    key,
    uploadUrl,
    headers: { "Content-Type": fileType, [ENCRYPTION_HEADER]: "AES256" },
  });
}
