# BATCH-51 BLUEPRINT — Frontend CI + nginx Production Config

**Lead Programmer:** Lead Agent  
**Date:** 2026-05-02  
**AIV Framework:** v5.1  
**Phase:** 4 — DevOps & Production

---

## TASK-01: Frontend Build & Test in CI

### Target File (MODIFY)
- `.github/workflows/ci.yml` — Add frontend job

### Specification

Add a `frontend` job to the existing CI workflow that runs in parallel with the backend job:

```yaml
  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run build
      - run: npm test
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: frontend-build
          path: frontend/dist/
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: frontend-coverage
          path: frontend/coverage/
```

Also rename existing job from `lint-and-test` to `backend` for clarity.

### Tests
- Verify CI workflow YAML is valid (no syntax test needed — GitHub validates on push)

---

## TASK-02: nginx Reverse Proxy + Production Docker

### Target Files (NEW)
- `nginx/nginx.conf` — Reverse proxy configuration
- `frontend.Dockerfile` — Multi-stage frontend build

### Target Files (MODIFY)
- `docker-compose.yml` — Add frontend + nginx services
- `docker-compose.prod.yml` — Production override (NEW)

### Specification

#### nginx.conf
```
upstream backend {
    server app:8000;
}

upstream frontend {
    server frontend:3000;
}

server {
    listen 80;
    server_name _;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # API routes → backend
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket
    location /api/v1/ws {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # Health check
    location /health {
        proxy_pass http://backend;
    }

    # Static files → frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
    }

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;
    gzip_min_length 1000;
}
```

#### frontend.Dockerfile
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 3000
```

Wait — actually the frontend should serve static files directly, not through a dev server. Let me reconsider: the nginx should serve the static files built by Vite, not proxy to a node server. So:

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx/frontend.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

And the main nginx should be:
- `/api/` → backend:8000
- `/api/v1/ws` → backend:8000 (WebSocket upgrade)
- `/` → serve static files from a shared volume (built by frontend container)
OR just have the frontend container serve via its own nginx and the main nginx proxies to it.

Simpler approach: single nginx that serves frontend static files directly and proxies API calls.

#### docker-compose.yml updates
```yaml
  frontend:
    build:
      context: frontend
      dockerfile: ../frontend.Dockerfile
    # No ports exposed directly

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - frontend_build:/usr/share/nginx/html
    depends_on:
      - app
      - frontend

volumes:
  postgres_data:
  redis_data:
  app_data:
  frontend_build:
```

Actually, let me keep it simple and use the frontend container's own nginx. The main nginx proxies to it.

#### docker-compose.prod.yml (NEW)
Production overrides:
- Resource limits
- Restart policies
- HTTPS placeholder
- Environment variable overrides

### Tests
- Docker-compose config validation
- nginx config test (`nginx -t`)

---

## Acceptance Criteria

| Criterion | Verification |
|:---|:---|
| CI workflow has frontend job | YAML check |
| frontend job runs lint, build, test | Step list |
| nginx.conf handles API + static + WebSocket | Config review |
| frontend.Dockerfile multi-stage build | File exists |
| docker-compose.yml includes frontend + nginx | Service list |
| docker-compose.prod.yml exists | File exists |

---

*BLUEPRINT — BATCH-51 — AIV Framework v5.1 — Lead Agent*
