#!/usr/bin/env python3
import os
import json
import uuid
import base64
import signal
import subprocess
import threading
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, abort, make_response

load_dotenv()

# Paths and storage
APP_DIR = Path(__file__).parent.resolve()
CONFIG_DIR = APP_DIR / "configs"
LIST_FILE = APP_DIR / "list.txt"
RUNNING = APP_DIR / "running.json"
SETTINGS = APP_DIR / "settings.json"
FRONTEND_DIST = APP_DIR / "frontend" / "dist"
V2RAY_BIN = Path("/v2ray/v2ray")  # installed in Dockerfile

# Load settings (fallback to env if settings.json missing)
def load_settings():
    s = {
        "VMESS_PORT": int(os.getenv("VMESS_PORT", "12345")),
        "VMESS_IP": os.getenv("VMESS_IP", "127.0.0.1"),
        "SUBSCRIPTION_URL": os.getenv("SUBSCRIPTION_URL", "/subscription"),
        "SUBSCRIPTION_PORT": int(os.getenv("SUBSCRIPTION_PORT", "8090"))
    }
    try:
        if SETTINGS.exists():
            with open(SETTINGS, "r") as f:
                disk = json.load(f)
            s.update(disk)
    except Exception:
        pass
    return s

def save_settings(s):
    with open(SETTINGS, "w") as f:
        json.dump(s, f, indent=2)

settings = load_settings()

# Ensure dirs/files
CONFIG_DIR.mkdir(exist_ok=True)
LIST_FILE.touch(exist_ok=True)
if not RUNNING.exists():
    base = {
        "inbounds": [{"port": 0, "protocol": "vmess", "settings": {"clients": []}, "streamSettings": {"network": "tcp"}}],
        "outbounds": [{"protocol": "freedom", "settings": {}}]
    }
    with open(RUNNING, "w") as f:
        json.dump(base, f, indent=2)

# Flask app
app = Flask(__name__, static_folder=str(FRONTEND_DIST), static_url_path="/")

# v2ray process handle (managed by this process)
v2ray_proc = None
v2ray_lock = threading.Lock()

def start_v2ray():
    global v2ray_proc
    with v2ray_lock:
        if v2ray_proc and v2ray_proc.poll() is None:
            return
        cmd = [str(V2RAY_BIN), "-c", str(RUNNING)]
        v2ray_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        app.logger.info(f"Started v2ray (pid={v2ray_proc.pid})")

def stop_v2ray():
    global v2ray_proc
    with v2ray_lock:
        if v2ray_proc and v2ray_proc.poll() is None:
            try:
                v2ray_proc.terminate()
            except Exception:
                pass
            try:
                v2ray_proc.wait(timeout=3)
            except Exception:
                try:
                    v2ray_proc.kill()
                except Exception:
                    pass
        v2ray_proc = None

def restart_v2ray():
    stop_v2ray()
    start_v2ray()

# On shutdown
def handle_exit(signum, frame):
    app.logger.info("Shutting down, stopping v2ray...")
    stop_v2ray()
    raise SystemExit()

signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

# Utility functions
def read_list_lines():
    if not LIST_FILE.exists():
        return []
    with open(LIST_FILE, "r") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    return lines

def parse_vmess_line(line):
    if line.startswith("vmess://"):
        b = line[len("vmess://"):]
        try:
            decoded = base64.b64decode(b + "===")  # pad
            obj = json.loads(decoded)
            obj["_raw"] = line
            return obj
        except Exception:
            return {"_raw": line}
    return {"_raw": line}

def list_clients():
    lines = read_list_lines()
    return [parse_vmess_line(l) for l in lines]

def write_list_lines(lines):
    with open(LIST_FILE, "w") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))

# API: list vmess
@app.route("/api/list", methods=["GET"])
def api_list():
    return jsonify(list_clients())

# API: create vmess
@app.route("/api/vmess", methods=["POST"])
def api_create():
    data = request.json or {}
    ps = (data.get("ps") or "").strip()
    if not ps:
        return jsonify({"error": "ps is required"}), 400
    filename = f"{ps}.json"
    cfg_path = CONFIG_DIR / filename
    if cfg_path.exists():
        return jsonify({"error": "exists"}), 409

    vmess_uuid = str(uuid.uuid4())
    vmess_cfg = {
        "inbounds": [{
            "port": int(settings["VMESS_PORT"]),
            "protocol": "vmess",
            "settings": {"clients": [{"id": vmess_uuid, "alterId": 0}]},
            "streamSettings": {"network": "tcp"}
        }],
        "outbounds": [{"protocol": "freedom", "settings": {}}]
    }
    with open(cfg_path, "w") as f:
        json.dump(vmess_cfg, f, indent=2)

    client_cfg = {
        "v": "2", "ps": ps, "add": settings["VMESS_IP"],
        "port": str(settings["VMESS_PORT"]), "id": vmess_uuid,
        "aid": "0", "net": "tcp", "type": "none", "host": "", "path": "", "tls": ""
    }
    encoded = base64.b64encode(json.dumps(client_cfg).encode()).decode()
    line = "vmess://" + encoded

    lines = read_list_lines()
    lines.append(line)
    write_list_lines(lines)

    # update running.json
    with open(RUNNING, "r") as f:
        run_cfg = json.load(f)
    run_cfg["inbounds"][0]["port"] = int(settings["VMESS_PORT"])
    run_cfg["inbounds"][0]["settings"]["clients"].append({"id": vmess_uuid, "alterId": 0})
    with open(RUNNING, "w") as f:
        json.dump(run_cfg, f, indent=2)

    # restart v2ray to pick up change
    restart_v2ray()

    return jsonify({"ps": ps, "id": vmess_uuid, "vmess": line})

# API: delete vmess by name
@app.route("/api/vmess/<name>", methods=["DELETE"])
def api_delete(name):
    cfg_path = CONFIG_DIR / f"{name}.json"
    user_id = None
    if cfg_path.exists():
        try:
            with open(cfg_path, "r") as f:
                data = json.load(f)
            user_id = data["inbounds"][0]["settings"]["clients"][0]["id"]
        except Exception:
            pass
        cfg_path.unlink()
    # remove from list.txt by ps matching (decode and match ps)
    lines = read_list_lines()
    new_lines = []
    for line in lines:
        obj = parse_vmess_line(line)
        if obj.get("ps") == name:
            continue
        new_lines.append(line)
    write_list_lines(new_lines)

    # remove from running.json if id found
    if user_id:
        with open(RUNNING, "r") as f:
            run_cfg = json.load(f)
        run_cfg["inbounds"][0]["settings"]["clients"] = [
            c for c in run_cfg["inbounds"][0]["settings"]["clients"] if c.get("id") != user_id
        ]
        with open(RUNNING, "w") as f:
            json.dump(run_cfg, f, indent=2)

    restart_v2ray()
    return jsonify({"deleted": name})

# API: clear all
@app.route("/api/vmess", methods=["DELETE"])
def api_clear():
    # empty list.txt
    write_list_lines([])
    # reset running.json
    base = {
        "inbounds": [{"port": 0, "protocol": "vmess", "settings": {"clients": []}, "streamSettings": {"network": "tcp"}}],
        "outbounds": [{"protocol": "freedom", "settings": {}}]
    }
    with open(RUNNING, "w") as f:
        json.dump(base, f, indent=2)
    # clear configs folder
    for f in CONFIG_DIR.iterdir():
        try:
            f.unlink()
        except Exception:
            pass
    restart_v2ray()
    return jsonify({"cleared": True})

# API: get settings
@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "GET":
        return jsonify(settings)
    data = request.json or {}
    # allow changing VMESS_IP, VMESS_PORT, SUBSCRIPTION_URL, SUBSCRIPTION_PORT
    allowed = ["VMESS_IP", "VMESS_PORT", "SUBSCRIPTION_URL", "SUBSCRIPTION_PORT"]
    changed = False
    for k in allowed:
        if k in data:
            settings[k] = data[k]
            changed = True
    if changed:
        save_settings(settings)
        # update running.json port if VMESS_PORT changed
        if "VMESS_PORT" in data:
            with open(RUNNING, "r") as f:
                run_cfg = json.load(f)
            run_cfg["inbounds"][0]["port"] = int(settings["VMESS_PORT"])
            with open(RUNNING, "w") as f:
                json.dump(run_cfg, f, indent=2)
            restart_v2ray()
    return jsonify(settings)

# Subscription endpoint: dynamic based on settings.SUBSCRIPTION_URL
@app.before_request
def maybe_subscription():
    sub = settings.get("SUBSCRIPTION_URL", "/subscription")
    if request.path == sub:
        # return list.txt content as plain text
        if LIST_FILE.exists():
            with open(LIST_FILE, "r") as f:
                data = f.read()
            return make_response((data, 200, {"Content-Type": "text/plain"}))
        else:
            return "", 404

# Serve frontend static assets and index.html
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    # if path matches api, abort to 404
    if path.startswith("api"):
        abort(404)
    if path != "" and (FRONTEND_DIST / path).exists():
        return send_from_directory(str(FRONTEND_DIST), path)
    return send_from_directory(str(FRONTEND_DIST), "index.html")

# health
@app.route("/api/health")
def health():
    running = v2ray_proc is not None and v2ray_proc.poll() is None
    return jsonify({"ok": True, "v2ray_running": running})

# Start v2ray and Flask
if __name__ == "__main__":
    start_v2ray()
    port = int(settings.get("SUBSCRIPTION_PORT", 8090))
    # Run Flask directly (single process so we can manage the v2ray subprocess)
    app.run(host="0.0.0.0", port=port, threaded=True)