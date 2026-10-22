# syntax=docker/dockerfile:1
# Frontend image: Next.js standalone server on Node LTS (alpine), run as the non-root `node` user.
#
#   docker build -t eap-frontend .                                    # same origin (behind Nginx)
#   docker build -t eap-frontend --build-arg NEXT_PUBLIC_API_URL=https://api.example.com .
#   docker run --rm -p 3000:3000 eap-frontend
#
# NEXT_PUBLIC_API_URL is inlined into the browser bundle at BUILD time; empty = the API is on the
# same domain (Nginx routes /api to the backend), which the refresh cookie and SSE rely on.

ARG NODE_VERSION=22

FROM node:${NODE_VERSION}-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:${NODE_VERSION}-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

FROM node:${NODE_VERSION}-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD wget -qO- http://127.0.0.1:3000/login > /dev/null || exit 1
CMD ["node", "server.js"]
