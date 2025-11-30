FROM python:3.11-slim

WORKDIR /app

# install v2ray core
RUN apt update && apt install -y wget unzip && \
    wget https://github.com/v2fly/v2ray-core/releases/latest/download/v2ray-linux-64.zip && \
    unzip v2ray-linux-64.zip -d /v2ray && \
    chmod +x /v2ray/v2ray && \
    rm v2ray-linux-64.zip

COPY vmess_manager.py .
COPY entrypoint.sh .

RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
