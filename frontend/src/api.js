const API = {
  list: () => fetch("/api/list").then(r => r.json()),
  create: (ps) => fetch("/api/vmess", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ps})}).then(r => r.json()),
  deleteOne: (ps) => fetch(`/api/vmess/${encodeURIComponent(ps)}`, {method:"DELETE"}).then(r => r.json()),
  clear: () => fetch("/api/vmess", {method:"DELETE"}).then(r => r.json()),
  settings: () => fetch("/api/settings").then(r => r.json()),
  saveSettings: (s) => fetch("/api/settings", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(s)}).then(r => r.json()),
  health: () => fetch("/api/health").then(r => r.json())
};

export default API;