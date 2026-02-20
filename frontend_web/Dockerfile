# Build stage
FROM node:20-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Production serve stage using Nginx
FROM nginx:alpine
# Copiamo l'output di Vite nella directory base di defaut di nginx
COPY --from=builder /app/dist /usr/share/nginx/html
# Aggiungiamo configurazione custom per Nginx SPA routing (utile per react-router in futuro)
RUN echo 'server { \
    listen 80; \
    location / { \
    root /usr/share/nginx/html; \
    index index.html index.htm; \
    try_files $uri $uri/ /index.html; \
    } \
    }' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
