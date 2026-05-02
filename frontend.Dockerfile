# ── Stage 1: Build ────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# ── Stage 2: Export ───────────────────────────────────────────────
FROM alpine:3.19

WORKDIR /app
COPY --from=builder /app/dist /app/dist

# The dist/ directory will be mounted by docker-compose into nginx
CMD ["cp", "-r", "/app/dist/.", "/output/"]
