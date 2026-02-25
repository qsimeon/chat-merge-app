FROM python:3.11-slim

# Install Node.js 20
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

WORKDIR /app

COPY . .

# Build React frontend → produces frontend/dist/
RUN cd frontend && npm ci && npm run build

# Install Python backend dependencies
RUN cd backend && uv sync

WORKDIR /app/backend

EXPOSE 8000

# $PORT is injected by Railway; default to 8000 locally
# --proxy-headers trusts X-Forwarded-Proto from Railway's HTTPS terminator
# so FastAPI redirect URLs use https:// not http://
CMD uv run uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'
