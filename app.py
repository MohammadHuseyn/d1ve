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

# Debug env (keeps other logging behavior separate)
DEBUG = os.getenv("DEBUG", "False").lower() in ("1", "true", "yes")


def dbg(msg):
    if DEBUG:
        print("[DEBUG]", msg)


# Load settings (fallback to env if settings.json missing)
def load_settings():
    def _int_env(key, default):
        v = os.getenv(key)
        if v is None:
            return default
        try:
            return int(v)
        except Exception:
            return default

    s = {
        "IP": os.getenv("IP", "127.0.0.1"),
        "VMESS_PORT": _int_env("VMESS_PORT", 51820),
        "HOST_PORT": _int_env("HOST_PORT", 8090),
        "SUBSCRIPTION_URL": os.getenv("SUBSCRIPTION_URL", "/subscription")
    }
    try:
        if SETTINGS.exists():
            with open(SETTINGS, "r") as f:
                disk = json.load(f)
            # coerce ints if present in disk
            if "VMESS_PORT" in disk:
                try:
                    disk["VMESS_PORT"] = int(disk["VMESS_PORT"])
                except Exception:
                    pass
            if "HOST_PORT" in disk:
                try:
                    disk["HOST_PORT"] = int(disk["HOST_PORT"])
                except Exception:
                    pass
            s.update(disk)
    except Exception:
        pass
    return s


def save_settings(s):
    with open(SETTINGS, "w") as f:
        json.dump(s, f, indent=2)


settings = load_settings()

# ensure directories / files
CONFIG_DIR.mkdir(exist_ok=True)
LIST_FILE.touch(exist_ok=True)


def init_running():
    """
    Ensure running.json exists and contains a valid inbound binding to VMESS_PORT
    and at least one client. write default list.txt entry if needed.
    """
    needs_init = False
    if not RUNNING.exists() or os.stat(RUNNING).st_size == 0:
        needs_init = True
    else:
        try:
            with open(RUNNING, "r") as f:
                cur = json.load(f)
            # basic validation
            if not cur.get("inbounds"):
                needs_init = True
        except Exception:
            needs_init = True

    if needs_init:
        default_uuid = str(uuid.uuid4())
        run_cfg = {
            "inbounds": [
                {
                    # explicitly listen on all interfaces
                    "listen": "0.0.0.0",
                    "port": settings["VMESS_PORT"],
                    "protocol": "vmess",
                    "settings": {"clients": [{"id": default_uuid, "alterId": 0}]},
                    "streamSettings": {"network": "tcp"}
                }
            ],
            "outbounds": [{"protocol": "freedom", "settings": {}}]
        }
        with open(RUNNING, "w") as f:
            json.dump(run_cfg, f, indent=2)

        client_cfg = {
            "v": "2",
            "ps": "default",
            "add": settings["IP"],
            "port": str(settings["VMESS_PORT"]),
            "id": default_uuid,
            "aid": "0",
            "net": "tcp",
            "type": "none",
            "host": "",
            "path": "",
            "tls": ""
        }
        line = "vmess://" + base64.b64encode(json.dumps(client_cfg).encode()).decode()
        LIST_FILE.write_text(line + "\n")
        print("Initialized running.json and list.txt with a default client")


init_running()

# Flask app
app = Flask(__name__, static_folder=str(FRONTEND_DIST), static_url_path="/")

# v2ray subprocess management
v2ray_proc = None
v2ray_lock = threading.Lock()


def _drain_stream_and_print(stream, prefix="[v2ray]"):
    try:
        for line in iter(stream.readline, ""):
            if not line:
                break
            # stream is text mode when used in Popen(text=True)
            print(f"{prefix} {line.rstrip()}", flush=True)
    except Exception:
        pass


def start_v2ray():
    global v2ray_proc
    with v2ray_lock:
        if v2ray_proc and v2ray_proc.poll() is None:
            dbg("v2ray already running")
            return
        cmd = [str(V2RAY_BIN), "run", "-config", str(RUNNING)]
        try:
            v2ray_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            print("Failed to start v2ray:", e)
            return

        print(f"Started v2ray (pid={v2ray_proc.pid})", flush=True)
        # spawn a thread to forward logs so docker logs shows them
        t = threading.Thread(target=_drain_stream_and_print, args=(v2ray_proc.stdout,), daemon=True)
        t.start()


def stop_v2ray():
    global v2ray_proc
    with v2ray_lock:
        if v2ray_proc and v2ray_proc.poll() is None:
            try:
                v2ray_proc.terminate()
            except Exception as e:
                dbg(f"Error terminating v2ray: {e}")
            try:
                v2ray_proc.wait(timeout=3)
            except Exception:
                try:
                    v2ray_proc.kill()
                except Exception as e:
                    dbg(f"Error killing v2ray: {e}")
        v2ray_proc = None


def restart_v2ray():
    stop_v2ray()
    start_v2ray()


# Shutdown handler
def handle_exit(signum, frame):
    print("Shutting down, stopping v2ray...", flush=True)
    stop_v2ray()
    raise SystemExit()


signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)


# Utilities for list.txt <-> vmess lines
def read_list_lines():
    if not LIST_FILE.exists():
        return []
    with open(LIST_FILE, "r") as f:
        return [l.strip() for l in f.readlines() if l.strip()]


def parse_vmess_line(line):
    if line.startswith("vmess://"):
        b = line[len("vmess://") :]
        try:
            # pad if necessary
            padded = b + ("=" * ((4 - len(b) % 4) % 4))
            decoded = base64.b64decode(padded)
            obj = json.loads(decoded)
            obj["_raw"] = line
            return obj
        except Exception:
            return {"_raw": line}
    return {"_raw": line}


def list_clients():
    return [parse_vmess_line(l) for l in read_list_lines()]


def write_list_lines(lines):
    with open(LIST_FILE, "w") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


# API endpoints
@app.route("/api/list", methods=["GET"])
def api_list():
    return jsonify(list_clients())


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
        "inbounds": [
            {
                "listen": "0.0.0.0",
                "port": settings["VMESS_PORT"],
                "protocol": "vmess",
                "settings": {"clients": [{"id": vmess_uuid, "alterId": 0}]},
                "streamSettings": {"network": "tcp"},
            }
        ],
        "outbounds": [{"protocol": "freedom", "settings": {}}],
    }
    with open(cfg_path, "w") as f:
        json.dump(vmess_cfg, f, indent=2)

    client_cfg = {
        "v": "2",
        "ps": ps,
        "add": settings["IP"],
        "port": str(settings["VMESS_PORT"]),
        "id": vmess_uuid,
        "aid": "0",
        "net": "tcp",
        "type": "none",
        "host": "",
        "path": "",
        "tls": "",
    }
    line = "vmess://" + base64.b64encode(json.dumps(client_cfg).encode()).decode()

    lines = read_list_lines()
    lines.append(line)
    write_list_lines(lines)

    # update running.json -> append client and ensure listening port
    with open(RUNNING, "r") as f:
        run_cfg = json.load(f)
    # ensure inbound exists
    if not run_cfg.get("inbounds"):
        run_cfg["inbounds"] = [
            {
                "listen": "0.0.0.0",
                "port": settings["VMESS_PORT"],
                "protocol": "vmess",
                "settings": {"clients": []},
                "streamSettings": {"network": "tcp"},
            }
        ]
    run_cfg["inbounds"][0]["listen"] = "0.0.0.0"
    run_cfg["inbounds"][0]["port"] = settings["VMESS_PORT"]
    clients_arr = run_cfg["inbounds"][0].get("settings", {}).get("clients", [])
    clients_arr.append({"id": vmess_uuid, "alterId": 0})
    run_cfg["inbounds"][0]["settings"]["clients"] = clients_arr

    with open(RUNNING, "w") as f:
        json.dump(run_cfg, f, indent=2)

    restart_v2ray()
    return jsonify({"ps": ps, "id": vmess_uuid, "vmess": line})


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
        try:
            cfg_path.unlink()
        except Exception:
            pass

    lines = read_list_lines()
    new_lines = []
    for line in lines:
        obj = parse_vmess_line(line)
        if obj.get("ps") == name:
            continue
        new_lines.append(line)
    write_list_lines(new_lines)

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


@app.route("/api/vmess", methods=["DELETE"])
def api_clear():
    write_list_lines([])
    base = {
        "inbounds": [
            {
                "listen": "0.0.0.0",
                "port": settings["VMESS_PORT"],
                "protocol": "vmess",
                "settings": {"clients": []},
                "streamSettings": {"network": "tcp"},
            }
        ],
        "outbounds": [{"protocol": "freedom", "settings": {}}],
    }
    with open(RUNNING, "w") as f:
        json.dump(base, f, indent=2)
    for f in CONFIG_DIR.iterdir():
        try:
            f.unlink()
        except Exception:
            pass
    restart_v2ray()
    return jsonify({"cleared": True})


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "GET":
        return jsonify(settings)
    data = request.json or {}
    changed = False
    allowed = ["IP", "VMESS_PORT", "HOST_PORT", "SUBSCRIPTION_URL"]
    for k in allowed:
        if k in data:
            # cast ports
            if k in ("VMESS_PORT", "HOST_PORT"):
                try:
                    settings[k] = int(data[k])
                except Exception:
                    continue
            else:
                settings[k] = data[k]
            changed = True
    if changed:
        save_settings(settings)
        # if VMESS_PORT changed, update running.json and restart v2ray
        if "VMESS_PORT" in data:
            with open(RUNNING, "r") as f:
                run_cfg = json.load(f)
            if not run_cfg.get("inbounds"):
                run_cfg["inbounds"] = []
            # ensure inbound exists
            if not run_cfg["inbounds"]:
                run_cfg["inbounds"].append(
                    {
                        "listen": "0.0.0.0",
                        "port": settings["VMESS_PORT"],
                        "protocol": "vmess",
                        "settings": {"clients": []},
                        "streamSettings": {"network": "tcp"},
                    }
                )
            run_cfg["inbounds"][0]["listen"] = "0.0.0.0"
            run_cfg["inbounds"][0]["port"] = settings["VMESS_PORT"]
            with open(RUNNING, "w") as f:
                json.dump(run_cfg, f, indent=2)
            restart_v2ray()
    return jsonify(settings)


# Subscription endpoint
@app.before_request
def maybe_subscription():
    sub = settings.get("SUBSCRIPTION_URL", "/subscription")
    # compare exactly
    if request.path == sub:
        if LIST_FILE.exists():
            return make_response((LIST_FILE.read_text(), 200, {"Content-Type": "text/plain"}))
        return "", 404


# Serve frontend
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if path.startswith("api"):
        abort(404)
    if path != "" and (FRONTEND_DIST / path).exists():
        return send_from_directory(str(FRONTEND_DIST), path)
    return send_from_directory(str(FRONTEND_DIST), "index.html")


# Health
@app.route("/api/health")
def health():
    running = v2ray_proc is not None and v2ray_proc.poll() is None
    return jsonify({"ok": True, "v2ray_running": running})


if __name__ == "__main__":
    # ensure running.json matches current settings on startup
    try:
        with open(RUNNING, "r") as f:
            cfg = json.load(f)
        # patch port if different
        if cfg.get("inbounds") and isinstance(cfg["inbounds"], list) and cfg["inbounds"]:
            if cfg["inbounds"][0].get("port") != settings["VMESS_PORT"]:
                cfg["inbounds"][0]["listen"] = "0.0.0.0"
                cfg["inbounds"][0]["port"] = settings["VMESS_PORT"]
                with open(RUNNING, "w") as f:
                    json.dump(cfg, f, indent=2)
    except Exception:
        pass

    # start v2ray then serve app on HOST_PORT
    start_v2ray()
    host_port = int(settings.get("HOST_PORT", 8090))
    print(f"Starting Flask on 0.0.0.0:{host_port}", flush=True)
    app.run(host="0.0.0.0", port=host_port, threaded=True)
