# Node.js Backend Dockerfile
# Uses a multi-stage build: deps first, then final image

FROM node:20-alpine AS base

# Set working directory
WORKDIR /app

# Install curl for healthcheck
RUN apk add --no-cache curl

# ---- Dependencies stage ----
FROM base AS deps

# Copy only package files first (leverages Docker layer caching)
COPY package.json package-lock.json ./

# Install all dependencies (including devDependencies for build)
RUN npm ci

# ---- Production stage ----
FROM base AS production

WORKDIR /app

# Copy installed production-only node_modules
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# Copy application source code
COPY src ./src

# Expose the application port
EXPOSE 5000

# Health check — hits the /health endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

# Start the server
CMD ["node", "src/index.js"]
