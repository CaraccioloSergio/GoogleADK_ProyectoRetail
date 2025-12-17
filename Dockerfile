FROM python:3.11-slim

# =========================
# Python runtime config
# =========================
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# =========================
# Workdir
# =========================
WORKDIR /app

# =========================
# System deps (mínimo)
# =========================
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# =========================
# Python deps
# =========================
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# =========================
# App code
# =========================
COPY . .

# =========================
# Cloud Run listens on $PORT
# =========================
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]

