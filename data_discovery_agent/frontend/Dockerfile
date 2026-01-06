# Build stage
FROM public.ecr.aws/docker/library/node:20-alpine AS build

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM public.ecr.aws/nginx/nginx:stable-alpine

# Install curl for health checks
RUN apk add --no-cache curl

# Copy built application
COPY --from=build /app/build /usr/share/nginx/html
# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf
# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000 || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]