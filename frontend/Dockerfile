# FridgeChef Frontend — Next.js 14 (NFR-OPS-001 containerized deploy)
FROM node:20-alpine AS base
WORKDIR /app

# Install deps (cache-friendly)
FROM base AS deps
COPY package.json ./
# package-lock.json 가 생기면 함께 복사 권장
RUN npm install --no-audit --no-fund

# Build stage
FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# Runtime stage
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.js ./next.config.js
EXPOSE 3000
CMD ["npm", "run", "start"]
