FROM node:20-alpine AS dev
WORKDIR /app
COPY package.json ./
RUN npm install
ENV NEXT_TELEMETRY_DISABLED=1
EXPOSE 3000
CMD ["npm", "run", "dev"]

FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS prod
RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs
WORKDIR /app
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000
CMD ["node", "server.js"]
