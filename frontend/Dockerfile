# --- deps ---
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- build ---
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* is inlined at build time for the browser bundle.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Built-in inbox on the API (backend POSTs to itself).
ARG NEXT_PUBLIC_DEFAULT_TARGET_BASE=http://127.0.0.1:8000
ENV NEXT_PUBLIC_DEFAULT_TARGET_BASE=$NEXT_PUBLIC_DEFAULT_TARGET_BASE

RUN npm run build

# --- run ---
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/package-lock.json ./package-lock.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/next.config.js ./next.config.js
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["npm", "run", "start"]
