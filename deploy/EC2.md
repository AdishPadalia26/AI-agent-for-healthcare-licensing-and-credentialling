# Deploying on AWS EC2 and S3

These steps use your own AWS account. Use synthetic documents only unless you have signed
business associate agreements covering AWS and Google.

## 1. S3 bucket

1. Create a private bucket with Block Public Access on and default encryption (SSE-S3) enabled.
2. Add this CORS rule, replacing the origin:

```json
[{
  "AllowedOrigins": ["https://your-domain.example"],
  "AllowedMethods": ["PUT"],
  "AllowedHeaders": ["content-type", "x-amz-server-side-encryption"],
  "MaxAgeSeconds": 300
}]
```

## 2. IAM role for the instance

Attach a role with `s3:GetObject`, `s3:PutObject`, and `s3:DeleteObject` on `arn:aws:s3:::BUCKET/users/*`,
`textract:StartDocumentAnalysis`, and `textract:GetDocumentAnalysis`. The Next.js S3 helper reads
`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, so also create an IAM user limited to
`s3:PutObject` on the same path for `frontend/.env.local`.

## 3. Instance

Launch Ubuntu 24.04 on `t3.large` or larger with 30 GB of disk. Allow inbound 80 and 443 only, and
restrict 22 to your IP. Install Docker with its Compose plugin, then run:

```bash
sudo sysctl -w vm.max_map_count=262144
git clone https://github.com/AdishPadalia26/AI-agent-for-healthcare-licensing-and-credentialling.git app
cd app
```

## 4. Configuration

Create `backend/.env` from `backend/.env.example` and `frontend/.env.local` from `frontend/.env.example`.

- Set `STORAGE_BACKEND=s3`, `OCR_PROVIDER=textract`, and `LLM_PROVIDER=gemini`.
- Set `BACKEND_JWT_SECRET` to the same long random value on both sides. Generate it with `openssl rand -hex 32`.
- Set a different random `DATA_ENCRYPTION_KEY`. Losing it makes stored provider data unreadable.
- Set `NEXTAUTH_URL=https://your-domain.example`, `CORS_ORIGINS` to the same origin, and `ADMIN_EMAILS`.

## 5. Start and verify

```bash
docker compose up -d --build
curl -f http://localhost/
docker compose exec api python -c "import urllib.request as u; print(u.urlopen('http://localhost:5000/api/health').read())"
```

## 6. TLS

Do not send real logins or documents over plain HTTP. Terminate TLS with an Application Load
Balancer and an ACM certificate, or add Certbot to the nginx container.
