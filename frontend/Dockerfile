# ============================================================
# Frontend 镜像：Vue 3 + Vite 构建，Nginx 静态托管
# 容器内监听 80 端口，对应宿主机的 frontend 服务。
# ============================================================

# 第一阶段：安装依赖并构建 Vue 前端。
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# 第二阶段：使用轻量 Nginx 托管 dist 静态文件。
FROM nginx:1.27-alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

