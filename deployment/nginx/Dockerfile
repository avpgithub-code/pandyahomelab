FROM nginx:1.25-alpine

# Install openssl for certificate generation
RUN apk add --no-cache openssl

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom config
COPY nginx.conf /etc/nginx/nginx.conf

# Create directory for SSL certificates and static files
RUN mkdir -p /etc/nginx/certs /var/www/html

# Generate self-signed certificate (for development; production uses Let's Encrypt)
RUN openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/certs/server.key \
    -out /etc/nginx/certs/server.crt \
    -subj "/C=US/ST=CA/L=Home/O=PandyaLab/CN=pandyahomelab.com"

# Copy landing page (will be bind-mounted or copied)
# COPY website/index.html /var/www/html/index.html

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/health || exit 1

# Expose ports
EXPOSE 80 443

# Run nginx
CMD ["nginx", "-g", "daemon off;"]
