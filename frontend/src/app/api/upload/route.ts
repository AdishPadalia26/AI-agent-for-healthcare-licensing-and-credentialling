import { NextRequest, NextResponse } from "next/server";
import { s3 } from "@/lib/s3";
import { PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const fileName = searchParams.get("fileName");
  const fileType = searchParams.get("fileType");

  if (!fileName || !fileType) {
    return NextResponse.json(
      { error: "Missing fileName or fileType" },
      { status: 400 }
    );
  }

  const command = new PutObjectCommand({
    Bucket: process.env.AWS_S3_BUCKET_NAME!,
    Key: fileName,
    ContentType: fileType,
  });

  const uploadUrl = await getSignedUrl(s3, command, { expiresIn: 3600 });

  return NextResponse.json({ uploadUrl });
}
