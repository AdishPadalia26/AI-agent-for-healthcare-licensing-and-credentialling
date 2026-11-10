FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY api ./api
COPY credentialing ./credentialing

RUN useradd --create-home appuser && mkdir -p /data && chown appuser /data
USER appuser

ENV DATA_DIR=/data
EXPOSE 5000

# One worker: background jobs run in this process's thread pool.
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--timeout", "120", "--bind", "0.0.0.0:5000", "app:app"]
