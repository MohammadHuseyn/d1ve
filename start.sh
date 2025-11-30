#!/usr/bin/env bash
set -e

# ensure working dir
cd /app

# persistent directories
mkdir -p configs
touch list.txt

# create default running.json if missing (app.py also does this but keep safe)
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

# run the Flask app (it will spawn v2ray subprocess)
exec python3 app.py