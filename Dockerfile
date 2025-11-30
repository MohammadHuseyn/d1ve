# ---- build frontend ----
FROM node:18-alpine AS node-build
WORKDIR /frontend
COPY frontend/package*.json ./
COPY frontend/vite.config.mjs frontend/index.html ./
COPY frontend/src ./src

RUN npm ci
RUN npm run build

# ---- final image ----
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# runtime deps
RUN apt-get update && apt-get install -y wget unzip ca-certificates && rm -rf /var/lib/apt/lists/*

# install python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# install v2ray binary
RUN wget -q https://github.com/v2fly/v2ray-core/releases/latest/download/v2ray-linux-64.zip -O /tmp/v2ray.zip \
 && unzip /tmp/v2ray.zip -d /v2ray \
 && chmod +x /v2ray/v2ray \
 && rm /tmp/v2ray.zip

# copy app
COPY app.py . 
COPY start.sh . 
COPY .env . 
COPY settings.json .

# copy built frontend
COPY --from=node-build /frontend/dist ./frontend/dist

# configs and data
RUN mkdir -p configs
VOLUME [ "/app/configs" ]

# expose port
ENV SUBSCRIPTION_PORT=8090
EXPOSE ${SUBSCRIPTION_PORT}

RUN chmod +x start.sh
CMD ["./start.sh"]
