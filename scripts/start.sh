#!/bin/sh

SERVER_IP=$(sh /app/scripts/detect_ip.sh)
echo "Server IP detected: $SERVER_IP"

if [ -z "$PORT" ]; then
  echo "ERROR: PORT environment variable required"
  exit 1
fi

sed "s/SERVER_IP_REPLACE/$SERVER_IP/g; s/PORT_REPLACE/$PORT/g" \
  /app/config/v2ray.json > /app/config/generated.json

echo "Starting V2Ray..."
exec /usr/bin/v2ray run -c /app/config/generated.json
