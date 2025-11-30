#!/usr/bin/env python3
import json, os, uuid, base64, subprocess, threading
from dotenv import load_dotenv
import http.server
import socketserver

load_dotenv()

# -------------------- CONFIG --------------------
CONFIG_DIR = "configs"
LIST_FILE = "list.txt"
RUNNING = "running.json"
VMESS_IP = os.getenv("VMESS_IP")
VMESS_PORT = int(os.getenv("VMESS_PORT"))
SUBSCRIPTION_URL = os.getenv("SUBSCRIPTION_URL", "/subscription")
SUBSCRIPTION_PORT = int(os.getenv("SUBSCRIPTION_PORT", "8080"))

os.makedirs(CONFIG_DIR, exist_ok=True)

# -------------------- SERVER --------------------
class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == SUBSCRIPTION_URL:
            if os.path.exists(LIST_FILE):
                with open(LIST_FILE, "r") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(data.encode())
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

def start_server():
    global httpd
    httpd = socketserver.TCPServer(("", SUBSCRIPTION_PORT), Handler)
    print(f"Subscription server at http://{VMESS_IP}:{SUBSCRIPTION_PORT}{SUBSCRIPTION_URL}")
    httpd.serve_forever()

def stop_server():
    global httpd
    if httpd:
        print("Stopping subscription server...")
        httpd.shutdown()
        httpd.server_close()

# -------------------- VMESS FUNCTIONS --------------------
def init_running():
    if not os.path.exists(RUNNING):
        base = {
            "inbounds": [{"port": 0, "protocol": "vmess", "settings": {"clients": []}, "streamSettings": {"network": "tcp"}}],
            "outbounds": [{"protocol": "freedom", "settings": {}}]
        }
        with open(RUNNING, "w") as f:
            json.dump(base, f, indent=2)

def restart_v2ray():
    print("Restarting V2Ray container...")
    subprocess.run(["docker", "restart", "d1ve"], check=False)

def create_vmess(ps=None):
    if not ps:
        ps = input("Enter VMess name (ps): ").strip()
        if not ps:
            print("VMess name cannot be empty.")
            return
    filename = f"{ps}.json"
    cfg_path = os.path.join(CONFIG_DIR, filename)
    if os.path.exists(cfg_path):
        print(f"Error: config '{ps}' exists")
        return

    vmess_uuid = str(uuid.uuid4())
    # config file
    vmess_cfg = {
        "inbounds": [{"port": VMESS_PORT, "protocol": "vmess", "settings": {"clients": [{"id": vmess_uuid,"alterId":0}]}, "streamSettings":{"network":"tcp"}}],
        "outbounds": [{"protocol":"freedom","settings":{}}]
    }
    with open(cfg_path, "w") as f:
        json.dump(vmess_cfg, f, indent=2)

    # client config base64
    client_cfg = {"v":"2","ps":ps,"add":VMESS_IP,"port":str(VMESS_PORT),"id":vmess_uuid,"aid":"0","net":"tcp","type":"none","host":"","path":"","tls":""}
    encoded = base64.b64encode(json.dumps(client_cfg).encode()).decode()
    with open(LIST_FILE, "a") as f:
        f.write("vmess://" + encoded + "\n")

    # update running.json
    init_running()
    with open(RUNNING,"r") as f:
        run_cfg = json.load(f)
    run_cfg["inbounds"][0]["port"] = VMESS_PORT
    run_cfg["inbounds"][0]["settings"]["clients"].append({"id":vmess_uuid,"alterId":0})
    with open(RUNNING,"w") as f:
        json.dump(run_cfg,f,indent=2)

    print(f"Created: {cfg_path}, UUID: {vmess_uuid}")
    restart_v2ray()

def delete_vmess(name=None):
    if not name:
        name = input("Enter VMess name to delete: ").strip()
        if not name:
            print("VMess name cannot be empty.")
            return
    cfg_path = os.path.join(CONFIG_DIR,f"{name}.json")
    user_id = None
    if os.path.exists(cfg_path):
        with open(cfg_path,"r") as f:
            data = json.load(f)
        user_id = data["inbounds"][0]["settings"]["clients"][0]["id"]
        os.remove(cfg_path)
        print("Deleted:", cfg_path)
    else:
        print("Not found:", cfg_path)

    if os.path.exists(LIST_FILE):
        with open(LIST_FILE,"r") as f:
            lines = f.readlines()
        with open(LIST_FILE,"w") as f:
            for line in lines:
                if name not in line:
                    f.write(line)

    if user_id:
        init_running()
        with open(RUNNING,"r") as f:
            run_cfg = json.load(f)
        run_cfg["inbounds"][0]["settings"]["clients"] = [c for c in run_cfg["inbounds"][0]["settings"]["clients"] if c["id"] != user_id]
        with open(RUNNING,"w") as f:
            json.dump(run_cfg,f,indent=2)
        print("Removed from running.json")
    restart_v2ray()
    
    
def clear():
    confirm = input("Are you sure you want to clear all configs? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        return

    # empty list.txt
    open(LIST_FILE,"w").close()

    # reset running.json
    base = {
        "inbounds": [{"port": 0, "protocol": "vmess", "settings": {"clients": []}, "streamSettings": {"network": "tcp"}}],
        "outbounds": [{"protocol": "freedom", "settings": {}}]
    }
    with open(RUNNING,"w") as f:
        json.dump(base,f,indent=2)

    # clear config files
    for f in os.listdir(CONFIG_DIR):
        open(os.path.join(CONFIG_DIR,f),"w").close()

    restart_v2ray()
    print("All configs cleared.")


def get_vmess(name=None):
    if not name:
        name = input("Enter VMess name to get: ").strip()
        if not name:
            print("VMess name cannot be empty.")
            return
    if not os.path.exists(LIST_FILE):
        print("No list.txt found")
        return
    with open(LIST_FILE,"r") as f:
        for line in f:
            if name in line:
                print(line.strip())
                return
    print("VMess not found")

def ls():
    if not os.path.exists(LIST_FILE):
        print("No list.txt found")
        return
    with open(LIST_FILE,"r") as f:
        print(f.read())

# -------------------- CLI LOOP --------------------
def cli_loop():
    print("VMess manager running. Commands: add, delete, clear, get, ls, exit")
    while True:
        try:
            cmd = input("> ").strip().split()
            if not cmd:
                continue
            action = cmd[0]
            if action == "add":
                create_vmess(cmd[1] if len(cmd)>1 else None)
            elif action == "delete":
                delete_vmess(cmd[1] if len(cmd)>1 else None)
            elif action == "clear":
                clear()
            elif action == "get":
                get_vmess(cmd[1] if len(cmd)>1 else None)
            elif action == "ls":
                ls()
            elif action == "exit":
                print("Exiting...")
                stop_server()
                break
            else:
                print("Unknown command")
        except KeyboardInterrupt:
            print("\nExiting...")
            stop_server()
            break

# -------------------- MAIN --------------------
if __name__ == "__main__":
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    cli_loop()
