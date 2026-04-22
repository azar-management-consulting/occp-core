FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# See landing-next/Dockerfile for rationale on `npm install` vs `npm ci`.
RUN npm install --no-audit --no-fund --prefer-offline

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_OCCP_API_URL=https://api.occp.ai
ENV NEXT_PUBLIC_OCCP_API_URL=$NEXT_PUBLIC_OCCP_API_URL
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -qO- http://0.0.0.0:3000/ || exit 1

CMD ["node", "server.js"]
