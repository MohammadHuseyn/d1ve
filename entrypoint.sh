#!/bin/sh

# auto create running.json if missing
python3 vmess_manager.py delete-all >/dev/null 2>&1 || true

# restart loop
while true; do
    /v2ray/v2ray run -c /app/running.json
    echo "V2Ray crashed. Restarting..."
    sleep 1
done
