# syntax=docker/dockerfile:1
# Build Stage
FROM node:20-alpine AS build

WORKDIR /app

# Copy dependency specifications first for layer caching
COPY package*.json ./
RUN npm ci

# Copy frontend source
COPY . .

ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# Production Stage: Hardened Nginx
FROM nginx:alpine

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# Hardened Nginx configuration with security headers & SPA routing
RUN printf '%s\n' \
'server {' \
'    listen 80;' \
'    server_name localhost;' \
'    server_tokens off;' \
'    ' \
'    # Security Headers' \
'    add_header X-Frame-Options "SAMEORIGIN" always;' \
'    add_header X-Content-Type-Options "nosniff" always;' \
'    add_header X-XSS-Protection "1; mode=block" always;' \
'    add_header Referrer-Policy "strict-origin-when-cross-origin" always;' \
'    ' \
'    location / {' \
'        root /usr/share/nginx/html;' \
'        index index.html index.htm;' \
'        try_files $uri $uri/ /index.html;' \
'    }' \
'}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
