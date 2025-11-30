#!/usr/bin/env bash
set -e

# Required env vars
: "${HOST_PORT:?HOST_PORT is required as env var}"
: "${IP:?IP is required as env var}"
: "${VMESS_PORT:?VMESS_PORT is required as env var}"

# ensure working dir
cd /app

# persistent directories
mkdir -p configs
touch list.txt

# create default running.json if missing
if [ ! -f running.json ]; then
  cat > running.json <<'JSON'
{
  "inbounds": [
    {
      "port": 0,
      "protocol": "vmess",
      "settings": { "clients": [] },
      "streamSettings": { "network": "tcp" }
    }
  ],
  "outbounds": [ { "protocol": "freedom", "settings": {} } ]
}
JSON
fi

# Determine mode: debug vs production
DEBUG=${DEBUG:-false}

if [ "$DEBUG" = "true" ]; then
  echo "[DEBUG] Running Flask directly"
  exec python3 app.py
else
  echo "[INFO] Running production with Gunicorn"
  exec gunicorn -w 4 -b 0.0.0.0:${PORT} app:app
fi
